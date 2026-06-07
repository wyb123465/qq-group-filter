"""Query handling and LLM-based summarization."""

import re
from datetime import datetime, timedelta

from qq_group_filter.models import QueryResult, GroupMessage
from qq_group_filter.persistence import MessageStore
from qq_group_filter.llm_provider import LLMProvider


# Time-range expressions stripped before keyword extraction.
TIME_PATTERNS = (
    "最近", "今天", "昨天", "前天", "本周", "这周", "上周",
    "本月", "这个月", "上个月", "最近几天", "几天",
)

# Chinese conversational filler / question particles that add no search value.
STOPWORDS = {
    "群里", "群", "有没有", "有人", "有", "没有", "是否",
    "讨论", "聊", "聊到", "说", "提到", "提及", "提起",
    "关于", "对于", "针对",
    "总结", "概括", "汇总", "整理", "现在", "当前", "信息", "消息", "内容", "下",
    "吗", "呢", "啊", "呀", "了", "的", "地", "得",
    "到", "过", "在", "看",
    "我", "你", "他", "她", "我们", "你们", "他们",
    "什么", "怎么", "怎样", "如何", "为什么",
    "一下", "一些", "一点",
    "想", "要", "需要", "想要", "知道", "了解",
    "能", "可以", "可否", "是不是",
}


