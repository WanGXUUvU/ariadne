# TASK-030 - 消息 Markdown / 代码块渲染

## 目标
让聊天界面正确渲染 assistant 回复中的 Markdown 格式：标题、列表、粗体、代码块带语法高亮。

## 产品线
聊天助理

## 范围内
- 引入 Markdown 渲染库（如 marked + highlight.js 或 react-markdown）
- assistant 消息使用 Markdown 渲染，user 消息保持纯文本
- 代码块显示语言标签和复制按钮
- 内联代码、粗体、斜体正常显示
- XSS 安全：渲染前过滤危险 HTML

## 范围外
- LaTeX 数学公式
- 图片上传预览
- 自定义主题编辑器

## 实现步骤
1. 安装 Markdown 渲染库。
2. 封装 `<MarkdownMessage>` 组件。
3. 替换消息列表中 assistant 消息的渲染方式。
4. 为代码块加复制按钮。
5. 确认 XSS 过滤（使用库的 sanitize 选项）。
6. 手动测试包含代码块的回复。

## 完成标准
- 代码块有语法高亮和复制按钮。
- 普通 Markdown 格式正确显示。
- 不出现 `<script>` 等危险内容被渲染的情况。

## 验证
- 手动让 assistant 返回包含 Python 代码块的回复，确认渲染正确。
- 前端构建命令通过。

## Review 检查点
- 是否启用了 Markdown 库的 sanitize 选项。
- 是否只对 assistant 消息渲染 Markdown，不对用户输入渲染。
- 复制按钮是否在 HTTPS 和 HTTP 本地开发都能用。
