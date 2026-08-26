from __future__ import annotations

from typing import Any

import json      
import struct
import math
import csv  
from pathlib import Path

STUDENT_PACKAGE_ROOT=Path(__file__).resolve().parents[1]
DATA_ROOT=STUDENT_PACKAGE_ROOT/"data"
OUTPUT_ROOT=STUDENT_PACKAGE_ROOT/"output"

FRAME_SIZE = 41

class ValidationError(Exception):
    def __init__(self, message: str, *, field: str = "", problem_type: str = "FIELD_ERROR", value: Any = None):
        super().__init__(message)
        self.field = field
        self.problem_type = problem_type
        self.value = value

def parse_state_vector(vector: list[Any]) -> dict[str, Any]:
    """将OpenSky状态向量转换为发送方内部结构化记录。"""
    icao24=vector[0]
    if not (len(icao24)==6):
        raise ValidationError("target_id长度不为6",field="target_id",problem_type="LENGTH_ERROR",value=icao24)
    elif not all(c in "0123456789abcdefABCDEF" for c in icao24):
        raise ValidationError("target_id不是6位十六进制",field="target_id",problem_type="TYPE_ERROR",value=icao24)
    callsign=vector[1]
    if callsign is not None:
        callsign=vector[1].strip()
        if not (1<=len(callsign)<=8):
            raise ValidationError("callsign去除空格后长度应为1-8",field="callsign",problem_type="LENGTH_ERROR",value=callsign)
        elif not (callsign.isascii()):
            raise ValidationError("callsign去除空格后应为1-8位ASCII",field="callsign",problem_type="TYPE_ERROR",value=callsign)
    origin_country=vector[2]
    time_position=vector[3]
    last_contact=vector[4]
    if time_position is not None:
        timestamp,timestamp_source=time_position,"position_time"
    elif last_contact is not None:
        timestamp,timestamp_source=last_contact,"last_contact_fallback"
    else:
        raise ValidationError("time_position与last_contact均为空，无法生成正常帧",field="timestamp",problem_type="REQUIRED_FIELD_MISSING")
    longitude=vector[5]
    latitude=vector[6]
    baro_altitude=vector[7]
    on_ground=vector[8]
    if on_ground is None:
        raise ValidationError("on_ground为空",field="on_ground",problem_type="REQUIRED_FIELD_MISSING")
    elif not isinstance(on_ground,bool):
        raise ValidationError("on_ground不为布尔值",field="on_ground",problem_type="TYPE_ERROR")
    velocity=vector[9]
    true_track=vector[10]
    vertical_rate=vector[11]
    geo_altitude=vector[13]
    if baro_altitude is not None:
        altitude,alt_type=baro_altitude,"barometric"
    elif geo_altitude is not None:
        altitude,alt_type=geo_altitude,"geometric"
    else:
        altitude,alt_type=None,"unknown"
    position_source=vector[16]
    if latitude is not None and not -90<=latitude<=90:
        raise ValidationError("lat超出量程", field="lat",problem_type="OUT_OF_RANGE",value=latitude)
    if longitude is not None and not -180<=longitude<=180:
        raise ValidationError("lon超出量程", field="lon",problem_type="OUT_OF_RANGE",value=longitude)
    if true_track is not None and not 0<=true_track<360:
        raise ValidationError("heading超出量程",field="heading",problem_type="OUT_OF_RANGE",value=true_track)
    if velocity is not None and not 0<=velocity<6553.5:
        raise ValidationError("speed 超出量程",field="speed",problem_type="OUT_OF_RANGE",value=velocity)
    if vertical_rate is not None and not -327.68<=vertical_rate<=327.68:
        raise ValidationError("vertical_rate超出量程",field="vertical_rate",problem_type="OUT_OF_RANGE",value=vertical_rate)
    return{
        "target_id":icao24,
        "callsign":callsign,
        "timestamp":timestamp,
        "timestamp_source":timestamp_source,
        "lat":latitude,
        "lon":longitude,
        "altitude":altitude,
        "alt_type":alt_type,
        "speed":velocity, 
        "heading":true_track, 
        "vertical_rate":vertical_rate,
        "on_ground":on_ground,
    }


def calculate_checksum(data_without_checksum: bytes) -> int:
    """计算前39字节无符号字节值之和模65536。"""
    return sum(data_without_checksum)%65536