class QueryHandler:
    """Handle user queries and generate summaries."""

    def __init__(self, store: MessageStore, llm: LLMProvider):
        """
        Initialize query handler.

        Args:
            store: Message storage instance
            llm: LLM provider instance
        """
        self.store = store
        self.llm = llm

    def _extract_time_range(self, query: str) -> datetime:
        """
        Extract time range from query text.

        Returns:
            Start time for filtering. Defaults to past 7 days if no
            time expression is recognized.
        """
        now = datetime.now()

        if re.search(r"最近|今天", query):
            return now - timedelta(hours=24)

        if "昨天" in query:
            return now - timedelta(days=2)

        if "前天" in query:
            return now - timedelta(days=3)

        if re.search(r"本周|这周", query):
            return now - timedelta(days=7)

        if re.search(r"上周", query):
            return now - timedelta(days=14)

        if re.search(r"本月|这个月", query):
            return now - timedelta(days=30)

        # Default: past 7 days
        return now - timedelta(days=7)

    def _extract_keywords(self, query: str) -> str:
        """
        Extract searchable keywords from a natural-language query.

        Strips time expressions, conversational fillers, and Chinese
        question particles, then tokenizes by Unicode word boundaries
        plus contiguous CJK runs. Returns a space-separated string suitable
        for the persistence layer to feed into FTS5 (AND semantics) or
        fall back to LIKE.

        Example:
            "最近群里有讨论GPU租赁吗" -> "GPU 租赁"
        """
        cleaned = query
        for pattern in TIME_PATTERNS:
            cleaned = cleaned.replace(pattern, " ")

        # Tokenize: ASCII words OR runs of CJK characters.
        raw_tokens = re.findall(r"[A-Za-z0-9_]+|[一-鿿]+", cleaned)

        keywords: list[str] = []
        for token in raw_tokens:
            if token in STOPWORDS:
                continue
            # Split contiguous CJK runs further by stopwords embedded inside,
            # so "讨论GPU租赁" → ["GPU", "租赁"] after the tokenize+strip pass.
            # (Tokens are already separated by ASCII vs CJK, so this is mainly
            # a safeguard for fully-CJK tokens like "关于实习" → "实习".)
            if re.fullmatch(r"[一-鿿]+", token):
                sub = self._strip_cjk_stopwords(token)
                if sub:
                    keywords.append(sub)
            else:
                keywords.append(token)

        return " ".join(keywords)

    def _strip_cjk_stopwords(self, token: str) -> str:
        """Greedily remove CJK stopwords appearing at the start/end of a token.

        Iterates by descending stopword length so longest match wins — this
        avoids hash-order non-determinism that would otherwise let "群里"
        get stripped before "群" (or vice-versa) inconsistently across runs.
        """
        # Sort once per call: longest stopwords first → longest-match-wins.
        sorted_sws = sorted(STOPWORDS, key=len, reverse=True)
        changed = True
        while changed and token:
            changed = False
            for sw in sorted_sws:
                if token.startswith(sw):
                    token = token[len(sw):]
                    changed = True
                    break
                if token.endswith(sw):
                    token = token[: -len(sw)]
                    changed = True
                    break
        return token

    def _is_broad_summary_query(self, query: str) -> bool:
        """Return True when the user asks for a general recent group summary."""
        has_summary_intent = re.search(r"总结|概括|汇总|整理|说说", query) is not None
        has_group_scope = re.search(r"群|消息|信息|聊天|内容", query) is not None
        return has_summary_intent and has_group_scope

    async def handle_query(self, user_id: int, query_text: str) -> QueryResult:
        """
        Handle a user query and generate summary.

        Args:
            user_id: User QQ number
            query_text: Natural language query

        Returns:
            QueryResult with summary and sources
        """
        start_time = self._extract_time_range(query_text)
        if self._is_broad_summary_query(query_text):
            search_query = ""
        else:
            keywords = self._extract_keywords(query_text)
            # Fall back to the raw query if keyword extraction leaves nothing.
            search_query = keywords if keywords else query_text

        messages = await self.store.search_messages(
            query=search_query,
            start_time=start_time,
            limit=50
        )

        if not messages:
            return QueryResult(
                summary="未找到相关消息",
                sources=[]
            )

        prompt = self._build_prompt(query_text, messages)

        try:
            summary = await self.llm.chat_completion([
                {"role": "system", "content": "你是一个 QQ 群聊消息助手。"},
                {"role": "user", "content": prompt}
            ])
        except Exception as e:
            summary = f"生成总结时出错：{str(e)}"

        sources = [
            {
                "group_name": msg.group_name,
                "user_nickname": msg.user_nickname,
                "timestamp": msg.timestamp.strftime("%Y-%m-%d %H:%M"),
                "snippet": msg.message[:100]
            }
            for msg in messages[:10]
        ]

        return QueryResult(summary=summary, sources=sources)

    def _build_prompt(self, query: str, messages: list[GroupMessage]) -> str:
        """Build prompt for LLM summarization."""
        messages_text = "\n\n".join([
            f"[{msg.group_name}] {msg.user_nickname} ({msg.timestamp.strftime('%Y-%m-%d %H:%M')}):\n{msg.message}"
            for msg in messages[:20]
        ])

        return f"""用户问了这个问题：
"{query}"

我从群聊历史中检索到以下相关消息：

{messages_text}

请用中文总结这些消息，回答用户的问题。要求：
1. 直接回答问题，简洁明了
2. 如果有多个相关讨论，分点说明
3. 每个要点后标注出处：[群名] 发言人 (时间)
4. 如果没有相关消息，明确告诉用户"未找到相关讨论"

总结："""

    async def generate_daily_digest(self, user_id: int) -> str:
        """
        Generate daily digest for user's interests.

        Args:
            user_id: User QQ number

        Returns:
            Digest text
        """
        interests = await self.store.get_interests(user_id)

        if not interests:
            return "您还没有设置关注主题。使用 /interests add <关键词> <描述> 来添加。"

        digest_parts = ["📊 您的关注主题更新 (过去24小时)\n"]
        now = datetime.now()
        start_time = now - timedelta(hours=24)

        for interest in interests:
            messages = await self.store.search_messages(
                query=interest.keyword,
                start_time=start_time,
                limit=10
            )

            if messages:
                digest_parts.append(f"\n🔹 {interest.keyword} ({len(messages)}条新消息)")
                for msg in messages[:3]:
                    snippet = msg.message[:50] + "..." if len(msg.message) > 50 else msg.message
                    digest_parts.append(
                        f"[{msg.group_name}] {msg.user_nickname}: \"{snippet}\""
                    )

        if len(digest_parts) == 1:
            return "过去24小时没有关于您关注主题的新消息。"

        return "\n".join(digest_parts)
