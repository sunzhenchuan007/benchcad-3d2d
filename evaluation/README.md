# Evaluation / 评测

The policy is shared across CAD backends. The local geometry metric is not a calibrated overall benchmark score. Runtime evaluators have not yet been ported into this directory.

| 分项 | 当前处理 |
|---|---|
| 几何恢复 | 独立 AI 从最终 DXF 和其 PNG 重建 STEP；本地 Case 13 已计算归一化旋转／镜像最大 IoU |
| 剖切位置 | 比较派生实际切面与人工 GT；Case 13 缺批准 GT，尚未评分 |
| 标注质量 | 近似文字包围盒只能给出碰撞候选，尚未完整扣分 |
| 视图冗余 | 完整性满足后再比较参考视图数；细则和评分器待验收 |
| 专家图纸重建校正 | 暂缓，不生成专家 DXF 的基准 STEP，也不除以专家重建 IoU |

IoU 政策：分别居中、按各自最长包围盒边等比例归一化；原候选搜索 24 个正交旋转，关于 XY 平面镜像后再搜索 24 个旋转，取较高值。镜像严格更高时报告两个值和 reflection_used=true；较低或持平时只报告原旋转值和 false。不是任意连续角度配准，也不保留绝对尺寸差异；绝对尺寸诊断另列。

政策版本为 normalized-iou48-mirror-max/1。iou24 保持仅旋转值，iou 是新政策采用值。不得用新字段含义覆盖旧实验记录。

无效参考几何、无效重建、缺提交、超时、工具故障和不支持的剖法应分开记录。正式重试次数、重建采样聚合、缺失分项和总分权重尚未冻结，不能事后择优隐藏失败。

[设计与限制](../docs/DESIGN.md) · [Case 13 结果](../docs/experiments/case013-solidworks-codex.md)
