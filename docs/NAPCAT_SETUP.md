# NapCat 接入指南

本指南将帮助你从零开始配置 NapCat，让你的 QQ 群聊过滤机器人连接到真实的 QQ 账号。

## ⚠️ 重要警告

- **账号风险**：通过第三方协议登录 QQ 存在封号风险，建议使用小号测试
- **非官方协议**：NapCat 基于逆向工程，不受腾讯官方支持
- **自行承担风险**：使用本工具即表示您理解并愿意承担所有相关风险

---

## 前置要求

- Windows 10/11 或 Linux (Ubuntu 20.04+)
- QQ 小号（强烈建议，不要用主号）
- 本机器人项目已配置完成

---

## 步骤 1: 下载 NapCat

### Windows

1. 访问 [NapCat Releases](https://github.com/NapNeko/NapCatQQ/releases)
2. 下载最新版本的 `NapCat-win-x64.zip`
3. 解压到任意目录，例如 `C:\NapCat`

### Linux

```bash
# 下载最新版本（替换为实际版本号）
wget https://github.com/NapNeko/NapCatQQ/releases/download/v2.x.x/NapCat-linux-x64.tar.gz

# 解压
tar -xzf NapCat-linux-x64.tar.gz
cd NapCat
```

---

## 步骤 2: 配置 NapCat

### 创建配置文件

在 NapCat 目录下创建 `config/onebot11.json`:

```json
{
  "http": {
    "enable": false
  },
  "ws": {
    "enable": false
  },
  "reverseWs": {
    "enable": true,
    "urls": ["ws://127.0.0.1:8080"]
  },
  "wsServer": {
    "enable": true,
    "host": "0.0.0.0",
    "port": 3001
  },
  "debug": false,
  "heartInterval": 30000,
  "accessToken": "",
  "messagePostFormat": "array"
}
```

**配置说明：**
- `wsServer.enable`: 启用 WebSocket 服务器（我们的机器人作为客户端连接）
- `wsServer.port`: WebSocket 端口，默认 3001（与 `.env` 中的 `ONEBOT_WS_URL` 对应）
- `accessToken`: 访问令牌（可选，留空表示不验证）

如果需要安全性，设置 `accessToken` 为一个随机字符串，例如：
```json
"accessToken": "your_random_token_here_abc123"
```
然后在 `.env` 中设置：
```bash
ONEBOT_ACCESS_TOKEN=your_random_token_here_abc123
```

---

## 步骤 3: 启动 NapCat 并登录 QQ

### Windows

1. 双击 `NapCat.exe` 启动
2. 首次启动会弹出 QQ 登录窗口
3. **扫码登录**（推荐）：
   - 使用手机 QQ 扫描二维码
   - 在手机上确认登录
4. 登录成功后，NapCat 会在后台运行

### Linux

```bash
# 启动 NapCat
./NapCat

# 首次登录会生成二维码，使用手机 QQ 扫码登录
# 登录成功后按 Ctrl+C 停止，然后以 daemon 模式重启：
nohup ./NapCat > napcat.log 2>&1 &
```

---

## 步骤 4: 验证 NapCat 运行状态

检查 NapCat 日志，确认 WebSocket 服务器已启动：

```
[INFO] WebSocket server listening on ws://0.0.0.0:3001
[INFO] OneBot v11 protocol initialized
```

---

## 步骤 5: 配置并启动机器人

### 5.1 创建 `.env` 文件

在机器人项目根目录下，复制 `.env.example` 到 `.env`:

```bash
cp .env.example .env
```

### 5.2 编辑 `.env`

```bash
# OneBot WebSocket 配置
ONEBOT_WS_URL=ws://localhost:3001
ONEBOT_ACCESS_TOKEN=                    # 如果 NapCat 设置了 token，填入相同值
BOT_QQ=123456789                        # 你登录 NapCat 的 QQ 号

# LLM 配置
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-xxxxxxxxxxxxx            # 你的 DeepSeek API Key
LLM_MODEL=deepseek-chat
LLM_TIMEOUT=30

# 数据库路径
DB_PATH=./data/messages.db

# 可选：仅监听特定群（逗号分隔）
# MONITORED_GROUPS=123456789,987654321
```

**如何获取 DeepSeek API Key：**
1. 访问 [DeepSeek 开放平台](https://platform.deepseek.com/)
2. 注册账号并登录
3. 进入"API Keys"页面
4. 创建新的 API Key 并复制

### 5.3 启动机器人

```bash
# 确保依赖已安装
uv sync

# 启动机器人
uv run python -m qq_group_filter
```

如果一切正常，你会看到：

```
2026-06-06 15:30:00 - qq_group_filter.bot - INFO - Starting QQ Group Filter Bot...
2026-06-06 15:30:00 - qq_group_filter.bot - INFO - Bot QQ: 123456789
2026-06-06 15:30:00 - qq_group_filter.bot - INFO - Database initialized: ./data/messages.db
2026-06-06 15:30:00 - qq_group_filter.bot - INFO - LLM provider initialized: deepseek-chat
2026-06-06 15:30:00 - qq_group_filter.onebot_client - INFO - Connected to OneBot server: ws://localhost:3001
2026-06-06 15:30:00 - qq_group_filter.bot - INFO - ✅ Bot started successfully!
2026-06-06 15:30:00 - qq_group_filter.bot - INFO - Listening for messages... (Press Ctrl+C to stop)
```

---

## 步骤 6: 测试机器人

### 6.1 测试消息存储

1. 在机器人加入的任意群聊中发送几条测试消息
2. 检查机器人日志，确认消息已被存储

### 6.2 测试私聊查询

1. 用你自己的 QQ 号私聊机器人 QQ
2. 发送：`/help`
3. 机器人应该回复帮助信息
4. 发送：`最近群里有讨论xxx吗`（替换为你刚发的测试消息关键词）
5. 机器人应该返回总结和引用

---

## 常见问题

### Q1: 连接失败 "Connection refused"

**原因：** NapCat 未启动或端口不对

**解决：**
- 确认 NapCat 正在运行
- 检查 `config/onebot11.json` 中的 `wsServer.port` 是否为 3001
- 检查 `.env` 中的 `ONEBOT_WS_URL` 是否正确

### Q2: 登录后立即掉线

**原因：** QQ 号可能被风控

**解决：**
- 使用新注册的小号（避免使用老号）
- 尝试更换设备登录（不同的 deviceID）
- 等待一段时间后重试

### Q3: 机器人收不到群消息

**原因：** 可能群权限问题或 NapCat 配置问题

**解决：**
- 确认机器人 QQ 已加入该群
- 检查 `.env` 中的 `MONITORED_GROUPS` 是否过滤了该群
- 查看 NapCat 日志，确认事件已触发

### Q4: LLM API 调用失败

**原因：** API Key 错误或网络问题

**解决：**
- 确认 `LLM_API_KEY` 正确
- 测试网络连接：`curl https://api.deepseek.com/v1/chat/completions`
- 检查 API 额度是否用尽

### Q5: 机器人回复很慢

**原因：** LLM API 响应时间较长

**解决：**
- 检索消息过多，可以调整 `query.py` 中的 `limit` 参数
- 更换更快的 LLM 服务（如国内镜像）
- 增加 `LLM_TIMEOUT` 值

---

## 生产环境部署（可选）

### 使用 systemd（Linux）

创建 `/etc/systemd/system/qq-bot.service`:

```ini
[Unit]
Description=QQ Group Filter Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/qq-group-filter
ExecStart=/home/your_user/.local/bin/uv run python -m qq_group_filter
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable qq-bot
sudo systemctl start qq-bot
sudo systemctl status qq-bot
```

---

## 进阶配置

### 设置白名单群

编辑 `.env`，仅监听特定群：

```bash
MONITORED_GROUPS=123456789,987654321,555666777
```

### 自定义 LLM 提示词

编辑 `src/qq_group_filter/query.py` 中的 `_build_prompt` 方法，自定义总结风格。

### 调整搜索结果数量

编辑 `src/qq_group_filter/query.py`，修改 `limit=50` 为更大或更小的值。

---

## 参考链接

- [NapCat 官方文档](https://napneko.github.io/guide/napcat)
- [OneBot v11 标准](https://github.com/botuniverse/onebot-11)
- [DeepSeek API 文档](https://platform.deepseek.com/api-docs/)

---

**祝你使用愉快！如有问题，请查阅日志或提交 Issue。**
