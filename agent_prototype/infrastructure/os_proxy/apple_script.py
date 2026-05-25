"""macOS AppleScript 物理驱动。
负责在 macOS 系统上调起原生 Finder 文件夹选择对话框，返回绝对路径。
"""

import subprocess
import os
from typing import Optional

def open_folder_dialog()->Optional[str]:
    """调起macOS文件夹选择弹窗，支持60s超时和取消"""

    script = 'POSIX path of (choose folder with prompt "Select a folder for the workspace")'

    try:
        result=subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode==0:
            path=result.stdout.strip()
            return os.path.abspath(path)
        
        return None
    except subprocess.TimeoutExpired:
        return None
    
    except Exception:
        return None