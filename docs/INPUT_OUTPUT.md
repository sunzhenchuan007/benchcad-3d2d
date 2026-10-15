# 输入、提交与评测端派生记录

当前 [方案](DESIGN.md)：标准化 STEP 输入，**AI 仅提交 DXF**；受控环境记录 CAD 操作日志与最终快照，评测脚本派生实际剖切 JSON。独立 AI 仍只根据 DXF 重建，脚本比较 IoU。尺寸链与特征树 JSON 不再作为必填输出。生产接口及总分规则待冻结。

## 1. 文件与可见性

```text
case/
├── input/model.step                 出图 AI 的标准化几何
├── geometry/axis_index.json          同一 STEP 推导的中性轴索引
└── private_gt/                      仅评测端可访问
    ├── reference.step
    ├── sections.json                人工要求，不是实际出图记录
    └── expert_reference.dxf          可选，重建校准／视图数量参考

submission/
└── drawing.dxf                      AI 唯一正式制图提交

evaluator/                          Agent 无写权限；重建 AI 无访问权限
├── events.jsonl                     受控 CAD 后端记录
├── actual_sections.json             脚本派生，AI 不填写
└── report.json                      分项结果与失败原因

reconstruction/
└── reconstructed.step               独立 AI 仅根据 DXF 产生
```

出图 AI 可读取 input 和中性工具接口，不能读人工目标、专家图纸或原生 GT 来源。重建 AI 只获得 DXF 与通用工具／单位说明，不能读输入 STEP、参考 STEP、日志、派生 JSON 或 GT。目录名字不产生保密性，必须以权限、挂载和工具可访问范围落实。

六例源文件注册状态保持不变，见 [CASE_SPEC.md](CASE_SPEC.md)。日志消费者已实现不表示案例已具备可评分 GT。

## 2. DXF 要求

图纸应表达原零件的外形、孔、台阶、腔体与必要尺寸，包含必要的专业剖视、剖切线、箭头和标识。不同布局或视图中的等价表达可接受。PDF 保留适配接口，暂不替代 DXF。

DXF handle 只用于本次提交内部定位，不同图纸不共享 handle 身份。几何参考绑定到固定 STEP 哈希及稳定轴／面／边引用。

## 3. 环境日志与派生 JSON

详细规范和 CLI 见 [操作日志派生报告](OPERATION_LOG_DERIVATION.md)。已实现规范化 JSONL 的流式适配器和状态归约接口；真实 CAD 后端适配器仍待实现。

环境需记录成功结果、稳定视图 ID、文档版本、实际平面参数、DXF 引用和最终快照，导出时绑定 DXF 哈希。不能从聊天文本、意图或失败调用猜测实际剖切。删除、撤销、重做应体现在最终状态中。

首版派生格式 `benchcad-derived-drawing/1` 描述实际状态，包含身份、坐标、导出绑定和视图集合，仅支持普通投影与单平面全剖。半剖、阶梯剖等需要扩展并明确切除区域／平面组合，不支持时拒绝处理。证据状态固定为未检查，不自行给分。

还需核验实际 DXF。日志可信性、快照完整性及所有制图入口覆盖是环境责任，不能靠 JSON 自称可信。无最终快照或必要 DXF 引用时输出 `incomplete`；格式不符、身份／哈希不一致或超预算时失败。

## 4. 人工 GT 与匹配

GT 规定关键轴与位置容差：`contains_axis` 要求包含整条轴；`crosses_axis_at_station` 要求横切交点落在规定站位。`angle_rule` 可选择不要求角度。GT 与实际状态做几何约束匹配，不做 JSON 字段相等比较。

公开文档此前描述草稿 v3，本地实验标注代码已到 `benchcad-section-position-draft/5`，含视图分类、required/optional/one_of、必选组及参考方案。本地代码和私有标注不在本 PR 发布范围，也未据此确认线上版本。`optional` 不等于已设计好的推荐奖励；`draft` 不等于验收通过。

原有轴线和位置字段可复用，但仍需正式 schema、迁移、验收、复杂剖视规则与 matcher。详见报告兼容表。每次运行的日志／DXF 哈希写入派生记录，无需塞进每条 GT。

## 5. 验证输出

分别报告 IoU、剖切位置及 DXF 碰撞／冗余。剖切报告定位命中、误差、缺失项及未核验的图纸证据；重建失败、基础设施错误、日志缺失和出图错误应区分。

草稿导出、源文件校验、日志解析成功或几何自检不能替代端到端模型评分。权重、容差、失败处理和总分尚未冻结。
