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
