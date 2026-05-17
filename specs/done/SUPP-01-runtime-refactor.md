# 补充卡 01 - Runtime 职责拆分

> 类型：补充卡（临时插入，非主线任务卡）

## 目标
把 `agent_runtime.py` 从“单文件大执行器”拆成更小的 runtime helpers，让 runtime 只保留一层编排，不再同时承担消息组装、tool loop、事件生成和回复收尾。

## 产品层
Backend Architecture

## 我对当前项目的理解
现在项目的上层边界已经相对清楚了：
- `application/` 负责一次业务请求的编排
- `model/` 负责模型请求/响应边界
- `runtime/` 负责 Agent 执行循环
- `context/` 负责 prompt、历史和 compact
- `tools/` 负责工具注册与执行

但 `runtime/agent_runtime.py` 仍然偏胖：
- system / user / assistant 消息组装在这里
- `ModelRequest` 构造在这里
- tool call 执行循环在这里
- tool result / tool error / final answer 事件生成在这里
- assistant message 的回写和 state mutation 也在这里

这会让后续任何新增的 runtime 能力都继续往同一个文件堆。

## 当前问题
- 文件职责过多，阅读成本高。
- tool loop 和事件生成强耦合。
- 消息准备和 response handling 强耦合。
- 未来如果加 streaming、interrupt、debug、retry policy，这个文件还会继续膨胀。
- 现在虽然能跑，但不适合继续加 runtime 相关能力。

## 本次优化原则
1. 只做职责拆分，不新增能力。
2. 保持 `/run` 行为不变。
3. 先拆 helpers，再考虑更深的结构调整。
4. 不把 application 的职责倒回 runtime。
5. 允许短期保留兼容 facade。

## 优化分层

### P0 - 先把 runtime 拆成 facade + helpers
目标：让 `agent_runtime.py` 只保留 Agent 外壳和主流程编排。

建议拆分为：
- `runtime/agent_runtime.py`
  - 保留 `Agent` facade 和 `run()` 主入口
- `runtime/message_builder.py`
  - 负责 system / history / current user message 的组合
- `runtime/tool_executor.py`
  - 负责单个 tool call 的执行和结果转换
- `runtime/response_handler.py`
  - 负责把 `ModelResponse` 转成 runtime 可消费的 assistant message / tool calls / final reply
- `runtime/event_builder.py`
  - 如果后续事件生成继续增长，再把 `AgentEvent` 组装拆出去

### P1 - 再压缩循环中的分支逻辑
目标：把 `tool call -> tool result -> 再次请求模型` 的循环逻辑变得更线性。

建议动作：
- 把单轮 tool turn 的处理提炼成独立函数
- 把“允许工具校验”和“工具执行”分开
- 把“状态更新”集中到一个出口

### P2 - 如果后续继续增长，再补 runtime 子层
目标：预留 streaming、interrupt、debug 的扩展位。

建议动作：
- 如果 streaming 落地，再单独抽 `streaming.py`
- 如果停止/取消运行落地，再单独抽 `execution_control.py`
- 如果事件格式进一步复杂，再单独抽 `trace_mapper.py`

## 建议关注的文件
| 当前文件 | 优化方向 | 是否优先动 |
|---|---|---|
| `agent_prototype/runtime/agent_runtime.py` | 拆成 facade + helpers | 是 |
| `agent_prototype/runtime/message_builder.py` | 新增 helper | 是 |
| `agent_prototype/runtime/tool_executor.py` | 新增 helper | 是 |
| `agent_prototype/runtime/response_handler.py` | 新增 helper | 是 |
| `agent_prototype/runtime/event_builder.py` | 视增长再拆 | 否 |

## 范围内
- 拆 runtime 中最明显的多职责代码
- 保持现有 `/run` 行为和测试语义不变
- 保留短期兼容入口
- 修复拆分过程中暴露的 import / 依赖问题

## 范围外
- 不新增 streaming
- 不新增 stop / cancel
- 不改模型协议
- 不改 application 业务边界
- 不改前端

## 实施顺序
1. 先把 `agent_runtime.py` 中最明显的职责切到 helper。
2. 再把 tool loop 中可复用的逻辑提炼出来。
3. 再把 response 解析和事件组装分离。
4. 最后回归测试，确认行为不变。

## 完成标准
- `agent_runtime.py` 不再是明显的大包。
- runtime 中每个 helper 都能用一句话说清职责。
- `/run` 行为不变。
- 现有测试通过。
- 后续新增 runtime 能力不会直接回流到单个大文件里。

## 验证
- `python3 -m unittest discover -s agent_prototype/tests -p 'test_*.py' -v`

## Review 检查点
- 是否真的把 runtime 拆薄了。
- 是否没有把 application 职责塞回 runtime。
- 是否保留了对外 Agent 接口的稳定性。
- 是否为 streaming / debug / interrupt 留出了扩展位。
