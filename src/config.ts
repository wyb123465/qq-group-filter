import { z } from "zod";
import { config as loadDotenv } from "dotenv";

loadDotenv();

const configSchema = z.object({
  // OneBot WebSocket
  ONEBOT_WS_URL: z.string().default("ws://localhost:3001"),
  ONEBOT_ACCESS_TOKEN: z.string().default(""),
  BOT_QQ: z.coerce.number(),

  // LLM
  LLM_BASE_URL: z.string().default("https://api.deepseek.com/v1"),
  LLM_API_KEY: z.string(),
  LLM_MODEL: z.string().default("deepseek-chat"),
  LLM_TIMEOUT: z.coerce.number().default(30),

  // Storage
  DB_PATH: z.string().default("./data/messages.db"),

  // Monitoring
  MONITORED_GROUPS: z
    .string()
    .default("")
    .transform((v) =>
      v
        ? v.split(",").map((s) => parseInt(s.trim(), 10)).filter(Boolean)
        : null
    ),

  // Scheduler
  DIGEST_HOUR: z.coerce.number().default(8),
});

export type Config = z.infer<typeof configSchema>;

let _config: Config | null = null;

export function getConfig(): Config {
  if (!_config) {
    _config = configSchema.parse(process.env);
  }
  return _config;
}

/** For tests — override config values. */
export function setConfig(overrides: Partial<Config>): Config {
  _config = { ...getConfig(), ...overrides } as Config;
  return _config;
}
