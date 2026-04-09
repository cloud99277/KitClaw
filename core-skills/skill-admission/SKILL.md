---
name: skill-admission
description: |
  KitClaw skill 收编验收：检查 skill 是否符合 KitClaw 公开仓库的准入标准。
  触发词：收编检查、admission、能不能公开、验收、准入。
  用在：决定哪些 skill 进入 KitClaw 主仓库前的质量关口。
---

# skill-admission — KitClaw Skill 收编验收

检查一个 skill 是否达到 KitClaw 公开仓库的准入标准。

## 准入标准（7 项检查）

| # | 检查项 | 级别 | 标准 |
|---|--------|------|------|
| 1 | **lint** | 必须 | frontmatter 格式正确，name hyphen-case，description 完整 |
| 2 | **security** | 必须 | 无 API key、token、password 等敏感数据 |
| 3 | **no-personal-deps** | 必须 | 无硬编码路径（/home/xxx、/mnt/x）、无用户名引用 |
| 4 | **agent-agnostic** | 必须 | 不依赖特定 Agent（Claude Code hooks、OMC 等） |
| 5 | **self-contained** | 必须 | SKILL.md 引用的 scripts/、references/ 文件全部存在 |
| 6 | **docs** | 推荐 | body ≥5 行，有标题结构，<500 行 |
| 7 | **no-aux-files** | 推荐 | 无 README.md、CHANGELOG.md、banner 等辅助文件 |

**通过规则**：所有「必须」项全部 pass → 准入。「推荐」项 fail → 警告但不阻止。

## 使用

### 检查单个 skill

```bash
python3 ~/.ai-skills/skill-admission/scripts/admit.py ~/.ai-skills/<skill-name>
```

### 批量检查（全仓库）

```bash
python3 ~/.ai-skills/skill-admission/scripts/admit.py ~/.ai-skills --all
```

### JSON 输出（给 CI/脚本用）

```bash
python3 ~/.ai-skills/skill-admission/scripts/admit.py ~/.ai-skills/<skill-name> --format json
```

### Strict 模式（推荐项也当必须）

```bash
python3 ~/.ai-skills/skill-admission/scripts/admit.py ~/.ai-skills/<skill-name> --strict
```

## 收编流程

```
1. 运行 admission 检查（原件上跑，不修改原件）
2. 复制到公开仓库（cp -r）
3. 在副本上修复所有 FAIL 项
4. 路径通用化（/home/xxx → $HOME 或通用写法）
5. 删除非标辅助文件（README.md、banner 等）
6. 通过 KitClaw pre-commit hook（自动校验 frontmatter + 安全）
7. git add + commit + push
```

## Frontmatter 校验规则（pre-commit hook）

KitClaw 的 `validate_frontmatter.py` 对不同文件有不同要求：

| 文件类型 | 必填 (阻塞提交) | 推荐 (warning, 不阻塞) |
|---|---|---|
| **SKILL.md** | `name` + `description` | `tags`, `scope` |
| **references/\*.md** | frontmatter 存在即可 | 无 |
| **其他 .md** | `title` | `tags`, `scope` |

SKILL.md 只需 `name` + `description`，与本地 skill 规范一致，不需要额外加 `title`。

## ⚠️ 关键规则：不要动原件

**公开仓库的 skill 必须从原件复制，绝不能修改 `~/.ai-skills/` 里的源文件。**

原因：
- `~/.ai-skills/` 是用户私有工作环境，包含个人路径、API key 引用、Agent 专属配置
- 公开仓库需要通用化处理（去掉硬编码路径、适配多 Agent），但原件需要保留以便日常使用
- KitClaw 治理 hook 已与本地规范对齐（SKILL.md 只需 name+description），两边标准一致

正确做法：

```bash
# 1. 从私有目录复制到公开仓库
cp -r ~/.ai-skills/my-skill ~/projects/kitclaw/core-skills/
# 或
cp -r ~/.ai-skills/my-skill ~/projects/ai-skills-hub/

# 2. 在公开仓库副本上做修改
#    - 去掉硬编码路径（/home/xxx → 通用写法）
#    - 满足目标仓库的治理标准（如加 title 字段）
#    - 删除非标辅助文件（README.md、banner.jpg 等）

# 3. 私有原件保持不动
```

**决不能做的事情：**
- ❌ 直接修改 `~/.ai-skills/` 里的文件来适配公开标准
- ❌ 从公开仓库反向覆盖私有原件
- ❌ 在私有原件上运行目标仓库的 pre-commit hook

## 与其他 skill 的关系

| 关联 skill | 关系 |
|------------|------|
| `skill-lint` | admission 内部调用 lint 逻辑 |
| `skill-security-audit` | admission 内部调用安全检查 |
| `skill-installer` | 安装后跑 admission 确认合规 |
