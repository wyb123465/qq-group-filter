"""Main bot logic."""

import asyncio
import logging
from datetime import datetime

from qq_group_filter.config import Config
from qq_group_filter.models import GroupMessage
from qq_group_filter.persistence import MessageStore
from qq_group_filter.llm_provider import LLMProvider
from qq_group_filter.onebot_client import OneBotClient
from qq_group_filter.onebot_message import onebot_message_to_text
from qq_group_filter.query import QueryHandler
from qq_group_filter.scheduler import DigestScheduler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

HELP_TEXT = """🤖 QQ 群聊过滤机器人

📝 使用方法：
• 直接发送问题：例如"最近群里有讨论GPU租赁吗"
• /help - 显示此帮助信息
• /interests list - 查看关注主题
• /interests add <关键词> <描述> - 添加关注主题
• /interests remove <ID> - 删除关注主题
• /digest - 生成每日摘要

💡 提示：
问题中可以包含时间词（"最近"、"昨天"、"本周"）来筛选时间范围。
"""


async def run_bot():
    """Run the QQ group filter bot."""
    # Load configuration
    try:
        config = Config()
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        logger.error("Make sure .env file exists with required fields (BOT_QQ, LLM_API_KEY)")
        return

    logger.info("Starting QQ Group Filter Bot...")
    logger.info(f"Bot QQ: {config.bot_qq}")

    # Initialize components
    store = MessageStore(config.db_path)
    await store.init_db()
    logger.info(f"Database initialized: {config.db_path}")

    llm = LLMProvider(
        base_url=config.llm_base_url,
        api_key=config.llm_api_key,
        model=config.llm_model,
        timeout=config.llm_timeout
    )
    logger.info(f"LLM provider initialized: {config.llm_model}")

    query_handler = QueryHandler(store, llm)

    client = OneBotClient(config.onebot_ws_url, config.onebot_access_token)

    # Register event handlers
    @client.on_group_message
    async def handle_group_message(event: dict):
        """Handle incoming group messages - store them."""
        try:
            # Check if we should monitor this group
            group_id = event["group_id"]
            if config.monitored_groups and group_id not in config.monitored_groups:
                return

            message_text = onebot_message_to_text(event.get("message"))
            if not message_text:
                return

            # OneBot v11 group_message events don't carry group_name.
            # Resolve via API + cache so saved messages have real names.
            group_name = await client.get_group_name(group_id)

            msg = GroupMessage(
                message_id=event["message_id"],
                group_id=group_id,
                group_name=group_name,
                user_id=event["sender"]["user_id"],
                user_nickname=event["sender"].get("nickname", "Unknown"),
                message=message_text,
                timestamp=datetime.fromtimestamp(event["time"])
            )

            await store.save_group_message(msg)
            logger.debug(f"Saved message from group {group_id}: {msg.message[:50]}")

        except Exception as e:
            logger.error(f"Error handling group message: {e}", exc_info=True)

    @client.on_private_message
    async def handle_private_message(event: dict):
        """Handle incoming private messages - process as commands or queries."""
        try:
            user_id = event["user_id"]
            text = onebot_message_to_text(event.get("message")).strip()

            if not text:
                await client.send_private_message(user_id, "暂时只支持文本消息。")
                return

            logger.info(f"Private message from {user_id}: {text}")

            # Route commands
            if text.startswith("/help"):
                await client.send_private_message(user_id, HELP_TEXT)

            elif text.startswith("/interests"):
                await handle_interests_command(user_id, text)

            elif text.startswith("/digest"):
                digest = await query_handler.generate_daily_digest(user_id)
                await client.send_private_message(user_id, digest)

            else:
                # Natural language query
                result = await query_handler.handle_query(user_id, text)
                reply = format_reply(result)
                await client.send_private_message(user_id, reply)

        except Exception as e:
            logger.error(f"Error handling private message: {e}", exc_info=True)
            await client.send_private_message(
                event["user_id"],
                f"❌ 处理消息时出错：{str(e)}"
            )

    async def handle_interests_command(user_id: int, text: str):
        """Handle /interests command."""
        parts = text.split(maxsplit=2)

        if len(parts) == 1 or parts[1] == "list":
            # List interests
            interests = await store.get_interests(user_id)
            if not interests:
                await client.send_private_message(user_id, "您还没有设置关注主题。")
                return

            lines = ["📌 您的关注主题：\n"]
            for interest in interests:
                lines.append(f"{interest.id}. {interest.keyword} - {interest.description}")

            await client.send_private_message(user_id, "\n".join(lines))

        elif parts[1] == "add":
            # Add interest
            if len(parts) < 3:
                await client.send_private_message(
                    user_id,
                    "用法：/interests add <关键词> <描述>\n例如：/interests add GPU租赁 关注GPU服务器租赁信息"
                )
                return

            # Parse keyword and description
            rest = parts[2].split(maxsplit=1)
            keyword = rest[0]
            description = rest[1] if len(rest) > 1 else ""

            await store.add_interest(user_id, keyword, description)
            await client.send_private_message(
                user_id,
                f"✅ 已添加关注主题：{keyword}"
            )

        elif parts[1] == "remove":
            # Remove interest
            if len(parts) < 3:
                await client.send_private_message(
                    user_id,
                    "用法：/interests remove <ID>\n使用 /interests list 查看ID"
                )
                return

            try:
                interest_id = int(parts[2])
                await store.remove_interest(interest_id)
                await client.send_private_message(user_id, f"✅ 已删除关注主题 #{interest_id}")
            except ValueError:
                await client.send_private_message(user_id, "❌ 无效的ID")

    def format_reply(result) -> str:
        """Format QueryResult into readable QQ message."""
        if not result.sources:
            return result.summary

        lines = [f"💬 {result.summary}\n", "\n📋 相关消息："]

        for i, source in enumerate(result.sources[:5], 1):
            lines.append(
                f"{i}. [{source['group_name']}] {source['user_nickname']} ({source['timestamp']})\n"
                f"   {source['snippet']}"
            )

        return "\n".join(lines)

    # Connect and run with auto-reconnect
    scheduler = DigestScheduler(query_handler, store, client, config.digest_hour)

    async def on_connected():
        """Bootstrap per-session state after each (re)connection."""
        await client.refresh_group_list()
        scheduler.start()

    try:
        logger.info("✅ Bot starting (with auto-reconnect)... Press Ctrl+C to stop")
        await client.listen_forever(on_connected=on_connected)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Bot error: {e}", exc_info=True)
    finally:
        await scheduler.stop()
        await client.close()
        await store.close()
        logger.info("Bot stopped")
