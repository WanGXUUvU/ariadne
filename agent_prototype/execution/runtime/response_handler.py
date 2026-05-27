"""应用服务层 (Application Layer) - 大模型响应解析适配

职责：
1. 统一解析大模型的输出响应文本，剔除并提取 thinking 思维链过程。
2. 将大模型生成的内容解析为最终的 AgentEvent 并组装最终 turn。

不负责：
1. 大模型 API 的实际发起调用。
2. 流式运行会话（StreamRunSession）生命周期管理。

数据流向：
- 输入：大模型返回的原始生成文本。
- 输出：过滤思维链后的最终文本回复及 Turn 结果事件。
- 上游来源：agent_prototype/execution/runtime/agent_runtime.py。
- 下游流向：提供给 Runtime 引擎进行会话状态追加。
"""

from agent_prototype.api.dto.schemas import AgentEvent,ChatMessage

def build_final_turn(raw_reply:str,event_index:int)->tuple[str,AgentEvent,ChatMessage]:
    """把最终回复转换成 runtime 可消费的 reply/event/assistant meessage. """

    reply = (raw_reply or "").strip()
    event=AgentEvent(
        index=event_index,
        type="final_answer",
        content=reply,
    )
    assistant_message = ChatMessage(role="assistant",content=raw_reply)
    return reply,event,assistant_message