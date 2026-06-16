from fastapi import APIRouter

from .agent_routes import router as agent_router
from .approval_routes import router as approval_router
from .compact_routes import router as compact_router
from .run_routes import router as run_router
from .session_routes import router as session_router
from .settings_routes import router as settings_router
from .skill_routes import router as skill_router
from .tool_routes import router as tool_router
from .trace_routes import router as trace_router
from .workspace_routes import router as workspace_router

router = APIRouter()
router.include_router(session_router)
router.include_router(run_router)
router.include_router(trace_router)
router.include_router(agent_router)
router.include_router(approval_router)
router.include_router(compact_router)
router.include_router(settings_router)
router.include_router(skill_router)
router.include_router(tool_router)
router.include_router(workspace_router)
