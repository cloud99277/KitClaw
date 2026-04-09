---
title: "Ghost Agent 方案深度审查"
status: draft
created: 2026-04-07
relates_to: ["rfcs/002-ghost-agent-backend.md"]
---

# Ghost Agent 方案深度审查

> **审查视角**：安全架构师 + 运维工程师 + 偏执的用户
> **目标**：在写一行代码之前，把所有会爆的地方找出来

---

## 1. API Key 安全

### 问题

API Key 存在哪里？当前设计是 `~/.kitclaw/config.toml`：

```toml
[llm_backend]
provider = "google"
model = "gemini-2.5-flash"
api_key = "AIza..."     # 明文！
```

这个文件对所有 Agent 可见。任何被 Agent 执行的 skill 脚本都能 `cat ~/.kitclaw/config.toml` 拿到 key。

### 风险等级：🟡 中

- 已有先例：Claude Code 的 API key 也是明文存在 `~/.claude/` 下
- 但 KitClaw 的定位是"跨 Agent 共享"，意味着更多进程可能接触到这个文件

### 对策

```
优先级链：
1. 环境变量 KITCLAW_LLM_API_KEY（推荐，不落盘）
2. OS keychain（macOS Keychain / Windows Credential Manager / Linux secret-tool）
3. config.toml 明文（最后手段，文件权限 600）
```

在 `kitclaw init` 时：
- 默认引导到环境变量方式
- 如果用户坚持写 config.toml，自动 `chmod 600`
- 在 `kitclaw doctor` 中检查：如果 config.toml 权限 > 600 且含 api_key，报警告

---

## 2. 成本控制

### 问题

`kitclaw session end` 内部要把整段对话发给 Ghost Agent 做压缩/提取。如果一个 200k token 的长对话：

| 模型 | 输入成本 (200k tokens) | 输出成本 (~2k tokens) | 总计 |
|------|----------------------|---------------------|------|
| Gemini 2.5 Flash | ~$0.01 | ~$0.001 | **~$0.01** |
| Claude Haiku 3.5 | ~$0.10 | ~$0.05 | **~$0.15** |
| GPT-4o-mini | ~$0.03 | ~$0.01 | **~$0.04** |
| DeepSeek Chat | ~$0.01 | ~$0.005 | **~$0.015** |

### 风险等级：🟢 低（Flash/DeepSeek 成本几乎可忽略）

### 对策

- 默认推荐 Gemini 2.5 Flash（最便宜 + 100 万上下文窗口）
- `kitclaw status` 中显示累计 API 成本
- 设置可选的月度成本上限（`[llm_backend] monthly_budget = 5.00`）
- 超限后降级为非 LLM 模式（见第 5 点）

---

## 3. 延迟与阻塞

### 问题

`kitclaw session end` 变成了一个**同步网络请求**。

- 200k tokens 输入 + 2k 输出，Gemini Flash 大约需要 **3-8 秒**
- 如果网络慢或 API 限流，可能 **15-30 秒**
- 用户在 IDE 终端里敲完 `kitclaw session end`，等 8 秒... 可以接受吗？

### 风险等级：🟡 中

Agent 调用时不存在人类体验问题（Agent 本身也在等 API）。但如果**用户直接在终端敲**命令，8 秒空白是烦人的。

### 对策

```
1. 进度提示：
   kitclaw session end
   ⠋ 正在压缩上下文 (187k tokens → Flash)...
   ⠋ 正在提取记忆...
   ✓ 完成 (6.2s)

2. 异步选项：
   kitclaw session end --async
   → 后台 fork 子进程处理，立即返回
   → 结果写到 ~/.kitclaw/pending/ 下
   → 下次 kitclaw 命令时自动合并

3. 超时保护：
   - 默认 30 秒超时
   - 超时后降级：保存原始对话快照（不压缩），打印警告
   - 不因为 API 超时导致会话数据丢失
```

---

## 4. 隐私与数据泄露

### 问题

这是**最严重的设计张力**。

Ghost Agent 机制意味着：**用户的整段对话（可能包含源代码、密码、商业秘密）被发送到第三方 API 服务器。**

某些场景下这是不可接受的：
- 企业内网开发环境
- 政府/军工项目
- 包含 API key、数据库密码的对话
- 敏感商业代码

### 风险等级：🔴 高

