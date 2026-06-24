"""Simple local database MCP server.

This server exposes a minimal read-only interface over the project's local
SQLite database. It is intentionally small so the MCP integration can stay
easy to debug.
"""

import os

from mcp.server.fastmcp import FastMCP
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

mcp = FastMCP("get_local_data")

# The database URL is injected by the MCP host process through stdio env.
DATABASEURL_URL = os.getenv("DATABASE_URL", "")

engine = create_engine(
    DATABASEURL_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@mcp.tool()
def get_tables() -> list[str]:
    """Get all table names from the current database."""

    inspector = inspect(engine)
    return inspector.get_table_names()


@mcp.tool()
def get_table_columns(table_name: str) -> list[str]:
    """Get all column names for a database table.

    Args:
        table_name: Exact table name to inspect.
    """

    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if table_name not in table_names:
        raise ValueError(f"table not found: {table_name}")

    return [column["name"] for column in inspector.get_columns(table_name)]


if __name__ == "__main__":
    mcp.run(transport="stdio")
