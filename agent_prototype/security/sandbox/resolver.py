"""物理安全沙箱路径解析与逃逸校验核心服务。"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SandboxPathResolver:
    """沙箱路径虚拟投影与防越界逃逸处理器。"""

    @staticmethod
    def resolve_and_rewrite(
        tool_name: str, arguments: str, workspace_path: str
    ) -> tuple[bool, str, Optional[str]]:
        """解析并重写工具入参中的路径字段，确保不越界。

        返回:
            (is_ok, modified_arguments_json_str, error_message)
        """
        try:
            args = json.loads(arguments or "{}")
        except Exception:
            # 如果不是合法 JSON，直接放行，让上层 ToolRegistry 解析报错
            return True, arguments, None

        path_keys = {
            "path",
            "file_path",
            "dir_path",
            "filename",
            "filepath",
            "directory",
        }
        sandbox_root = Path(workspace_path).resolve()
        modified = False

        for k, v in args.items():
            if k in path_keys and isinstance(v, str):
                p_str = v.strip()
                p_path = Path(p_str)

                # 虚拟投影转换
                if p_path.is_absolute():
                    resolved_p = (sandbox_root / p_str.lstrip("/")).resolve()
                else:
                    resolved_p = (sandbox_root / p_str).resolve()

                # 校验防越界逃逸
                is_inside = (sandbox_root in resolved_p.parents) or (
                    resolved_p == sandbox_root
                )
                if not is_inside:
                    logger.error(
                        f"[SandboxPathResolver] 沙箱安全拦截！路径越界逃逸: {v} -> {resolved_p}"
                    )
                    return (
                        False,
                        arguments,
                        f"Sandbox Violation: Path '{v}' resolves outside the workspace '{sandbox_root}'.",
                    )

                args[k] = str(resolved_p)
                modified = True

        if modified:
            return True, json.dumps(args), None
        return True, arguments, None
