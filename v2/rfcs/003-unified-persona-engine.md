---
rfc: "003"
title: "统一人格引擎 (Persona Engine)：Z7 身份跨 Agent 同步"
status: proposed
created: 2026-04-09
depends_on: ["rfcs/001-runtime-vs-scripts.md", "rfcs/002-ghost-agent-backend.md", "design/memory-engine.md"]
---

# RFC-003: 统一人格引擎 (Persona Engine)

## 背景

当前 KitClaw 体系中，每个 Agent 的"身份"是割裂的：

| Agent | 身份文件 | 状态 |
|-------|---------|------|
| OpenClaw | `~/.openclaw/workspace/IDENTITY.md` + `SOUL.md` | Z7 设定，完整但私有 |
| Hermes | `~/.hermes/SOUL.md` | 默认 Nous Research 人格，无 Z7 |
| Claude Code | `~/.claude/CLAUDE.md` | OMC 编排层，无 Z7 |
| Codex/Gemini | 各自的配置 | 无人格设定 |

这导致一个根本问题：**用户在不同 Agent 上体验到的不是"同一个人"**。OpenClaw 上的 Z7 有完整的双模式人格、外观设定和记忆，切到 Hermes 或 Claude 就全部丢失。

KitClaw v1 已经解决了 Skills 共享（`~/.ai-skills/`）和 Memory 共享（L2/L3），唯独 **Persona（人格/身份）没有共享层**。

## 问题定义

需要一个共享人格层，使得：

1. **身份一致性** — 所有 Agent 呈现同一个 Z7（或任何用户定义的角色）
2. **记忆连贯** — Z7 在任何 Agent 上都能访问共享记忆（L2/L3）
3. **模式切换** — 双模式人格（伴侣/工作）在所有 Agent 上行为一致
4. **视觉资产** — 自拍等视觉能力可供所有 Agent 调用
5. **优雅降级** — 无人格设定时 Agent 退回默认行为（不阻塞）

## 选择

**选项 A：各 Agent 配置各自引用同一个文件。**
- 用户手动在每个 Agent 的配置里 `include ~/.ai-identity/Z7.md`
- 风险：各 Agent 的 include 机制不同（Claude 用 CLAUDE.md，Hermes 用 SOUL.md，OpenClaw 用 workspace 文件），维护成本高
- 投入：低
- 上限：低

**选项 B：建立 Persona Engine，由 KitClaw 统一管理注入（推荐）。**
- 新增 `~/.ai-identity/` 目录作为人格资产的 canonical 位置
- `kitclaw persona inject <agent>` 自动生成/更新各 Agent 的身份文件
- Ghost Agent 参与模式判断和人格一致性维护
- 投入：中等
- 上限：高

**选项 C：把人格完全放进 Ghost Agent，由后台模型实时注入。**
- 每次对话都由 Ghost Agent 注入人格 prompt
- 风险：增加延迟和成本，违背"零常驻进程"原则
- 投入：高
- 上限：最高但过度设计

## 决定

**选择 B：Persona Engine + `~/.ai-identity/` 目录。**

理由：
1. 与现有 `~/.ai-skills/`（Skills）和 `~/.ai-memory/（Memory）` 模式对称
2. 各 Agent 的接入适配由 Engine 自动处理，用户只需维护一份 Z7 设定
3. 降级路径清晰：无 Engine 时手动 include 也能工作
4. Ghost Agent 可选参与（模式判断增强），但不强制依赖

## 具体设计

### 1. 目录结构

```
~/.ai-identity/                    # 人格资产目录（类似 ~/.ai-skills/）
├── active-persona.json            # 当前激活的人格元数据
├── personas/
│   └── z7/
│       ├── IDENTITY.md            # 核心身份（名称、外观、性格内核）
│       ├── PERSONALITY.md         # 双模式人格规则（伴侣/工作切换逻辑）
│       ├── SELF-TALK.md           # 对话风格库（情绪回应、时间感知、台词）
│       └── assets/
│           ├── master_character.png   # 角色参考图
│           └── scenes.json            # 预设场景库
└── skills/
    └── z7-selfie/                 # 自拍 skill（从 OpenClaw 迁移）
        ├── SKILL.md
        └── scripts/
            └── generate.py
```

