from fastapi import APIRouter

from agent_prototype.interface.api.routes.run_routes import router as run_router
from agent_prototype.interface.api.routes.session_routes import router as session_router
from agent_prototype.interface.api.routes.skill_routes import router as skill_router
from agent_prototype.interface.api.routes.trace_routes import router as trace_router
from agent_prototype.interface.api.routes.agent_routes import router as agent_router
from agent_prototype.interface.api.routes.tool_routes import router as tool_router
from agent_prototype.interface.api.routes.approval_routes import router as approval_router
from agent_prototype.interface.api.routes.settings_routes import router as settings_router
from agent_prototype.interface.api.routes.compact_routes import router as compact_router
router = APIRouter()
from agent_prototype.interface.api.routes.workspace_routes import router as workspace_router

router.include_router(run_router)
router.include_router(session_router)
router.include_router(skill_router)
router.include_router(trace_router)
router.include_router(agent_router)
router.include_router(tool_router)
router.include_router(approval_router)
router.include_router(settings_router)
router.include_router(compact_router)
router.include_router(workspace_router)
