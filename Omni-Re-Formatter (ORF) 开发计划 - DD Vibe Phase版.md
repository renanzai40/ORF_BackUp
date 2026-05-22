# Omni-Re-Formatter (ORF) 开发计划 - DD Vibe Phase版

## 文档信息

- **版本**: v1.1-Phase
- **执行方式**: 按 Phase 逐个喂给 vibe 智能体执行
- **核心功能**: 读取 OL 翻译后的 MD / XLIFF，调用对应轮子生成目标格式，做少量胶水代码（路径映射、资源管理、日志系统、错误处理）
- **生效日期**: 2026年5月

## 🔗 前置依赖：OPP & OL 改进状态

> 以下改进已完成并推送至 GitHub。ORF 开发应基于这些新特性设计。

### OPP v0.2.0 已完成改进

| 改进项 | 状态 | 输出文件 | 说明 |
|--------|------|----------|------|
| manifest.json 生成 | ✅ 已完成 | `{base_name}_manifest.json` | 记录源文件、格式、MD5、输出路径、图片信息 |
| Skeleton 保存 | ✅ 已完成 | `{base_name}.skeleton.zip` | 原始 DOCX/PPTX 的完整 OOXML ZIP 结构 |

**manifest.json 结构**:
```json
{
  "manifest_version": "1.0",
  "generated_at": "2026-05-22T14:30:00Z",
  "tool": "OPP",
  "tool_version": "0.2.0",
  "source": {
    "file_path": "/path/to/spec.docx",
    "original_filename": "spec.docx",
    "format": "DOCX",
    "file_size_bytes": 45824,
    "file_hash_md5": "a1b2c3d4..."
  },
  "extraction": {
    "source_lang": "en",
    "target_lang": "zh",
    "outputs": {
      "markdown": { "path": "spec.md", "paragraph_count": 150, "table_count": 3 },
      "xliff": { "path": "spec.xlf", "trans_unit_count": 42 }
    },
    "images": [...]
  },
  "skeleton": {
    "path": "spec.skeleton.zip",
    "format": "ZIP",
    "key_files": ["word/document.xml", "word/styles.xml", ...]
  },
  "resources": { "storage_dir": "resources", "image_count": 5 }
}
```

**skeleton.zip 内容**（用于 XLIFF→DOCX 回填）:
```
spec.skeleton.zip
├── [Content_Types].xml
├── _rels/.rels
├── docProps/app.xml
├── docProps/core.xml
├── word/document.xml      ← 翻译内容回填目标
├── word/styles.xml
├── word/numbering.xml
├── word/settings.xml
└── ...
```

### OL 已完成改进

| 改进项 | 状态 | 输出格式 | 说明 |
|--------|------|----------|------|
| YAML frontmatter | ✅ 已完成 | MD 文件开头 | 记录 source_lang, target_lang, original_file, processor, version, translated_at |

**OL 输出 MD 结构**:
```yaml
---
source_lang: en
target_lang: zh
original_file: spec.md
processor: "OL"
version: "0.1.0"
translated_at: 2026-05-22T15:00:00Z
...

# 用户手册

这是翻译后的内容。
```

---

## 🌟 项目背景与关系

### 全局生态位

ORF 是 Omni 文档本地化生态的最后一环，负责将标准化中间件还原为目标复杂格式，形成闭环。

- **OPP (Omni-Pre-Processor) v0.2.0+**: 拆解者。将复杂格式（DOCX/PPTX/PDF）拆解为标准化中间件：MD文件 + XLIFF文件 + 资源目录(Images) + **manifest.json** + **skeleton.zip**。

- **OL (Omni-Localizer)**: 翻译者。读取 OPP 的输出，对 MD/XLIFF 进行本地化翻译，输出：本地化MD（**含 YAML frontmatter**） + 本地化XLIFF。

- **ORF (Omni-Re-Formatter)**: 重组者。读取 OL 翻译后的 MD/XLIFF 及 manifest.json/skeleton.zip，调用 Pandoc/md2pptx/translate-toolkit 等成熟轮子，配合自研胶水代码（manifest 解析、skeleton 回填、资源路径还原、样式模板映射、日志与错误追踪），重组生成本地化的复杂格式文档。

