# Specifications: QQ Group Filter Bot

## 1. System Overview

**Name**: QQ Group Filter Bot (qq-group-filter)  
**Purpose**: Intelligent QQ group message filtering and summarization using LLM  
**Platform**: Python 3.10+, asyncio-based  
**Deployment**: Single-process daemon, systemd/Docker  

---

## 2. Functional Requirements

### FR-1: Message Collection
- **FR-1.1**: Bot MUST connect to OneBot v11 WebSocket server (NapCat/Lagrange.Core)
- **FR-1.2**: Bot MUST receive and store all group messages from monitored groups
- **FR-1.3**: Bot MUST store: message_id, group_id, group_name, user_id, user_nickname, message content, timestamp
- **FR-1.4**: Storage MUST be idempotent (duplicate message_ids ignored)
- **FR-1.5**: Bot MUST handle WebSocket disconnections and reconnect automatically with exponential backoff

### FR-2: Natural Language Query
- **FR-2.1**: User MUST be able to send private messages to the bot QQ account
- **FR-2.2**: Bot MUST interpret natural language queries (e.g., "最近群里有讨论实习吗")
- **FR-2.3**: Bot MUST extract time range from query:
  - "最近" → past 24 hours
  - "昨天" → previous calendar day
  - "本周" → current week
  - No time mentioned → default to past 7 days
- **FR-2.4**: Bot MUST perform full-text search on stored messages using extracted keywords
- **FR-2.5**: Bot MUST call LLM to summarize retrieved messages
- **FR-2.6**: Bot MUST reply to user via QQ private message with summary + cited sources

### FR-3: Interest Management
- **FR-3.1**: User MUST be able to define persistent "interests" (topics they care about)
- **FR-3.2**: Commands: `/interests add`, `/interests list`, `/interests remove`
- **FR-3.3**: Each interest is associated with the user_id

### FR-4: Daily Digest
- **FR-4.1**: User MUST be able to request digest: `/digest`
- **FR-4.2**: Bot MUST generate summary of user's interests over past 24 hours

### FR-5: Command System
- **FR-5.1**: Bot MUST recognize commands starting with `/`
- **FR-5.2**: Supported: `/help`, `/interests`, `/digest`
- **FR-5.3**: Non-command messages MUST be treated as natural language queries

---

## 3. Non-Functional Requirements

### NFR-1: Performance
- **NFR-1.1**: Full-text search MUST complete within 500ms for 100k messages
- **NFR-1.2**: LLM API timeout MUST be 30 seconds
- **NFR-1.3**: Bot MUST handle up to 10 concurrent private message queries

### NFR-2: Reliability
- **NFR-2.1**: Message storage MUST be persistent (survive restart)
- **NFR-2.2**: Bot MUST auto-reconnect to OneBot server on disconnect
- **NFR-2.3**: Configuration MUST be loaded from `.env` file

### NFR-3: Security
- **NFR-3.1**: API keys MUST be stored in `.env` (not in code)
- **NFR-3.2**: `.env` MUST be in `.gitignore`
- **NFR-3.3**: OneBot access_token MUST be validated if configured

### NFR-4: Maintainability
- **NFR-4.1**: Code MUST have type annotations (PEP 484)
- **NFR-4.2**: Unit test coverage MUST be > 70%
- **NFR-4.3**: All modules MUST have docstrings

---

## 4. API Specifications

### 4.1 OneBot v11 WebSocket

**Group Message Event**:
```json
{
  "post_type": "message",
  "message_type": "group",
  "message_id": 12345,
  "group_id": 123456789,
  "user_id": 987654321,
  "message": "大家好",
  "sender": {"nickname": "张三"},
  "time": 1717660800
}
```

**Private Message Event**:
```json
{
  "post_type": "message",
  "message_type": "private",
  "message_id": 12346,
  "user_id": 111222333,
  "message": "最近群里有讨论实习吗",
  "sender": {"nickname": "李四"},
  "time": 1717660900
}
```

**Send Private Message**:
```json
{
  "action": "send_private_msg",
  "params": {"user_id": 111222333, "message": "回复内容"},
  "echo": "request_id"
}
```

### 4.2 LLM Provider (OpenAI-compatible)

**Endpoint**: `POST {base_url}/chat/completions`

**Request**:
```json
{
  "model": "deepseek-chat",
  "messages": [
    {"role": "system", "content": "你是一个 QQ 群聊消息助手"},
    {"role": "user", "content": "问题 + 检索消息"}
  ],
  "temperature": 0.7,
  "max_tokens": 1000
}
```

---

## 5. Data Schema

### SQLite Tables

```sql
CREATE TABLE group_messages (
    message_id INTEGER PRIMARY KEY,
    group_id INTEGER NOT NULL,
    group_name TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    user_nickname TEXT NOT NULL,
    message TEXT NOT NULL,
    timestamp INTEGER NOT NULL
);

CREATE VIRTUAL TABLE messages_fts USING fts5(
    message,
    content='group_messages',
    content_rowid='message_id',
    tokenize='unicode61'
);

CREATE TABLE interests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    description TEXT,
    created_at INTEGER NOT NULL,
    active INTEGER DEFAULT 1
);
```

---

## 6. Configuration

**.env.example**:
```bash
ONEBOT_WS_URL=ws://localhost:3001
ONEBOT_ACCESS_TOKEN=
BOT_QQ=123456789

LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-xxxxx
LLM_MODEL=deepseek-chat
LLM_TIMEOUT=30

DB_PATH=./data/messages.db
```

---

## 7. References

- **OneBot v11**: https://github.com/botuniverse/onebot-11
- **NapCat**: https://github.com/NapNeko/NapCatQQ
- **DeepSeek API**: https://platform.deepseek.com/api-docs/
- **SQLite FTS5**: https://www.sqlite.org/fts5.html
