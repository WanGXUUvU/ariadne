"""接口与适配层 (Interface Layer) - FastAPI 应用程序入口

职责：
1. 初始化 FastAPI 应用程序实例。
2. 配置跨域 CORS 中间件，支持前端跨域请求。
3. 全局路由注册（绑定 /api/v1 下的所有子路由）。
4. 注册全局异常处理器，确保错误被标准 DTO 格式捕获。

不负责：
1. 具体的业务编排逻辑（由 Application 层的服务负责）。
2. 底层数据库物理 CRUD 操作（由 Infrastructure/Persistence 负责）。

数据流向：
- 输入：客户端网络 HTTP / SSE 请求。
- 输出：初始化后的 FastAPI 实例及其标准 JSON/SSE 响应。
- 上游来源：前端浏览器客户端。
- 下游流向：路由解析分发到 backend/api/routes/* 控制器。
"""

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional local dev dependency
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
