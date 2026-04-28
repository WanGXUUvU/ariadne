from .schemas import AgentInput, AgentState, AgentOutput, ChatMessage, ToolCall,AgentEvent
from .llm_client import call_llm
from .tool_registry import ToolRegistry,DEFAULT_TOOL_REGISTRY
from typing import Optional
from .agent_definition import AgentDefinition,DEFAULT_AGENT_DEFINITION

def strip_think(content:str)->str:
    if "</think>" not in content:
        return content.strip()
    return content.split("</think>",1)[1].strip()



class Agent:
    def __init__(self,state:Optional[AgentState]=None,definition:Optional[AgentDefinition]=None,tool_registry:Optional[ToolRegistry]=None):
        self.state = state or AgentState()
        self.definition=definition or DEFAULT_AGENT_DEFINITION
        self.tool_registry=tool_registry or DEFAULT_TOOL_REGISTRY
    def run(self, agent_input: AgentInput) -> AgentOutput:

        events= []
        event_index = 0
        self.state.messages.append(ChatMessage(role="user", content=agent_input.user_input))
        self.state.step += 1

        # 发送给模型的完整上下文：system + 历史消息 + 当前用户输入。
        messages = [ChatMessage(role="system", content=self.definition.system_prompt)] + self.state.messages

        while True:
            # 第一次请求模型时，它可能返回 tool_calls，而不是最终回复。
            assistant_msg = call_llm([m.model_dump(exclude_none=True) for m in messages],self.tool_registry.get_tool_schemas())

            if assistant_msg.get("tool_calls"):
                # 先把“模型要求调用工具”这条 assistant 消息记下来。
                assistant_message = ChatMessage(
                    role="assistant",
                    content=assistant_msg.get("content"),
                    tool_calls=[ToolCall.model_validate(tc) for tc in assistant_msg["tool_calls"]],
                )
                messages.append(assistant_message)
                self.state.messages.append(assistant_message)
                

                for tool_call in assistant_message.tool_calls or []:
                    events.append(
                        AgentEvent(
                            index=event_index,
                            type="assistant_tool_call",
                            tool_name=tool_call.function.name,
                            tool_call_id=tool_call.id,
                            content=tool_call.function.arguments,
                        )
                    )
                    event_index += 1
                    tool_result = self.tool_registry.execute_tool_call(
                        tool_call.function.name,
                        tool_call.function.arguments,
                    )
                    # 把工具执行结果作为 tool 消息回填给模型。
                    # tool_call_id 必须和这次 tool_calls 的 id 对上。
                    tool_message = ChatMessage(
                        role="tool",
                        tool_call_id=tool_call.id,
                        content=tool_result,
                    )
                    messages.append(tool_message)
                    
                    self.state.messages.append(tool_message)

                    events.append(
                        AgentEvent(
                            index=event_index,
                            type="tool_result",
                            tool_name=tool_call.function.name,
                            tool_call_id=tool_call.id,
                            content=tool_result,
                        )
                    )
                    event_index += 1
                continue

            # 如果没有 tool_calls，说明模型已经给出了最终回复。
            raw_reply = assistant_msg.get("content", "")
            reply=strip_think(raw_reply)

            events.append(
                AgentEvent(
                    index=event_index,
                    type="final_answer",
                    content=reply
                )
            )
            assistant_message = ChatMessage(role="assistant", content=raw_reply)
            messages.append(assistant_message)
            self.state.messages.append(assistant_message)
            return AgentOutput(reply=reply, state=self.state,events=events)
