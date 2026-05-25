"""子 Agent 线程池与 Future 注册表。

本模块统一管理进程级的执行资源：
- _executor : 全局线程池，用于异步运行子 Agent 任务。
- _global_futures : run_id → Future 映射，跟踪所有在途子 Agent。

RunService 和 ResumeRunService 均从此处导入，避免各自持有独立的池。
"""

from concurrent.futures import ThreadPoolExecutor

# 进程级线程池，只创建一次。max_workers 控制并发子 Agent 上限。
_executor = ThreadPoolExecutor(
    max_workers=8,
    thread_name_prefix="child_agent",
)

# child_run_id → Future，进程级内存，重启后清空
_global_futures: dict = {}
