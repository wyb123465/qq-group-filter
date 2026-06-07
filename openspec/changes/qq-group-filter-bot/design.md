# Design: QQ Group Filter Bot

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         User (QQ)                           │
└────────────┬────────────────────────────────────────────────┘
             │ Private Message: "最近群里有讨论实习吗?"
             ↓
┌─────────────────────────────────────────────────────────────┐
│                    NapCat / Lagrange.Core                   │
│                  (OneBot v11 WebSocket Server)              │
└────────────┬────────────────────────────────────────────────┘
             │ WebSocket (群消息事件 + 私聊事件)
             ↓
┌─────────────────────────────────────────────────────────────┐
│                   OneBot Client (bot.py)                    │
│  - WebSocket 连接管理、心跳、重连                              │
│  - 事件解析 (group_message, private_message)                │
│  - 发送消息 API                                              │
└────┬────────────────────────────────────────────┬───────────┘
     │ group_message                             │ private_message
     ↓                                           ↓
┌─────────────────────┐              ┌────────────────────────┐
│  Message Store      │              │   Query Handler        │
│  (persistence.py)   │              │   (query.py)           │
│  - SQLite + FTS5    │              │  - 解析用户意图          │
│  - 群消息增量存储     │              │  - 检索相关消息          │
│  - 关注主题管理       │              │  - 调用 LLM 总结        │
└─────────────────────┘              └──────┬─────────────────┘
                                            │
                                            ↓
                               ┌────────────────────────────┐
                               │   LLM Provider             │
                               │   (llm_provider.py)        │
                               │  - OpenAI-compatible API   │
                               │  - DeepSeek/通义千问/...    │
                               └────────────────────────────┘
```

## Component Design

### 1. Configuration (`config.py`)

```python
from pydantic_settings import BaseSettings

class Config(BaseSettings):
    # OneBot WebSocket
    onebot_ws_url: str = "ws://localhost:3001"
    onebot_access_token: str = ""
    
    # Bot QQ number (机器人自己的 QQ 号)
    bot_qq: int
    
    # LLM Provider
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str
    llm_model: str = "deepseek-chat"
    llm_timeout: int = 30
    
    # Storage
    db_path: str = "./data/messages.db"
    
    # Monitoring (optional)
    monitored_groups: list[int] | None = None  # None = monitor all
    
    class Config:
        env_file = ".env"
```

### 2. Data Models (`models.py`)

```python
from pydantic import BaseModel, Field
from datetime import datetime

class GroupMessage(BaseModel):
    """群消息"""
    message_id: int
    group_id: int
    group_name: str
    user_id: int
    user_nickname: str
    message: str
    timestamp: datetime

class PrivateMessage(BaseModel):
    """私聊消息"""
    message_id: int
    user_id: int
    user_nickname: str
    message: str
    timestamp: datetime

class Interest(BaseModel):
    """用户关注的主题"""
    id: int | None = None
    user_id: int
    keyword: str
    description: str
    created_at: datetime = Field(default_factory=datetime.now)
    active: bool = True

class QueryResult(BaseModel):
    """检索结果"""
    summary: str
    sources: list[dict]  # [{group_name, user_nickname, timestamp, snippet}]
```

### 3. Storage Layer (`persistence.py`)

```python
class MessageStore:
    """消息存储与检索"""
    
    async def init_db(self):
        """初始化数据库，创建表和 FTS5 索引"""
        
    async def save_group_message(self, msg: GroupMessage):
        """存储群消息（幂等，基于 message_id）"""
        
    async def search_messages(
        self,
        query: str,
        group_ids: list[int] | None = None,
        start_time: datetime | None = None,
        limit: int = 50
    ) -> list[GroupMessage]:
        """全文检索消息
        - FTS5 关键词搜索
        - 按时间倒序
        - 支持群过滤
        """
        
    async def add_interest(self, user_id: int, keyword: str, desc: str):
        """添加关注主题"""
        
    async def get_interests(self, user_id: int) -> list[Interest]:
        """获取用户的所有关注主题"""
