"""接口与适配层 (Interface Layer) - FastAPI 路由依赖注入提供者

职责：
1. 提供 FastAPI 专用的 Depends 注入项，统一管理数据库 Session 的生命周期。
2. 提供各个应用层 Service 服务实例的依赖注入创建（如 RunService, SessionService 等）。

不负责：
1. 任何具体的业务逻辑执行或路由控制。
2. 数据库物理连接池的维护。

数据流向：
- 输入：FastAPI 依赖注入机制。
- 输出：数据库 Session 对象及应用服务实例。
- 上游来源：FastAPI 路由网关。
- 下游流向：作为入参被注入到所有的路由控制器中。
"""

from fastapi.responses import JSONResponse  # 返回统一 HTTP 响应
from agent_prototype.api.dto.schemas import ApiError, ErrorResponse  # 导入统一错误 schema

def error_response(status_code:int,code:str,message:str)->JSONResponse:
    """输入：HTTP状态码、错误代码、错误文案。输出：统一错误响应格式"""
    
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=ApiError(
                code=code,
                message=message,
            )
        ).model_dump()
    )
