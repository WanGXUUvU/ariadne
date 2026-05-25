"""SQLite 仓储层 - 物理工作区数据访问对象 (DAO)。
负责 workspaces 表的物理 CRUD，不处理事务边界。
"""

from typing import List,Optional
from sqlalchemy.orm import Session
from ..models import WorkspaceRecord

class SqliteWorkspaceStore:
    """SQLite武器工作区仓储类"""

    def __init__(self,db=Session):
        self.db=db

    def list_all(self)->List[WorkspaceRecord]:
        return self.db.query(WorkspaceRecord).order_by(WorkspaceRecord.created_at.desc()).all()
    
    def get_by_path(self,path:str)->Optional[WorkspaceRecord]:
        return self.db.query(WorkspaceRecord).filter(WorkspaceRecord.path == path).first()
    
    def save(self, workspace: WorkspaceRecord) -> None:
        """物理写入数据库会话（不执行 db.commit，交由 Service 事务控制）"""
        self.db.add(workspace)