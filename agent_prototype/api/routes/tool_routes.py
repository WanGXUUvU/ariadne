"""接口与适配层 (Interface Layer) - 工具路由控制器

职责：
1. 暴露工具列表查询接口，获取可用工具的完整定义列表。
2. 将后端的工具元数据转换为前端渲染所需的结构。

不负责：
1. 工具的实际执行调度或中间件拦截（由 Application ToolRunner 负责）。
2. 物理工具的底层实现注册。

数据流向：
- 输入：HTTP GET /api/v1/tools 请求。
- 输出：可用的工具定义列表 JSON 响应。
- 上游来源：前端对话窗输入框或组件多选下拉。
- 下游流向：调用 agent_prototype/tools/registry.py 提取可用列表。
"""

from fastapi import APIRouter
from agent_prototype.tools.registry import DEFAULT_TOOL_REGISTRY

router=APIRouter()

@router.get("/tools")
def list_tools_api():
    return [{"name":name} for name in DEFAULT_TOOL_REGISTRY._tools.keys()]