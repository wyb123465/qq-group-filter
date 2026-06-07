import type { OneBotClient } from "./onebot-client.js";
import type { MessageStore } from "./persistence.js";
import type { QueryHandler } from "./query.js";

export class DigestScheduler {
  private timer: ReturnType<typeof setTimeout> | null = null;
  private running = false;

  constructor(
    private queryHandler: QueryHandler,
    private store: MessageStore,
    private client: OneBotClient,
    private digestHour: number
  ) {}

  start(): void {
    if (this.digestHour < 0) {
      console.log("[scheduler] Digest disabled (DIGEST_HOUR = -1)");
      return;
    }
    if (this.running) return;
    this.running = true;
    this.scheduleNext();
    console.log(`[scheduler] Daily digest at ${String(this.digestHour).padStart(2, "0")}:00`);
  }

  stop(): void {
    this.running = false;
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }

  private scheduleNext(): void {
    const delay = this.msUntilNextFire();
    this.timer = setTimeout(() => this.fire(), delay);
  }

  /** Milliseconds until next occurrence of digestHour:00. */
  msUntilNextFire(): number {
    const now = new Date();
    const target = new Date(now);
    target.setHours(this.digestHour, 0, 0, 0);
    if (target.getTime() <= now.getTime()) {
      target.setDate(target.getDate() + 1);
    }
    return target.getTime() - now.getTime();
  }

  private async fire(): Promise<void> {
    await this.pushAll();
    if (this.running) this.scheduleNext();
  }

  async pushAll(): Promise<void> {
    const userIds = this.store.getUsersWithInterests();
    console.log(`[scheduler] Pushing digest to ${userIds.length} user(s)`);

    for (const userId of userIds) {
      try {
        const digest = await this.queryHandler.generateDailyDigest(userId);
        if (!digest.includes("没有")) {
          await this.client.sendPrivateMessage(userId, digest);
        }
      } catch (e) {
        console.error(`[scheduler] Push to ${userId} failed:`, e);
      }
    }
  }
}
