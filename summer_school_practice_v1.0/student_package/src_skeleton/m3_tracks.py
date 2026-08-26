from __future__ import annotations

from typing import Any
from collections import defaultdict
import csv
import sqlite3

import m2_protocol


TRACK_CSV_FIELDS=["target_id","timestamp","message_seq","track_sequence_no","lat","lon","altitude","speed","heading"]
SITUATION_CSV_FIELDS=["target_id","callsign","latest_time","lat","lon","altitude","speed","heading","vertical_rate","on_ground","track_length","alt_type","time_source","message_valid"]


def decode_message_stream(data: bytes, frame_size: int = 41, errors: list | None = None) -> list[dict[str, Any]]:
    """按固定帧长批量解码；记录并忽略不完整尾帧。"""
    records=[]
    tail=len(data)%frame_size
    if tail!=0 and errors is not None:
        errors.append({"record_no":"","target_id":"","stage":"stream","field":"frame_stream",
                       "problem_type":"LENGTH_ERROR","value":tail,
                       "description":f"总长度{len(data)}不是{frame_size}的整数倍，尾部{tail}字节不完整尾帧已忽略"})
    for idx,i in enumerate(range(0,len(data)-tail,frame_size)):
        try:
            records.append(m2_protocol.decode_position_message(data[i:i+frame_size]))
        except m2_protocol.ValidationError as e:
            if errors is not None:
                errors.append(m2_protocol.log_row(idx,"","decode",e))
            continue
    return records


DB_SCHEMA="""CREATE TABLE IF NOT EXISTS state_record (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id TEXT,
    callsign TEXT NULL,
    timestamp INTEGER,
    timestamp_source TEXT,
    message_seq INTEGER,
    lat REAL NULL,
    lon REAL NULL,
    altitude REAL NULL,
    alt_type TEXT NULL,
    speed REAL NULL,
    heading REAL NULL,
    vertical_rate REAL NULL,
    on_ground INTEGER,
    status_flags INTEGER,
    validity_flags INTEGER,
    message_valid INTEGER,
    source TEXT
);"""
DB_COLUMNS=["target_id","callsign","timestamp","timestamp_source","message_seq",
    "lat","lon","altitude","alt_type","speed","heading","vertical_rate",
    "on_ground","status_flags","validity_flags","message_valid","source"]


def save_records_to_sqlite(records: list[dict[str, Any]], db_path: str) -> None:
    """选做：保存接收记录，None必须写为NULL。"""
    con=sqlite3.connect(db_path)
    try:
        con.execute(DB_SCHEMA)
        con.execute("DELETE FROM state_record")  
        acceptable=[r for r in records if r.get("message_valid") is True and r.get("target_id") and r.get("timestamp") is not None]
        rows=[tuple(r.get(c) for c in DB_COLUMNS) for r in acceptable]
        con.executemany(f"INSERT INTO state_record ({','.join(DB_COLUMNS)}) VALUES ({','.join('?'*len(DB_COLUMNS))})",rows)
        con.commit()
    finally:
        con.close()


