# TASK-060 - Plugin Marketplace 与本地安装

## 目标
补齐 Codex 官方插件分发链路的最小版本，支持 repo / local marketplace 和本地插件安装。

## 产品层
Plugin Platform

## 依赖
- `TASK-057` Plugin 包结构对齐

## 范围内
- 支持读取 `.agents/plugins/marketplace.json`
- 支持 repo 范围和个人范围的 local marketplace
- 解析 marketplace 中的 plugin entry、source、policy、category
- 支持本地路径安装和启用/禁用状态
- 提供最小 plugin index / install metadata

## 范围外
- 远程 Git marketplace
- 官方插件目录
- 自动升级
- 安全签名

## 实现步骤
1. 定义 marketplace schema。
2. 读取 repo / personal marketplace 文件。
3. 解析 local plugin source 并校验相对路径规则。
4. 记录插件安装状态和启用状态。
5. 写测试覆盖坏 marketplace、坏 source.path、缺插件目录和启停切换。

## 完成标准
- 本地 marketplace 可用。
- 插件安装源和安装状态可以被读取。
- 不需要先连远程仓库也能验证插件分发链路。

## 验证
- `python3 -m unittest backend.tests.test_agent -v`

## Review 检查点
- marketplace 是否只做本地最小闭环。
- source.path 是否被安全约束。
- 安装和启用是否分成两个状态。
