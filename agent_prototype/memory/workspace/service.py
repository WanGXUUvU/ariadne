
import os
from typing import List, Optional
from sqlalchemy.orm import Session
from agent_prototype.infra.db.orm_models import WorkspaceRecord
from agent_prototype.memory.workspace.store import SqliteWorkspaceStore
from agent_prototype.tools.builtin.util.apple_script import open_folder_dialog

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