```

**Schema:**
```sql
-- 群消息表
CREATE TABLE group_messages (
    message_id INTEGER PRIMARY KEY,
    group_id INTEGER NOT NULL,
    group_name TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    user_nickname TEXT NOT NULL,
    message TEXT NOT NULL,
    timestamp INTEGER NOT NULL
);

-- FTS5 全文索引
CREATE VIRTUAL TABLE messages_fts USING fts5(
    message, 
    content='group_messages', 
    content_rowid='message_id',
    tokenize='unicode61'
);

-- 关注主题表
CREATE TABLE interests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    description TEXT,
    created_at INTEGER NOT NULL,
    active INTEGER DEFAULT 1
);
```

### 4. OneBot Client (`onebot_client.py`)

```python
class OneBotClient:
    """OneBot v11 WebSocket 客户端"""
    
    async def connect(self):
        """建立 WebSocket 连接，发送认证"""
        
    async def listen(self):
        """监听事件循环
        - 心跳响应
        - 分发 group_message / private_message 事件
        - 自动重连
        """
        
    async def send_private_message(self, user_id: int, message: str):
        """发送私聊消息"""
        
    async def send_group_message(self, group_id: int, message: str):
        """发送群消息（可选，未来扩展）"""
        
    def on_group_message(self, callback):
        """注册群消息事件处理器"""
        
    def on_private_message(self, callback):
        """注册私聊消息事件处理器"""
```

**Event Format (OneBot v11 Standard):**
```json
// 群消息事件
{
  "post_type": "message",
  "message_type": "group",
  "sub_type": "normal",
  "message_id": 12345,
  "group_id": 123456789,
  "user_id": 987654321,
  "message": "大家好",
  "raw_message": "大家好",
  "sender": {
    "user_id": 987654321,
    "nickname": "张三",
    "card": "张三-前端"
  },
  "time": 1717660800
}

// 私聊消息事件
{
  "post_type": "message",
  "message_type": "private",
  "sub_type": "friend",
  "message_id": 12346,
  "user_id": 111222333,
  "message": "最近群里有讨论实习吗",
  "sender": {
    "user_id": 111222333,
    "nickname": "李四"
  },
  "time": 1717660900
}
```

### 5. LLM Provider (`llm_provider.py`)

```python
class LLMProvider:
    """OpenAI 兼容的 LLM 调用"""
    
    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """调用 chat/completions API"""
        # POST {base_url}/chat/completions
        # Body: {model, messages, temperature, max_tokens}
```

### 6. Query Handler (`query.py`)

```python
class QueryHandler:
    """处理用户提问"""
    
    async def handle_query(
        self,
        user_id: int,
        query_text: str
    ) -> QueryResult:
        """
        1. 提取时间范围（"最近"→过去24小时，"昨天"→具体日期）
        2. 提取关键词（用简单 NLP 或直接用全句）
        3. 调用 MessageStore.search_messages
        4. 构造 prompt 给 LLM 总结
        5. 返回总结 + 引用
        """
        
    async def generate_daily_digest(
        self,
        user_id: int
    ) -> str:
        """生成用户关注主题的每日摘要"""
```

**Prompt Template:**
```
你是一个 QQ 群聊消息助手。用户问了这个问题：
"{user_query}"

我从群聊历史中检索到以下相关消息：
{retrieved_messages}

