# M6综合运行说明

## 基本信息

- 姓名：（填写）
- 学号：10245101406
- GitHub用户名：drsauron2024
- Python版本：3.14.7
- 是否使用SQLite：是
- M4候选来源：学校预生成候选

## 安装与运行

先按课程包 `environment/README_environment.md` 建立独立 `.venv`。在课程包根目录清空 `student_package/output/` 后执行：

```powershell
.\.venv\Scripts\python.exe student_package\src_skeleton\run_all.py
```

## 程序入口

统一入口为 `src_skeleton/run_all.py`，按数据依赖链依次调用四个模块的端到端入口：

1. `m2_protocol.main()`——OpenSky 解析、41 字节帧编解码与往返验证（parse/encode/decode_validate 三阶段）；
2. `m3_tracks.main()`——批量解码、航迹与当前态势（build_tracks 阶段，含选做 SQLite 与航迹图）；
3. `m4_mapping.main()`——候选核验、统一映射与 NDJSON（map_unified 阶段）；
4. `m5_quality.main()`——固定规则检查、告警与质量态势（check_quality 阶段）；
5. `export_results()`——端到端成果汇总。

运行前会清空 `output/`（保留 README.md），保证从空输出目录可重复运行。

## 输入文件

- M2：`data/raw_states.json`（5 条教学样例）
- M3：`data/partner_messages_multitime.bin`（9 帧、369 字节）
- M4：M3 生成的 `output/current_situation.csv`（OpenSky 态势）+ `data/m4/partner_current_situation.csv`（TeachingLink 态势）+ `reference/pre_generated_mapping_candidate.csv`（候选）
- M5：`data/m5/anomaly_cases.csv`、`data/m5/anomaly_rules.csv`

## 输出文件

- 编解码：`encoded_messages.bin`、`decoded_partner_states.csv`、`roundtrip_report.csv`、`validation_log.csv`
- 航迹与态势：`decoded_multitime.csv`、`track_table.csv`、`current_situation.csv`、`states.db`、`states_db_query.csv`、`partner_messages_multitime_tracks.png`
- 映射：`llm_mapping_candidate.csv`、`verified_mapping_table.csv`、`unified_situation.ndjson`
- 质量：`alert_log.csv`、`quality_situation.csv`
- 说明：`docs/M1_interface_risk.md`、`docs/M4_mapping_review.md`、`docs/M5_result_note.md`

## 实验结果

- M2：5 条教学记录 → 3 帧（123 字节），2 条坏记录进 validation_log；往返对比 24 行全部通过（误差 ≤ 1 量化单位）
- M3：9 帧全部解码 → 9 条航迹记录、3 个当前态势目标；SQLite 入库 9 条并查询成功
- M4：8 条预生成候选经核验修正/补全为 30 条正式映射（1 条候选未采纳），生成 6 条统一消息（两来源同目标关键字段一致）
- M5：6 条记录命中 5 条告警（HIGH 1、MEDIUM 4），正常记录零误报
- 真实数据验证：用本人程序读取 `data/opensky_real/`（71 条真实向量）——71/71 解析编码、与参考帧逐字节一致、71/71 解码通过、往返精度超标字段数 0、航迹 71 条/态势目标 24 个

## 已知限制

- 教学协议 TeachingLink 仅用于课程教学，不对应真实装备协议；message_valid 不代表来源真实性；
- 帧边界假定已对齐，不做失步重同步；传输无重传与协议状态机（课程边界约定）；
- M1 系统处理流程图（PDF/PNG）尚未生成；
- 真实数据验证通过切换模块 main 中的输入路径进行，不产出交付文件。

## 最终提交信息

- 仓库链接：（填写）
- 最终commit ID：（填写）
- 最后检查日期：（填写）
