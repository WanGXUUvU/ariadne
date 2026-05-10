from fastapi import APIRouter

from .run_routes import router as run_router
from .session_routes import router as session_router
from .skill_routes import router as skill_router
from .trace_routes import router as trace_router

router = APIRouter()

router.include_router(run_router)
router.include_router(session_router)
router.include_router(skill_router)
router.include_router(trace_router)