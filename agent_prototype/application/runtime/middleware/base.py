"""基于通用地基定义的工具中间件基础。
职责：
- 提供专门针对工具调用的 ToolCallContext 上下文小推车。
"""


from dataclasses import dataclass,field
from typing import Any,Optional

@dataclass
class ToolCallContext:
    """工具调用上下文对象"""

    tool_name:str
    tool_args:str
    tool_call_id:str
    session_id:str
    run_id:Optional[str]=None
    extra:dict[str,Any]=field(default_factory=dict)
    """元数据字典，用于不同拦截器之间传递自定义状态或配置"""