def encode_position_message(record: dict[str, Any], message_seq: int) -> bytes:
    """按41字节TeachingLink格式封装一条位置状态消息。"""
    status_flag=0
    if record["on_ground"]:
        status_flag|=record["on_ground"]
    if record["alt_type"]=="geometric":
        status_flag|=1<<1
    if record["timestamp_source"]=="last_contact_fallback":
        status_flag|=1<<2
    validity_flags=0
    lat=lon=altitude=speed=heading=vertical_rate=0
    callsign=b"\x00"*8
    if record["lat"] is not None:
        lat=math.floor((record["lat"]+90)/180*(2**22-1)+0.5)
        if 0<=lat<=2**22-1:
            validity_flags|=1<<0
        else:
            raise ValidationError("latitude超出量程",field="latitude_code",problem_type="OUT_OF_RANGE",value=record["lat"]) 
    if record["lon"] is not None:
        lon=math.floor((record["lon"]+180)/360*(2**22-1)+0.5)
        if 0<=lon<=2**22-1:
            validity_flags|=1<<1
        else:
            raise ValidationError("longitude超出量程",field="longitude_code",problem_type="OUT_OF_RANGE",value=record["lon"]) 
    if record["altitude"] is not None:
        altitude=math.floor(record["altitude"]+1000+0.5)
        if 0<=altitude<=2**16-1:
            validity_flags|=1<<2
        else:
            raise ValidationError("altitude超出量程",field="altitude_code",problem_type="OUT_OF_RANGE",value=record["altitude"]) 
    if record["speed"] is not None:
        speed=math.floor(record["speed"]/0.1+0.5)
        if 0<=speed<=2**16-1:
            validity_flags|=1<<3
        else:
            raise ValidationError("speed超出量程",field="speed_code",problem_type="OUT_OF_RANGE",value=record["speed"])
    if record["heading"] is not None:
        heading=math.floor(record["heading"]/0.01+0.5)
        if 0<=heading<=2**16-1:
            validity_flags|=1<<4
        else:
            raise ValidationError("heading超出量程",field="heading_code",problem_type="OUT_OF_RANGE",value=record["heading"])
    if record["vertical_rate"] is not None:
        vertical_rate=math.floor((record["vertical_rate"]+327.68)/0.01+0.5)
        if 0<=vertical_rate<=2**16-1:
            validity_flags|=1<<5
        else:
            raise ValidationError("vertical_rate超出量程",field="vertical_rate_coded",problem_type="OUT_OF_RANGE",value=record["vertical_rate"])
    if record["callsign"] is not None:
        callsign=record["callsign"].encode("ascii")
        if 1<=len(callsign)<=8:
            validity_flags|=1<<6
            callsign=callsign.ljust(8, b"\x00")
        else:
            raise ValidationError("callsign超过8位",field="callsign_code",problem_type="LENGTH_ERROR",value=record["callsign"])
    target_id=int(record["target_id"],16)
    frame=struct.pack(">HBBHHI",0x4453,1,1,FRAME_SIZE,message_seq%65536,record["timestamp"])
    frame+=bytes([(target_id>>16)&0xFF,(target_id>>8)&0xFF,target_id&0xFF])
    frame+=callsign
    frame+=bytes([(lat>>16)&0xFF,(lat>>8)&0xFF,lat&0xFF])
    frame+=bytes([(lon>>16)&0xFF,(lon>>8)&0xFF,lon&0xFF])
    frame+=struct.pack(">HHHHBB",altitude,speed,heading,vertical_rate,status_flag,validity_flags)
    frame+=struct.pack(">H",calculate_checksum(frame))
    return frame


