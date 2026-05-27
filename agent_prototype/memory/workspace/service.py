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
- 上游来源：agent_prototype/api/routes/workspace_routes.py。
- 下游流向：调用 agent_prototype/memory/workspace/store.py 写入数据库。
"""

import os
from typing import List, Optional
from sqlalchemy.orm import Session
from agent_prototype.infra.db.orm_models import WorkspaceRecord
from agent_prototype.memory.workspace.store import SqliteWorkspaceStore
from agent_prototype.tools.builtin.os.apple_script import open_folder_dialog

class WorkspaceService:

    def __init__(self,db:Session):
        self.db=db
        self.store=SqliteWorkspaceStore(db)

    def list_workspace(self):
        return self.store.list_all()
    
    def register_workspace(self,path:str)->WorkspaceRecord:
        #物理路径规范化
        abs_path=os.path.abspath(path)
        name=os.path.basename(abs_path)
        existing = self.store.get_by_path(abs_path)
        if existing:
            return existing
        
        workspace_record=WorkspaceRecord(name=name,path=path)
        self.store.save(workspace_record)

        self.db.commit()
        self.db.refresh(workspace_record)

        return workspace_record
    
    def select_dialog(self)->Optional[WorkspaceRecord]:

        selected_path=open_folder_dialog()

        if not selected_path:
            return None
        
        return self.register_workspace(selected_path)

