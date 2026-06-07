# QQ 群聊过滤机器人 - 项目总结

## 项目概述

一个基于 **OneBot v11 协议**和**大语言模型**的智能 QQ 群聊消息过滤与总结工具。用户可以通过 QQ 私聊直接向机器人提问（如"最近群里有讨论实习吗"），机器人会从海量历史消息中检索相关内容并用 LLM 生成带出处的总结回复。

**开发时间**: 约 2 小时  
**代码行数**: 约 2600 行（包括测试）  
**测试覆盖**: 45 个测试用例，100% 通过

---

## 核心功能

✅ **自动采集群消息** - 实时监听所有 QQ 群聊，持久化存储到 SQLite  
✅ **自然语言提问** - 直接在 QQ 私聊问机器人，自动提取时间范围和关键词  
✅ **智能检索与总结** - SQLite FTS5 全文搜索 + DeepSeek LLM 总结，生成带出处的回复  
✅ **关注主题管理** - 定义长期关注话题（如"GPU租赁"、"实习机会"），定时生成摘要  
✅ **完整文档** - NapCat 接入指南、OpenSpec 设计文档、README

---

## 技术架构

### 技术栈
- **语言**: Python 3.10+ (asyncio 异步编程)
- **存储**: SQLite + aiosqlite + FTS5 全文索引
- **LLM**: OpenAI 兼容接口（默认 DeepSeek，可配置通义千问/Moonshot等）
- **QQ 协议**: OneBot v11 WebSocket 客户端（连接 NapCat/Lagrange.Core）
- **依赖管理**: uv（清华镜像）
- **测试**: pytest + pytest-asyncio

### 模块结构

```
src/qq_group_filter/
├── __init__.py           # 包初始化
├── __main__.py           # 入口点
├── config.py             # 配置管理 (pydantic-settings)
├── models.py             # 数据模型 (Pydantic)
├── persistence.py        # SQLite 存储层
├── llm_provider.py       # LLM API 客户端
├── onebot_client.py      # OneBot v11 WebSocket 客户端
├── onebot_message.py     # OneBot 消息段文本化
├── query.py              # 查询处理与总结逻辑
├── scheduler.py          # 每日关注主题摘要推送调度器
└── bot.py                # 主循环与事件路由

tests/
├── test_persistence.py       # 存储层测试（11 个用例）
├── test_llm_provider.py      # LLM provider 测试（3 个用例）
├── test_config.py            # 配置解析测试
├── test_onebot_client.py     # OneBot 客户端测试
├── test_onebot_messages.py   # OneBot 消息段文本化测试
├── test_scheduler.py         # 每日摘要调度测试
└── test_project_metadata.py  # 项目元数据测试
```

---

## 使用示例

### 自然语言提问

**用户**（私聊机器人）:
```
最近群里有讨论 GPU 租赁吗
```

**机器人回复**:
```
💬 有两个群提到了 GPU 租赁，主要讨论了 AutoDL 和恒源云的价格对比...

📋 相关消息：
1. [硬件交流群] 张三 (2026-06-05 14:23)
   "AutoDL 3090 现在降价到 2.5/小时了..."
```

---

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 配置 .env
cp .env.example .env
# 编辑 .env，填入 BOT_QQ、LLM_API_KEY

# 3. 启动 NapCat（参考 docs/NAPCAT_SETUP.md）

# 4. 启动机器人
uv run python -m qq_group_filter
```

详细接入指南请查看 [NAPCAT_SETUP.md](NAPCAT_SETUP.md)

---

## 项目文档

- **../README.md** - 项目介绍和快速开始
- **NAPCAT_SETUP.md** - NapCat 完整接入指南
- **../openspec/changes/qq-group-filter-bot/** - OpenSpec 设计文档
  - proposal.md - 需求和解决方案
  - design.md - 架构设计
  - specs.md - 功能规格
  - tasks.md - 任务清单

---

## 测试

```bash
# 运行所有测试
uv run pytest tests/ -v

# 代码覆盖率
uv run pytest tests/ --cov=src/qq_group_filter
```

所有 45 个测试用例均通过 ✅

---

## 许可证

MIT License
