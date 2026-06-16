# TASK-049 - Verify 命令运行器

## 目标
把测试、lint、迁移检查等验证命令封装成可追踪的 verify runner。

## 产品层
Verification

## 范围内
- 定义 verify command 配置
- 默认支持 unittest 命令
- 运行命令并记录 stdout、stderr、exit code
- trace 中展示验证结果
- 设置超时

## 范围外
- 任意 shell 全开放
- CI 系统
- 自动修复失败测试

## 实现步骤
1. 新建 `verify_runner.py`。
2. 定义允许执行的 verify 命令列表。
3. 用 subprocess 运行命令并设置 timeout。
4. 将结果写入 run record 或 trace。
5. 增加 `/verify` command。

## 完成标准
- 用户可以一键运行项目默认测试。
- 失败结果能被清楚返回。
- 不允许执行未配置的任意命令。

## 验证
- 测试成功命令、失败命令、未知命令。
- `python3 -m unittest backend.tests.test_agent -v`

## Review 检查点
- 命令白名单是否清楚。
- 超时是否合理。
- 输出是否有长度限制。

