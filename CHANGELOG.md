# Changelog

## v0.3.3 (2026-05-28)

### 🛠️ 修复

- **Bug #4: XPath namespace 未注册**: `_backfill_translation` 等方法中调用 `root.xpath("//w:t")` 前现注册 word 命名空间
  - 添加 `WORD_NS_MAP = {"w": W_NS}` 常量
  - 所有 `root.xpath("//w:t")` 和 `root.xpath("//w:p")` 调用现传入 `namespaces=WORD_NS_MAP`
  - 修复 "Undefined namespace prefix 'w'" 异常导致翻译静默失败的问题

- **Bug #5: xml_declaration 与 unicode encoding 不兼容**: `etree.tostring(encoding="unicode", xml_declaration=True)` 导致 ValueError
  - `encoding="unicode"` 返回 Python str，不兼容 XML 声明
  - 改为 `xml_declaration=False`
  - 修复所有 trans-unit 翻译未写入输出的静默失败问题

- **Bug #6: `inject_images` 覆盖翻译结果**: `convert` 和 `apply-xliff` 命令中图片注入后翻译被原始骨架覆盖
  - `inject_images(skeleton_path, images, output_path)` 将 `skeleton_path` 内容重新打包，忽略已翻译内容
  - 修复：先将已翻译输出复制到临时文件，以临时文件为骨架注入图片，再写入最终输出
  - 影响：`convert --images-json` 和 `apply-xliff --images-json` 两个命令

## v0.3.2 (2026-05-28)

### 🛠️ 修复

- **MD 管道图片注入限制**：文档说明 `--images-json` 参数对 MD 管道无效
  - `md2docx.inject_images()` 返回 `([], images)` 空操作
  - MD 管道使用 pre-processing 方案（base64 → temp files → pandoc）
  - 如需精确图片注入，需使用 XLIFF 管道

- **MD 管道结构丢失**：文档说明 Markdown 格式限制
  - MD 是行级格式，不保留 DOCX 段落边界
  - Pandoc 将 `![Image](url)` 当作行内元素处理
  - 原始 DOCX 的 15 个独立图片段落会在 MD→DOCX 后丢失
  - 需要精确结构保留时请使用 XLIFF 管道

### ✨ 新功能

- **MCP `xliff_content` 参数**：新增 `xliff_content: Optional[str]` 参数
  - `apply_xliff` 工具现在接受内联 XLIFF 内容字符串
  - 新增 `--xliff-content` CLI 选项
  - 与 `--xliff` 互斥，同时提供返回错误

### 🔧 通道注入实现

| 通道 | 方法 | 注入方式 |
|------|------|---------|
| `xliff2docx` | `inject_images()` | 按 `paragraph_index` 插入 `<w:drawing>` 到段落 |
| `xliff2pptx` | `inject_images()` | 按 `slide_index` 插入 `<p:pic>` 到幻灯片 |
| `xliff2html` | `inject_images()` | 按 `element_index` 插入 `<img>` 到 DOM |
| `xliff2epub` | `inject_images()` | 按 `spine_index` 插入到章节 XHTML |

## v0.3.0 (2026-05-27)

### ✨ 新功能

- **图片精确定位注入**：ORF 现在支持在 XLIFF 回填时精确注入图片到目标文档
  - OPP 提取图片时附带 `paragraph_index` / `slide_index` / `element_index` / `spine_index` 等位置元数据
  - ORF 通过新增 `--images-json` 参数接收图片注入指令
  - 支持 DOCX、PPTX、HTML、EPUB 四种格式的图片注入

### 🆕 新增 API

- **MCP `apply_xliff` 扩展**：新增 `images` 参数，接收 OPP 传来的图片 placement 数据
- **CLI `--images-json` 参数**：`apply-xliff` 命令新增图片注入支持
- **源格式自动检测**：`detect_from_skeleton()` 从 skeleton.zip 内部结构自动识别源格式

### 📦 新增数据结构

- **`ImagePlacement`** (mcp/schemas.py)：图片注入指令数据结构
  ```python
  {
      data_base64: str,           # base64 编码的图片数据
      mime_type: str,             # image/png, image/jpeg, etc.
      width: Optional[int],
      height: Optional[int],
      # 位置字段 (格式互斥)
      paragraph_index: Optional[int],  # DOCX
      slide_index: Optional[int],      # PPTX
      page_number: Optional[int],       # PDF
      element_index: Optional[int],    # HTML
      spine_index: Optional[int],       # EPUB
  }
  ```

### 🔧 通道注入实现

| 通道 | 方法 | 注入方式 |
|------|------|---------|
| `xliff2docx` | `inject_images()` | 按 `paragraph_index` 插入 `<w:drawing>` 到段落 |
| `xliff2pptx` | `inject_images()` | 按 `slide_index` 插入 `<p:pic>` 到幻灯片 |
| `xliff2html` | `inject_images()` | 按 `element_index` 插入 `<img>` 到 DOM |
| `xliff2epub` | `inject_images()` | 按 `spine_index` 插入到章节 XHTML |

