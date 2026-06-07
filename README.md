# QQ Group Filter Bot

智能 QQ 群聊消息过滤与总结机器人，基于 OneBot v11 协议 + TypeScript。

## 功能特性

- 🤖 **自动采集**: 实时监听所有群聊消息并持久化存储（SQLite + FTS5）
- 💬 **自然语言提问**: 直接在 QQ 私聊问机器人"最近群里有讨论实习吗"
- 🔍 **智能检索**: FTS5 全文搜索 + LLM 总结，自动提取时间范围和关键词
- 📌 **关注主题**: 定义长期关注的话题，定时生成摘要推送
- 📊 **每日推送**: 每天自动推送关注主题的更新（可配置时间）
- 🔄 **自动重连**: WebSocket 断线自动重连（指数退避）

## 技术栈

- **语言**: TypeScript (Node.js 20+)
- **协议**: OneBot v11 WebSocket (连接 NapCat/Lagrange.Core)
- **存储**: better-sqlite3 + FTS5 全文索引
- **LLM**: OpenAI 兼容接口（默认 DeepSeek）
- **校验**: Zod schema validation
- **测试**: Vitest (28 个用例)

## 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env，填入必要配置
```

### 3. 运行

```bash
npm start
```

### 开发模式（热重载）

```bash
npm run dev
```

## 使用指南

### 在 QQ 中与机器人交互

**自然语言提问**:
```
你: 最近群里有讨论 GPU 租赁吗
机器人: 💬 有两个群提到了 GPU 租赁...
       📋 相关消息：
       1. [硬件群] 张三 (2026-06-07 14:23)
          AutoDL 3090 降价到 2.5/小时了...
```

**管理关注主题**:
```
/interests add GPU租赁 关注 GPU 服务器租赁的优惠信息
/interests list
/interests remove 1
```

**手动生成摘要**:
```
/digest
```

## 项目结构

```
src/
├── main.ts              # 入口
├── bot.ts               # 主循环与事件路由
├── config.ts            # 配置管理 (Zod)
├── models.ts            # 数据模型
├── persistence.ts       # SQLite 存储 + FTS5
├── llm.ts               # LLM API 客户端
├── onebot-client.ts     # OneBot v11 WebSocket 客户端
├── onebot-message.ts    # 消息段文本化
├── query.ts             # 查询处理与总结
└── scheduler.ts         # 定时摘要推送

tests/
├── persistence.test.ts  # 存储层 (12 用例)
├── query.test.ts        # 查询逻辑 (6 用例)
├── onebot-message.test.ts # 消息解析 (4 用例)
└── integration.test.ts  # 集成测试 (6 用例)
```

## 开发

```bash
# 类型检查
npm run lint

# 运行测试
npm test

# 监听模式测试
npm run test:watch
```

## NapCat 接入指南

详见 [docs/NAPCAT_SETUP.md](docs/NAPCAT_SETUP.md)

## ⚠️ 风险提示

- 本项目通过第三方协议（OneBot v11）接入 QQ，**存在账号封禁风险**
- 建议使用小号进行测试
- Tencent 未提供官方 Bot API

## 许可证

MIT License
