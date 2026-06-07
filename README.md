# QQ Group Filter Bot

智能 QQ 群聊消息过滤与总结机器人，基于 OneBot v11 协议。

## 功能特性

- 🤖 **自动采集**: 实时监听所有群聊消息并持久化存储
- 💬 **自然语言提问**: 直接在 QQ 私聊问机器人"最近群里有讨论实习吗"
- 🔍 **智能检索**: SQLite FTS5 全文搜索 + LLM 总结，自动提取时间范围和关键词
- 📌 **关注主题**: 定义长期关注的话题，定时生成摘要推送
- 📊 **带出处引用**: 回复包含 [群名] 发言人 (时间) 的具体引用

## 快速开始

### 1. 安装依赖

```bash
# 安装 uv（如果还没有）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆项目
git clone <your-repo-url>
cd qq-group-filter

# 同步依赖
uv sync
```

### 2. 配置

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env，填入必要的配置
# - BOT_QQ: 机器人 QQ 号
# - LLM_API_KEY: DeepSeek 或其他 OpenAI 兼容 API 的 key
# - ONEBOT_WS_URL: NapCat WebSocket 地址（默认 ws://localhost:3001）
```

### 3. 运行

```bash
uv run python -m qq_group_filter
```

## 使用指南

### 在 QQ 中与机器人交互

**自然语言提问**:
```
你: 最近群里有讨论 GPU 租赁吗
机器人: 📋 找到 2 条相关消息：
       [硬件交流群] 张三 (2026-06-05 14:23)
       > "AutoDL 3090 现在降价到 2.5/小时了..."
       
       💡 总结：有人推荐了 AutoDL 和恒源云的 GPU 租赁方案...
```

**管理关注主题**:
```
/interests add GPU租赁 关注 GPU 服务器租赁的优惠信息
/interests list
/interests remove 1
```

**生成每日摘要**:
```
/digest
```

## 技术架构

- **语言**: Python 3.10+ (asyncio)
- **存储**: SQLite + FTS5 全文索引
- **LLM**: OpenAI 兼容接口（默认 DeepSeek）
- **QQ 协议**: OneBot v11 (via NapCat/Lagrange.Core)
- **测试**: pytest + pytest-asyncio

## 文档

- [NapCat 接入指南](docs/NAPCAT_SETUP.md)
- [项目总结](docs/PROJECT_SUMMARY.md)

## 开发

```bash
# 运行测试
uv run pytest tests/ -v

# 代码覆盖率
uv run pytest tests/ --cov=src/qq_group_filter
```

## ⚠️ 风险提示

- 本项目通过第三方协议（OneBot v11）接入 QQ，**存在账号封禁风险**
- Tencent 未提供官方 Bot API，使用本项目即代表您理解并愿意承担相关风险
- 建议使用小号进行测试

## 许可证

MIT License

## 致谢

- [OneBot](https://github.com/botuniverse/onebot-11) - 标准化 QQ 机器人协议
- [NapCat](https://github.com/NapNeko/NapCatQQ) - 现代化的 OneBot v11 实现
- [DeepSeek](https://platform.deepseek.com/) - 高性价比的 LLM API
