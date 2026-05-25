from fastapi import APIRouter
from agent_prototype.infrastructure.tools.tool_registry import DEFAULT_TOOL_REGISTRY

router=APIRouter()

@router.get("/tools")
def list_tools_api():
    return [{"name":name} for name in DEFAULT_TOOL_REGISTRY._tools.keys()]