### 对策

这是一个**架构级**需要解决的问题，不是一个小 flag 能搞定的：

```
方案 1：数据脱敏预处理（推荐作为默认行为）
  - 发送前，用正则/启发式扫描对话内容
  - 替换所有 API key、密码、token、连接字符串为 [REDACTED]
  - 替换文件路径中的敏感部分
  - 扫描模式可配置（~/.kitclaw/config.toml 中的 [privacy] 区块）

方案 2：本地模型选项（Ollama）
  [llm_backend]
  provider = "ollama"               # 完全本地，零数据外传
  model = "qwen2.5:7b"
  endpoint = "http://localhost:11434"
  
  - 对隐私敏感用户是终极解决方案
  - 质量比 Flash 低但对压缩/提取够用
  - 需要用户本地有 GPU 或能接受慢速

方案 3：完全禁用 Ghost Agent
  [llm_backend]
  enabled = false
  
  - 退化为 v1 行为：无自动压缩/提取
  - 但 CLI 统一入口、Session 管理、Governance 等非 LLM 功能依然可用
  - 这保证了：没有 API key 的用户也能用 KitClaw v2
```

**配置文件新增**：

```toml
[privacy]
redact_before_send = true           # 默认开启脱敏
redact_patterns = [
  "(?i)(api[_-]?key|token|secret|password)\\s*[=:]\\s*\\S+",
  "(?i)(mongodb|postgresql|mysql)://\\S+",
  "sk-[a-zA-Z0-9]{20,}",           # OpenAI key pattern
  "AIza[a-zA-Z0-9_-]{35}",         # Google API key pattern
]
redact_file_paths = true            # 替换 /home/username/ 为 /home/[USER]/
```

---

## 5. 优雅降级（Graceful Degradation）

### 问题

Ghost Agent 不是一个"总是可用"的基础设施：
- 用户可能没配 API key
- API 可能宕机
- 网络可能断开
- 可能超出月度预算

如果 Ghost Agent 不可用时整个 KitClaw 瘫痪，那这个架构就失败了。

### 风险等级：🔴 高

### 对策：三级降级策略

```
Level 0：Ghost Agent 可用（正常模式）
  ↓ API 不可用
Level 1：提取式摘要（无 LLM 降级）
  - 用启发式规则提取关键信息
  - 保留最后 N 条消息 + 所有包含 [decision]/[action] 的消息
  - 提取文件路径、错误信息、命令等结构化数据
  - 质量不如 LLM 但不丢数据
  ↓ 提取也失败
Level 2：原始快照保存（兜底）
  - 原封不动保存对话 JSON（gzip 压缩）
  - 下次 kitclaw 启动时如果 Ghost Agent 恢复，补做处理
  - 绝不丢失任何用户数据
```

**关键原则：Ghost Agent 是增强层，不是必要层。KitClaw v2 的所有非 LLM 功能（CLI、Session、Governance、Observability）必须在没有 API key 的情况下完全正常工作。**

---

## 6. Ghost Agent 自身的上下文窗口限制

### 问题

如果对话有 300k tokens，发给 Ghost Agent：
- Gemini 2.5 Flash（1M 窗口）→ ✅ 无问题
- Claude Haiku（200k 窗口）→ ⚠️ 可能装不下
- Ollama 本地模型（通常 8k-32k 窗口）→ ❌ 完全装不下

### 风险等级：🟡 中

### 对策

```python
def prepare_for_ghost_agent(messages, ghost_model_context_window):
    """如果对话超过 Ghost Agent 的窗口，先做预裁剪"""
    
    total_tokens = estimate_tokens(messages)
    
    if total_tokens <= ghost_model_context_window * 0.8:
        return messages  # 装得下，全量发送
    
    # 策略：保留首尾 + 采样中间
    # 1. 保留第一条消息（原始请求）
    # 2. 保留最后 20% 的消息（最新状态）
    # 3. 中间部分按优先级采样：
    #    - 包含 [decision]/[action] 的消息优先保留
    #    - 包含错误信息的消息优先保留
    #    - 其余等间距采样
    
    budget = int(ghost_model_context_window * 0.7)  # 留 30% 给 prompt + output
    return smart_truncate(messages, budget)
```

---

## 7. 输出解析的鲁棒性

### 问题