### ORF 的核心原则

> 不重复造轮子，只做优秀的胶水：格式转换的脏活累活交给成熟轮子，ORF 专注解决上下游数据对齐、路径丢失、格式降级与可观测性问题。

### ORF 输入来源（基于 OPP/OL 改进）

| 文件类型 | 来源 | 关键字段 |
|----------|------|----------|
| MD 文件（含 frontmatter） | OL 输出 | `source_lang`, `target_lang`, `original_file`, `translated_at` |
| XLIFF 文件 | OL 输出 | 翻译单元 |
| manifest.json | OPP 输出 | `source.format`, `source.file_hash_md5`, `skeleton.path`, `resources.storage_dir` |
| skeleton.zip | OPP 输出 | 原始 OOXML 结构（word/document.xml 等） |
| images/ | OPP 资源目录 | MD5 去重后的图片文件 |

---

## Phase 0: 项目骨架与 MD 回写基础（DOCX/ODT/EPUB）

### 📋 Phase 0 执行计划

#### 1. 概述与目标

- 搭建 ORF 项目仓库结构，配置 CI/CD
- 实现 MD → DOCX/ODT/EPUB 三种基础回写通道（基于本地化后的 MD）
- 构建统一的格式回写抽象层与资源路径映射胶水代码
- **读取 manifest.json 和 YAML frontmatter**，解析源格式和翻译上下文

#### 2. 工具矩阵

| 环节 | 工具 | 职责 |
|------|------|------|
| MD→DOCX | Pandoc | Markdown 转 DOCX，支持 reference-doc 模板 |
| MD→ODT | Pandoc | Markdown 转 ODT，支持 reference-odt 模板 |
| MD→EPUB | Pandoc | Markdown 转 EPUB，处理元数据与目录 |
| 资源管理 | OPP resource_manager | 复用/适配其 MD5 去重、路径维护逻辑 |
| Manifest 解析 | 标准库 json | 读取 OPP 的 manifest.json |
| Frontmatter 解析 | 标准库 yaml | 读取 OL 的 YAML frontmatter |
| 日志系统 | loguru | 结构化日志记录，追踪转换全生命周期 |
| 测试框架 | pytest | 单元测试与集成测试 |

#### 3. ORF 应解析的元数据

| 元数据来源 | 字段 | 用途 |
|------------|------|------|
| manifest.json | `source.format` | 确定目标格式（DOCX/PPTX 等） |
| manifest.json | `skeleton.path` | Phase 1 XLIFF→DOCX 回填需要 |
| manifest.json | `resources.storage_dir` | 图片资源目录位置 |
| manifest.json | `source.file_hash_md5` | 完整性校验 |
| YAML frontmatter | `source_lang` | 源语言 |
| YAML frontmatter | `target_lang` | 目标语言 |
| YAML frontmatter | `original_file` | 原始文件名（用于日志/报告） |
| YAML frontmatter | `translated_at` | 翻译时间（用于日志/报告） |

### 🧪 UTDD - 单元测试驱动（本Phase要写的测试）

**测试交付物**: `tests/test_md2docx_channel.py`, `tests/test_md2odt_channel.py`, `tests/test_md2epub_channel.py`, `tests/test_resource_manager.py`, `tests/test_logging_system.py`, `tests/test_manifest_parser.py`, `tests/test_frontmatter_parser.py`

