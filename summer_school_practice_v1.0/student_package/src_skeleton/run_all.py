from __future__ import annotations

import csv
from pathlib import Path

import m2_protocol
import m3_tracks
import m4_mapping
import m5_quality


STUDENT_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = STUDENT_PACKAGE_ROOT / "output"
DATA_ROOT = STUDENT_PACKAGE_ROOT / "data"


# 输入配置：切换数据只改这里
M2_VECTORS_SOURCE = DATA_ROOT / "raw_states.json"
M3_STREAM_SOURCE = DATA_ROOT / "partner_messages_multitime.bin"
# 真实OpenSky数据（验证用，两行一起切换）：
# M2_VECTORS_SOURCE = DATA_ROOT / "opensky_real" / "source"
# M3_STREAM_SOURCE = DATA_ROOT / "opensky_real" / "opensky_real_messages.bin"
M4_OPENSKY_SITUATION = OUTPUT_ROOT / "current_situation.csv"
M4_PARTNER_SITUATION = DATA_ROOT / "m4" / "partner_current_situation.csv"
M5_CASES_SOURCE = DATA_ROOT / "m5" / "anomaly_cases.csv"
M5_RULES_SOURCE = DATA_ROOT / "m5" / "anomaly_rules.csv"


def prepare_output_directory() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for p in OUTPUT_ROOT.iterdir():
        if p.name != "README.md":
            p.unlink()


def parse() -> None:
    m2_protocol.run_pipeline(M2_VECTORS_SOURCE)


def encode() -> None:
    pass


def decode_validate() -> None:
    pass


def build_tracks() -> None:
    m3_tracks.run(M3_STREAM_SOURCE)


def map_unified() -> None:
    m4_mapping.run(M4_OPENSKY_SITUATION, M4_PARTNER_SITUATION)


def check_quality() -> None:
    m5_quality.run(M5_CASES_SOURCE, M5_RULES_SOURCE)


def export_results() -> None:
    n_frames=len((OUTPUT_ROOT/"encoded_messages.bin").read_bytes())//41
    with open(OUTPUT_ROOT/"unified_situation.ndjson",encoding="utf-8") as f:
        n_unified=sum(1 for _ in f)
    with open(OUTPUT_ROOT/"alert_log.csv",encoding="utf-8-sig",newline="") as f:
        n_alerts=sum(1 for _ in csv.DictReader(f))
    print(f"端到端汇总: M2帧 {n_frames} | 统一消息 {n_unified} 条 | M5告警 {n_alerts} 条")
    for p in sorted(OUTPUT_ROOT.iterdir()):
        print("  output/",p.name)


def run_pipeline() -> None:
    prepare_output_directory()
    parse()
    encode()
    decode_validate()
    build_tracks()
    map_unified()
    check_quality()
    export_results()


def main() -> int:
    try:
        run_pipeline()
    except NotImplementedError as exc:
        print(exc)
        print("当前文件是学生骨架，模块实现完成后再进行端到端运行。")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
