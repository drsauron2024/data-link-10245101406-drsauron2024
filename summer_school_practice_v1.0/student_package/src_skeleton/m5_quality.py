from __future__ import annotations

from typing import Any
from collections import defaultdict
import csv

import m2_protocol


BATCH_TIME = 1710000120

ALERT_CSV_FIELDS=["alert_time","target_id","alert_type","severity","field","description"]
SITUATION_CSV_FIELDS=["target_id","timestamp","position_valid","delayed","duplicate_detected","heading_valid","message_valid","anomaly_level","display_status"]


def _num(s: Any) -> float | None:
    s=("" if s is None else str(s)).strip()
    return float(s) if s else None


def _record_time(record: dict[str, Any]):
    """record_time取latest_time或timestamp。"""
    return record.get("latest_time") if record.get("latest_time") is not None else record.get("timestamp")


def check_record(record: dict[str, Any], batch_time: int = BATCH_TIME) -> list[dict[str, Any]]:
    """检查位置缺失、时间延迟和航向越界，返回该记录触发的告警列表。"""
    alerts=[]
    tid=record.get("target_id","")
    rt=_record_time(record)
    lat=_num(record.get("lat"))
    lon=_num(record.get("lon"))
    if lat is None or lon is None:
        field="lat" if lat is None else "lon"
        alerts.append({"alert_time":batch_time,"target_id":tid,"alert_type":"POSITION_MISSING",
                       "severity":"HIGH","field":field,"description":f"{field}为空，位置缺失",
                       "record_time":rt})
    if rt is not None and batch_time-int(rt)>60:
        alerts.append({"alert_time":batch_time,"target_id":tid,"alert_type":"DATA_DELAYED",
                       "severity":"MEDIUM","field":"timestamp",
                       "description":f"batch_time-record_time={batch_time-int(rt)}秒>60",
                       "record_time":rt})
    heading=_num(record.get("heading"))
    if heading is not None and not 0<=heading<360:
        alerts.append({"alert_time":batch_time,"target_id":tid,"alert_type":"HEADING_OUT_OF_RANGE",
                       "severity":"MEDIUM","field":"heading",
                       "description":f"heading={heading} 不在[0,360)",
                       "record_time":rt})
    if str(record.get("message_valid"))=="False":
        alerts.append({"alert_time":batch_time,"target_id":tid,"alert_type":"FRAME_VALIDATION_ERROR",
                       "severity":"HIGH","field":"message_valid",
                       "description":"帧未通过接收检查；不代表来源真实性或安全完整性",
                       "record_time":rt})
    return alerts


def check_duplicates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """使用target_id+timestamp联合键检查重复。"""
    groups=defaultdict(list)
    for r in records:
        groups[(r.get("target_id"),_record_time(r))].append(r)
    alerts=[]
    for (tid,ts),rows in groups.items():
        if len(rows)>1:
            for _ in rows:
                alerts.append({"alert_time":BATCH_TIME,"target_id":tid,"alert_type":"DUPLICATE_RECORD",
                               "severity":"MEDIUM","field":"timestamp",
                               "description":f"target_id+timestamp联合键({tid},{ts})出现{len(rows)}次",
                               "record_time":ts})
    return alerts


def build_quality_situation(records: list[dict[str, Any]], alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按HIGH > MEDIUM > NONE合成质量态势，直接消费检查结果alerts。"""
    grouped=defaultdict(list)
    for a in alerts:
        grouped[(a.get("target_id"),a.get("record_time"))].append(a)
    rows=[]
    for r in records:
        tid=r.get("target_id","")
        rt=_record_time(r)
        rec_alerts=grouped.get((tid,rt),[])
        types={a["alert_type"] for a in rec_alerts}
        level="HIGH" if any(a["severity"]=="HIGH" for a in rec_alerts) else \
              ("MEDIUM" if types else "NONE")
        rows.append({
            "target_id":tid,
            "timestamp":rt,
            "position_valid":"POSITION_MISSING" not in types,
            "delayed":"DATA_DELAYED" in types,
            "duplicate_detected":"DUPLICATE_RECORD" in types,
            "heading_valid":"HEADING_OUT_OF_RANGE" not in types,
            "message_valid":str(r.get("message_valid"))=="True",
            "anomaly_level":level,
            "display_status":"NORMAL" if level=="NONE" else level,
        })
    return rows


def run(cases_path, rules_path) -> int:
    m2_protocol.OUTPUT_ROOT.mkdir(parents=True,exist_ok=True)
    with open(rules_path,"r",encoding="utf-8-sig",newline="") as f:
        rules=list(csv.DictReader(f))
    with open(cases_path,"r",encoding="utf-8-sig",newline="") as f:
        cases=list(csv.DictReader(f))
    alerts=[]
    for r in cases:
        alerts.extend(check_record(r))
    alerts.extend(check_duplicates(cases))
    situations=build_quality_situation(cases,alerts)
    m2_protocol.write_csv(m2_protocol.OUTPUT_ROOT/"alert_log.csv",ALERT_CSV_FIELDS,
                          [{k:a.get(k,"") for k in ALERT_CSV_FIELDS} for a in alerts])
    m2_protocol.write_csv(m2_protocol.OUTPUT_ROOT/"quality_situation.csv",SITUATION_CSV_FIELDS,situations)
    by_type=defaultdict(int)
    by_sev=defaultdict(int)
    for a in alerts:
        by_type[a["alert_type"]]+=1
        by_sev[a["severity"]]+=1
    print(f"规则 {len(rules)} 条 | 记录 {len(cases)} 条 | 告警 {len(alerts)} 条: "+
          " ".join(f"{k}={v}" for k,v in sorted(by_type.items()))+
          f" | HIGH={by_sev.get('HIGH',0)} MEDIUM={by_sev.get('MEDIUM',0)}")
    return 0


def main() -> int:
    return run(m2_protocol.DATA_ROOT/"m5"/"anomaly_cases.csv",
               m2_protocol.DATA_ROOT/"m5"/"anomaly_rules.csv")


if __name__=="__main__":
    raise SystemExit(main())
