from __future__ import annotations

from typing import Any
import csv
import json

import m2_protocol


# 人工核验后的正式映射（依据 source_field_definitions.md / teaching_message_spec.md / 手册表17）
# 已修正预生成候选中的错误：经纬度颠倒、高度漏偏置、bit2语义、callsign有效性、候选不完整
AUTHORITATIVE_MAPPING=[
    # ---------- OpenSky 来源（M3 当前态势，物理量已是度/米） ----------
    {"source_format":"OpenSky","input_field":"target_id","unified_field":"track_id",
     "mapping_rule":"统一转为六位小写十六进制字符串，保留前导0","unit_conversion":"","null_strategy":"必需",
     "evidence":"source_field_definitions.md: track_id","verified":"yes"},
    {"source_format":"OpenSky","input_field":"latest_time","unified_field":"timestamp",
     "mapping_rule":"直接映射Unix秒，必须为正整数","unit_conversion":"","null_strategy":"必需",
     "evidence":"source_field_definitions.md: timestamp","verified":"yes"},
    {"source_format":"OpenSky","input_field":"time_source","unified_field":"quality.time_source",
     "mapping_rule":"position_time或last_contact_fallback直接映射","unit_conversion":"","null_strategy":"默认position_time",
     "evidence":"source_field_definitions.md: quality.time_source","verified":"yes"},
    {"source_format":"OpenSky","input_field":"callsign","unified_field":"identity.callsign",
     "mapping_rule":"直接映射","unit_conversion":"","null_strategy":"空则null",
     "evidence":"source_field_definitions.md: identity.callsign","verified":"yes"},
    {"source_format":"OpenSky","input_field":"lat","unified_field":"position.lat",
     "mapping_rule":"直接映射（度）","unit_conversion":"无","null_strategy":"空则null",
     "evidence":"source_field_definitions.md: position.lat","verified":"yes"},
    {"source_format":"OpenSky","input_field":"lon","unified_field":"position.lon",
     "mapping_rule":"直接映射（度）","unit_conversion":"无","null_strategy":"空则null",
     "evidence":"source_field_definitions.md: position.lon","verified":"yes"},
    {"source_format":"OpenSky","input_field":"altitude","unified_field":"position.alt",
     "mapping_rule":"直接映射（米）","unit_conversion":"无","null_strategy":"空则null",
     "evidence":"source_field_definitions.md: position.alt","verified":"yes"},
    {"source_format":"OpenSky","input_field":"alt_type","unified_field":"position.alt_type",
     "mapping_rule":"barometric/geometric/unknown直接映射","unit_conversion":"","null_strategy":"空则unknown",
     "evidence":"source_field_definitions.md: position.alt_type","verified":"yes"},
    {"source_format":"OpenSky","input_field":"speed","unified_field":"motion.speed",
     "mapping_rule":"直接映射（米/秒）","unit_conversion":"无","null_strategy":"空则null",
     "evidence":"source_field_definitions.md: motion.speed","verified":"yes"},
    {"source_format":"OpenSky","input_field":"heading","unified_field":"motion.heading",
     "mapping_rule":"直接映射（度）","unit_conversion":"无","null_strategy":"空则null",
     "evidence":"source_field_definitions.md: motion.heading","verified":"yes"},
    {"source_format":"OpenSky","input_field":"vertical_rate","unified_field":"motion.vertical_rate",
     "mapping_rule":"直接映射（米/秒）","unit_conversion":"无","null_strategy":"空则null",
     "evidence":"source_field_definitions.md: motion.vertical_rate","verified":"yes"},
    {"source_format":"OpenSky","input_field":"on_ground","unified_field":"status.on_ground",
     "mapping_rule":"转换为布尔值","unit_conversion":"","null_strategy":"必需",
     "evidence":"source_field_definitions.md: status.on_ground","verified":"yes"},
    {"source_format":"OpenSky","input_field":"lat/lon","unified_field":"quality.position_valid",
     "mapping_rule":"经纬度非空且处于合法范围","unit_conversion":"","null_strategy":"默认false",
     "evidence":"source_field_definitions.md: quality.position_valid","verified":"yes"},
    {"source_format":"OpenSky","input_field":"latest_time","unified_field":"quality.time_valid",
     "mapping_rule":"timestamp为正整数","unit_conversion":"","null_strategy":"默认false",
     "evidence":"source_field_definitions.md: quality.time_valid","verified":"yes"},
    {"source_format":"OpenSky","input_field":"message_valid","unified_field":"quality.message_valid",
     "mapping_rule":"源记录结构校验结果直接映射","unit_conversion":"","null_strategy":"默认false",
     "evidence":"source_field_definitions.md: quality.message_valid","verified":"yes"},
    # ---------- TeachingLink 来源（伙伴方态势：协议整数＋有效位恢复） ----------
    {"source_format":"TeachingLink","input_field":"target_id","unified_field":"track_id",
     "mapping_rule":"统一转为六位小写十六进制字符串，保留前导0","unit_conversion":"","null_strategy":"必需",
     "evidence":"source_field_definitions.md: track_id","verified":"yes"},
    {"source_format":"TeachingLink","input_field":"latest_time","unified_field":"timestamp",
     "mapping_rule":"直接映射Unix秒，必须为正整数","unit_conversion":"","null_strategy":"必需",
     "evidence":"source_field_definitions.md: timestamp","verified":"yes"},
    {"source_format":"TeachingLink","input_field":"status_flags.bit2","unified_field":"quality.time_source",
     "mapping_rule":"bit2=1时为last_contact_fallback，否则position_time（修正：候选错映射为time_valid）","unit_conversion":"","null_strategy":"默认position_time",
     "evidence":"teaching_message_spec.md: status_flags","verified":"yes"},
    {"source_format":"TeachingLink","input_field":"callsign+validity_flags.bit6","unified_field":"identity.callsign",
     "mapping_rule":"有效时去除补0直接映射（修正：候选漏有效性位）","unit_conversion":"","null_strategy":"无效时null",
     "evidence":"partner_field_dictionary.csv: callsign","verified":"yes"},
    {"source_format":"TeachingLink","input_field":"latitude_code+validity_flags.bit0","unified_field":"position.lat",
     "mapping_rule":"有效时code/(2²²−1)×180−90（修正：候选误写为position.lon）","unit_conversion":"22位定点，180°满量程","null_strategy":"无效时null",
     "evidence":"teaching_message_spec.md: 定点编码","verified":"yes"},
    {"source_format":"TeachingLink","input_field":"longitude_code+validity_flags.bit1","unified_field":"position.lon",
     "mapping_rule":"有效时code/(2²²−1)×360−180（修正：候选误写为position.lat）","unit_conversion":"22位定点，360°满量程","null_strategy":"无效时null",
     "evidence":"teaching_message_spec.md: 定点编码","verified":"yes"},
    {"source_format":"TeachingLink","input_field":"altitude_code+validity_flags.bit2","unified_field":"position.alt",
     "mapping_rule":"有效时code−1000（修正：候选漏物理偏置）","unit_conversion":"1米分辨率，偏置−1000米","null_strategy":"无效时null",
     "evidence":"teaching_message_spec.md: 定点编码","verified":"yes"},
    {"source_format":"TeachingLink","input_field":"status_flags.bit1","unified_field":"position.alt_type",
     "mapping_rule":"高度有效时1=geometric、0=barometric；无效时unknown","unit_conversion":"","null_strategy":"高度无效时unknown",
     "evidence":"teaching_message_spec.md: status_flags","verified":"yes"},
    {"source_format":"TeachingLink","input_field":"speed_code+validity_flags.bit3","unified_field":"motion.speed",
     "mapping_rule":"有效时code×0.1","unit_conversion":"0.1米/秒分辨率","null_strategy":"无效时null",
     "evidence":"teaching_message_spec.md: 定点编码","verified":"yes"},
    {"source_format":"TeachingLink","input_field":"heading_code+validity_flags.bit4","unified_field":"motion.heading",
     "mapping_rule":"有效时code×0.01且小于360°","unit_conversion":"0.01°分辨率","null_strategy":"无效时null",
     "evidence":"teaching_message_spec.md: 定点编码","verified":"yes"},
    {"source_format":"TeachingLink","input_field":"vertical_rate_code+validity_flags.bit5","unified_field":"motion.vertical_rate",
     "mapping_rule":"有效时code×0.01−327.68","unit_conversion":"0.01米/秒分辨率，偏置327.68","null_strategy":"无效时null",
     "evidence":"teaching_message_spec.md: 定点编码","verified":"yes"},
    {"source_format":"TeachingLink","input_field":"status_flags.bit0","unified_field":"status.on_ground",
     "mapping_rule":"转换为布尔值","unit_conversion":"","null_strategy":"必需",
     "evidence":"teaching_message_spec.md: status_flags","verified":"yes"},
    {"source_format":"TeachingLink","input_field":"纬经有效位+解码范围","unified_field":"quality.position_valid",
     "mapping_rule":"纬度与经度有效位均为1且解码值处于合法范围","unit_conversion":"","null_strategy":"默认false",
     "evidence":"source_field_definitions.md: quality.position_valid","verified":"yes"},
    {"source_format":"TeachingLink","input_field":"timestamp及帧接收结果","unified_field":"quality.time_valid",
     "mapping_rule":"timestamp为正整数且message_valid=true；时间回退不等于时间无效","unit_conversion":"","null_strategy":"默认false",
     "evidence":"source_field_definitions.md: quality.time_valid","verified":"yes"},
    {"source_format":"TeachingLink","input_field":"message_valid","unified_field":"quality.message_valid",
     "mapping_rule":"完整帧接收判据直接映射，不得扩大为来源可信","unit_conversion":"","null_strategy":"默认false",
     "evidence":"partner_field_dictionary.csv: message_valid","verified":"yes"},
]