| 核心函数 | 正常输入用例 | 边界值用例 | 异常输入用例 |
|----------|--------------|------------|----------------|
| **MD→DOCX通道** | | | |
| `convert_md_to_docx()` | 标准本地化 MD（含标题/列表/表格/图片）<br>带模板的转换 | 空 MD 文档<br>只含标题的 MD<br>1000页超大 MD | 损坏的 MD 语法<br>图片路径异常<br>模板文件损坏 |
| **Manifest 解析** | | | |
| `parse_manifest()` | 标准 manifest.json<br>含 skeleton 路径 | 缺少可选字段<br>manifest_version 为 "1.0" | 缺少必要字段<br>manifest.json 不存在<br>JSON 格式错误 |
| **Frontmatter 解析** | | | |
| `parse_frontmatter()` | 标准 YAML frontmatter<br>含所有字段 | 缺少可选字段<br>仅有必需字段 | frontmatter 不存在<br>YAML 格式错误<br>重复 `---` 块 |
| **资源管理器 (胶水)** | | | |
| `resolve_image_paths()` | 图片在 images/ 下<br>MD 中使用相对路径 | 0图片文档<br>图片名含特殊字符<br>重复图片(MD5相同) | 图片缺失<br>路径越界访问 |
| **日志系统 (胶水)** | | | |
| `log_conversion_event()` | 记录转换开始/结束/耗时 | 空转换参数 | 无效日志级别<br>日志文件不可写 |

### ✅ ATDD - 验收测试驱动（本Phase的验收标准）

**正常流程验收标准**

- OPP输出 MD → OL本地化 → ORF回写：
  - DOCX：标题/列表/表格结构保持，图片路径正确还原
  - ODT：在 LibreOffice 中打开样式正常，无断链
  - EPUB：在阅读器中目录、图片、链接正常
- manifest.json 解析成功率 100%
- YAML frontmatter 解析成功率 100%
- 图片引用路径 100% 可解析，无断链
- 支持用户自定义 reference.docx / reference.odt 模板

**❌ 异常流程验收标准**

- MD 语法错误 → 自动降级为纯文本段落 + 在文档首行插入警告注释
- 表格过于复杂 → 降级为简单表格 + 警告
- 图片缺失 → 插入占位图 [Image Missing] + 警告文本
- manifest.json 缺失 → 尝试从 YAML frontmatter 推断信息，记录警告
- YAML frontmatter 缺失 → 使用默认值，记录警告
- 转换失败 → 生成详细 JSON 错误报告，进程不崩溃

**🔲 边界条件验收标准**

- 单文档页数上限：10,000 段（超出触发分节/分文件处理）
- 单文件大小上限：500MB（超出自动降级流式处理）
- 图片分辨率上限：默认 300dpi（超出自动缩放）
- 并发转换上限：5 个任务（超出排队等待）

**⚡ 非功能性验收标准**

- MD → DOCX/ODT/EPUB 转换性能 ≥ 15MB/s（单线程）
- Manifest + Frontmatter 解析性能 ≤ 10ms
- 内存开销 ≤ 原始文件大小 2 倍
- 日志记录完整性 100%，关键操作（manifest 解析、skeleton 路径、轮子调用、错误降级）均可追溯

### 🎯 BDD - 行为驱动场景（本Phase的关键场景）

**场景1：DOCX通道端到端（基于 manifest + frontmatter）**

Given: OPP→OL 输出目录包含 manual_zh.md、manual_zh_manifest.json、images/ 目录

When: 用户执行 orf apply-md manual_zh.md --target-format docx --template template.docx --output manual_zh.docx

Then:
- ORF 解析 manual_zh_manifest.json 获取源格式（DOCX）
- ORF 解析 manual_zh.md 的 YAML frontmatter 获取翻译上下文
- manual_zh.docx 成功生成
- 标题层级、列表、表格与 MD 对应
- 图片从 images/ 正确嵌入 DOCX，无断链
- loguru 记录完整的转换生命周期日志

**场景2：ODT通道**

Given: 同上输入

When: 用户执行 orf apply-md manual_zh.md --target-format odt --reference-odt template.odt --output manual_zh.odt

Then:
- manual_zh.odt 在 LibreOffice 中打开样式正常
- 结构与 MD 完全对应，图片显示正常

**场景3：EPUB通道**

Given: 同上输入

When: 用户执行 orf apply-md manual_zh.md --target-format epub --title "用户手册" --output manual_zh.epub

Then:
- manual_zh.epub 可在 Apple Books/Calibre 正常打开
- 目录、图片、链接结构完整

