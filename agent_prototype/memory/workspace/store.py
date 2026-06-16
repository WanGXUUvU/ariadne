"""SQLite 仓储层 - 物理工作区数据访问对象 (DAO)。
负责 workspaces 表的物理 CRUD，不处理事务边界。
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from agent_prototype.infra.db.orm_models import WorkspaceRecord


class SqliteWorkspaceStore:
    """SQLite 物理工作区仓储类

    这个类是“工作空间数据仓库”。它是专门帮工作空间服务打杂的，只管从数据库的工作空间表里查数据或往里塞数据。比如：查出所有存过的工作区，或者根据文件夹路径找对应记录。它不负责决定事务何时提交（commit），把控制权留给上层服务。
    """

    def __init__(self, db: Session):
        """物理工作区仓储初始化，把操作数据库的“钥匙”拿好。

        需要拿到的东西：
        - db (Session): 数据库会话连接。
        """
        self.db = db

    def list_all(self) -> List[WorkspaceRecord]:
        """从数据库里查出所有的工作空间记录，并且按创建时间的先后顺序，越新创建的排在越前面。

        会给出来的结果：
        - List[WorkspaceRecord]: 排好序的工作空间记录列表。
        """
        return (
            self.db.query(WorkspaceRecord)
            .order_by(WorkspaceRecord.created_at.desc())
            .all()
        )

    def get_by_path(self, path: str) -> Optional[WorkspaceRecord]:
        """根据文件夹在电脑上的绝对物理路径，去数据库里查查有没有对它的注册记录。

        需要拿到的东西：
        - path (str): 文件夹的物理路径。

        会给出来的结果：
        - Optional[WorkspaceRecord]: 查到的工作空间记录，如果没有注册过这个路径，就返回 None。
        """
        return (
            self.db.query(WorkspaceRecord).filter(WorkspaceRecord.path == path).first()
        )

    def save(self, workspace: WorkspaceRecord) -> None:
        """把一个新创建的工作空间记录塞进数据库暂存区（但不立即保存，等待上层服务统一发话进行 commit 提交）。

        需要拿到的东西：
        - workspace (WorkspaceRecord): 要保存的工作区记录对象。
        """
        self.db.add(workspace)
