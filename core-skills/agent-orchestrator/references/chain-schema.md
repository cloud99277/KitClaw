---
name: chain-schema
---
# 编排链 YAML Schema

> **版本**：1.0
> **所属**：agent-orchestrator
> **最后更新**：2026-03-09

---

## 1. 概述

编排链是一个 YAML 文件，定义了多个 skill 的线性执行顺序。orchestrator 读取此文件，验证相邻 skill 的 IO 类型匹配，并输出分步执行计划。

## 2. Schema 定义

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | 固定为 `"1.0"` |
| `name` | string | 链的唯一标识名（kebab-case） |
| `description` | string | 链的用途说明 |
| `steps` | list | 步骤列表（至少 1 个） |

### 可选字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `variables` | list | 链的输入变量定义 |

### steps 中每一步

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `skill` | ✅ | string | skill 目录名（如 `translate`） |
| `input` | 可选 | dict | 传给 skill 的输入参数 |
| `output` | 可选 | string | 本步骤的输出文件名 |

### variables 中每个变量

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `name` | ✅ | string | 变量名（大写，如 `URL`） |
| `description` | 可选 | string | 变量说明 |
| `required` | 可选 | boolean | 是否必填，默认 true |

## 3. 变量机制

- 在 `input` 的值中使用 `$VAR_NAME` 引用变量
- 变量在 `plan` 模式下通过 `--var NAME=VALUE` 提供
- 未提供 required 变量时报错

## 4. 完整示例

```yaml
schema_version: "1.0"
name: translate-tweet-publish
description: 获取推文、翻译、发布到微信

variables:
  - name: URL
    description: 推文 URL
    required: true

steps:
  - skill: baoyu-danger-x-to-markdown
    input:
      url: "$URL"
    output: content.md

  - skill: translate
    input:
      file: content.md
      to: zh-CN
      mode: normal
    output: translation.md

  - skill: baoyu-post-to-wechat
    input:
      file: translation.md
```

## 5. YAML 子集限制

agent-orchestrator 使用内置的 YAML 子集解析器（零依赖），**仅支持以下语法**：

| 支持 | 不支持 |
|------|--------|
| flat key-value（`name: value`） | 多行字符串（`\|`、`>`） |
| 列表（`- item`） | 锚点和引用（`&`、`*`） |
| 列表下的 key-value（`- skill: name`） | YAML 标签（`!!`） |
| inline dict（`{k: v, k2: v2}`） | 多文档（`---` 分隔符） |
| 字符串值（带/不带引号） | 复杂嵌套（>2 层） |
| `$VAR` 变量引用 | 条件表达式 |
| 注释（`#`） | 合并键（`<<:`） |

遇到不支持的语法时，解析器会输出明确错误信息。

## 6. IO 验证规则

orchestrator 验证编排链时，检查相邻步骤的 IO 类型匹配：

1. 读取每个 skill 的 SKILL.md frontmatter 中 `io:` 声明
2. 检查 step[n].output_type ∈ step[n+1].input_types
3. 匹配优先级：精确匹配 > 兼容匹配 > 不匹配
4. 兼容规则从 `type-registry.json` 动态加载

详见 Phase 1 `IO-CONVENTION.md` 第 4 节。

---

## 变更日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-03-09 | 1.0 | 初始版本 |