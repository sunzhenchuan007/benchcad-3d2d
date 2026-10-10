# 可运行框架 development-v0.2

本地框架基于仓库原有 required_variables、variables 与关系链合同建立。源案例 01/13/15/84/86/88 仍是 source_collected，未被伪装成已经配对或完成 GT 的评分案例。

## 文件布局

```text
config/rules.v0.2.json       可修改权重、容差、剖切标记罚分和规模上限
schemas/                    GT、prediction、规则和报告的 JSON 接口
benchcad3d2d/
  contracts.py              版本、单位、ID、数字及资源检查
  linear.py                 线性关系消元、欠约束、冲突和证明
  evidence.py               JSON 诊断与受控 DXF 证据适配器
  adapters.py               统一证据接口与 PDF 备选占位
  evaluator.py              特征匹配、完整性、视图与效率评分
  __main__.py               统一 CLI
tools/run_framework_demo.py 原有关系链示例及双孔位置关系示例
tools/build_controlled_demo.py 真实 CQ→STEP、DXF、GT 和缺陷样本生成
tests/test_framework.py     对等价、遗漏、矛盾、伪声明和标记的回归检查
.outputs/                  运行产物，Git 忽略；不进入源案例注册表
```

规则详见 [RULES_V0_2.md](RULES_V0_2.md)。原 DESIGN.md 是整体目标；本页和规则页说明目前真正实现的子集。
本地执行证据见 [FRAMEWORK_VALIDATION.md](FRAMEWORK_VALIDATION.md)。

## 不需要 CAD 依赖的运行

Python 3.10+ 和 NumPy 即可。当前两个本地 Python 环境均已有 NumPy，没有安装包或更改环境：

```sh
python tools/verify_sources.py
python -m unittest discover -s tests -v
python tools/run_framework_demo.py
python -m benchcad3d2d verify --gt .outputs/framework/dimension_chain/baseline/gt.json --prediction .outputs/framework/dimension_chain/baseline/prediction.json --out .outputs/relation-report.json
```

输出包含每个参数的确定状态、正确值/恢复值、证明标注 ID、冲突、结构遗漏、冗余标注和规则指纹。
relations-only 报告的 score 为 null，whole_drawing_complete 为 false；CLI 返回成功只代表显式声明的关系范围通过，不代表完成工程图任务。
退出码：0 为关系诊断通过/整图通过，1 为验证失败，2 为输入格式错误，3 为预留适配器尚未实现。

PDF 评分识别器暂不完善，已开放 `--mode pdf` 和评测端 Python 适配接口。当前返回 `unsupported`、总分 null，不采纳 JSON 声明充当图纸证据。字段与接入边界见 [EVIDENCE_ADAPTERS.md](EVIDENCE_ADAPTERS.md)。受控 DXF 仍是已实现的图纸评分路径。

## 实际 CAD 演示

在已有包含 cadquery、OCP 和 ezdxf 的 Python 环境中执行：

```sh
python tools/build_controlled_demo.py
python -m benchcad3d2d verify --gt .outputs/controlled_c002/gt/gt.json --prediction .outputs/controlled_c002/submissions/good/prediction.json --drawing .outputs/controlled_c002/submissions/good/drawing.dxf --mode controlled-dxf --out .outputs/controlled-report.json
python -m unittest discover -s tests -v
```

该脚本生成 120×56×20 mm 板件及两个阶梯盲孔，导出并重新读取 STEP，检查 BRep、实体数、四段圆柱面和解析体积。
GT 明确列出 **15 个连续参数**与两个盲孔终止条件。两孔的四个尺寸分别保留，不因 GT 已知相同就替图纸提供等值关系；只有实际绘出的 2X 相同孔说明通过后，才加入相等约束。

有 25 组实际 DXF：原 20 组，加孔到两边的等价/重复/矛盾链，以及文字重叠、文字压轮廓。沉孔与小孔直径现集中在剖视图。使用全矩阵依赖分析，详见 [成熟方法与来源](MATRIX_METHOD.md) 和 [验证记录](FRAMEWORK_VALIDATION.md)。
这些由脚本构造，用来验证评分行为；不是模型作答，也不是独立 benchmark 泛化结果。

当前本机可用 CAD 环境：`D:\Anaconda\envs\benchcad\python.exe`。无需改系统 Python。该路径只是本次运行说明，不是库内部硬编码要求。

## GT / prediction 的最小内容

GT 保留：schema_version、case_id、units、geometry.anchors、variables、required_variables、entities、structure。
实际图纸模式额外保留 annotation_bindings、view_requirements、reference_view_count；这些内部映射不挂载给模型。

prediction 保留：schema_version、case_id、units、features、views、dimensions、structure。
受控图纸标注使用 drawing_ref 指向实际 DXF 实体，binding_ref 指向可信制图工具的几何绑定；内部系数由后台绑定表生成，模型不能随意填一套矩阵假装图纸已表达。
本演示直接构造绑定表和提交，尚未实现供真实 Agent 使用的公共 CAD 制图工具/绑定登记服务。

schemas 是接口说明；实际输入仍须通过 contracts.py 与证据适配器的语义检查。JSON Schema 校验本身不能证明锚点正确或图纸完整。

## 后续扩展顺序

1. 从用户提供的原生 SLDPRT 或受控 CQ 构造提取、审核参数，并与选定 STEP 配对；先试实际特征较简单的案例，不按源编号猜难度。
2. 接入可信制图工具，记录中性的几何引用、投影变换和尺寸绑定，避免让 Agent 看内部 GT ID。
3. 增加原生 SLDDRW 与其他 DXF 表示、一般视图变换，以及任意合法编号/同义结构符号。
4. 扩展半剖、局部剖、相交孔和非线性约束；未支持项继续显式失败。
5. 由专家校准权重、容差、表达例外与参考成本，再冻结正式规则并测试独立案例。

原生提取、任意图纸解析、一般非线性、多解验证和专家品位评估当前均未完成。本框架没有自动安装、上传、提交或推送内容。