### 🛠️ 修复

- **xliff2docx.py:28-38**: XLIFF namespace 兼容性
  - 新增 `XLIFF_NS_1_1` / `XLIFF_NS_2_0` 常量，支持 OPP 输出的 XLIFF 1.1 namespace
  - 自动检测 root 元素 namespace，先尝试 1.2 → 1.1 → 2.0 降级策略
  - 解决 OPP XLIFF 1.1 与 ORF 硬编码 1.2 导致的解析失败问题
- **cli.py:75**: `apply-md` 命令新增 `--images-json` 参数
  - 支持接收 OPP 图片 placement JSON 文件
  - 加载后调用 converter 的 `inject_images()` 方法注入图片
- **cli.py:267-285**: JSON 输出 metadata 序列化修复
  - 新增 `_safe_json_dumps()` / `_sanitize_for_json()` 过滤不可序列化对象
  - 修复 `result.metadata` 含复杂对象时 `json.dumps` 崩溃问题
- **16 MD converters**: 新增 `inject_images()` stub methods
  - 所有 Pandoc-based MD 转换器（md2docx/md2odt/md2pdf/md2rtf/md2html/md2csv/md2json/md2xlsx/md2xml/md2ipynb/md2eml/md2msg/md2icml/md2srt/md2epub）
  - MD 链路图片由 Pandoc 自动处理（base64 内嵌在 MD 中）
  - stub 返回 `(empty, all_images)` 并记录 WARNING 日志说明不支持段落索引注入
- **md2docx.py:44-114**: MD 图片预处理器（替换 `--embed-media`）
  - 新增 `_find_base64_images()` / `_preprocess_md_images()` 方法
  - 在 Pandoc 调用前将 MD 中的 base64 data URI 图片提取到临时文件
  - 将 MD 中的 `![alt](data:image/...;base64,...)` 改写为 `![alt](temp/images/image_HASH.ext)`
  - 修复 OPP generate_markdown 嵌入 base64 data URI 时 Pandoc 丢失 32% 图片的问题
  - 不依赖 `--embed-media` flag（适用于 pandoc 3.1.x）
- **xliff2docx.py:377-490**: 回填逻辑重构（内联标签支持）
  - `_backfill_translation` 重写：strip inline tag 后匹配 normalized text
  - 新增 `_backfill_with_inline_elements()` / `_backfill_split_runs()` 处理跨多 run 文本
  - 修复 OPP XLIFF 含 `<bx>/<ex>` 内联标签时回填 100% 失败的问题
  - **修复 XPath 无效表达式**：所有 `//{{{W_NS}}}t` 改为 `//w:t`（XPath 1.0 不支持 `{uri}element` 语法）
- **xliff2docx.py:343-356**: `_backfill_translation` 返回修改后的 document_xml
  - 从 `bool` 改为 `str`，每次调用返回最新的 document_xml
  - 解决 `document_xml` 传值而非传引用导致修改无法回写的问题

### 🐛 Orphaned 图片处理

- 无位置信息的图片统一采用 **WARNING 日志 + 末尾追加**策略
- 不再静默丢弃图片

---

## v0.2.2 (2026-05-26)

### 🐛 修复

- **mcp/server.py:20-73**: MCP `apply_md` 工具 JSON-RPC 响应为空
  - 添加空 stdout 检查和 JSON 解析异常处理
  - 修复 `_run_cli_command` 在 CLI 返回空输出时抛出 `JSONDecodeError` 的问题
- **converters/base.py:44-61**: `ConversionResult.errors` 类型不匹配
  - `__post_init__` 自动将字符串错误归一化为 `ErrorDetail` 对象
  - 覆盖全部 22 个文件、77 处字符串错误传参
- **parsers/manifest.py:99-106**: OPP manifest 字段兼容性
  - 添加 `file_path`/`path`、`original_filename`/`name`、`format`/`type` 字段映射
  - 兼容 OPP 不同版本输出的字段名差异
- **cli.py:224**: `click.progressbar` 在 JSON 模式下污染 stdout
  - `--json` 模式下 progressbar 输出到 stderr，保持 stdout 纯净供 JSON 使用

---

## v0.2.1 (2026-05-25)

### 🐛 修复

- **cli.py:219**: 修复转换失败时 crash（AttributeError on string errors）
  - 4 处错误处理代码现在能同时处理 `ErrorDetail` 对象和纯字符串
  - 影响范围：`apply-md` / `apply-xliff` 成功/失败路径的 JSON 输出 + 文本错误输出
- **frontmatter.py:80**: `original_file` 改为 Optional（某些 pipeline 场景不需原始文件名）
- **manifest.py**: `Manifest.version` → `Manifest.manifest_version` 与 OPP JSON key 保持一致

---

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