def verify_candidate_mapping(candidate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """依据字段定义、单位、有效性和样例，形成人工核验后的正式映射。"""
    verified_rows=[]
    candidate_index={(r.get("source_format"),r.get("input_field")):r for r in candidate_rows}
    covered=set()
    for rule in AUTHORITATIVE_MAPPING:
        key=(rule["source_format"],rule["input_field"])
        if key in candidate_index:
            covered.add(key)
        verified_rows.append(dict(rule))
    for r in candidate_rows:
        key=(r.get("source_format"),r.get("input_field"))
        if key not in covered:
            verified_rows.append({"source_format":r.get("source_format"),
                                  "input_field":r.get("input_field"),
                                  "unified_field":r.get("candidate_unified_field",""),
                                  "mapping_rule":r.get("candidate_rule",""),
                                  "unit_conversion":"","null_strategy":"",
                                  "evidence":"候选与权威定义不符，未采纳","verified":"no"})
    return verified_rows


def _num(s: Any) -> int | float | None:
    s=("" if s is None else str(s)).strip()
    return float(s) if s else None


def _int(s: Any) -> int:
    s=("" if s is None else str(s)).strip()
    return int(s) if s else 0


def map_to_unified(record: dict[str, Any], source_format: str) -> dict[str, Any]:
    """使用人工核验后的规则生成统一态势消息。"""
    if source_format=="OpenSky":
        lat=_num(record.get("lat"))
        lon=_num(record.get("lon"))
        ts=_int(record.get("latest_time"))
        return {
            "track_id":str(record.get("target_id","")),
            "source":"OpenSky",
            "timestamp":ts,
            "identity":{"callsign":record.get("callsign") or None},
            "position":{"lat":lat,"lon":lon,"alt":_num(record.get("altitude")),
                        "alt_type":record.get("alt_type") or "unknown"},
            "motion":{"speed":_num(record.get("speed")),"heading":_num(record.get("heading")),
                      "vertical_rate":_num(record.get("vertical_rate"))},
            "status":{"on_ground":str(record.get("on_ground"))=="True"},
            "quality":{
                "position_valid":lat is not None and -90<=lat<=90 and lon is not None and -180<=lon<=180,
                "time_valid":isinstance(ts,int) and ts>0,
                "message_valid":str(record.get("message_valid"))=="True",
                "time_source":record.get("time_source") or "position_time",
                "anomaly_flags":[],
            },
        }
    if source_format=="TeachingLink":
        vf=_int(record.get("validity_flags"))
        sf=_int(record.get("status_flags"))
        lat_valid=bool(vf&0x01)
        lon_valid=bool(vf&0x02)
        alt_valid=bool(vf&0x04)
        speed_valid=bool(vf&0x08)
        heading_valid=bool(vf&0x10)
        vr_valid=bool(vf&0x20)
        cs_valid=bool(vf&0x40)
        lat=_int(record.get("latitude_code"))/(2**22-1)*180-90 if lat_valid else None
        lon=_int(record.get("longitude_code"))/(2**22-1)*360-180 if lon_valid else None
        alt=float(_int(record.get("altitude_code"))-1000) if alt_valid else None
        speed=_int(record.get("speed_code"))*0.1 if speed_valid else None
        heading=_int(record.get("heading_code"))*0.01 if heading_valid else None
        vr=_int(record.get("vertical_rate_code"))*0.01-327.68 if vr_valid else None
        ts=_int(record.get("latest_time"))
        return {
            "track_id":str(record.get("target_id","")),
            "source":"TeachingLink",
            "timestamp":ts,
            "identity":{"callsign":(record.get("callsign") or None) if cs_valid else None},
            "position":{"lat":lat,"lon":lon,"alt":alt,
                        "alt_type":(("geometric" if (sf&0x02) else "barometric") if alt_valid else "unknown")},
            "motion":{"speed":speed,"heading":heading,"vertical_rate":vr},
            "status":{"on_ground":bool(sf&0x01)},
            "quality":{
                "position_valid":lat_valid and lon_valid and lat is not None and -90<=lat<=90 and lon is not None and -180<=lon<=180,
                "time_valid":isinstance(ts,int) and ts>0 and str(record.get("message_valid"))=="True",
                "message_valid":str(record.get("message_valid"))=="True",
                "time_source":"last_contact_fallback" if (sf&0x04) else "position_time",
                "anomaly_flags":[],
            },
        }
    raise ValueError(f"未知source_format: {source_format}")


def read_csv_rows(path) -> list[dict[str, Any]]:
    with open(path,"r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def run(opensky_situation_path, partner_situation_path) -> int:
    m2_protocol.OUTPUT_ROOT.mkdir(parents=True,exist_ok=True)
    opensky_rows=read_csv_rows(opensky_situation_path)
    partner_rows=read_csv_rows(partner_situation_path)
    candidate_rows=read_csv_rows(m2_protocol.STUDENT_PACKAGE_ROOT/"reference"/"pre_generated_mapping_candidate.csv")
    verified_rows=verify_candidate_mapping(candidate_rows)
    unified_rows=[map_to_unified(r,"OpenSky") for r in opensky_rows]
    unified_rows+=[map_to_unified(r,"TeachingLink") for r in partner_rows]
    with open(m2_protocol.OUTPUT_ROOT/"unified_situation.ndjson","w",encoding="utf-8") as f:
        for row in unified_rows:
            f.write(json.dumps(row,ensure_ascii=False)+"\n")
    m2_protocol.write_csv(m2_protocol.OUTPUT_ROOT/"llm_mapping_candidate.csv",
                          ["source_format","input_field","candidate_unified_field","candidate_rule","confidence","review_note"],
                          candidate_rows)
    m2_protocol.write_csv(m2_protocol.OUTPUT_ROOT/"verified_mapping_table.csv",
                          ["source_format","input_field","unified_field","mapping_rule","unit_conversion","null_strategy","evidence","verified"],
                          verified_rows)
    def _fmt(x):
        return f"{x:.6f}" if x is not None else "None"
    by_track={r["track_id"]:r for r in unified_rows}
    for tid in sorted(by_track):
        others=[r for r in unified_rows if r["track_id"]==tid and r is not by_track[tid]]
        for other in others:
            a,b=by_track[tid],other
            print(f"对比 {tid}: {a['source']} lat={_fmt(a['position']['lat'])} lon={_fmt(a['position']['lon'])} | "
                  f"{b['source']} lat={_fmt(b['position']['lat'])} lon={_fmt(b['position']['lon'])}")
    '''print(f"统一消息: {len(unified_rows)} 条 (OpenSky {len(opensky_rows)} + TeachingLink {len(partner_rows)}) | "
          f"正式映射 {len(verified_rows)} 条 | 候选 {len(candidate_rows)} 条")'''
    return 0


def main() -> int:
    return run(m2_protocol.OUTPUT_ROOT/"current_situation.csv",
               m2_protocol.DATA_ROOT/"m4"/"partner_current_situation.csv")


if __name__=="__main__":
    raise SystemExit(main())
