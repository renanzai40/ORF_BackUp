# Omni-Re-Formatter (ORF)

ORF 是 Omni 文档本地化生态的最后一环，负责将标准化中间件还原为目标复杂格式。

## 核心功能

- 读取 OL 翻译后的 MD/XLIFF 及 manifest.json/skeleton.zip
- 调用 Pandoc/md2pptx/translate-toolkit 等成熟轮子
- 配合自研胶水代码（manifest 解析、skeleton 回填、资源路径还原）
- 重组生成本地化的复杂格式文档

## 支持格式

- **MD 回写**: DOCX, ODT, EPUB, HTML, RTF, PDF, PPTX
- **XLIFF 回写**: DOCX, PPTX, EPUB, HTML, ODF

## 安装

```bash
pip install omni-re-formatter
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
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `apply-md` | 将 MD 文件转换为目标格式 |
| `apply-xliff` | 应用 XLIFF 翻译到原始文档 |
| `convert-batch` | 批量转换 MD 文件 |
| `info` | 显示文档信息 |

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/

# 代码检查
ruff check src/orf
mypy src/orf
```

## 项目状态

**功能状态**: ✅ 生产可用
- 272 个测试用例通过
- 支持 7 种输出格式（MD 回写）+ 5 种（XLIFF 回写）
- 完整的错误处理和日志系统

**代码质量**: ⚠️ 持续改进中
- ruff 检查通过
- mypy 有部分类型注解缺失（库依赖存根未安装）