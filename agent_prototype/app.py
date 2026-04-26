from fastapi import FastAPI
from contextlib import asynccontextmanager

from .routes import router
from .db import Base,engine
from .models import SessionRecord

@asynccontextmanager
async def lifespan(app:FastAPI):
    Base.metadata.create_all(bind=engine)
    yield#在之前的事startup 之后的shutdown

app=FastAPI(lifespan=lifespan)
app.include_router(router)


