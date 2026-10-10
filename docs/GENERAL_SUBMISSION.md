# 通用提交规范 prediction/0.2

本接口由 [issue #5](https://github.com/sunzhenchuan007/benchcad-3d2d/issues/5) 跟踪。模型继续提交 DXF 工程图与 JSON；自然语言答复不参与评分。JSON 是机器可读取的声明与实体索引，不是模型自行给出的验证结论。

本地程序与缺陷对照证据见 [GENERAL_VIEW_VALIDATION.md](GENERAL_VIEW_VALIDATION.md)。

已有 prediction/0.1 和 controlled-dxf 开发评分保持兼容。prediction/0.2 已有独立 STEP/DXF 投影核验，**尚未接入通用尺寸附着求解和整图总分**。新接口返回 `views_verified`，总分始终为 null，不能用于排行榜或宣称整图通过。

## 给模型的输出要求

提交 `drawing.dxf` 和 `prediction.json`。文件单位为 mm，空间坐标沿用输入 STEP 的坐标系。允许自由选择视图布局、纸面旋转、统一比例和空间正交投影方向，不要求任何固定视图名称或与参考图相同的布局。实体放在 DXF modelspace；可以使用嵌套、单实例 INSERT。当前不接受 paper-space viewport 或数组 INSERT。

严格遵循 [prediction.v0.2.schema.json](../schemas/prediction.v0.2.schema.json)。必须包含：

| 字段 | 模型应提交的内容 | 验证边界 |
| --- | --- | --- |
| `input_sha256`、`drawing_sha256` | 输入 STEP 与最终 DXF 的文件哈希 | 后台对实际文件重新计算；不能由提交替换评测输入 |
| `features` | 识别的特征、参数和输入几何引用 | 当前只核对引用是否存在，不评价特征类别/参数正确性 |
| `views[].projection` | 投影原点、图上向右/向上对应的空间单位向量，以及朝向观察者的法向 | 程序检查正交性，并从 STEP 重建该方向投影，与 DXF 双向比较 |
| `views[].sheet` | 图纸原点、纸面旋转角、统一比例 | 从实际图线反变换到模型长度单位核验 |
| `views[].geometry` | 可见轮廓、隐藏边、剖切边、剖面线 HATCH 的实体引用 | 检查实际实体和几何；不得只给坐标列表代替图线 |
| `views[].section` | 剖切面、保留侧、母视图、编号及剖切线/箭头/文字引用 | 重建截面和保留实体，核对剖切线、观看方向、编号与剖面区域 |
| `dimensions` | 类型、数值、实体引用、空间附着对象、测量含义 | 当前检查实体存在性；附着语义未验证，不能进入矩阵或计分 |
| `structure` | 实际绘出的对称、贯穿、数量、等值等标注及附着对象 | 当前检查引用存在性；结构含义未验证，不能成为约束 |
| `auxiliary` | 中心线与普通文字的实体引用 | 中心线必须具有 CENTER 线型；不能把额外轮廓随意隐藏为辅助线 |

不提交私有 `binding_ref`、GT 参数 ID、矩阵系数 `terms` 或“验证已通过”等自评字段。模型可通过评测端提供的 `inspect-step` 获得中性的面/边几何目录；这些引用不包含特征标签、必要尺寸清单或 GT 关系。引用目录算法版本为 geometry-catalog/0.1，需在同一评测环境生成与核验。

所有引用仍是不可信声明。文件哈希正确、引用存在、JSON Schema 通过，都不等于图纸内容正确。

## 空间方向与纸面方向分开

对空间点 p，投影原点 o，向右/向上单位向量 r、u：

```text
local_x = dot(r, p - o)
local_y = dot(u, p - o)
sheet_xy = sheet_origin + scale × Rotate(sheet_angle) × [local_x, local_y]
normal = cross(r, u)  # 指向观察者；视线方向是 -normal
```

例如常见 XY 投影可声明 r=[1,0,0]、u=[0,1,0]、normal=[0,0,1]。XZ 投影可声明 r=[1,0,0]、u=[0,0,1]、normal=[0,-1,0]。YZ 投影可声明 r=[0,1,0]、u=[0,0,1]、normal=[1,0,0]。也接受任意正交方向基；无需给视图贴“俯视图”标签。

方向是模型提供的候选，程序用 CAD 内核核验，不通过视图名称猜方向。若对称几何允许多个方向产生同一投影，单个视图无法唯一辨识方向；此模块接受几何等价投影，不宣称恢复了唯一方向。通用尺寸绑定必须进一步消解实体与位置歧义。

斜向投影的图上线段长度一般不是空间真长。`measurement.kind` 必须区分 `true_length`、`projected_length` 与 `angle`；未验证真长条件时，不得把投影长度直接填入 X/Y/Z 尺寸链。

## 实体引用不是图块名称

引用是一串 DXF handle，例如 `["A1", "B2", "C3"]`：从 modelspace 的 INSERT A1 进入块，再通过 INSERT B2，最终定位到实体 C3。裸 modelspace 实体可用 `["C3"]`。

程序读取每级实际 INSERT 的变换。相同块的不同实例必须分别引用；不能仅凭块名称或最后一级 handle 认定是同一条图线。隐藏/关闭/冻结图层上的证据拒绝。图上未分类实体会阻止本次视图核验通过，额外轮廓也参与双向几何比较。

## 平面全剖视

`section.kind` 当前为 `planar_full`。模型应声明剖切面的 `point_mm`、单位 `normal` 和 `retained_side`，并给出母视图、编号和实际图面标记的引用。

剖视方向必须垂直于剖切面，保留实体位于观察方向的后半空间。母视图必须能将该剖切面显示为一条剖切线。程序使用 OpenCascade 截面与半空间布尔运算，再对保留实体执行隐藏线消除；不是仅判断“剖切面碰到了零件”。

核验包括：投影轮廓、剖切边界、保留实体轮廓、剖面 HATCH 边界（含内部空洞）、剖切线位置和覆盖范围、两端观看箭头、两端编号与剖视标题。编号任意，例 B/B 与 B-B；不固定为 A-A。当前箭头采用实际三角 SOLID，剖面线采用 patterned HATCH。

任意方向适用于**正交投影和平面全剖视**，不表示已经支持透视、阶梯/旋转/半剖/局部剖。复杂剖视需要后续扩展，不能伪装成 planar_full 自动通过。

## 独立程序核验与评分边界

```sh
python -m benchcad3d2d inspect-step --input-step input/model.step --out geometry-catalog.json
python -m benchcad3d2d verify-views --input-step input/model.step --drawing drawing.dxf --prediction prediction.json --out view-report.json
python tools/build_projection_demo.py
```

需要已有 CadQuery/OCP、ezdxf、NumPy 环境。投影内核使用 OpenCascade HLR，截面使用布尔运算；曲线比较是有采样分辨率的双向点到线段距离，默认模型长度容差 0.1 mm，不是解析 Hausdorff 距离证明。DXF 曲线支持 LINE/ARC/CIRCLE/ELLIPSE/折线/SPLINE；超出资源上限或不支持的实体会拒绝。

`verify-views` 成功退出只表示该提交的视图证据核验通过。它没有判定视图组合足以表达全部特征，也没有验证尺寸关系、遮挡、GD&T 或完整工程制图规范。报告始终有 `score:null`、`whole_drawing_complete:false`、空的 `verified_annotation_ids`，并列出尚未验证的标注/特征。禁止退回 JSON-only 评分。

现有 controlled-dxf 的 F40/D35/V20/E5 总分是开发混合指标：F 比较提交 JSON 的三维特征理解；D 使用实际核验的 DXF 标注约束；V 检查实际视图、剖切标记和遮挡；E 检查一致约束的冗余。F 正确不能证明图纸完整。报告新增 `score_basis` 明示每项证据来源。

后续通用评分应由已核验的尺寸/结构附着生成空间方程，再与 GT 对照；同时将特征理解诊断与图纸表达结果分开报告。没有图纸证据的声明不能获得图纸表达分数。当前不得把新的视图核验结果与旧的私有模板绑定拼接，宣称完成通用整图评分。