def build_tracks(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """仅使用可接受记录，按target_id分组并按timestamp排序。"""
    groups=defaultdict(list)
    for r in records:
        if r.get("message_valid") is True and r.get("target_id") and r.get("timestamp") is not None:
            groups[r["target_id"]].append(r)
    tracks=[]
    for tid in sorted(groups):
        for seq_no,r in enumerate(sorted(groups[tid],key=lambda x:x["timestamp"]),start=1):
            tracks.append({
                "target_id":r["target_id"],
                "timestamp":r["timestamp"],
                "message_seq":r["message_seq"],
                "track_sequence_no":seq_no,
                "lat":r["lat"],"lon":r["lon"],
                "altitude":r["altitude"],"speed":r["speed"],"heading":r["heading"],
            })
    return tracks


def build_current_situation(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """每个目标保留时间最新的可接受记录；可选字段缺失仍可入选。"""
    groups=defaultdict(list)
    for r in records:
        if r.get("message_valid") is True and r.get("target_id") and r.get("timestamp") is not None:
            groups[r["target_id"]].append(r)
    situations=[]
    for tid in sorted(groups):
        g=sorted(groups[tid],key=lambda x:x["timestamp"])
        r=g[-1]
        situations.append({
            "target_id":r["target_id"],
            "callsign":r["callsign"],
            "latest_time":r["timestamp"],
            "lat":r["lat"],"lon":r["lon"],
            "altitude":r["altitude"],"speed":r["speed"],"heading":r["heading"],
            "vertical_rate":r["vertical_rate"],
            "on_ground":r["on_ground"],
            "track_length":len(g),
            "alt_type":r["alt_type"],
            "time_source":r["time_source"],
            "message_valid":r["message_valid"],
        })
    return situations


def query_sqlite(db_path: str) -> list[dict[str, Any]]:
    """选做：重新读取数据库并执行一项简单查询（每目标记录数与最新时间）。"""
    con=sqlite3.connect(db_path)
    try:
        con.row_factory=sqlite3.Row
        rows=con.execute("SELECT target_id, COUNT(*) AS record_count, MAX(timestamp) AS latest_time "
                         "FROM state_record GROUP BY target_id ORDER BY target_id").fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def plot_tracks(records: list[dict[str, Any]], out_path, annotate: bool = True) -> None:
    """选做：按目标绘制航迹图，按时间顺序连线，可选点旁标注时刻。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    groups=defaultdict(list)
    for r in records:
        if r.get("message_valid") is True and r.get("target_id") and r.get("timestamp") is not None:
            groups[r["target_id"]].append(r)
    fig,ax=plt.subplots(figsize=(16,10))
    for tid in sorted(groups):
        g=sorted(groups[tid],key=lambda x:x["timestamp"])
        xs=[r["lon"] for r in g if r["lon"] is not None]
        ys=[r["lat"] for r in g if r["lat"] is not None]
        ax.plot(xs,ys,marker="o",markersize=6,label=f"target {tid}")
        if annotate:
            for r in g:
                if r["lon"] is not None and r["lat"] is not None:
                    ax.annotate(str(r["timestamp"]%100000),(r["lon"],r["lat"]),fontsize=8)
    ax.set_xlabel("Longitude (deg)")
    ax.set_ylabel("Latitude (deg)")
    ax.set_title("M3 Tracks (optional)")
    ax.legend()
    fig.savefig(out_path,dpi=150,bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    # 切换真实数据：把这行改成 DATA_ROOT/"opensky_real"/"opensky_real_messages.bin"
    data_path=m2_protocol.DATA_ROOT/"partner_messages_multitime.bin"
    m2_protocol.OUTPUT_ROOT.mkdir(parents=True,exist_ok=True)
    log_path=m2_protocol.OUTPUT_ROOT/"validation_log.csv"
    log_rows=[]
    if log_path.exists():
        with log_path.open("r",encoding="utf-8-sig",newline="") as f:
            log_rows=list(csv.DictReader(f))
    data=data_path.read_bytes()
    errors=[]
    records=decode_message_stream(data,41,errors)
    log_rows.extend(errors)
    tracks=build_tracks(records)
    situations=build_current_situation(records)
    m2_protocol.write_csv(m2_protocol.OUTPUT_ROOT/"decoded_multitime.csv",m2_protocol.DECODED_CSV_FIELDS,records)
    m2_protocol.write_csv(m2_protocol.OUTPUT_ROOT/"track_table.csv",TRACK_CSV_FIELDS,tracks)
    m2_protocol.write_csv(m2_protocol.OUTPUT_ROOT/"current_situation.csv",SITUATION_CSV_FIELDS,situations)
    m2_protocol.write_csv(log_path,m2_protocol.LOG_CSV_FIELDS,log_rows)
    db_path=str(m2_protocol.OUTPUT_ROOT/"states.db")
    save_records_to_sqlite(records,db_path)
    query_result=query_sqlite(db_path)
    m2_protocol.write_csv(m2_protocol.OUTPUT_ROOT/"states_db_query.csv",
                          ["target_id","record_count","latest_time"],query_result)
    plot_tracks(records,m2_protocol.OUTPUT_ROOT/f"{data_path.stem}_tracks.png",
                annotate=data_path.stem=="partner_messages_multitime")
    for row in query_result:
        print(f"SQLite查询: {row['target_id']} 记录数={row['record_count']} 最新时间={row['latest_time']}")
    print(f"{data_path.name}: 解码 {len(records)} 条 | 航迹 {len(tracks)} | 态势目标 {len(situations)} | 流级错误 {len(errors)}")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
