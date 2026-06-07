import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { MessageStore } from "../src/persistence.js";
import { QueryHandler } from "../src/query.js";
import { DigestScheduler } from "../src/scheduler.js";
import type { GroupMessage, QueryResult } from "../src/models.js";

// --- Fakes ---

class FakeLLM {
  calls: any[] = [];
  response = "这是LLM总结";
  async chatCompletion(messages: any[]) {
    this.calls.push(messages);
    return this.response;
  }
}

class FakeClient {
  sent: Array<{ userId: number; message: string }> = [];
  async sendPrivateMessage(userId: number, message: string) {
    this.sent.push({ userId, message });
  }
}

// --- Tests ---

describe("Bot integration", () => {
  let store: MessageStore;

  beforeEach(() => {
    store = new MessageStore(":memory:");
    store.init();
  });
  afterEach(() => store.close());

  it("should store group messages and retrieve them via query", async () => {
    const now = Math.floor(Date.now() / 1000);
    for (let i = 0; i < 3; i++) {
      store.saveGroupMessage({
        messageId: 2000 + i,
        groupId: 111,
        groupName: "技术群",
        userId: 9001 + i,
        userNickname: `用户${i}`,
        message: `GPU 租赁方案${i}: AutoDL 很便宜`,
        timestamp: now,
      });
    }

    const llm = new FakeLLM();
    llm.response = "最近有3条关于GPU租赁的讨论";
    const handler = new QueryHandler(store, llm as any);

    const result = await handler.handleQuery(12345, "最近群里有讨论GPU租赁吗");
    expect(result.summary).toContain("GPU租赁");
    expect(result.sources).toHaveLength(3);
    expect(llm.calls.length).toBeGreaterThan(0);
  });

  it("should return 'no results' without calling LLM", async () => {
    const llm = new FakeLLM();
    const handler = new QueryHandler(store, llm as any);

    const result = await handler.handleQuery(12345, "量子计算");
    expect(result.summary).toContain("未找到");
    expect(llm.calls).toHaveLength(0);
  });

  it("should generate digest for interests", async () => {
    store.addInterest(12345, "GPU", "关注GPU");
    store.saveGroupMessage({
      messageId: 3001,
      groupId: 222,
      groupName: "求职群",
      userId: 9999,
      userNickname: "李四",
      message: "GPU服务器降价了，推荐大家看看",
      timestamp: Math.floor(Date.now() / 1000),
    });

    const handler = new QueryHandler(store, new FakeLLM() as any);
    const digest = await handler.generateDailyDigest(12345);
    expect(digest).toContain("GPU");
    expect(digest).toContain("1条新消息");
    expect(digest).toContain("李四");
  });
});

describe("DigestScheduler", () => {
  let store: MessageStore;

  beforeEach(() => {
    store = new MessageStore(":memory:");
    store.init();
  });
  afterEach(() => store.close());

  it("should push digest only to users with matching messages", async () => {
    store.addInterest(1001, "GPU", "GPU相关");
    store.addInterest(2002, "实习", "实习相关");
    store.saveGroupMessage({
      messageId: 1,
      groupId: 111,
      groupName: "技术群",
      userId: 9999,
      userNickname: "张三",
      message: "GPU降价了",
      timestamp: Math.floor(Date.now() / 1000),
    });

    const fakeClient = new FakeClient();
    const handler = new QueryHandler(store, new FakeLLM() as any);
    const scheduler = new DigestScheduler(handler, store, fakeClient as any, 8);

    await scheduler.pushAll();

    const to1001 = fakeClient.sent.filter((m) => m.userId === 1001);
    const to2002 = fakeClient.sent.filter((m) => m.userId === 2002);
    expect(to1001).toHaveLength(1);
    expect(to1001[0].message).toContain("GPU");
    expect(to2002).toHaveLength(0);
  });

  it("should not start when digest_hour is -1", () => {
    const s = new DigestScheduler(null as any, null as any, null as any, -1);
    s.start();
    expect((s as any).running).toBe(false);
  });

  it("msUntilNextFire should be between 0 and 86400000", () => {
    const s = new DigestScheduler(null as any, null as any, null as any, 3);
    const ms = s.msUntilNextFire();
    expect(ms).toBeGreaterThan(0);
    expect(ms).toBeLessThanOrEqual(86400000);
  });
});
