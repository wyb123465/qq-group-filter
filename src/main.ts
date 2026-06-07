import { runBot } from "./bot.js";

runBot().catch((e) => {
  console.error("❌ Fatal error:", e);
  process.exit(1);
});