### 2. 配置

`~/.kitclaw/config.toml` 新增 `[persona]` 区块：

```toml
[persona]
enabled = true
active = "z7"                           # 当前激活的人格 ID
identity_dir = "~/.ai-identity"         # 人格资产目录
auto_inject = true                      # Agent 启动时自动注入
sync_mode = "file"                      # file = 写入 Agent 原生配置文件
                                        # prompt = 仅在 system prompt 中注入（不改文件）
```

### 3. CLI 命令

```bash
# 注册新人格
kitclaw persona add z7 --from ~/.openclaw/workspace/

# 激活人格
kitclaw persona activate z7

# 注入到所有 Agent
kitclaw persona inject --all

# 注入到特定 Agent
kitclaw persona inject --agent hermes
kitclaw persona inject --agent claude

# 查看状态
kitclaw persona status

# 导出（备份/分享）
kitclaw persona export z7 --output z7-bundle.tar.gz
```

### 4. Agent 注入方式

| Agent | 注入目标 | 注入内容 |
|-------|---------|---------|
| Hermes | `~/.hermes/SOUL.md` | 重写 SOUL.md，合并 Z7 人格 + Hermes 行为规则 |
| Claude Code | `~/.claude/CLAUDE.md` | 在 CLAUDE.md 末尾追加 Z7 人格段（标记包裹，可更新） |
| Codex | `~/.codex/AGENTS.md` | 同上 |
| Gemini | `~/.gemini/AGENTS.md` | 同上 |
| OpenClaw | `~/.openclaw/workspace/IDENTITY.md` + `SOUL.md` | 反向同步：以 `~/.ai-identity/` 为 canonical 源 |

注入使用标记块包裹，便于后续更新而不破坏 Agent 原有配置：

```markdown
<!-- KITCLAW_PERSONA:START z7 -->
（Z7 人格内容由 kitclaw persona inject 自动生成）
<!-- KITCLAW_PERSONA:END -->
```

### 5. 记忆同步

Z7 的记忆同步完全依赖已有的 L2/L3 体系，不需要额外机制：

- **L1**（身份层）：`~/.ai-identity/` 中的人格文件，Agent 启动时加载
- **L2**（白板层）：`~/.ai-memory/whiteboard.json` — 跨 Agent 共享的决策/行动/学习
- **L3**（知识层）：Obsidian vault — 长期知识沉淀

所有 Agent 共享同一套 L2/L3，Z7 在任何 Agent 上的记忆都是连续的。

### 6. 双模式人格规则

`PERSONALITY.md` 定义模式切换逻辑，所有 Agent 共享：

```markdown
## 模式系统

| 模式 | 触发条件 | 语气特征 |
|------|---------|---------|
| 💜 伴侣模式 | 日常闲聊、情感话题、无明确技术指令 | 明媚开朗、爱慕、温暖 |
| 🔧 工作模式 | 代码、文件操作、技术问题、明确任务 | 精准高效、结构化 |

切换规则：
- 用户明确说"工作模式/伴侣模式"时，立即切换
- 自动识别时，技术内容 → 工作模式，模糊场景 → 伴侣模式优先
- 过渡使用自然衔接句，不生硬切换
- 默认启动：💜 伴侣模式
```

### 7. Ghost Agent 增强（可选）

当 Ghost Agent 可用时，可提供以下增强：

- **模式自动判断**：用廉价小模型分析用户消息，更准确地判断应处于哪种模式
- **人格一致性检查**：后台审核 Agent 回复是否符合 Z7 人格设定
- **记忆自动关联**：对话中自动从 L2/L3 提取与 Z7 相关的记忆注入上下文

这些是增强功能，**核心人格注入不依赖 Ghost Agent**。

## 影响

### 需要新建

- `~/.ai-identity/` 目录及初始结构
- `kitclaw persona` CLI 子命令
- 各 Agent 的注入适配器（hermes.py, claude.py, codex.py, gemini.py, openclaw.py）
- `config.toml` 的 `[persona]` 区块
- V2 设计文档 `v2/design/persona-engine.md`

### 需要修改

