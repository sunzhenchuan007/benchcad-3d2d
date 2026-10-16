# BenchCAD 3D→2D with FreeCAD

**Planned backend; no end-to-end BenchCAD run is claimed.** FreeCAD performs CAD operations, TechDraw is its drawing workbench, and ezdxf is a separate DXF inspection/processing library. Codex CLI can drive this backend too; it is independent of the CAD choice.

**待实现：使用同一 benchmark 规则，另写 FreeCAD 的 CAD 操作与状态提取。** 不能把 SolidWorks 的脚本改名后称为 FreeCAD 版本，也不能将 FreeCAD 软件的功能列表当成本项目验收结果。

## 技术分工

| 工具 | 计划用途 |
|---|---|
| FreeCAD Python API / Part | 导入 STEP，读取几何，保存原生模型 |
| TechDraw | 生成投影、剖视、尺寸和图页；具体类型逐项验证 |
| ezdxf | 检查或处理 DXF、定位图元；不承担 STEP 的实体投影内核 |
| 公共渲染工具 | 从最终 DXF 生成统一重建输入预览，保持来源哈希 |
| CAD 状态适配器 | 从最终 .FCStd 和导出记录提取实际视图／剖切 JSON |

## 首轮验收清单

- [ ] 固定 FreeCAD／TechDraw 版本与可运行的操作系统环境。
- [ ] 导入登记 STEP，检查单位、实体和坐标；不接触专家答案。
- [ ] 生成普通投影与直线全剖，保存并重开 .FCStd。
- [ ] 创建关联尺寸，检查实际图纸数值和附着对象。
- [ ] 导出含尺寸、剖面线、文字和剖切标识的 DXF；逐项验证导出保真。
- [ ] 渲染最终 DXF，统一预览规则，支持模型打开图像反馈。
- [ ] 提取最终视图、切面与坐标变换；绑定原生文件、DXF 和快照哈希。
- [ ] 对不支持或无法提取的剖法明确失败，不制造完整 JSON。
- [ ] 接入受控日志／收卷协议，验证文件隔离及资源边界。
- [ ] 在同一案例上完成独立重建与公共 IoU 计算，报告差异。

半剖、阶梯剖、局部剖、详图等复杂类型在基础链路通过后分别验收。Windows／Linux 运行与无界面自动化方式待实际选择和试验；本次没有安装 FreeCAD、配置 Docker 或宣称无界面导出可用。

接口与产物职责见 [输入输出规范](../../docs/INPUT_OUTPUT.md)；目录和共享边界见 [架构](../../docs/ARCHITECTURE.md)。
