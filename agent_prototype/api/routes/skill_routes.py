from fastapi import APIRouter, status  # 导入路由和状态码
from ...core.schemas import SkillSummary  # 导入 skill schema
from ...application.skill_service import disable_skill_service, enable_skill_service  # 导入 skill service
from ...skills.skill_loader import list_skills  # 导入 skill 列表
from .common import error_response  # 导入统一错误响应

router = APIRouter()  # 创建路由器

@router.get("/skills", response_model=list[SkillSummary])  # 定义技能列表
def list_skills_api() -> list[SkillSummary]:  # 无参数
    """输入：无。输出：SkillSummary 列表。"""  # 接口说明
    return list_skills()  # 直接返回 skill 列表

@router.post("/skills/{skill_name}/disable", response_model=SkillSummary)  # 定义禁用接口
def disable_skill_api(skill_name: str) -> SkillSummary:  # 接收 skill 名
    """输入：skill 名称。输出：禁用后的 SkillSummary。"""  # 接口说明
    try:  # 捕获业务错误
        return disable_skill_service(skill_name)  # 调用 service
    except ValueError as exc:  # 捕获错误
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))  # 返回统一错误

@router.post("/skills/{skill_name}/enable", response_model=SkillSummary)  # 定义启用接口
def enable_skill_api(skill_name: str) -> SkillSummary:  # 接收 skill 名
    """输入：skill 名称。输出：启用后的 SkillSummary。"""  # 接口说明
    try:  # 捕获业务错误
        return enable_skill_service(skill_name)  # 调用 service
    except ValueError as exc:  # 捕获错误
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))  # 返回统一错误
