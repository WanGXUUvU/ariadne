import os

from mcp.server.fastmcp import FastMCP
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

mcp = FastMCP("get_local_data")

DATABASEURL_URL = os.getenv("DATABASE_URL", "")

engine = create_engine(
    DATABASEURL_URL,
    echo=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@mcp.tool()
def get_tables() -> list[str]:
    inspector = inspect(engine)
    return inspector.get_table_names()


if __name__ == "__main__":
    mcp.run(transport="stdio")
