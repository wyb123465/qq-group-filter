"""Entry point for qq-group-filter bot."""

import asyncio
import sys


def main():
    """Main entry point. Bot handles its own Ctrl+C — we just convert errors to exit codes."""
    try:
        from qq_group_filter.bot import run_bot
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
