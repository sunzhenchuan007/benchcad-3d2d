# SolidWorks：统一运行入口

**用 `tools/solidworks.py` 配置、检查、启动并查看已有 SolidWorks 试验。
它调用已经准备好的本地控制程序，保留原有 CAD 工具、模型配置和评分流程。**

这次发布的是可执行的入口适配器，不是完整的 SolidWorks 安装包。
新电脑仍需准备 Windows、SOLIDWORKS 许可、Codex CLI、两个 Python 环境、
工具和模板、沙箱配置及各项预检证据。只有下载这个仓库，尚不能运行新 case。
入口本身只需 Python 3.11+ 的标准库；运行时依赖由本地试验环境提供。

## 1. 配置一次

在仓库根目录执行，替换以下两个通用路径：

```powershell
python tools/solidworks.py init --pilot-root "C:/benchcad/prepared-case" --python "C:/Python311/python.exe"
```

命令生成 `.local/solidworks.toml`，只保存试验目录与控制器 Python 路径。
路径可包含空格；已有配置不会被覆盖。该目录被 Git 忽略，不应上传。
也可参照 `backends/solidworks/entry.example.toml` 手工编写配置，再用 `--config` 指定。
相对路径以配置文件所在目录为基准。

模型、思考强度和资源预算仍以试验目录的 `config.json` 为准。
入口不会悄悄改模型、预算、提示词或登录配置。需要改变实验条件时，应准备新的试验目录，
再指向它；这次没有新增任意 STEP 的自动准备功能。

## 2. 检查

```powershell
python tools/solidworks.py doctor --config .local/solidworks.toml
```

逐项返回 Windows 平台、文件、可执行程序路径、预算字段、已有预检记录和模型目录的检查结果。
`ready_for_existing_runtime=true` 只表示这些准备项齐全。
它不会启动 CAD、联网验证账号、测试当前许可或重新执行沙箱隔离测试。
旧预检记录可能过时；换电脑、换解释器或升级 CLI 后必须由运行环境重新做预检。

## 3. 启动

```powershell
# 先确认是否允许启动；不请求模型、不启动 CAD
python tools/solidworks.py run --config .local/solidworks.toml --dry-run

# 正式前台运行，可能消耗账户额度
python tools/solidworks.py run --config .local/solidworks.toml
```

已有进度时必须显式加 `--resume`。继续执行沿用原控制程序的重试规则，
不会清零尝试次数，也不等于恢复 CLI 对话。已完成试验拒绝重跑，应查看结果或准备新试验。
存在运行锁时拒绝启动；入口不会自动删除锁，也不把锁的存在直接判断为进程仍活着。

运行时终端输出阶段变化，例如 drawing → submission → reconstruction → evaluation。
完整 stdout/stderr 单独保留在试验目录 `.launcher/<本次编号>/`，不会用大量原始日志淹没终端。
原控制器的 CAD 日志、CLI 事件和中间产物继续按原目录保留。

这是前台入口，请保持终端开启。中断入口不能保证 CAD 子进程已经停止；
此时保留运行锁并记录 `entry_interrupted_child_may_be_running`，由操作者核实本次进程，
不要直接删除锁重跑。入口不关闭其他用户的 SolidWorks 会话。

## 4. 看进度和结果

另开一个终端：

```powershell
python tools/solidworks.py status --config .local/solidworks.toml
python tools/solidworks.py results --config .local/solidworks.toml
```

这两个命令只读原始记录，不启动模型，也不重写历史报告。它们使用同一 JSON 结构，
便于人查看和其他程序解析。`status` 可在运行中调用，`results` 可在结束后调用。

| 字段 | 含义 |
|---|---|
| stage / status | 原控制程序记录的阶段和状态 |
| launcher.exit_code | 本次控制程序进程退出码；没有新入口记录时为 null |
| stages.*.cli_launches | 每阶段启动 CLI 的次数，不是模型轮数 |
| last_command_executions | 最近一次 CLI 已完成的命令数；通常在该次 CLI 退出后更新 |
| reported_cad_requests | 原报告中该阶段 CAD 请求次数；未生成报告时可能为 null |
| submission_requested | 提交标记存在；不代表原生文件已通过验收 |
| metrics | 已保存的指标；缺失值保持 null，不制造零分或总分 |
| artifacts | 已存在的常用产物，相对于试验目录的路径 |
| model_rounds | 目前为 null，入口没有准确的模型决策轮统计或硬上限 |

结果依次区分：**模型请求提交 → 原生图纸收卷成功 → 重建完成 → 指标算出**。
`partial_metrics_completed` 仍表示只有部分指标，并非所有指标齐全。
结果中出现文件路径也不额外证明其内容合格；以原控制程序的验收记录为准。

入口退出码：`0` 为查询成功、检查通过或控制程序正常结束；`2` 为配置、检查或启动条件错误；
`1` 为已启动的控制程序异常退出。程序返回 0 也不表示 benchmark 得了满分。

## 隐私与实验边界

不把 API Key 写入入口配置；不读取或复制 Codex/Claude 登录文件。
本入口只在操作者侧运行，不交给被测模型。不要上传本地配置、`.launcher/`、
CLI 日志、私有 GT 或完整试验目录。GitHub 中只提交通用代码、示例配置和说明。

入口没有增加新的文件沙箱或资源限制，也不改变原有 Windows Job 约束。
它没有把 CadQuery 版本的 500K/60轮/2小时预算套到 Codex CLI；实际预算由 `doctor`
报告现有配置。SolidWorks 本地试验和 CadQuery API Agent 仍是不同运行方式。
