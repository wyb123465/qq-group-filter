import WebSocket from "ws";
import { randomUUID } from "crypto";

export type EventHandler = (event: Record<string, any>) => void | Promise<void>;

const RECONNECT_BACKOFF = [5, 10, 20, 40, 60]; // seconds

export class OneBotClient {
  private wsUrl: string;
  private accessToken: string;
  private ws: WebSocket | null = null;
  private running = false;
  private shouldStop = false;

  private handlers: Record<string, EventHandler[]> = {
    group_message: [],
    private_message: [],
  };

  private pendingResponses = new Map<string, {
    resolve: (v: any) => void;
    reject: (e: Error) => void;
  }>();

  private groupNameCache = new Map<number, string>();

  constructor(wsUrl: string, accessToken = "") {
    this.wsUrl = wsUrl;
    this.accessToken = accessToken;
  }

  // --- Handler registration ---

  onGroupMessage(handler: EventHandler): void {
    this.handlers.group_message.push(handler);
  }

  onPrivateMessage(handler: EventHandler): void {
    this.handlers.private_message.push(handler);
  }

  // --- Connection ---

  private connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const headers: Record<string, string> = {};
      if (this.accessToken) {
        headers.Authorization = `Bearer ${this.accessToken}`;
      }
      this.ws = new WebSocket(this.wsUrl, { headers });

      this.ws.on("open", () => {
        console.log(`[onebot] Connected to ${this.wsUrl}`);
        resolve();
      });
      this.ws.on("error", (err) => reject(err));
      this.ws.on("message", (raw) => {
        try {
          const event = JSON.parse(raw.toString());
          this.dispatchEvent(event);
        } catch {
          console.warn("[onebot] Invalid JSON received");
        }
      });
      this.ws.on("close", () => {
        this.running = false;
      });
    });
  }

  async listenForever(onConnected?: () => Promise<void>): Promise<void> {
    let backoffIdx = 0;

    while (!this.shouldStop) {
      try {
        await this.connect();
        this.running = true;
        backoffIdx = 0;

        if (onConnected) {
          try { await onConnected(); } catch (e) {
            console.error("[onebot] on_connected error:", e);
          }
        }

        // Wait until the socket closes
        await new Promise<void>((resolve) => {
          this.ws!.on("close", resolve);
        });
      } catch (e) {
        console.error("[onebot] Connection error:", e);
      }

      if (this.shouldStop) break;

      const delay = RECONNECT_BACKOFF[Math.min(backoffIdx, RECONNECT_BACKOFF.length - 1)];
      backoffIdx++;
      console.log(`[onebot] Reconnecting in ${delay}s...`);
      await sleep(delay * 1000);
    }
  }

  // --- Event dispatch ---

  private dispatchEvent(event: Record<string, any>): void {
    // Action response (echo correlation)
    const echo = event.echo;
    if (echo && this.pendingResponses.has(echo)) {
      const { resolve } = this.pendingResponses.get(echo)!;
      this.pendingResponses.delete(echo);
      resolve(event);
      return;
    }

    // Heartbeat
    if (event.meta_event_type === "heartbeat") return;

    // Message events
    if (event.post_type === "message") {
      const handlers = this.handlers[`${event.message_type}_message`] ?? [];
      for (const h of handlers) {
        Promise.resolve(h(event)).catch((e) =>
          console.error("[onebot] Handler error:", e)
        );
      }
    }
  }

  // --- Action API ---

  async callAction(action: string, params: Record<string, any> = {}, timeout = 10000): Promise<any> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("Not connected");
    }

    const echo = randomUUID();
    const payload = JSON.stringify({ action, params, echo });

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingResponses.delete(echo);
        reject(new Error(`Action ${action} timed out`));
      }, timeout);

      this.pendingResponses.set(echo, {
        resolve: (v) => { clearTimeout(timer); resolve(v); },
        reject: (e) => { clearTimeout(timer); reject(e); },
      });

      this.ws!.send(payload);
    });
  }

  async sendPrivateMessage(userId: number, message: string): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({
      action: "send_private_msg",
      params: { user_id: userId, message },
      echo: `pm_${userId}_${Date.now()}`,
    }));
  }

  // --- Group name cache ---

  async refreshGroupList(): Promise<void> {
    try {
      const resp = await this.callAction("get_group_list");
      const data = resp?.data;
      if (!Array.isArray(data)) return;
      for (const entry of data) {
        if (entry.group_id && entry.group_name) {
          this.groupNameCache.set(entry.group_id, entry.group_name);
        }
      }
      console.log(`[onebot] Cached ${this.groupNameCache.size} group names`);
    } catch (e) {
      console.warn("[onebot] get_group_list failed:", e);
    }
  }

  async getGroupName(groupId: number): Promise<string> {
    if (this.groupNameCache.has(groupId)) {
      return this.groupNameCache.get(groupId)!;
    }
    try {
      const resp = await this.callAction("get_group_info", { group_id: groupId }, 5000);
      const name = resp?.data?.group_name;
      if (name) {
        this.groupNameCache.set(groupId, name);
        return name;
      }
    } catch { /* fallback below */ }
    return String(groupId);
  }

  // --- Shutdown ---

  close(): void {
    this.shouldStop = true;
    if (this.ws) {
      this.ws.close();
    }
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