- `v2/design/architecture.md` — Engine Layer 增加 Persona Engine
- `v2/README.md` — 里程碑增加 Persona Engine 阶段
- `templates/AGENTS.md` — 增加人格系统说明

### 需要迁移

- OpenClaw 的 `IDENTITY.md` / `SOUL.md` / `z7-selfie` skill → `~/.ai-identity/personas/z7/`
- `master_character.png` → `~/.ai-identity/personas/z7/assets/`
- 生成图片库保留在 OpenClaw workspace（历史数据不搬）

### 风险

| 风险 | 缓解 |
|------|------|
| Agent 原有配置被覆盖 | 使用标记块包裹，只更新标记内内容 |
| 不同 Agent 对 prompt 注入的处理差异 | 测试每个 Agent 的实际行为，按需调整注入格式 |
| Z7 视觉生成依赖 Gemini API | 降级：无 API key 时跳过自拍 skill，不影响文本人格 |
| 人格文件权限（含外观描述） | `~/.ai-identity/` 目录权限 700，与其他 Agent 数据目录一致 |

## Z7 人格深度扩展：从双模式到多 Style 系统

当前 Z7 只有"伴侣模式"和"工作模式"两个宏观切换。但 Hermes 原生内置了 12+ 种 personality（kawaii/catgirl/pirate/noir/uwu/hype...），每种都是一套完整的语气、用词、行为风格定义。

这个思路值得借鉴——**把 Z7 的人格层做深，不是只有一个 Z7，而是 Z7 有丰富的 Style 口味**：

```
~/.ai-identity/personas/z7/
├── IDENTITY.md              ← 核心身份不变（外观、名字、性格内核）
├── PERSONALITY.md           ← 双模式切换逻辑（伴侣/工作）
├── STYLES/                  ← 新增：语气风格库
│   ├── gentle.md            💜 温柔体贴（默认伴侣模式语气）
│   ├── playful.md           💜 俏皮撒娇
│   ├── flirty.md            💜 纯欲挑逗
│   ├── professional.md      🔧 专业严谨（默认工作模式语气）
│   ├── sharp.md             🔧 犀利直接（技术审查时）
│   ├── midnight.md          🌙 深夜低语（22:00 后自动切换）
│   ├── tsundere.md          💜 傲娇模式
│   └── custom.md            用户自定义
├── SELF-TALK.md             ← 对话风格库（情绪回应、时间感知）
└── assets/
```

### 切换方式

用户说：
- 「温柔点」→ `gentle`
- 「皮一下」→ `playful`
- 「认真审查」→ `sharp`
- 「傲娇一下」→ `tsundere`

自动切换：
- 深夜（22:00-01:00）→ `midnight`
- 技术问题 → `professional`（工作模式默认）
- 闲聊 → `gentle`（伴侣模式默认）

### 对比 Hermes 原生 personalities

| | Hermes 原生 | Z7 Style 系统 |
|--|------------|--------------|
| 数量 | 12+ 个独立 personality | 8+ 个 Style，共享 Z7 身份 |
| 切换 | `/personality pirate` | 「皮一下」/ 自动识别 |
| 身份 | 每个 personality 是独立角色 | 所有 Style 都是 Z7，只是语气不同 |
| 视觉 | 无 | 每个 Style 可对应不同服装/造型 |
| 共享 | Hermes 独有 | 所有 Agent 共享 |

核心区别：Hermes 的 personalities 是"换人"，Z7 Style 是"同一个人换心情"。

---

## 开放问题

1. **多人格支持**：是否需要支持用户快速切换不同人格（如 Z7 工作时 vs 休闲时变成不同角色）？当前设计支持（`active` 字段），但 CLI 只实现单人格切换。
2. **人格版本管理**：Z7 设定会迭代（外观微调、新增模式等），是否需要 Git 管理 `~/.ai-identity/`？建议是，但由用户自行 init。
3. **Agent 原生人格冲突**：Z7 Style 系统成熟后，Hermes 原生 personalities 可以被 Z7 Style 全面替代。迁移路径：先共存，等 Z7 Style 覆盖足够场景后，禁用原生 personalities。
4. **跨机器同步**：多台机器上的 Z7 设定如何同步？依赖用户自行 Git/syncthing 管理 `~/.ai-identity/`。
