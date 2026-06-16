"""VFS 暂存器单元测试。

覆盖场景：
1. 暂存写入后能正确读回，物理磁盘 0 污染
2. 物理文件未暂存时降级读取物理磁盘
3. 暂存删除后文件逻辑不可见，物理文件依然存在
4. commit_all() 将暂存写入和删除真正落盘
5. clear() 清空暂存，物理磁盘 0 污染
6. 并发安全：多线程同时写入不崩溃
"""

import os
import shutil
import tempfile
import threading
import unittest

from backend.execution.runtime.vfs import StagingFileSystem


class TestStagingFileSystem(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.vfs = StagingFileSystem()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_staged_write_does_not_touch_disk(self):
        """写入 VFS 后，物理磁盘上不应该有任何文件。"""
        path = os.path.join(self.test_dir, "a.py")
        self.vfs.write_text(path, "print('hello')")

        self.assertEqual(self.vfs.read_text(path), "print('hello')")
        self.assertTrue(self.vfs.exists(path))
        # 🟢 物理磁盘 0 痕迹
        self.assertFalse(os.path.exists(path))

    def test_read_fallback_to_physical_disk(self):
        """VFS 未暂存时，read_text 应降级读取物理磁盘。"""
        path = os.path.join(self.test_dir, "b.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write("physical content")

        self.assertEqual(self.vfs.read_text(path), "physical content")
        self.assertTrue(self.vfs.exists(path))

    def test_staged_delete_hides_file(self):
        """暂存删除后，文件在 VFS 视角不可见，物理文件依然存在。"""
        path = os.path.join(self.test_dir, "c.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write("old content")

        self.vfs.delete_file(path)

        self.assertFalse(self.vfs.exists(path))
        with self.assertRaises(FileNotFoundError):
            self.vfs.read_text(path)
        # 🟢 物理文件依然存在（还没真正删除）
        self.assertTrue(os.path.exists(path))

    def test_commit_all_writes_and_deletes_on_disk(self):
        """commit_all 后，写入和删除都应真正落盘。"""
        write_path = os.path.join(self.test_dir, "new.py")
        delete_path = os.path.join(self.test_dir, "old.py")

        with open(delete_path, "w", encoding="utf-8") as f:
            f.write("to be deleted")

        self.vfs.write_text(write_path, "new content")
        self.vfs.delete_file(delete_path)
        self.vfs.commit_all()

        # 🟢 新文件落盘
        self.assertTrue(os.path.exists(write_path))
        with open(write_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "new content")

        # 🟢 旧文件已删除
        self.assertFalse(os.path.exists(delete_path))

        # 🟢 暂存区已清空（文件已落盘，不再在暂存字典中）
        self.assertEqual(len(self.vfs.staged_writes), 0)
        self.assertEqual(len(self.vfs.staged_deletes), 0)

    def test_clear_discards_all_staged_changes(self):
        """clear() 后，所有暂存丢弃，物理磁盘 0 污染。"""
        path = os.path.join(self.test_dir, "rollback.py")
        self.vfs.write_text(path, "dont write me")
        self.vfs.clear()

        self.assertFalse(self.vfs.exists(path))
        # 🟢 物理磁盘 0 痕迹
        self.assertFalse(os.path.exists(path))

    def test_concurrent_writes_are_thread_safe(self):
        """多线程同时写入 VFS，不应崩溃或数据丢失。"""
        errors = []

        def write_files(index: int):
            try:
                path = os.path.join(self.test_dir, f"thread_{index}.py")
                self.vfs.write_text(path, f"content {index}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_files, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 🟢 没有任何崩溃
        self.assertEqual(errors, [])
        # 🟢 20 个文件全部正确暂存
        self.assertEqual(len(self.vfs.staged_writes), 20)


if __name__ == "__main__":
    unittest.main()
