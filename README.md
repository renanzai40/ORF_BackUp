# Omni-Re-Formatter (ORF)

ORF 是 Omni 文档本地化生态的最后一环，负责将标准化中间件还原为目标复杂格式。

## 核心功能

- 读取 OL 翻译后的 MD/XLIFF 及 manifest.json/skeleton.zip
- 调用 Pandoc/md2pptx/translate-toolkit 等成熟轮子
- 配合自研胶水代码（manifest 解析、skeleton 回填、资源路径还原）
- 重组生成本地化的复杂格式文档

## 支持格式

- **MD 回写**: DOCX, ODT, EPUB, HTML, RTF, PDF
- **XLIFF 回写**: DOCX (基于 skeleton.zip), ODF

## 安装

```bash
pip install omni-re-formatter
```

## 快速开始

```bash
# MD 转 DOCX
orf apply-md translated.md --target-format docx --output result.docx

# XLIFF 回填（需要 skeleton.zip）
orf apply-xliff original.skeleton.zip --xliff translated.xlf --output result.docx
```

## 依赖关系

- OPP (Omni-Pre-Processor): 提取文档为 MD/XLIFF + manifest.json + skeleton.zip
- OL (Omni-Localizer): 翻译 MD/XLIFF，输出含 YAML frontmatter 的本地化文件
- ORF: 读取本地化文件，还原为目标格式

## 开发

```bash
pip install -e ".[dev]"
pytest tests/
```