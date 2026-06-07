# Tasks: QQ Group Filter Bot

## Phase 1: Foundation & Setup

### T1.1 Project Scaffolding
- [ ] Create `pyproject.toml` with uv, Python 3.10+, dependencies
- [ ] Set up package structure: `src/qq_group_filter/`
- [ ] Create `.env.example` with all config keys
- [ ] Add `.gitignore` (`.env`, `data/`, `__pycache__`, etc.)
- [ ] Write basic `README.md` with project description

**Dependencies:**
```toml
dependencies = [
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "aiosqlite>=0.20.0",
    "httpx>=0.28.0",
    "websockets>=12.0",
    "python-dotenv>=1.0.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.12.0",
]
```

**Files to create:**
- `pyproject.toml`
- `src/qq_group_filter/__init__.py`
- `src/qq_group_filter/__main__.py`
- `.env.example`
- `.gitignore`
- `README.md`

---

## Phase 2: Data Layer

### T2.1 Define Data Models
- [ ] `src/qq_group_filter/models.py`
  - `GroupMessage` (message_id, group_id, group_name, user_id, user_nickname, message, timestamp)
  - `PrivateMessage` (message_id, user_id, user_nickname, message, timestamp)
  - `Interest` (id, user_id, keyword, description, created_at, active)
  - `QueryResult` (summary, sources)

### T2.2 Configuration Management
- [ ] `src/qq_group_filter/config.py`
  - Use `pydantic-settings` for `.env` loading
  - Config fields: onebot_ws_url, onebot_access_token, bot_qq, llm_base_url, llm_api_key, llm_model, db_path, monitored_groups

### T2.3 Storage Layer Implementation
- [ ] `src/qq_group_filter/persistence.py`
  - `MessageStore` class with aiosqlite
  - `init_db()`: create tables + FTS5 index
  - `save_group_message()`: upsert message (idempotent by message_id)
  - `search_messages()`: FTS5 full-text search with time/group filters
  - `add_interest()`, `get_interests()`, `remove_interest()`
  - SQL schema:
    ```sql
    CREATE TABLE IF NOT EXISTS group_messages (
        message_id INTEGER PRIMARY KEY,
        group_id INTEGER NOT NULL,
        group_name TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        user_nickname TEXT NOT NULL,
        message TEXT NOT NULL,
        timestamp INTEGER NOT NULL
    );
    
    CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
        message,
        content='group_messages',
        content_rowid='message_id',
        tokenize='unicode61'
    );
    
    CREATE TABLE IF NOT EXISTS interests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        keyword TEXT NOT NULL,
        description TEXT,
        created_at INTEGER NOT NULL,
        active INTEGER DEFAULT 1
    );
    ```

### T2.4 Test Storage Layer
- [ ] `tests/test_persistence.py`
  - Test `init_db()` creates tables correctly
  - Test `save_group_message()` inserts and updates
  - Test `search_messages()` with FTS5 (Chinese text)
  - Test interest CRUD operations
  - Use in-memory SQLite (`:memory:`)

---

## Phase 3: External Integrations

### T3.1 LLM Provider
- [ ] `src/qq_group_filter/llm_provider.py`
  - `LLMProvider` class with httpx async client
  - `chat_completion(messages, temperature, max_tokens)` → str
  - POST to `{base_url}/chat/completions` with OpenAI-compatible format
  - Error handling: timeout, HTTP errors, rate limits
  - Retry with exponential backoff (optional)

### T3.2 Test LLM Provider
- [ ] `tests/test_llm_provider.py`
  - Mock httpx responses
  - Test successful chat completion
  - Test timeout handling
  - Test error responses (401, 429, 500)

### T3.3 OneBot v11 Client
- [ ] `src/qq_group_filter/onebot_client.py`
  - `OneBotClient` class with websockets
  - `connect()`: establish WebSocket, send auth if access_token present
  - `listen()`: event loop with heartbeat response
  - Event parsing: `group_message`, `private_message`
  - Callbacks: `on_group_message(handler)`, `on_private_message(handler)`
  - Actions: `send_private_message(user_id, message)`, `send_group_message(group_id, message)`
  - Auto-reconnect with backoff
  - Graceful shutdown on KeyboardInterrupt

**OneBot v11 API Reference:**
- Event format: https://github.com/botuniverse/onebot-11/blob/master/event/message.md
- Action format: https://github.com/botuniverse/onebot-11/blob/master/api/public.md

### T3.4 Test OneBot Client
- [ ] `tests/test_onebot_client.py`
  - Mock WebSocket server (use pytest-asyncio + websockets)
  - Test connection + auth
  - Test event parsing (group_message, private_message)
  - Test send_private_message action
  - Test reconnect logic

---

## Phase 4: Query & Summarization Logic

### T4.1 Query Handler
- [ ] `src/qq_group_filter/query.py`
  - `QueryHandler` class with `MessageStore` and `LLMProvider` dependencies
  - `handle_query(user_id, query_text)` → `QueryResult`
    1. Extract time range from query ("最近" → 24h, "昨天" → specific date)
    2. Extract keywords (simple: use full query as keyword)
    3. Call `store.search_messages(query, start_time, limit=50)`
    4. If no results, return "未找到相关消息"
    5. Construct prompt with retrieved messages
    6. Call `llm.chat_completion()`
    7. Parse LLM response into `QueryResult`
  - `generate_daily_digest(user_id)` → str
    - Get user's interests
    - For each interest, search messages in past 24h
    - Summarize with LLM
    - Combine into digest

