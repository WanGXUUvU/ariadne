from agent_prototype.interface.dto.schemas import AgentEvent,ChatMessage

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