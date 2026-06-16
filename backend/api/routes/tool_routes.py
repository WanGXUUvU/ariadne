"""工具模块 HTTP 路由适配层。

职责：
- 暴露获取可用工具定义列表的 HTTP GET 接口。

上游：
- 前端工作台工具管理组件

下游：
- DEFAULT_TOOL_REGISTRY (tools/registry)

不负责：
- 不做工具执行逻辑调度或安全中间件拦截。
- 不提供具体内置工具定义。
"""

from fastapi import APIRouter
from backend.tools.registry import DEFAULT_TOOL_REGISTRY

router = APIRouter()


@router.get("/tools")
def list_tools_api():
    """获取全局默认注册表中的所有可用工具名称列表。"""
    return [{"name": name} for name in DEFAULT_TOOL_REGISTRY._tools.keys()]
