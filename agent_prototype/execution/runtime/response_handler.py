"""应用服务层 (Application Layer) - 大模型响应解析适配

职责：
1. 统一解析大模型的输出响应文本，剔除并提取 thinking 思维链过程。
2. 将大模型生成的内容解析为最终的 RunEvent 并组装最终 turn。

不负责：
1. 大模型 API 的实际发起调用。
2. 流式运行会话（RunSSEBridge）生命周期管理。

数据流向：
- 输入：大模型返回的原始生成文本。
- 输出：过滤思维链后的最终文本回复及 Turn 结果事件。
- 上游来源：agent_prototype/execution/runtime/agent_runner.py。
- 下游流向：提供给 Runtime 引擎进行会话状态追加。
"""

from agent_prototype.core.types import ChatMessage
from agent_prototype.execution.runtime.types import RunEvent


def build_reply(raw_reply: str, event_index: int) -> tuple[str, RunEvent, ChatMessage]:
    """这是一个“回复打包机”。
    当大模型完成全部思考和对话，吐出它最终的回答文本时，这个打包机就会把这段原始回答进行精简修剪，
    并把它们变形成三个不同的零件，方便后面的运行逻辑直接拿去用。

    需要拿到的东西：
    - raw_reply: 大模型吐出来的原始回答文本。
    - event_index: 这轮事件在整个对话中的排队序号（索引）。

    会给出来的结果：
    - 一个包含三个元素的元组，分别是：
      1. 修剪掉首尾空白后的纯回复文本（reply）。
      2. 包装了序号的“最终回答”事件对象（RunEvent），用于发送给前端。
      3. 包装了角色为 assistant 的原始消息对象（ChatMessage），用于存进历史聊天记录。
    """

    reply = (raw_reply or "").strip()
    event = RunEvent(
        index=event_index,
        type="final_answer",
        content=reply,
    )
    assistant_message = ChatMessage(role="assistant", content=raw_reply)
    return reply, event, assistant_message
