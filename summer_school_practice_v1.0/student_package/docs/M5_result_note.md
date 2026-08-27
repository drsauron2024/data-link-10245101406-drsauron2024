# M5 异常结果说明

  批次时间：1710000120

  四类必做规则是否均运行：是——R1 位置缺失、R2 数据延迟、R3 联合键重复、R4 航向越界均运行；另实现选做规则（message_valid=false 转换为 FRAME_VALIDATION_ERROR，本批次无此类记录）。

  告警总数及按类型统计：共 5 条——POSITION_MISSING 1、DATA_DELAYED 1、DUPLICATE_RECORD 2、HEADING_OUT_OF_RANGE 1。

  HIGH/MEDIUM 数量：HIGH 1（780def 位置缺失）、MEDIUM 4。

  正常记录是否被误报：否——780abc 四项检查全部通过，anomaly_level=NONE、display_status=NORMAL，未产生告警。

  heading=360 与 heading为空的处理：780bbb 的 heading=360.0 触发 HEADING_OUT_OF_RANGE（MEDIUM，边界值 360 不属于 [0,360)）；本批次无 heading 为空的记录，按规则"heading 为空时不触发航向越界"，空值不会误报。

  字段缺失、帧验证失败、来源真实性三者的区别：字段缺失=字段为空/有效位为0（780def 的 lat 为空 → POSITION_MISSING，告警只针对数据缺失本身）；帧验证失败=帧未通过接收判据（message_valid=false → FRAME_VALIDATION_ERROR，本批次无）；两者均不涉及来源真实性——message_valid 只代表帧通过本规范的格式与校验检查，不代表数据真实或安全。
