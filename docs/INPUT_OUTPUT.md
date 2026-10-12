# 输入与输出约定

本页采用当前 [评测方案](DESIGN.md)：标准化 STEP 输入，DXF 与剖切 JSON 输出，独立 AI 根据 DXF 重建后比较 IoU。旧尺寸链变量表和模型特征树 JSON 不再作为本路线的必填输出。以下为待冻结的接口设计，不表示仓库已提供完整评分命令。

## 1 案例和提交边界

建议的数据职责如下，具体封装需在接口实现时版本化：

```text
case/
├── input/model.step                 提供给出图 AI 的标准化几何
├── geometry/axis_index.json          同一 STEP 推导的中性轴线索引
└── private_gt/
    ├── reference.step               几何比较参考
    ├── sections.json                人工剖切要求
    └── expert_reference.dxf          可选，验证 AI 校准及视图数量参考

submission/
├── drawing.dxf                      出图 AI 的实际工程图
└── prediction.json                  实际剖切与视图关联

verification/
├── reconstructed.step               独立验证 AI 仅根据 DXF 重构
└── report.json                      IoU、剖切和碰撞等检查结果
```

`reference.step` 与选定标准化输入的几何一致。中性索引不包含“必须切哪些轴”等答案；人工目标和专家图纸属于后台评分信息。

出图 AI 可见 `input/` 和公开几何工具接口。验证 AI 只可见提交的 `drawing.dxf` 与通用说明，不能看到上述输入 STEP、`private_gt/`、`prediction.json` 或原生 CAD。输出目录与数据目录分开，隔离必须由文件访问权限或沙箱挂载实现。

目前的源文件注册格式和六例 `source_collected` 状态保持不变，见 [CASE_SPEC.md](CASE_SPEC.md)。本方案没有通过空文件或虚构结果把源案例升格为可评分案例。

## 2 DXF 要求

DXF 应包含足以表达原零件的视图、必要尺寸和孔／台阶／腔体等特征。采用剖视时应有对应的规范剖切表达。不同布局、旋转和视图中的等价标注可接受；需能关联图纸上的实际几何和 JSON 的视图、剖切记录。

AI 自己图纸内的 DXF handle 可以帮助定位证据，但不同图纸的 handle 不共享身份。几何身份绑定到固定 STEP 的 SHA-256 及稳定面／边／轴引用。

PDF 作为将来的识别适配器备选，不取代当前要求的 DXF。

## 3 出图 AI 的剖切 JSON

JSON 记录的是实际采用的剖切，而不是让 AI 自报得分或自行指定“哪些位置应通过”。建议包含：

| 信息 | 作用 |
| --- | --- |
| case 标识、输入 STEP 哈希、单位和坐标约定 | 确定参考几何与空间基准 |
| 视图标识和投影／图纸坐标映射 | 关联 3D 剖切和 DXF 中的视图 |
| 剖视类型 | 全剖、半剖等实际表达方式 |
| 切面点和单位法向 | 定义 STEP 坐标中的真实剖切位置与方向 |
| DXF 证据引用 | 定位剖切线、标识与相应剖视区域 |

单个切面记录可表示为以下形式。这只是字段含义示例，不是已冻结的 prediction schema，也不对应任何真实 case 的 GT：

```json
{
  "id": "section_1",
  "view_id": "view_section_1",
  "section_type": "full",
  "plane": {"point_mm": [0, 0, 0], "normal": [1, 0, 0]},
  "dxf_evidence": {"cutting_mark": "A-A", "view_region_id": "region_1"}
}
```

单平面不能完整描述所有半剖、阶梯剖或旋转剖。相应切面组合、切除区域和方向模板需要扩展接口并明确支持范围；不支持的类型不能静默当成普通全剖评分。

JSON 与 DXF 的证据匹配仍需实现。只有 JSON 中有剖切声明、图纸却未表达时，不能自动认定专业表达合格。

## 4 人工剖切 GT

GT 记录对实际剖切的要求，主要包括：

- 固定 STEP 哈希、稳定轴引用和轴线几何。
- `contains_axis`：要求切面包含目标轴线。
- `crosses_axis_at_station`：要求横切交点落在指定轴向位置与容差内。
- `angle_rule`：不要求角度，或指定参考切面法向及允许误差。
- 必要／推荐分类：拟用于缺失扣分与推荐奖励，当前网页草稿尚未包含这项分类。
- 标注人、时间和说明，用于追溯人工草稿。

当前网页的 `benchcad-section-position-draft/3` 为标注草稿格式，使用 `status: draft`。完整面指纹保存在配套 `axis_index.json`，不在每条记录中重复展开。它不是出图 AI 的实际切面提交格式；评分器需比较“GT 要求”与“AI 实际切面”。

## 5 验证输出

独立验证 AI 输出 `reconstructed.step`。脚本报告参考与重构的几何有效性、对齐策略和 IoU，并保留失败原因。

剖切报告应列出命中的目标、位置误差、可选角度误差、缺失项及未验证的图纸证据。碰撞报告应定位问题所在视图、图纸对象和重叠区域。视图冗余按统一规则与对应专家数量比较。

权重、容差、阈值、失败处理和总分尚未冻结。草稿标注、几何自检或上传成功不能替代完整 benchmark 评分结果。
