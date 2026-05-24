# Changelog

## v0.2.0 (2026-05-24)

### Agent-Oriented 架构重构

ORF v0.2.0 从传统 CLI 工具重构为 **AI Agent 原生集成** 的文档转换引擎。

### ✨ 新功能

- **MCP Server** (`orf-mcp-server`)：基于 FastMCP，对外暴露 5 个类型安全工具
  - `apply_md` — MD 转目标格式
  - `apply_xliff` — XLIFF 翻译回填
  - `batch_convert` — 批量转换
  - `detect_format` — 文档格式自动检测
  - `info` — 文档信息查询
- **Pydantic 类型模型**：所有 MCP 工具输入输出由 Pydantic 模型严格验证，解决 38% schema 不匹配问题
- **PathValidator 路径安全**：全局目录遍历防护，`resolve()` + 白名单策略
- **ForemanAgent 作业编排**：按格式自动路由到 Specialist，支持 SIMPLE/MODERATE/COMPLEX 三级复杂度评估
- **4 个 Format Specialist**：FormatSpecialist、DataSpecialist、MarkupSpecialist、EmailSpecialist
- **HITL 人工审批**：大文件/云存储/人工干预场景需审批通过方可执行
- **审计日志**：每条日志携带 correlation_id + agent_id，支持跨系统全链路追踪
- **CLI --json 模式**：所有 4 个命令支持 `--json` 参数输出结构化 JSON 结果
- **ConversionResult 类型增强**：ErrorDetail 增加 code/message/recovery_strategy 字段
- **端到端管线测试**：OPP→OL→ORF 全链路 E2E 测试套件

### 🔧 变更

- pyproject.toml: `version = "0.2.0"`，新增 `[mcp]` optional dependency
- 新增 `orf-mcp-server` 控制台入口点
- 测试覆盖率扩展至 MCP 集成测试 + E2E 管线测试（400+ 用例）

### 🐛 修复

- 无

### 📦 依赖

- 新增可选依赖：`fastmcp>=0.1.0`

---

## v0.1.0 (2026-04-??)

- 初始发布
- MD 回写：DOCX, ODT, EPUB, HTML, RTF, PDF, PPTX, ICML, SRT
- XLIFF 回写：DOCX, PPTX, EPUB, HTML, ODF
- 云存储集成：AWS S3, Azure Blob Storage
- AI 布局检测与溢出修正
- 数据格式：XLSX, CSV, JSON
- 结构化标记：XML
- Jupyter 笔记本：IPYNB
- 邮件格式：EML, MSG