### 🔄 TDD - 测试驱动开发循环（本Phase的开发流程）

| 阶段 | 动作 | 验证标准 |
|------|------|----------|
| 🔴 红 | 先写 MD→DOCX/ODT/EPUB 三个通道及胶水代码的所有测试用例 | 测试全部失败（证明测试有效） |
| 🟢 绿 | 基于 Pandoc 实现三个通道，编写 manifest/frontmatter 解析与路径映射胶水代码 | 所有测试通过 |
| 🔄 重构 | 抽象通用 MD 回写接口 BaseMDConverter，为后续 PPTX/XLIFF 通道复用 | 测试仍然全部通过 |

**本Phase测试交付物清单**：

- `tests/test_md2docx_channel.py`（MD→DOCX 回写）
- `tests/test_md2odt_channel.py`（MD→ODT 回写）
- `tests/test_md2epub_channel.py`（MD→EPUB 回写）
- `tests/test_manifest_parser.py`（manifest.json 解析）
- `tests/test_frontmatter_parser.py`（YAML frontmatter 解析）
- `tests/test_resource_manager.py`（图片资源管理胶水）
- `tests/test_logging_system.py`（日志系统胶水）

### ⚠️ 本Phase风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| Pandoc 版本差异导致输出不一致 | 格式错乱 | CI 中锁定 Pandoc 版本 + 输出样本对比测试 (Snapshot Testing) |
| ODT 模板兼容性问题 | 样式丢失 | 提供标准模板库 + 模板预检工具 |
| EPUB 生成不符合规范 | 阅读器无法打开 | 集成 EPUB 验证器 + 自动修复常见标签问题 |
| manifest.json/frontmatter 格式不兼容 | 解析失败 | 宽松解析 + 降级策略 + 详细警告 |

---

## Phase 1: MD→PPTX 回写与 XLIFF 回写（ODF/DOCX）

### 📋 Phase 1 执行计划

#### 1. 概述与目标

- 实现 MD → PPTX 回写通道（基于 md2pptx）
- 实现 XLIFF → ODF/DOCX 回写通道（基于 translate-toolkit 与 **OPP skeleton.zip** 回填）
- 完善错误处理胶水机制

#### 2. 工具矩阵

| 环节 | 工具 | 职责 |
|------|------|------|
| MD→PPTX | md2pptx | Markdown 按 H1/H2 拆分转 PowerPoint |
| XLIFF→ODF | translate-toolkit (xliff2odf) | 将 XLIFF 翻译回填到原始 ODF 骨架 |
| XLIFF→DOCX | OPP skeleton.zip + 自研胶水 | 解析 skeleton.zip 回填翻译到 word/document.xml |
| Skeleton 解析 | zipfile | 解压 OPP skeleton.zip，定位 word/document.xml |
| 错误处理 | sentry-sdk / loguru | 错误追踪、降级与报告聚合 |

#### 3. XLIFF→DOCX 回填流程（基于 skeleton.zip）

```
1. 读取 manifest.json 获取 skeleton.path
2. 解压 skeleton.zip 到临时目录
3. 读取 XLIIF 翻译单元 (source/target)
4. 解析 word/document.xml 中的 <w:t> 元素
5. 按 trans-unit id 映射，将翻译 target 回填到对应 <w:t>
6. 重新打包为新的 DOCX (zip)
7. 替换 skeleton.zip 为新 DOCX
```

### 🧪 UTDD - 单元测试驱动（本Phase要写的测试）

**测试交付物**: `tests/test_md2pptx_channel.py`, `tests/test_xliff2odf_channel.py`, `tests/test_xliff2docx_channel.py`, `tests/test_skeleton_loader.py`, `tests/test_error_handler.py`