请用中文总结这些消息，回答用户的问题。要求：
1. 直接回答问题，简洁明了
2. 如果有多个相关讨论，分点说明
3. 每个要点后标注出处：[群名] 发言人 时间
4. 如果没有相关消息，明确告诉用户"未找到相关讨论"
```

### 7. Bot Main Loop (`bot.py`)

```python
async def main():
    config = Config()
    store = MessageStore(config.db_path)
    await store.init_db()
    
    llm = LLMProvider(config)
    query_handler = QueryHandler(store, llm)
    
    client = OneBotClient(config.onebot_ws_url, config.onebot_access_token)
    
    @client.on_group_message
    async def handle_group_msg(event):
        """群消息 → 存储"""
        msg = GroupMessage(
            message_id=event["message_id"],
            group_id=event["group_id"],
            group_name=event.get("group_name", str(event["group_id"])),
            user_id=event["sender"]["user_id"],
            user_nickname=event["sender"]["nickname"],
            message=event["message"],
            timestamp=datetime.fromtimestamp(event["time"])
        )
        await store.save_group_message(msg)
    
    @client.on_private_message
    async def handle_private_msg(event):
        """私聊消息 → 处理命令或提问"""
        user_id = event["user_id"]
        text = event["message"].strip()
        
        # 命令路由
        if text.startswith("/help"):
            await client.send_private_message(user_id, HELP_TEXT)
        elif text.startswith("/interests"):
            # 管理关注主题
            pass
        elif text.startswith("/digest"):
            # 生成摘要
            digest = await query_handler.generate_daily_digest(user_id)
            await client.send_private_message(user_id, digest)
        else:
            # 自然语言提问
            result = await query_handler.handle_query(user_id, text)
            reply = format_reply(result)
            await client.send_private_message(user_id, reply)
    
    await client.connect()
    await client.listen()  # 阻塞运行

if __name__ == "__main__":
    asyncio.run(main())
```

## Data Flow Examples

### Example 1: 用户提问 "最近群里有讨论实习吗"

1. **Event**: OneBot 发送 `private_message` 事件
2. **Parse**: `handle_private_msg` 识别为提问（非命令）
3. **Query**: `query_handler.handle_query("最近群里有讨论实习吗")`
   - 解析时间范围：过去 24 小时
   - 关键词："实习"
   - `store.search_messages(query="实习", start_time=24h_ago, limit=50)`
4. **Retrieve**: SQLite FTS5 返回 5 条匹配消息
5. **Summarize**: 构造 prompt → 调用 DeepSeek API
6. **Reply**: 格式化回复（摘要 + 出处）→ `client.send_private_message`

### Example 2: 自动摘要

- Cron job 每天 8:00 触发
- 遍历有关注主题的用户
- 为每个用户生成摘要：检索过去 24h 包含其关注关键词的消息 → LLM 总结
- 发送摘要到用户私聊

## Testing Strategy

### Unit Tests
- `test_persistence.py`: 存储、检索、FTS
- `test_onebot_client.py`: 事件解析、消息格式化
- `test_llm_provider.py`: API 调用（mock httpx）
- `test_query.py`: 提问处理逻辑（mock LLM）

### Integration Tests
- `test_e2e.py`: 模拟 OneBot 事件 → 存储 → 私聊提问 → 回复

### Manual Tests
- 连接真实 NapCat → 观察日志
- 在 QQ 私聊中提问 → 验证回复准确性

## Deployment

### Option 1: Systemd Service (Linux)
```ini
[Unit]
Description=QQ Group Filter Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/qq-group-filter
ExecStart=/home/ubuntu/.local/bin/uv run python -m qq_group_filter
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Option 2: Docker
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv sync
CMD ["uv", "run", "python", "-m", "qq_group_filter"]
```

## Security Considerations

1. **API Key 保护**: `.env` 文件加入 `.gitignore`，禁止提交到版本控制
2. **Access Token**: OneBot access_token 配置验证，防止未授权连接
3. **用户隔离**: 每个用户的关注主题、摘要权限隔离（当前版本单用户，未来多用户需鉴权）
4. **Rate Limiting**: LLM API 调用加频率限制，防止滥用
5. **敏感信息过滤**: 不记录包含手机号、身份证等敏感信息的消息（可选）

## Performance Considerations

- **SQLite FTS5**: 100k+ 消息检索性能良好（< 100ms）
- **Index Strategy**: 群 ID + 时间戳索引，加速按群过滤
- **Message Retention**: 可选自动清理 30 天前的消息（节省空间）
- **Concurrent Queries**: asyncio 支持并发处理多个私聊提问

## Future Enhancements

- 语义向量检索（embedding + FAISS/Qdrant）
- 多轮对话上下文（记住用户对话状态）
- Web UI 可视化（群消息统计、热词云图）
- 支持更多消息类型（图片 OCR、文件摘要）