def decode_position_message(data: bytes) -> dict[str, Any]:
    """检查帧接收条件并恢复接收方结构化记录。"""
    if len(data)!=FRAME_SIZE:
        raise ValidationError(f"长度错误: 收到{len(data)}字节，要求{FRAME_SIZE}",field="frame_length",problem_type="LENGTH_ERROR",value=len(data))
    magic,version,message_type,message_length,message_seq,timestamp,target_id,callsign,latitude_code,longitude_code,\
    altitude_code, speed_code,heading_code,vertical_rate_code,status_flags,validity_flags,checksum=\
    struct.unpack(">HBBHHI3s8s3s3sHHHHBBH",data)
    target_id=int.from_bytes(target_id,"big")
    latitude_code=int.from_bytes(latitude_code,"big")
    longitude_code=int.from_bytes(longitude_code,"big")
    if not message_length==41:
        raise ValidationError("帧长度错误",field="message_length",problem_type="LENGTH_ERROR",value=message_length)
    if not magic==0x4453:
        raise ValidationError("magic值错误",field="magic",problem_type="MAGIC_ERROR",value=magic)
    if not version==1:
        raise ValidationError("version错误",field="version",problem_type="VERSION_ERROR",value=version)
    if not message_type==1:
        raise ValidationError("message_type错误",field="message_type",problem_type="MESSAGE_TYPE_ERROR",value=message_type)
    expected=calculate_checksum(data[:-2])
    if not checksum==expected:
        raise ValidationError("checksum错误",field="checksum",problem_type="CHECKSUM_ERROR",value=checksum)
    if latitude_code & 0xC00000:
        raise ValidationError("latitude_code保留位非0",field="latitude_code",problem_type="RESERVED_BITS_ERROR",value=latitude_code)
    if longitude_code & 0xC00000:
        raise ValidationError("longitude_code保留位非0",field="longitude_code",problem_type="RESERVED_BITS_ERROR",value=longitude_code)
    if status_flags & 0xF8:
        raise ValidationError("status_flags保留位非0",field="status_flags",problem_type="RESERVED_BITS_ERROR",value=status_flags)
    if validity_flags & 0x80:
        raise ValidationError("validity_flags保留位非0",field="validity_flags",problem_type="RESERVED_BITS_ERROR",value=validity_flags)
    consistency=[("lat",validity_flags&0x01,latitude_code),("lon",validity_flags&0x02,longitude_code),
                 ("altitude",validity_flags&0x04,altitude_code),("speed",validity_flags&0x08,speed_code),
                 ("heading",validity_flags&0x10,heading_code),("vertical_rate",validity_flags&0x20,vertical_rate_code),
                 ("callsign",validity_flags&0x40,int.from_bytes(callsign,"big"))]
    for name,bit,code in consistency:
        if not bit and code!=0:
            raise ValidationError("有效位为0但占位非0",field=name,problem_type="FLAG_VALUE_INCONSISTENCY",value=code)
    lat_valid=bool(validity_flags&0x01)
    lon_valid=bool(validity_flags&0x02)
    altitude_valid=bool(validity_flags&0x04)
    speed_valid=bool(validity_flags&0x08)
    heading_valid=bool(validity_flags&0x10)
    vertical_rate_valid=bool(validity_flags&0x20)
    callsign_valid=bool(validity_flags&0x40)
    lat=latitude_code/(2**22-1)*180-90 if lat_valid else None
    lon=longitude_code/(2**22-1)*360-180 if lon_valid else None
    altitude=float(altitude_code-1000) if altitude_valid else None
    speed=speed_code*0.1 if speed_valid else None
    heading=heading_code*0.01 if heading_valid else None
    vertical_rate=vertical_rate_code*0.01-327.68 if vertical_rate_valid else None
    callsign_str=callsign.rstrip(b"\x00").decode("ascii","replace") if callsign_valid else None
    alt_type=("geometric" if (status_flags&0x02) else "barometric") if altitude_valid else "unknown"
    on_ground=bool(status_flags&0x01)
    time_source="last_contact_fallback" if (status_flags&0x04) else "position_time"
    return {
        "target_id":f"{target_id:06x}",
        "callsign":callsign_str,
        "timestamp":timestamp,
        "timestamp_source":time_source,
        "time_source":time_source,
        "message_seq":message_seq,
        "lat":lat,
        "lon":lon,
        "altitude":altitude,
        "alt_type":alt_type,
        "speed":speed,
        "heading":heading,
        "vertical_rate":vertical_rate,
        "on_ground":on_ground,
        "status_flags":status_flags,
        "validity_flags":validity_flags,
        "latitude_code":latitude_code,
        "longitude_code":longitude_code,
        "altitude_code":altitude_code,
        "speed_code":speed_code,
        "heading_code":heading_code,
        "vertical_rate_code":vertical_rate_code,
        "lat_valid":lat_valid,
        "lon_valid":lon_valid,
        "altitude_valid":altitude_valid,
        "speed_valid":speed_valid,
        "heading_valid":heading_valid,
        "vertical_rate_valid":vertical_rate_valid,
        "callsign_valid":callsign_valid,
        "checksum":checksum,
        "expected_checksum":expected,
        "message_valid":True,
        "validation_errors":"",
        "source":"teaching_link",
    }


DECODED_CSV_FIELDS=["target_id","callsign","timestamp","timestamp_source","time_source","message_seq",
    "lat","lon","altitude","alt_type","speed","heading","vertical_rate","on_ground",
    "status_flags","validity_flags","latitude_code","longitude_code","altitude_code",
    "speed_code","heading_code","vertical_rate_code","lat_valid","lon_valid",
    "altitude_valid","speed_valid","heading_valid","vertical_rate_valid","callsign_valid",
    "checksum","expected_checksum","message_valid","validation_errors","source"]