| 核心函数 | 正常输入用例 | 边界值用例 | 异常输入用例 |
|----------|--------------|------------|----------------|
| **MD→PPTX通道** | | | |
| `convert_md_to_pptx()` | 标准 PPTX 来源的 MD<br>带模板转换 | 单页幻灯片 MD<br>1000+页 MD | MD 中不支持的 PPTX 特性<br>模板损坏 |
| `split_md_to_slides()` | H1 封面，H2 新幻灯片 | 无标题纯段落<br>深度嵌套标题 | 标题层级混乱 |
| **Skeleton 加载器** | | | |
| `load_skeleton()` | 有效 skeleton.zip<br>包含 word/document.xml | skeleton.zip 为空<br>缺少关键文件 | skeleton.zip 不存在<br>非 ZIP 格式<br>document.xml 缺失 |
| **XLIFF→DOCX通道** | | | |
| `xliff_to_docx()` | OPP 输出 DOCX + OL 翻译后 XLIFF<br>skeleton.zip 可用 | 单元 XLIFF<br>复杂表格 | XLIFF 单元与段落映射失败<br>XML 结构破坏 |
| **错误处理器 (胶水)** | | | |
| `handle_conversion_error()` | 捕获并记录转换错误，执行降级 | 空错误对象 | 错误报告发送失败<br>降级策略也失败 |

### ✅ ATDD - 验收测试驱动（本Phase的验收标准）

**正常流程验收标准**

- PPTX：幻灯片数量、备注、图片位置与原文一致
- ODF：xliff2odf 后，ODT/ODS 可正常打开，翻译单元 100% 填回原位
- DOCX：skeleton.zip + XLIFF 回填后，段落/表格/图片与原文位置对应
- 错误处理：所有转换错误均有详细记录，并给出用户友好提示

**❌ 异常流程验收标准**

- PPTX：无法映射的表格/形状 → 降级为文本框 + 警告
- ODF：XLIFF 与 ODF 不匹配 → 报错并提示重新生成 XLIFF，不强行回填
- DOCX：skeleton.zip 缺失 → 报错并提示需要 OPP 重新生成含 skeleton 的输出
- DOCX：XLIFF→DOCX 映射失败 → 生成警告报告，保留原文不覆盖
- 错误处理：网络中断 → 本地缓存错误报告，恢复后上传

**🔲 边界条件验收标准**

- 幻灯片数上限：500 页（超出分文件输出）
- 单页内容上限：10000 字符（超出拆分为多页）
- XLIFF 翻译单元上限：10000 单元（超出分块处理）

**⚡ 非功能性验收标准**

- MD → PPTX 转换性能 ≥ 10MB/s
- XLIFF → ODF/DOCX 转换性能 ≥ 5MB/s
- Skeleton 加载 + 解压 ≤ 500ms
- 错误处理延迟 ≤ 100ms

### 🎯 BDD - 行为驱动场景（本Phase的关键场景）

**场景1：PPTX完整本地化流水线**

Given: OPP→OL 输出目录包含 demo_zh.md、demo_zh_manifest.json、demo.skeleton.zip、images/

When: 用户执行 orf apply-md demo_zh.md --target-format pptx --template template.pptx --output demo_zh.pptx

Then:
- demo_zh.pptx 为中文版演示文稿
- 每页幻灯片标题与内容结构一致
- 演讲者备注保留在每页备注区

**场景2：XLIFF→ODF 回填**

Given: OPP 输出的原始 doc.odt 与 OL 翻译后的 translated.xlf

When: 用户执行 orf apply-xliff doc.odt --xliff translated.xlf --target-format odf --output doc_zh.odt

Then:
- doc_zh.odt 为翻译后的 ODT
- 翻译单元精准回填到对应 XML 节点
- 图片、样式保持不变

**场景3：XLIFF→DOCX 回填（基于 skeleton.zip）**

Given: OPP→OL 输出目录包含 spec_zh.md、spec_zh_manifest.json、spec.skeleton.zip、spec.xlf

When: 用户执行 orf apply-xliff spec.skeleton.zip --xliff spec.xlf --output spec_zh.docx

Then:
- spec_zh.docx 为翻译后的 DOCX
- 翻译单元通过 skeleton.zip 的 word/document.xml 精准回填
- 样式和结构完全保留

### 🔄 TDD - 测试驱动开发循环（本Phase的开发流程）

