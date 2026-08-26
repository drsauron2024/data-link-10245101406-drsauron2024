# M4 AI辅助映射核验说明

- 候选来源：学校预生成候选（`reference/pre_generated_mapping_candidate.csv`）
- 使用的提示或候选文件：同上（未使用大模型，按手册降级路径）
- 发现的字段、单位、层次、有效性或来源问题：
  1. 经纬度颠倒：候选将 `latitude_code+bit0` 映射到 `position.lon`、`longitude_code+bit1` 映射到 `position.lat`（review_note 已提示"字段层次可能需要核验"）；
  2. 高度漏物理偏置：候选规则为"code 乘 1 米"，正确为 `code−1000`（米）；
  3. 呼号漏有效性位：候选"去除补0后直接映射"未处理 bit6=0 时统一字段应为 null，且 input_field 未标注有效性条件；
  4. 时间来源张冠李戴：候选把 `status_flags.bit2` 映射到 `quality.time_valid`，实际 bit2 是 timestamp_fallback，应映射 `quality.time_source`；
  5. 候选不完整：8 条候选未覆盖 alt_type、on_ground、speed/heading/vertical_rate、position_valid、time_valid 等，正式映射共 30 条，其中 22 条为依据权威定义补全。
- 人工修订依据：`schema/source_field_definitions.md`（两种来源权威映射表）、`schema/teaching_message_spec.md`（定点编码与标志位定义）、手册表 17。
- 正常样例验证结果：780abc 在两个来源中恢复一致——lat=31.250382、lon=121.493669，量化恢复误差为零（两个来源共用同一套 22 位定点规则）。
- 真实零值与缺失值样例验证结果：000001 的 lat/lon 为真实近零值（有效位=1），两个来源均保留数值而非判为缺失；780def 的 lat/lon 缺失（有效位=0），两个来源均为 null 且 `position_valid=false`，同时 alt=7400.0（geometric）、heading=268.0 等有效字段正常恢复——真实零值、字段缺失与协议整数 0 三者未混淆。
- 不应由大模型自行决定的内容：偏置、分辨率、位宽、有效位语义、保留位与校验和等协议事实；时间回退不等于时间无效；message_valid 只代表通过本规范的格式与校验检查，不代表来源真实性。
