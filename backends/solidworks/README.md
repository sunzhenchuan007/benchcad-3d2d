# BenchCAD 3D→2D with SolidWorks

**Local pilot completed; portable runner not yet published.** This backend uses SOLIDWORKS on Windows. Codex CLI is the agent runner, not the CAD engine. See the [shared architecture](../../docs/ARCHITECTURE.md), [detailed agent guide](../../docs/AGENT_SOLIDWORKS_CODEX.md), and [Case 13 report](../../docs/experiments/case013-solidworks-codex.md).

**已完成本地流程试验，尚未发布可直接安装运行的后端代码。** 当前证据范围是 SOLIDWORKS 2023、Codex CLI 0.163.0、Case 13；不代表所有案例或所有剖法通过。

| 环节 | Case 13 的实际做法 |
|---|---|
| 输入 | STEP 加由同一 STEP 生成的中性原生缓存；没有原始设计树答案 |
| 工具 | Python、CadQuery/OCP、ezdxf、SOLIDWORKS API 与常用帮助函数 |
| 画图 | 模型决定视图、剖切、标注和布局；CAD 执行 |
| 自查 | AI 导出工作 DXF，调用渲染脚本，再打开 PNG |
| 提交 | AI 保存 output/drawing.SLDDRW，写 output/SUBMIT.json，结束 CLI |
| 收卷 | 控制程序重开原生图纸，导出最终 DXF、提取 drawing.json、渲染 preview.png |
| 重建 | 新会话仅用最终 DXF 和其 PNG 建模并提交 STEP |
| 指标 | 归一化旋转／镜像最大 IoU；剖切 GT 分数和完整碰撞扣分未完成 |

帮助函数已用于普通视图、直线全剖及几何关联尺寸。半剖、阶梯剖、局部剖和局部放大不因 CAD 软件支持就自动算作 benchmark 适配完成。完整工具表与输入／反馈见详细指南。

后续迁移必须补齐：安装与许可说明、可移植配置、依赖版本、工作进程启动、原生引用打包、收卷一致性、资源限制、所有工具访问路径的隔离测试，以及与公共日志接口的适配。此目录当前只有说明，不提供无实现的启动命令。
