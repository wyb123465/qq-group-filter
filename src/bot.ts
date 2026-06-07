import { getConfig } from "./config.js";
import { MessageStore } from "./persistence.js";
import { LLMProvider } from "./llm.js";
import { OneBotClient } from "./onebot-client.js";
import { QueryHandler } from "./query.js";
import { DigestScheduler } from "./scheduler.js";
import { onebotMessageToText } from "./onebot-message.js";
import type { GroupMessage } from "./models.js";

const HELP_TEXT = `🤖 QQ 群聊过滤机器人

📝 使用方法：
• 直接发送问题：例如"最近群里有讨论GPU租赁吗"
• /help - 显示此帮助信息
• /interests list - 查看关注主题
• /interests add <关键词> <描述> - 添加关注主题
• /interests remove <ID> - 删除关注主题
• /digest - 生成每日摘要

💡 提示：
问题中可以包含时间词（"最近"、"昨天"、"本周"）来筛选时间范围。`;

export async function runBot(): Promise<void> {
  const config = getConfig();
  console.log(`[bot] Starting... Bot QQ: ${config.BOT_QQ}`);

  // Initialize components
  const store = new MessageStore(config.DB_PATH);
  store.init();
  console.log(`[bot] Database initialized: ${config.DB_PATH}`);

  const llm = new LLMProvider({
    baseUrl: config.LLM_BASE_URL,
    apiKey: config.LLM_API_KEY,
    model: config.LLM_MODEL,
    timeout: config.LLM_TIMEOUT,
  });

  const queryHandler = new QueryHandler(store, llm);
  const client = new OneBotClient(config.ONEBOT_WS_URL, config.ONEBOT_ACCESS_TOKEN);
  const scheduler = new DigestScheduler(queryHandler, store, client, config.DIGEST_HOUR);

  // --- Group message handler ---
  client.onGroupMessage(async (event) => {
    const groupId = event.group_id;
    if (config.MONITORED_GROUPS && !config.MONITORED_GROUPS.includes(groupId)) return;

    const messageText = onebotMessageToText(event.message);
    if (!messageText) return;

    const groupName = await client.getGroupName(groupId);

    const msg: GroupMessage = {
      messageId: event.message_id,
      groupId,
      groupName,
      userId: event.sender.user_id,
      userNickname: event.sender.nickname ?? "Unknown",
      message: messageText,
      timestamp: event.time,
    };

    store.saveGroupMessage(msg);
  });

  // --- Private message handler ---
  client.onPrivateMessage(async (event) => {
    const userId: number = event.user_id;
    const text = onebotMessageToText(event.message).trim();

    if (!text) {
      await client.sendPrivateMessage(userId, "暂时只支持文本消息。");
      return;
    }

    try {
      if (text.startsWith("/help")) {
        await client.sendPrivateMessage(userId, HELP_TEXT);
      } else if (text.startsWith("/interests")) {
        await handleInterests(userId, text, store, client);
      } else if (text.startsWith("/digest")) {
        const digest = await queryHandler.generateDailyDigest(userId);
        await client.sendPrivateMessage(userId, digest);
      } else {
        const result = await queryHandler.handleQuery(userId, text);
        await client.sendPrivateMessage(userId, formatReply(result));
      }
    } catch (e: any) {
      console.error("[bot] Error handling private msg:", e);
      await client.sendPrivateMessage(userId, `❌ 处理出错：${e.message}`);
    }
  });

  // --- Start ---
  const onConnected = async () => {
    await client.refreshGroupList();
    scheduler.start();
  };

  const shutdown = () => {
    console.log("[bot] Shutting down...");
    scheduler.stop();
    client.close();
    store.close();
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);

  console.log("[bot] ✅ Starting (with auto-reconnect)...");
  await client.listenForever(onConnected);
}

// --- Helpers ---

async function handleInterests(
  userId: number,
  text: string,
  store: MessageStore,
  client: OneBotClient
): Promise<void> {
  const parts = text.split(/\s+/, 3);

  if (parts.length === 1 || parts[1] === "list") {
    const interests = store.getInterests(userId);
    if (interests.length === 0) {
      await client.sendPrivateMessage(userId, "您还没有设置关注主题。");
      return;
    }
    const lines = ["📌 您的关注主题：\n"];
    for (const i of interests) {
      lines.push(`${i.id}. ${i.keyword} - ${i.description ?? ""}`);
    }
    await client.sendPrivateMessage(userId, lines.join("\n"));
  } else if (parts[1] === "add") {
    const rest = text.slice(text.indexOf("add") + 3).trim();
    const [keyword, ...descParts] = rest.split(/\s+/);
    if (!keyword) {
      await client.sendPrivateMessage(userId,
        "用法：/interests add <关键词> <描述>\n例如：/interests add GPU租赁 关注GPU服务器租赁信息"
      );
      return;
    }
    store.addInterest(userId, keyword, descParts.join(" "));
    await client.sendPrivateMessage(userId, `✅ 已添加关注主题：${keyword}`);
  } else if (parts[1] === "remove") {
    const id = parseInt(parts[2], 10);
    if (isNaN(id)) {
      await client.sendPrivateMessage(userId, "❌ 无效的ID");
      return;
    }
    store.removeInterest(id);
    await client.sendPrivateMessage(userId, `✅ 已删除关注主题 #${id}`);
  }
}

function formatReply(result: { summary: string; sources: any[] }): string {
  if (result.sources.length === 0) return result.summary;

  const lines = [`💬 ${result.summary}\n`, "\n📋 相关消息："];
  for (let i = 0; i < Math.min(result.sources.length, 5); i++) {
    const s = result.sources[i];
    lines.push(`${i + 1}. [${s.groupName}] ${s.userNickname} (${s.timestamp})\n   ${s.snippet}`);
  }
  return lines.join("\n");
}
