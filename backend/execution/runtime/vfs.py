"""运行期内存 VFS 暂存器与 run 级注册表。"""

import os
import shutil
import threading
from typing import Optional


class StagingFileSystem:
    """事务性内存文件暂存器（线程安全）。"""

    def __init__(self) -> None:
        self.staged_writes: dict[str, str] = {}
        self.staged_deletes: set[str] = set()
        self.lock = threading.Lock()

    def write_text(self, abs_path: str, content: str) -> None:
        with self.lock:
            self.staged_deletes.discard(abs_path)
            self.staged_writes[abs_path] = content

    def delete_file(self, abs_path: str) -> None:
        with self.lock:
            self.staged_writes.pop(abs_path, None)
            self.staged_deletes.add(abs_path)

    def read_text(self, abs_path: str) -> str:
        with self.lock:
            if abs_path in self.staged_deletes:
                raise FileNotFoundError(f"[VFS] File marked as deleted: {abs_path}")
            if abs_path in self.staged_writes:
                return self.staged_writes[abs_path]

        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"[Physical] File not found: {abs_path}")

        with open(abs_path, "r", encoding="utf-8") as f:
            return f.read()

    def exists(self, abs_path: str) -> bool:
        with self.lock:
            if abs_path in self.staged_deletes:
                return False
            if abs_path in self.staged_writes:
                return True
        return os.path.exists(abs_path)

    def commit_all(self) -> None:
        with self.lock:
            for abs_path in self.staged_deletes:
                if os.path.exists(abs_path):
                    if os.path.isdir(abs_path):
                        shutil.rmtree(abs_path)
                    else:
                        os.remove(abs_path)

            for abs_path, content in self.staged_writes.items():
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(content)

            self.staged_writes.clear()
            self.staged_deletes.clear()

    def clear(self) -> None:
        with self.lock:
            self.staged_writes.clear()
            self.staged_deletes.clear()


class RunVfsRegistry:
    """按 run_id 持有 VFS，跨 pause/resume 保活。"""

    _lock = threading.Lock()
    _vfss: dict[str, StagingFileSystem] = {}

    @classmethod
    def create(cls, run_id: str) -> StagingFileSystem:
        with cls._lock:
            vfs = StagingFileSystem()
            cls._vfss[run_id] = vfs
            return vfs

    @classmethod
    def get(cls, run_id: str) -> Optional[StagingFileSystem]:
        with cls._lock:
            return cls._vfss.get(run_id)

    @classmethod
    def take(cls, run_id: str) -> Optional[StagingFileSystem]:
        with cls._lock:
            return cls._vfss.pop(run_id, None)

    @classmethod
    def discard(cls, run_id: str) -> None:
        vfs = cls.take(run_id)
        if vfs is not None:
            vfs.clear()