Ghost Agent 的输出需要被解析为结构化数据（JSON）。但 LLM 输出本质上不可靠：
- 可能返回 markdown 包裹的 JSON
- 可能多一个逗号
- 可能幻觉出不存在的字段
- 可能返回与预期完全不同的格式

### 风险等级：🟡 中

### 对策

```python
def parse_ghost_response(raw: str, expected_type: str) -> dict | None:
    """鲁棒的 Ghost Agent 输出解析"""
    
    # 1. 尝试直接 JSON parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    
    # 2. 提取 ```json ... ``` 代码块
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 3. 尝试修复常见 JSON 错误（尾逗号、单引号等）
    fixed = fix_common_json_errors(raw)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    
    # 4. 如果是压缩任务，纯文本也能用
    if expected_type == "compact":
        return {"summary": raw, "format": "raw_text"}
    
    # 5. 全部失败 → 记录日志，返回 None
    log_warning(f"Ghost Agent 输出无法解析: {raw[:200]}...")
    return None
```

---

## 8. 离线/无网络环境

### 问题

部分开发者在：
- 飞机上
- 企业内网（无外网）
- 网络不稳定的环境

Ghost Agent 完全无法工作。

### 风险等级：🟡 中

### 对策

| 环境 | Ghost Agent 可用？ | 降级策略 |
|------|-------------------|----------|
| 正常网络 | ✅ | 正常使用 |
| 无网络 | ❌ | Level 1 提取式摘要 + Level 2 原始快照 |
| 有本地 Ollama | ✅ | provider = "ollama"，完全离线可用 |
| 内网有代理 | ✅ | 支持 HTTP_PROXY 环境变量 |

在 `kitclaw init` 时检测网络：
```
检测到无法连接 API... 
您可以：
  1. 配置 Ollama 本地模型（完全离线）
  2. 跳过 Ghost Agent 配置（使用降级模式）
  3. 稍后手动配置（kitclaw config set llm_backend.provider google）
```

---

## 9. 并发与文件锁的实际可靠性

### 问题

文件锁在以下场景不可靠：
- NFS / 网络文件系统：`fcntl.flock()` 可能不生效
- WSL 跨边界：Windows 进程和 WSL 进程同时访问同一文件
- 进程崩溃：锁文件残留导致死锁

### 风险等级：🟡 中

### 对策

```python
import fcntl
import os
import time

class FileLock:
    """基于 lockfile 的排他锁（非 flock，更可靠）"""
    
    def __init__(self, target_path: str, timeout: int = 10):
        self.lock_path = target_path + ".lock"
        self.timeout = timeout
        self.fd = None
    
    def acquire(self):
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            try:
                # O_CREAT | O_EXCL：原子创建，已存在则失败
                self.fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                # 写入 PID + 时间戳（用于死锁检测）
                os.write(self.fd, f"{os.getpid()}:{time.time()}\n".encode())
                return True
            except FileExistsError:
                # 检查是否为陈旧锁（进程已死或超过 60 秒）
                if self._is_stale_lock():
                    os.unlink(self.lock_path)
                    continue
                time.sleep(0.1)
        raise TimeoutError(f"无法获取文件锁: {self.lock_path}")
    
    def release(self):
        if self.fd is not None:
            os.close(self.fd)
            try:
                os.unlink(self.lock_path)
            except FileNotFoundError:
                pass
    
    def _is_stale_lock(self) -> bool:
        """检测是否为过期/死进程的残留锁"""
        try:
            with open(self.lock_path) as f:
                content = f.read().strip()
            pid_str, ts_str = content.split(":")
            pid = int(pid_str)
            ts = float(ts_str)
            # 进程已死？
            try:
                os.kill(pid, 0)  # 不发信号，只检查存在性
            except OSError:
                return True  # 进程不存在
            # 超过 60 秒？
            return (time.time() - ts) > 60
        except (ValueError, FileNotFoundError, PermissionError):
            return True  # 无法解析 = 视为过期
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, *args):
        self.release()
```

**使用**：
```python
with FileLock("~/.ai-memory/topics/project-kitclaw.md"):
    # 读取、去重、追加写入
    ...
```

---

## 10. "零外部依赖"原则的妥协评估

### 问题

