# Codex CLI agent adapter

**CLI 是模型运行系统，CAD 后端是被调用的软件。** 同一个 Codex CLI 接入可以分别使用 SolidWorks 或 FreeCAD 的工具；不同后端需要各自的工具说明和环境配置。

本地 Case 13 控制程序把任务说明通过 stdin 送入 codex exec。CLI 把任务与可用工具发给模型，执行模型请求的工具调用，将日志或图像结果作为后续上下文；模型最终结束答复后，外部控制程序处理提交文件。

模型可读取允许文件、写代码、执行命令、打开已经生成的图片。CAD 命令成功不会自动产生视觉反馈；AI 先渲染，再调用看图工具。反馈包括执行输出、异常、退出状态和图像，不包含隐藏 GT 分数。

当前说明来自本地 CLI 0.163.0 试验，不能把 CLI 的一次 turn、一次 shell 调用或 CAD 请求都称作一次模型推理轮。API 自建 Agent 将是另一种接入，不在本次实现范围。

[完整工具、循环、反馈与提交说明](../../docs/AGENT_SOLIDWORKS_CODEX.md) · [输入输出](../../docs/INPUT_OUTPUT.md)
