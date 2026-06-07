# Proposal: QQ Group Message Filter Bot

## Problem Statement

用户加入了大量 QQ 群聊（工作群、技术群、社区群等），每天产生数百甚至上千条消息。大部分消息与用户当前关注的内容无关，手动翻看所有群记录时间成本高、容易遗漏关键信息。

用户需要一个智能助手，能够：
1. 自动监听所有群聊消息并存储
2. 理解用户的自然语言提问（如"最近群里有没有讨论关于实习的消息"）
3. 从海量历史消息中检索相关内容
4. 用大模型总结并给出带出处（群名、发言人、时间）的回答
5. 支持定义"长期关注主题"，定期推送摘要

## Proposed Solution

构建一个基于 **OneBot v11 协议**的 QQ 机器人，具备：

### Core Features
1. **消息采集与存储**
   - 通过 OneBot v11 WebSocket 连接到 NapCat/Lagrange.Core
   - 实时接收所有群消息并持久化到 SQLite（群名、发言人、时间、内容）
   - 支持全文检索（SQLite FTS5）

2. **自然语言问答**
   - 用户通过 QQ 私聊机器人提问（如："最近群里有人提到面试经验吗"）
   - 系统检索相关消息 → 调用 LLM（默认 DeepSeek，OpenAI 兼容接口）生成总结
   - 回复包含：摘要 + 具体出处（[群名] 张三 2026-06-05 14:23: "..."）

3. **关注主题管理**
   - 用户可定义长期关注的主题（如："实习机会", "GPU 服务器租赁"）
   - 定时/按需生成"过去 24 小时你关注的主题有这些更新"摘要

4. **交互方式**
   - **主要**：QQ 私聊机器人（用户直接在 QQ 里问，机器人回复）
   - **次要**：可选 CLI 命令行接口（方便脚本化/定时任务）

### Technical Stack
- **Language**: Python 3.10+
- **Framework**: asyncio + httpx
- **Storage**: aiosqlite (SQLite with FTS5 full-text search)
- **LLM Provider**: OpenAI-compatible API (default DeepSeek, configurable base_url)
- **QQ Integration**: OneBot v11 WebSocket client (connects to NapCat/Lagrange.Core)
- **Testing**: pytest + pytest-asyncio
- **Package Manager**: uv (Tsinghua mirror)
- **Deployment**: systemd service / Docker (optional)

### Architecture Principles
1. **Provider abstraction**: LLM provider 可插拔（复用 multi-agent-project 的 provider 模式）
2. **Adapter abstraction**: OneBot 客户端与业务逻辑解耦，未来可支持其他协议
3. **Safe demo mode**: 提供模拟 OneBot 事件生成器，无需真实 QQ 账号即可测试全流程
4. **Incremental storage**: 消息增量存储，支持断线重连后补齐缺失消息（通过 message_id）

## Success Criteria

- [ ] 能够连接到 NapCat 并接收真实群消息
- [ ] 存储至少 3 个群、100+ 条消息后，自然语言提问能准确检索并总结
- [ ] 端到端测试覆盖：接收群消息 → 私聊提问 → LLM 总结 → 回复
- [ ] 文档包含：README（项目说明）、NAPCAT_SETUP.md（从零接入 NapCat 的完整指南）
- [ ] 代码质量：类型注解、单元测试覆盖率 >70%、通过 pytest

## Out of Scope (Future Work)

- Web UI（当前版本聚焦 QQ 内交互）
- 语义向量检索（当前版本用关键词 + FTS，未来可接 embedding）
- 多轮对话上下文（当前版本每次提问独立处理）
- 群聊主动发言（机器人只在私聊中回复，不在群里发言）

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| QQ 账号封禁风险 | 文档明确警示风险；提供模拟模式供开发测试；建议用小号 |
| OneBot 协议变更 | 依赖成熟的 OneBot v11 标准，社区活跃；提供适配器抽象层 |
| LLM API 成本 | 默认 DeepSeek（0.1元/1M tokens，性价比高）；支持本地模型 |
| 消息量过大导致检索慢 | SQLite FTS5 优化；按时间范围预筛选；可选仅监听特定群 |

## Timeline Estimate

- Setup & Storage: 2 hours
- OneBot Client: 3 hours
- LLM Integration & Retrieval: 2 hours
- Bot Logic & Commands: 2 hours
- Testing & Documentation: 2 hours
- **Total**: ~11 hours (可在 1-2 天内完成)
