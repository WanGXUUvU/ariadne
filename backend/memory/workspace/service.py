"""应用服务层 (Application Layer) - 物理工作区服务

职责：
1. 编排会话与物理工作区（本地文件夹）的绑定用例逻辑。
2. 注册和管理本地物理路径，作为安全沙箱路径过滤的全局基准。

不负责：
1. 具体的磁盘文件读写或安全沙箱越界拦截细节。
2. 数据库底层表结构的直接物理操作。

数据流向：
- 输入：绑定路径参数及会话 ID。
- 输出：绑定的工作区业务实体。
- 上游来源：backend/api/routes/workspace_routes.py。
- 下游流向：调用 backend/memory/workspace/store.py 写入数据库。
"""

import os
from typing import Optional
from sqlalchemy.orm import Session
from backend.infra.db.orm_models import WorkspaceRecord
from backend.memory.workspace.store import SqliteWorkspaceStore
from backend.infra.os_proxy.apple_script import open_folder_dialog


class WorkspaceService:
    """工作空间服务类 (OOP)

    这个类是“工作空间管理器”。它主要用来打理你在本地电脑里的开发文件夹（也就是“工作区” Workspace）。比如：列出所有注册过的工作区目录、注册一个新的物理文件夹作为工作区，或者弹出一个苹果系统原生的“文件夹选择框”让你挑个目录注册进来。
    """

    def __init__(self, db: Session):
        """工作空间服务初始化，拿好操作数据库的“钥匙”。

        需要拿到的东西：
        - db (Session): 数据库会话连接。
        """
        self.db = db
        self.store = SqliteWorkspaceStore(db)

    def list_workspace(self):
        """获取所有已经在系统里注册过的工作空间列表。

        会给出来的结果：
        - list[WorkspaceRecord]: 已经在数据库里保存过的所有工作区记录列表。
        """
        return self.store.list_all()

    def register_workspace(self, path: str) -> WorkspaceRecord:
        """把电脑上的一个文件夹路径注册到我们的系统里，做成一个工作空间。
        它会自动把路径转换成绝对路径（比如去掉多余的相对符号），自动截取文件夹的名字作为工作区的名称，然后保存到数据库里。如果这个文件夹之前已经注册过了，就会直接把原先的记录找出来返回。

        需要拿到的东西：
        - path (str): 电脑上文件夹的物理路径（可以是绝对路径，也可以是相对路径）。

        会给出来的结果：
        - WorkspaceRecord: 刚刚注册或早已存在的数据库工作空间记录对象。
        """
        # 物理路径规范化
        abs_path = os.path.abspath(path)
        name = os.path.basename(abs_path)
        existing = self.store.get_by_path(abs_path)
        if existing:
            return existing

        workspace_record = WorkspaceRecord(name=name, path=path)
        self.store.save(workspace_record)

        self.db.commit()
        self.db.refresh(workspace_record)

        return workspace_record

    def select_dialog(self) -> Optional[WorkspaceRecord]:
        """弹出一个苹果系统风格的“选择文件夹”对话框。
        当你在弹窗里选中了某个文件夹并点击“确定”后，这个函数会自动把该文件夹路径注册为工作空间并返回；如果你直接点“取消”没选任何文件夹，它就会识趣地返回 None。

        会给出来的结果：
        - Optional[WorkspaceRecord]: 选中并成功注册的工作空间记录对象，没选则返回 None。
        """
        selected_path = open_folder_dialog()

        if not selected_path:
            return None

        return self.register_workspace(selected_path)
