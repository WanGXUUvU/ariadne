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

router = APIRouter()


@router.get("/tools")
def list_tools_api():
    """这个函数是用来获取系统里目前注册的所有工具名称列表的。

    工具是 Agent 用来完成具体现实任务的武器（比如查询天气、计算器等），前端需要知道有哪些武器可以用。

    需要拿到的东西：
    - 无需传入额外参数。

    会给出来的结果：
    - 包含所有已注册工具名称的字典列表，形如 [{"name": "tool_a"}, {"name": "tool_b"}]。
    """
    return [{"name": name} for name in DEFAULT_TOOL_REGISTRY._tools.keys()]