| 阶段 | 动作 | 验证标准 |
|------|------|----------|
| 🔴 红 | 先写 MD→PPTX 和 XLIFF→ODF/DOCX 的所有测试用例 | 测试全部失败 |
| 🟢 绿 | 基于 md2pptx 和 translate-toolkit 实现通道及回填胶水 | 所有测试通过 |
| 🔄 重构 | 统一 XLIFF 回写接口，抽象通用转换流程 | 测试仍然全部通过 |

**本Phase测试交付物清单**：

- `tests/test_md2pptx_channel.py`（MD→PPTX 回写）
- `tests/test_xliff2odf_channel.py`（XLIFF→ODF 回写）
- `tests/test_xliff2docx_channel.py`（XLIFF→DOCX 回写）
- `tests/test_skeleton_loader.py`（skeleton.zip 加载与解析）
- `tests/test_error_handler.py`（错误处理器）

### ⚠️ 本Phase风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| md2pptx 功能限制 | PPTX 高级特性丢失 | 降级策略 + 生成特性丢失警告清单 |
| skeleton.zip 缺失或损坏 | XLIFF→DOCX 无法回填 | 检测并报错，提示用户使用含 skeleton 的 OPP 输出 |
| XLIFF 与原格式对应关系复杂 | 回填错位 | 严格 trans-unit id 映射 + 回填后 XML 结构校验 |
| 错误处理阻塞主流程 | 转换速度下降 | 异步错误上报 + 批量日志刷新 |

---

## Phase 2: 多格式汇聚与自动探测与资源统一管理

### 📋 Phase 2 执行计划

#### 1. 概述与目标

- 实现输入格式自动探测引擎（读取 manifest.json 或推断）
- 实现图片资源统一管理（去重/命名/跨格式路径维护）
- 扩展支持更多格式（HTML、RTF、PDF 等）

#### 2. 工具矩阵

| 环节 | 工具 | 职责 |
|------|------|------|
| 格式探测 | manifest.json + python-magic | 先查 manifest.json，再 fallback 到 magic bytes |
| MD→HTML | Pandoc | Markdown 转 HTML，支持 CSS 注入 |
| MD→RTF | Pandoc | Markdown 转 RTF |
| MD→PDF | Pandoc + LaTeX / WeasyPrint | Markdown 转 PDF |

### 🧪 UTDD - 单元测试驱动（本Phase要写的测试）

**测试交付物**: `tests/test_auto_detector.py`, `tests/test_resource_manager.py`, `tests/test_md2html_channel.py`, `tests/test_md2rtf_channel.py`, `tests/test_md2pdf_channel.py`

| 核心函数 | 正常输入用例 | 边界值用例 | 异常输入用例 |
|----------|--------------|------------|----------------|
| **格式自动探测** | | | |
| `detect_format()` | manifest.json 存在<br>无 manifest 但有 magic bytes | manifest.json 缺失<br>无扩展名文件 | manifest.json 格式错误<br>二进制头破损 |
| **资源管理器 (胶水)** | | | |
| `manage_resources()` | 图片 MD5 去重<br>跨格式路径转换 | 0图片<br>1000+图片 | 重复 MD5 冲突<br>跨平台路径符号差异 |
| **MD→PDF通道** | | | |
| `convert_md_to_pdf()` | 标准 MD→PDF 转换<br>含中文字体模板 | 超大文档<br>含数学公式 (LaTeX) | LaTeX 编译失败<br>中文字体缺失 |

### ✅ ATDD - 验收测试驱动（本Phase的验收标准）

**正常流程验收标准**

- manifest.json 存在时：格式自动探测准确率 100%
- manifest.json 缺失时：magic bytes 探测准确率 ≥ 95%
- 图片去重率 100%（相同图片不重复存储）
- 所有新增格式（HTML/RTF/PDF）转换成功率 ≥ 95%

**❌ 异常流程验收标准**

- manifest.json 格式错误 → 回退到 magic bytes 探测 + 警告
- 格式探测失败 → 提示用户手动指定 `--target-format`
- 资源冲突 → 自动重命名并记录映射表
- PDF 生成失败 → 提供降级选项（如 HTML→PDF 或纯 MD 打包）