v1 以"纯 Python stdlib"为荣。Ghost Agent 引入了：
- HTTP API 调用（可用 stdlib `urllib.request`）
- JSON 解析（stdlib `json`）
- gzip 压缩（stdlib `gzip`）

实际上 **sklearn/tiktoken 等可选依赖之外，核心功能仍然可以保持零外部依赖**。

### 结论：🟢 可以接受

```python
# 用 stdlib 实现 API 调用（无需 requests/httpx）
import urllib.request
import json

def call_ghost_agent(prompt: str, config: dict) -> str:
    """用纯 stdlib 调用 LLM API"""
    
    provider = config["provider"]
    
    if provider == "google":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{config['model']}:generateContent"
        headers = {"Content-Type": "application/json"}
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}]
        }).encode()
        url += f"?key={config['api_key']}"
    
    elif provider == "anthropic":
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": config["api_key"],
            "anthropic-version": "2023-06-01"
        }
        body = json.dumps({
            "model": config["model"],
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
    
    elif provider == "openai":
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}"
        }
        body = json.dumps({
            "model": config["model"],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096
        }).encode()
    
    elif provider == "ollama":
        url = f"{config.get('endpoint', 'http://localhost:11434')}/api/generate"
        headers = {"Content-Type": "application/json"}
        body = json.dumps({
            "model": config["model"],
            "prompt": prompt,
            "stream": False
        }).encode()
    
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    
    # 统一提取文本
    return extract_text_from_response(result, provider)
```

**零外部依赖得以保持。**

---

## 11. 综合决策矩阵

| 风险点 | 严重度 | 对策 | 对策复杂度 |
|--------|--------|------|-----------|
| API Key 安全 | 🟡 | 环境变量优先 + chmod 600 | 低 |
| 成本 | 🟢 | Flash 默认 + 月度上限 | 低 |
| 延迟/阻塞 | 🟡 | 进度提示 + --async + 超时降级 | 中 |
| **隐私/数据泄露** | **🔴** | **脱敏 + Ollama 本地 + 可禁用** | **高** |
| **优雅降级** | **🔴** | **三级降级策略** | **中** |
| 上下文窗口溢出 | 🟡 | 预裁剪（保留首尾 + 采样中间） | 中 |
| 输出解析鲁棒性 | 🟡 | 多级 fallback 解析 | 低 |
| 离线环境 | 🟡 | Ollama + 降级模式 | 低 |
| 文件锁可靠性 | 🟡 | lockfile（非 flock）+ 死锁检测 | 中 |
| 外部依赖 | 🟢 | 纯 stdlib urllib 即可 | 低 |

---

## 12. 最终结论与修订建议

### Ghost Agent 方案：✅ 审查通过，但需要修补 2 个严重盲点

1. **🔴 隐私保护必须是一等公民**
   - 在 `config.toml` 中增加 `[privacy]` 区块
   - 默认开启 `redact_before_send = true`
   - 支持 `provider = "ollama"` 作为零数据外传方案
   - 支持 `enabled = false` 完全禁用

2. **🔴 优雅降级必须设计进架构**
   - Ghost Agent 是增强层不是必要层
   - 三级降级：LLM → 提取式 → 原始快照
   - 没有 API key 的用户必须能正常使用所有非 LLM 功能

### 修订后的 config.toml 完整设计

```toml
[llm_backend]
enabled = true                        # false = 完全禁用 Ghost Agent
provider = "google"                   # google | anthropic | openai | deepseek | ollama
model = "gemini-2.5-flash"
# api_key 优先从环境变量 KITCLAW_LLM_API_KEY 读取
# 如果未设环境变量，从这里读取（不推荐）
# api_key = ""
endpoint = ""                         # Ollama 或自定义 endpoint
timeout = 30                          # API 超时秒数
monthly_budget = 5.00                 # 月度预算上限（美元），0 = 无上限
retry_max = 2                         # 失败重试次数
fallback_on_failure = true            # 失败时降级为非 LLM 模式

[privacy]
redact_before_send = true             # 发送前脱敏
redact_patterns = [                   # 正则模式列表
  "(?i)(api[_-]?key|token|secret|password)\\s*[=:]\\s*\\S+",
  "sk-[a-zA-Z0-9]{20,}",
  "AIza[a-zA-Z0-9_-]{35}",
]
redact_file_paths = true              # 替换用户名路径为 [USER]
```
