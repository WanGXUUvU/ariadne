from fastapi import FastAPI
from routes import router
from db import engine,Base
#先让Todos注册到Base上
import models
app = FastAPI()
app.include_router(router)
#旧版数据库连接
#init_db()

#把 Python 里定义好的表模型，同步创建到数据库里，但只负责创建，不负责迁移
Base.metadata.create_all(bind=engine)