**🔲 边界条件验收标准**

- 单个文档页数上限：10,000 页
- 单个文件大小上限：500MB
- 资源数量上限：10,000 个文件

**⚡ 非功能性验收标准**

- 格式探测响应时间 ≤ 50ms（已含 manifest 读取）
- 资源管理性能 ≥ 50MB/s
- 所有格式转换性能 ≥ 10MB/s

### 🎯 BDD - 行为驱动场景（本Phase的关键场景）

**场景1：自动格式探测与转换**

Given: 用户丢失了原文件信息，只有 OL 输出的 manual_zh.md、manual_zh_manifest.json、images/

When: 用户执行 orf apply-md manual_zh.md --target-format auto --output manual_zh

Then:
- 系统读取 manifest.json 获取源格式为 DOCX
- 生成 manual_zh.docx
- 日志记录探测过程和依据

### 🔄 TDD - 测试驱动开发循环（本Phase的开发流程）

| 阶段 | 动作 | 验证标准 |
|------|------|----------|
| 🔴 红 | 先写格式探测、资源管理和新增格式转换的所有测试用例 | 测试全部失败 |
| 🟢 绿 | 实现格式探测、资源管理和新增格式转换 | 所有测试通过 |
| 🔄 重构 | 统一资源管理接口，优化性能 | 测试仍然全部通过 |

**本Phase测试交付物清单**：

- `tests/test_auto_detector.py`（格式自动探测引擎）
- `tests/test_resource_manager.py`（图片资源统一管理）
- `tests/test_md2html_channel.py`, `test_md2rtf_channel.py`, `test_md2pdf_channel.py`

### ⚠️ 本Phase风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| 格式探测误判 | 转换失败 | Magic Number + manifest 双重验证机制 |
| PDF 生成依赖外部 LaTeX | 环境不一致导致编译失败 | 提供多引擎支持 |

---

## Phase 3: 用户体验与端到端集成与 PyPI 发布

### 📋 Phase 3 执行计划

#### 1. 概述与目标

- 完善 CLI 用户体验，提供直观的命令行界面
- 实现 OPP → OL → ORF **完整流水线**集成测试
- 准备 PyPI 发布，打包和分发

#### 2. 工具矩阵

| 环节 | 工具 | 职责 |
|------|------|------|
| CLI框架 | click | 命令行界面构建 |
| 进度条 | tqdm | 转换进度显示 |
| 打包 | setuptools / pyproject.toml | PyPI 包打包 |
| 发布 | twine | PyPI 包发布 |

### 🧪 UTDD - 单元测试驱动（本Phase要写的测试）

**测试交付物**: `tests/test_cli.py`, `tests/test_integration.py`, `tests/test_packaging.py`

| 核心函数 | 正常输入用例 | 边界值用例 | 异常输入用例 |
|----------|--------------|------------|----------------|
| **CLI交互** | | | |
| `parse_arguments()` | 标准命令行参数<br>可选参数组合 | 无参数<br>冲突参数 | 无效参数<br>缺少必要参数 |
| **端到端集成** | | | |
| `run_full_pipeline()` | OPP→OL→ORF 完整流程 | 部分流程失败<br>大文件处理 | 中间步骤失败<br>资源缺失 |

### ✅ ATDD - 验收测试驱动（本Phase的验收标准）

**正常流程验收标准**

- CLI 提供清晰的帮助信息和进度反馈
- OPP → OL → ORF 端到端测试通过率 100%
- PyPI 包可一键安装 (`pip install omni-re-formatter`)，依赖自动解决

**❌ 异常流程验收标准**

- CLI 提供友好的错误提示和修复建议
- 端到端流程部分失败 → 提供部分结果和错误报告

### 🎯 BDD - 行为驱动场景（本Phase的关键场景）

**场景：结构化文档的完整本地化流水线**

Given: 用户有一个 DOCX 格式的技术规格书 spec.docx（英文）

When: 用户执行以下命令序列：