**Prompt Template:**
```python
SUMMARIZE_PROMPT = """你是一个 QQ 群聊消息助手。用户问了这个问题：
"{query}"

我从群聊历史中检索到以下相关消息：

{messages}

请用中文总结这些消息，回答用户的问题。要求：
1. 直接回答问题，简洁明了
2. 如果有多个相关讨论，分点说明
3. 每个要点后标注出处：[群名] 发言人 (时间)
4. 如果没有相关消息，明确告诉用户"未找到相关讨论"

总结："""
```

### T4.2 Test Query Handler
- [ ] `tests/test_query.py`
  - Mock `MessageStore.search_messages()` to return sample messages
  - Mock `LLMProvider.chat_completion()` to return canned summary
  - Test `handle_query()` constructs correct prompt
  - Test "no results" case
  - Test `generate_daily_digest()`

---

## Phase 5: Bot Main Loop & Commands

### T5.1 Command Router
- [ ] `src/qq_group_filter/commands.py`
  - Parse private message text → command or query
  - Commands:
    - `/help`: show available commands
    - `/interests list`: list user's interests
    - `/interests add <keyword> <description>`: add interest
    - `/interests remove <id>`: remove interest
    - `/digest`: generate daily digest
    - Default: treat as natural language query

### T5.2 Bot Main Loop
- [ ] `src/qq_group_filter/bot.py`
  - `async def main()`:
    1. Load config
    2. Init MessageStore
    3. Init LLMProvider
    4. Init QueryHandler
    5. Init OneBotClient
    6. Register event handlers:
       - `on_group_message`: save to store
       - `on_private_message`: route command/query → reply
    7. Connect and listen (blocks)
  - Entry point in `__main__.py`: `asyncio.run(main())`

### T5.3 Format Reply
- [ ] Helper function to format `QueryResult` into readable QQ message
  - Example:
    ```
    📋 找到 3 条相关消息：
    
    1. 关于实习的讨论
    [技术交流群] 张三 (2026-06-05 14:23)
    > "我们公司正在招前端实习生，base 北京..."
    
    2. 面试经验分享
    [求职群] 李四 (2026-06-04 19:45)
    > "刚面完字节实习，问了很多 React..."
    
    💡 总结：最近两天有两个群提到实习机会，主要集中在前端和算法方向...
    ```

---

## Phase 6: Testing & Documentation

### T6.1 End-to-End Test
- [ ] `tests/test_e2e.py`
  - Simulate full flow:
    1. Start bot with mock OneBot server
    2. Send group message event → verify stored in DB
    3. Send private message event (query) → verify reply sent
  - Use real SQLite (in-memory) and mock LLM

### T6.2 NapCat Setup Guide
- [ ] `docs/NAPCAT_SETUP.md`
  - Prerequisites: Windows/Linux, QQ account (recommend using alt account)
  - Download NapCat: https://github.com/NapNeko/NapCatQQ/releases
  - Install and configure:
    - Set WebSocket reverse server
    - Get access token
    - Start NapCat → login QQ via QR code
  - Configure bot `.env`:
    ```
    ONEBOT_WS_URL=ws://localhost:3001
    ONEBOT_ACCESS_TOKEN=your_token
    BOT_QQ=123456789
    ```
  - Run bot: `uv run python -m qq_group_filter`
  - Test: send private message to bot QQ → should reply

### T6.3 README & Examples
- [ ] Update `README.md`
  - Features
  - Installation: `git clone`, `uv sync`
  - Configuration: copy `.env.example` → `.env`, fill in keys
  - Usage:
    - Start bot: `uv run python -m qq_group_filter`
    - Ask in QQ: "最近群里有讨论 GPU 租赁吗"
    - Manage interests: `/interests add GPU租赁 关注 GPU 服务器租赁信息`
  - Screenshots (optional)
  - Risks & Disclaimer: account ban risk, use at your own risk

### T6.4 Run All Tests
- [ ] `pytest tests/ -v --cov=src/qq_group_filter`
- [ ] Fix any failing tests
- [ ] Ensure coverage > 70%

---

## Phase 7: Polish & Deployment (Optional)

### T7.1 Logging
- [ ] Add structured logging (Python `logging` module)
  - Log levels: INFO for events, WARNING for errors, DEBUG for details
  - Log to file: `logs/bot.log` with rotation

### T7.2 Deployment Scripts
- [ ] `deploy/systemd/qq-bot.service`
- [ ] `deploy/docker/Dockerfile` (optional)
- [ ] `deploy/docker/docker-compose.yml` (optional)

### T7.3 Archive OpenSpec Change
- [ ] Verify all tasks complete
- [ ] `openspec archive qq-group-filter-bot`
- [ ] Update main spec if applicable

---

## Task Dependencies

```
Phase 1 (T1.1) → Phase 2 (T2.1, T2.2, T2.3, T2.4)
                      ↓
Phase 3 (T3.1, T3.2, T3.3, T3.4)
                      ↓
Phase 4 (T4.1, T4.2) depends on Phase 2 + Phase 3
                      ↓
Phase 5 (T5.1, T5.2, T5.3) depends on all previous
                      ↓
Phase 6 (T6.1, T6.2, T6.3, T6.4)
                      ↓
Phase 7 (optional)
```

## Estimated Timeline

| Phase | Time | Total |
|-------|------|-------|
| Phase 1 | 1h | 1h |
| Phase 2 | 2h | 3h |
| Phase 3 | 3h | 6h |
| Phase 4 | 2h | 8h |
| Phase 5 | 1h | 9h |
| Phase 6 | 2h | 11h |
| Phase 7 | 1h | 12h |

**Critical Path**: Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6
