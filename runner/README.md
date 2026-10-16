# Task controller / 任务控制程序

This directory documents the shared controller responsibilities. It does not yet contain the portable Case 13 runner.

控制程序负责准备模型可见输入、固定提示词和工具版本、启动独立会话、限制总预算、收卷、组织评测并记录证据。CAD 后端负责具体制图，Codex CLI 负责其内部模型与工具循环。

当前本地试验每阶段 60 分钟、CAD 单次 300 秒；记录操作次数，但没有 30 个模型决策轮的硬上限。提交标记在 CLI 退出后读取，不是标记出现即锁定。Windows Job 的 4 GiB 聚合提交内存和 50% CPU 配额只约束已归入的本地进程，不限制远端模型服务器。

对各 case 和重复运行使用新会话。出图与重建分别准备目录，重建只收最终 DXF 与其预览。私有 GT、原 STEP 和评测输出不得通过其他工具入口泄露给重建 AI；完整隔离验收仍是发布可运行控制器前的要求。

详细顺序、错误反馈、退出状态、任务计数和未实现项见 [AI 工作说明](../docs/AGENT_SOLIDWORKS_CODEX.md)。
