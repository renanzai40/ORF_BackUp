# Omni-Re-Formatter (ORF)

ORF 是 Omni 文档本地化生态的最后一环，负责将标准化中间件还原为目标复杂格式。

## 核心功能

- 读取 OL 翻译后的 MD/XLIFF 及 manifest.json/skeleton.zip
- 调用 Pandoc/md2pptx/translate-toolkit 等成熟轮子
- 配合自研胶水代码（manifest 解析、skeleton 回填、资源路径还原）
- 重组生成本地化的复杂格式文档

## 支持格式

### MD 回写
- DOCX, ODT, EPUB, HTML, RTF, PDF, PPTX
- ICML (InDesign), SRT (字幕)

### XLIFF 回写
- DOCX, PPTX, EPUB, HTML, ODF

### 云存储
- AWS S3, Azure Blob Storage

### AI 辅助
- 布局溢出检测与修正

### 数据格式
- XLSX, CSV, JSON

### 结构化标记
- XML

### Jupyter 笔记本
- IPYNB

### 邮件格式
- EML, MSG

## 安装

```bash
# 核心功能
pip install omni-re-formatter

# 开发依赖
pip install -e ".[dev]"

# 可选依赖
pip install -e ".[weasyprint]"   # PDF 生成
pip install -e ".[cloud]"       # S3/Azure 支持
pip install -e ".[ai]"          # AI 布局修正
pip install -e ".[office]"      # XLSX 支持
pip install -e ".[notebook]"     # IPYNB 支持
pip install -e ".[email-output]" # MSG 支持
```

## 快速开始

```bash
# MD 转 DOCX
orf apply-md translated.md --target-format docx --output result.docx

# MD 转 EPUB
orf apply-md translated.md --target-format epub --output result.epub

# XLIFF 回填（需要 skeleton.zip）
orf apply-xliff original.docx --xliff translated.xlf --output result.docx

# 批量转换
orf convert-batch ./translated --target-format docx --pattern "*.md"

# 云存储下载资源
# 配置 S3 或 Azure Blob 后，ORF 可直接从云端读取
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `apply-md` | 将 MD 文件转换为目标格式 |
| `apply-xliff` | 应用 XLIFF 翻译到原始文档 |
| `convert-batch` | 批量转换 MD 文件 |
| `info` | 显示文档信息 |

## 项目状态

- 294+ 个测试用例通过
- MD 回写: 9 种格式 (DOCX, ODT, EPUB, HTML, RTF, PDF, PPTX, ICML, SRT)
- XLIFF 回写: 5 种格式 (DOCX, PPTX, EPUB, HTML, ODF)
- 云存储: S3 + Azure Blob 集成
- AI: 布局溢出检测与修正
- 数据格式: XLSX, CSV, JSON
- 结构化标记: XML
- Jupyter 笔记本: IPYNB
- 邮件格式: EML, MSG
- 完整的错误处理和日志系统

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/

# 代码检查
ruff check src/orf
mypy src/orf --ignore-missing-imports

# 构建包
python -m build
```

## 架构

```
src/orf/
├── channels/          # 格式转换通道 (MD→X, XLIFF→X)
├── converters/        # 转换器基类与流式处理
├── parsers/          # manifest.json, frontmatter 解析
├── detection/         # 格式自动探测
├── resources/        # 图片资源管理
├── skeleton/          # skeleton.zip 加载与回填
├── cloud/            # S3, Azure Blob 客户端
├── ai/               # 布局分析与溢出修正
└── logging/          # 日志系统
```

## 相关项目

- [OPP (Omni-Pre-Processor)](https://github.com/1StepMore/Omni_Pre_Processor) - 文档提取为 MD/XLIFF
- [OL (Omni-Localizer)](https://github.com/1StepMore) - 翻译 MD/XLIFF

## 许可证

MIT
