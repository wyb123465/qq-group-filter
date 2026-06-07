import type { GroupMessage, QueryResult } from "./models.js";
import type { MessageStore } from "./persistence.js";
import type { LLMProvider } from "./llm.js";

// Time expressions to strip before keyword extraction
const TIME_PATTERNS = [
  "最近", "今天", "昨天", "前天", "本周", "这周", "上周", "本月", "这个月",
];

// Chinese stop words that add no search value
const STOPWORDS = new Set([
  "群里", "群", "有没有", "有人", "有", "没有", "是否",
  "讨论", "聊", "聊到", "说", "提到", "提及", "提起",
  "关于", "对于", "针对",
  "吗", "呢", "啊", "呀", "了", "的", "地", "得",
  "到", "过", "在", "看",
  "我", "你", "他", "她", "我们", "你们", "他们",
  "什么", "怎么", "怎样", "如何", "为什么",
  "一下", "一些", "一点",
  "想", "要", "需要", "想要", "知道", "了解",
  "能", "可以", "可否", "是不是",
]);

// Sorted by length desc for greedy stripping
const SORTED_STOPWORDS = [...STOPWORDS].sort((a, b) => b.length - a.length);

export class QueryHandler {
  constructor(
    private store: MessageStore,
    private llm: LLMProvider
  ) {}

  /** Extract time range start (unix seconds) from query text. */
  extractTimeRange(query: string): number {
    const now = Math.floor(Date.now() / 1000);
    if (/最近|今天/.test(query)) return now - 86400;
    if (query.includes("昨天")) return now - 86400 * 2;
    if (query.includes("前天")) return now - 86400 * 3;
    if (/本周|这周/.test(query)) return now - 86400 * 7;
    if (query.includes("上周")) return now - 86400 * 14;
    if (/本月|这个月/.test(query)) return now - 86400 * 30;
    return now - 86400 * 7; // default: 7 days
  }

  /** Extract searchable keywords from a natural language query. */
  extractKeywords(query: string): string {
    let cleaned = query;
    for (const p of TIME_PATTERNS) {
      cleaned = cleaned.replaceAll(p, " ");
    }

    const rawTokens = cleaned.match(/[A-Za-z0-9_]+|[一-鿿]+/g) ?? [];
    const keywords: string[] = [];

    for (const token of rawTokens) {
      if (STOPWORDS.has(token)) continue;
      if (/^[一-鿿]+$/.test(token)) {
        const stripped = this.stripCjkStopwords(token);
        if (stripped) keywords.push(stripped);
      } else {
        keywords.push(token);
      }
    }
    return keywords.join(" ");
  }

  private stripCjkStopwords(token: string): string {
    let changed = true;
    while (changed && token) {
      changed = false;
      for (const sw of SORTED_STOPWORDS) {
        if (token.startsWith(sw)) {
          token = token.slice(sw.length);
          changed = true;
          break;
        }
        if (token.endsWith(sw)) {
          token = token.slice(0, -sw.length);
          changed = true;
          break;
        }
      }
    }
    return token;
  }

  private isBroadSummaryQuery(query: string): boolean {
    const hasIntent = /总结|概括|汇总|整理|说说/.test(query);
    const hasScope = /群|消息|信息|聊天|内容/.test(query);
    return hasIntent && hasScope;
  }

  async handleQuery(userId: number, queryText: string): Promise<QueryResult> {
    const startTime = this.extractTimeRange(queryText);

    let searchQuery: string;
    if (this.isBroadSummaryQuery(queryText)) {
      searchQuery = "";
    } else {
      const kw = this.extractKeywords(queryText);
      searchQuery = kw || queryText;
    }

    const messages = this.store.searchMessages({
      query: searchQuery,
      startTime,
      limit: 50,
    });

    if (messages.length === 0) {
      return { summary: "未找到相关消息", sources: [] };
    }

    const prompt = this.buildPrompt(queryText, messages);
    let summary: string;
    try {
      summary = await this.llm.chatCompletion([
        { role: "system", content: "你是一个 QQ 群聊消息助手。" },
        { role: "user", content: prompt },
      ]);
    } catch (e: any) {
      summary = `生成总结时出错：${e.message}`;
    }

    const sources = messages.slice(0, 10).map((msg) => ({
      groupName: msg.groupName,
      userNickname: msg.userNickname,
      timestamp: formatTimestamp(msg.timestamp),
      snippet: msg.message.slice(0, 100),
    }));

    return { summary, sources };
  }

  private buildPrompt(query: string, messages: GroupMessage[]): string {
    const messagesText = messages
      .slice(0, 20)
      .map((m) => `[${m.groupName}] ${m.userNickname} (${formatTimestamp(m.timestamp)}):\n${m.message}`)
      .join("\n\n");

    return `用户问了这个问题：
"${query}"

我从群聊历史中检索到以下相关消息：

${messagesText}

请用中文总结这些消息，回答用户的问题。要求：
1. 直接回答问题，简洁明了
2. 如果有多个相关讨论，分点说明
3. 每个要点后标注出处：[群名] 发言人 (时间)
4. 如果没有相关消息，明确告诉用户"未找到相关讨论"

总结：`;
  }

  async generateDailyDigest(userId: number): Promise<string> {
    const interests = this.store.getInterests(userId);
    if (interests.length === 0) {
      return "您还没有设置关注主题。使用 /interests add <关键词> <描述> 来添加。";
    }

    const now = Math.floor(Date.now() / 1000);
    const startTime = now - 86400;
    const parts: string[] = ["📊 您的关注主题更新 (过去24小时)\n"];

    for (const interest of interests) {
      const messages = this.store.searchMessages({
        query: interest.keyword,
        startTime,
        limit: 10,
      });
      if (messages.length > 0) {
        parts.push(`\n🔹 ${interest.keyword} (${messages.length}条新消息)`);
        for (const msg of messages.slice(0, 3)) {
          const snippet = msg.message.length > 50 ? msg.message.slice(0, 50) + "..." : msg.message;
          parts.push(`[${msg.groupName}] ${msg.userNickname}: "${snippet}"`);
        }
      }
    }

    if (parts.length === 1) {
      return "过去24小时没有关于您关注主题的新消息。";
    }
    return parts.join("\n");
  }
}

function formatTimestamp(ts: number): string {
  const d = new Date(ts * 1000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
