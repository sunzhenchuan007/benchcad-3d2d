# 图纸证据适配接口

当前主评分路径是受控 DXF。PDF 识别器保留为备选，暂不实现文本提取、矢量解析、OCR、几何附着识别或 PDF 评分校准，也不增加 PDF 依赖。

后续工作由 [issue #1](https://github.com/sunzhenchuan007/benchcad-3d2d/issues/1) 跟踪，通过关联该 issue 的 PR 提交与审查；仅交付占位接口时保持 issue 开放。

## 统一入口

`benchcad3d2d/adapters.py` 定义 `EvidenceAdapter` 与 `DrawingEvidence`。适配器由评测端维护，接收 `(gt, prediction, drawing, rules)`，返回下列证据供同一个矩阵与评分流程使用：

| 字段 | 内容 |
| --- | --- |
| `equations` | 已核验标注的标量约束；每行包含 `terms`、`value`、`annotation_id` |
| `nominal_equations`（可选） | 实际可见且已绑定的名义标注约束，用于发现矛盾；不是接受其数值正确 |
| `structures` | 已核验的结构标注，使用后台规范化实体 ID |
| `verified_annotation_ids`（可选） | 获得实际图纸证据支持的提交标注 ID |
| `views` | 必要视图逐项检查；包含 `type`、`geometry_ok`、`marking_complete`，全剖视还需 `marking_penalty_points`；应显式提供 `readability_complete`、`readability_score` 与失败原因 |
| `rejected`、`unsupported` | 标注拒绝原因、无法核验项；任何此类项都会阻止整图通过 |
| `drawing_verified` | 是否实际执行图纸检查；不能仅根据 JSON 声明设为 true |
| `view_count` | 实际绘制的视图数量，用于表达效率 |

未来 PDF 适配器须检查所有必要视图、剖切标记及可读性。不能将 GT 真值填入约束，不能以预测 JSON 替代图上证据，也不能默默忽略图上额外的尺寸。无法确定的文本、附着或剖视应报告 `unsupported`；OCR 识别到数字本身不等于已核验尺寸关系。

开发时可通过 Python 的 `evaluate(..., mode="pdf", evidence_adapter=trusted_pdf_collector)` 接入评测端实现；也可在评测端将内置 `collect_pdf` 替换为真实实现。提交 JSON 与命令行不提供加载任意代码或自行注册识别器的途径。这个接口是内部开发合同，尚未冻结为生产插件协议。

## 当前 PDF 占位行为

CLI 已预留 `--mode pdf --drawing <路径.pdf>`。对于存在的 PDF 路径，内置适配器直接报告：

- `status: "unsupported"`，退出码 **3**。
- `score: null`，`whole_drawing_complete: false`。
- 图纸证据未检查、未通过，`unsupported` 包含 `adapter_not_implemented`。
- 不采纳 JSON 的尺寸或结构作为已绘出信息；分项只作诊断，总分不可用于排行。

缺少图纸参数、路径不存在或扩展名错误属于 `invalid_input`，退出码 **2**。当前只检查路径，不解析 PDF 内容，不宣称文件内容有效。

PDF 占位不会自动退回 JSON 评分，也不会自动切换到另一个 DXF。后续是否启用 PDF、其证据支持范围与校准结果由评测配置明确决定。推荐的 DXF 派生 PDF 预览导出仍是后续工作，当前没有新增导出器。