```bash
opp convert spec.docx --target-format both --output-dir preprocess/

ol translate preprocess/spec.xlf --target-lang ja-JP --output preprocess/spec_ja.xlf

orf apply-xliff preprocess/spec.skeleton.zip --xliff preprocess/spec_ja.xlf --output spec_ja.docx
```

Then:
- spec_ja.docx 为日文版技术规格书
- 所有排版格式与原始 DOCX 完全一致（通过 skeleton.zip 回填）
- XLIFF 翻译单元 100% 应用到对应位置
- 图片引用和路径保持不变
- manifest.json 和 YAML frontmatter 全程可追溯

### 🔄 TDD - 测试驱动开发循环（本Phase的开发流程）

| 阶段 | 动作 | 验证标准 |
|------|------|----------|
| 🔴 红 | 先写 CLI、端到端集成和打包的所有测试用例 | 测试全部失败 |
| 🟢 绿 | 实现 CLI、端到端集成和打包 | 所有测试通过 |
| 🔄 重构 | 优化用户体验，简化流程 | 测试仍然全部通过 |

**本Phase测试交付物清单**：

- `tests/test_cli.py`（CLI 交互测试）
- `tests/test_integration.py`（端到端集成测试）
- `tests/test_packaging.py`（打包与发布测试）

### ⚠️ 本Phase风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| CLI 设计不符合用户习惯 | 学习成本高 | 用户测试 + 迭代优化 |
| PyPI 发布依赖冲突 | 安装失败 | Poetry / pdm 严格锁版本 + 多环境测试 |

---

## 总体风险分析与缓解策略

| 风险等级 | 风险描述 | 影响范围 | 缓解策略 |
|----------|----------|----------|----------|
| 🔴 高 | Pandoc 版本兼容性问题 | 所有格式转换 | 版本锁定 + 兼容性测试矩阵 |
| 🔴 高 | skeleton.zip 缺失导致 XLIFF→DOCX 无法回填 | DOCX 回填 | 明确要求 OPP 输出含 skeleton，或降级到 MD→DOCX 模式 |
| 🔴 高 | manifest.json/frontmatter 格式不兼容 | 所有通道 | 宽松解析 + 降级策略 + 详细警告 |
| 🟡 中 | md2pptx 功能限制 | PPTX 转换质量 | 降级策略 + 警告系统 |
| 🟡 中 | PDF 生成依赖外部工具 | 环境不一致 | 多引擎支持 (WeasyPrint 备选) + Docker 化 |
| 🟢 低 | CLI 用户体验不佳 | 学习成本 | 用户测试 + 文档完善 |

---

## 里程碑总览与交付物

| 里程碑 | 阶段 | 核心交付物 | 预计工期 |
|--------|------|------------|----------|
| M0 | Phase 0：项目骨架与 MD 回写基础 | 项目仓库、三种格式回写通道、manifest/frontmatter 解析器、UTDD 测试矩阵、CI | 1.5 天 |
| M1 | Phase 1：PPTX 回写与 XLIFF 回写 | PPTX 通道、skeleton loader、XLIFF 回写通道、错误处理系统 | 1.5 天 |
| M2 | Phase 2：多格式汇聚与管理 | 格式探测（基于 manifest）、资源管理、新增格式支持 | 1.5 天 |
| M3 | Phase 3：用户体验与集成 | CLI 优化、OPP→OL→ORF 端到端集成、PyPI 发布 | 1.5 天 |

**总计预计工期：6 天**

**总测试文件：约 32 个**（含 manifest/frontmatter 解析器测试）

**总测试用例：约 280 个**

**测试覆盖率目标：≥ 90%**

---

## 技术债务与后续优化

- **性能优化**：对于超大文件，实现流式处理和分块转换，避免 Pandoc OOM
- **格式扩展**：持续增加对新格式的支持（如 InDesign ICML、SRT 字幕等）
- **云服务集成**：支持 AWS S3、Azure Blob 等云存储资源直接读写
- **AI 辅助排版**：集成 AI 视觉模型，自动修复因翻译导致的长文本排版溢出问题
