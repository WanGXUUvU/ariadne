# TASK-040 - Debug config 与 health 接口

## 目标
提供最小诊断接口，方便排查模型配置、数据库、技能索引、工具注册是否正常。

## 产品层
Debug / Operations

## 范围内
- 新增 `/health`
- 新增 `/debug/config`
- 检查数据库可用性
- 检查 skill 索引是否可读
- 检查 Tool Registry 注册数量
- 检查 plugin registry 状态
- 隐藏 API Key 等敏感信息

## 范围外
- 完整监控系统
- 鉴权
- 日志聚合

## 实现步骤
1. 新建 health service。
2. 实现数据库 ping。
3. 读取 skill index、plugin registry 和 tool registry 概况。
4. 返回 sanitized config。
5. 写测试确认敏感字段不会出现。

## 完成标准
- `/health` 能用于快速判断服务是否可用。
- `/debug/config` 能帮助开发排错。
- 不泄漏密钥。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 输出是否足够短。
- 是否包含敏感字段。
- 是否依赖外部网络。
