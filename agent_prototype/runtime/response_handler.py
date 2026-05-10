from ..core.schemas import AgentEvent,ChatMessage

def strip_think(content: str) -> str:
    """去掉模型回复里的 think 包裹，只保留用户可见正文。"""
    if "</think>" not in content:
        return content.strip()
    return content.split("</think>", 1)[1].strip()

def build_final_turn(raw_reply:str,event_index:int)->tuple[str,AgentEvent,ChatMessage]:
    """把最终回复转换成 runtime 可消费的 reply/event/assistant meessage. """

    reply = strip_think(raw_reply or "")
    event=AgentEvent(
        index=event_index,
        type="final_answer",
        content=reply,
    )
    assistant_message = ChatMessage(role="assistant",content=raw_reply)
    return reply,event,assistant_message