LOG_CSV_FIELDS=["record_no","target_id","stage","field","problem_type","value","description"]
RT_CSV_FIELDS=["field","source_value","source_valid","protocol_code","flag_bit",
    "decoded_value","decoded_valid","absolute_error/tolerance","passed"]


def write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer=csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def log_row(record_no, target_id, stage, e):
    return {"record_no":record_no,"target_id":target_id,"stage":stage,"field":e.field,
            "problem_type":e.problem_type,"value":"" if e.value is None else e.value,
            "description":str(e)}


def _read_vectors(path) -> list:
    if path.is_dir():
        vectors=[]
        for p in sorted(path.glob("*.json")):
            vectors.extend(json.loads(p.read_text(encoding="utf-8"))["states"])
        return vectors
    return json.loads(path.read_text(encoding="utf-8"))["states"]


def run_pipeline(vectors_path) -> int:
    raw={"states":_read_vectors(vectors_path)}
    OUTPUT_ROOT.mkdir(parents=True,exist_ok=True)
    frames=[]
    source_records=[]
    decoded_rows=[]
    log_rows=[]
    for i,vector in enumerate(raw["states"]):
        record_no=i+1
        try:
            rec=parse_state_vector(vector)
        except ValidationError as e:
            log_rows.append(log_row(record_no, vector[0] if isinstance(vector[0],str) else "", "parse", e))
            continue
        try:
            frame=encode_position_message(rec,len(frames)+1)   # 序号从1起，与课程参考实现一致
        except ValidationError as e:
            log_rows.append(log_row(record_no, rec["target_id"], "encode", e))
            continue
        try:
            dec=decode_position_message(frame)
        except ValidationError as e:
            log_rows.append(log_row(record_no, rec["target_id"], "decode", e))
            continue
        frames.append(frame)
        source_records.append(rec)
        decoded_rows.append(dec)

    (OUTPUT_ROOT/"encoded_messages.bin").write_bytes(b"".join(frames))
    rt_rows=[]
    numeric_fields=[("lat",180/(2**22-1)),("lon",360/(2**22-1)),
                    ("altitude",1.0),("speed",0.1),("heading",0.01),("vertical_rate",0.01)]
    flag_bits={"lat":0,"lon":1,"altitude":2,"speed":3,"heading":4,"vertical_rate":5,"callsign":6}
    code_fields={"lat":"latitude_code","lon":"longitude_code","altitude":"altitude_code",
                 "speed":"speed_code","heading":"heading_code","vertical_rate":"vertical_rate_code"}
    for src,dec in zip(source_records,decoded_rows):
        for field,tol in numeric_fields:
            sv,dv=src[field],dec[field]
            if sv is not None and dv is not None:
                err=abs(dv-sv)
                rt_rows.append({"field":field,"source_value":sv,"source_valid":True,
                                "protocol_code":dec[code_fields[field]],"flag_bit":flag_bits[field],
                                "decoded_value":dv,"decoded_valid":True,
                                "absolute_error/tolerance":f"{err/tol:.4f}","passed":err<=tol})
            elif sv is not None or dv is not None:
                rt_rows.append({"field":field,"source_value":"" if sv is None else sv,
                                "source_valid":sv is not None,"protocol_code":"","flag_bit":"",
                                "decoded_value":"" if dv is None else dv,"decoded_valid":dv is not None,
                                "absolute_error/tolerance":"","passed":False})
            else:
                rt_rows.append({"field":field,"source_value":"","source_valid":False,
                                "protocol_code":"","flag_bit":"","decoded_value":"",
                                "decoded_valid":False,"absolute_error/tolerance":"","passed":True})
        for field in ("callsign","timestamp"):
            sv,dv=src[field],dec[field]
            rt_rows.append({"field":field,"source_value":"" if sv is None else sv,
                            "source_valid":sv is not None,"protocol_code":"",
                            "flag_bit":"" if field=="timestamp" else 6,
                            "decoded_value":"" if dv is None else dv,"decoded_valid":dv is not None,
                            "absolute_error/tolerance":"","passed":sv==dv})

    write_csv(OUTPUT_ROOT/"decoded_partner_states.csv",DECODED_CSV_FIELDS,decoded_rows)
    write_csv(OUTPUT_ROOT/"roundtrip_report.csv",RT_CSV_FIELDS,rt_rows)
    write_csv(OUTPUT_ROOT/"validation_log.csv",LOG_CSV_FIELDS,log_rows)
    return 0


def main() -> int:
    return run_pipeline(DATA_ROOT/"raw_states.json")


if __name__=="__main__":
    raise SystemExit(main())
        
