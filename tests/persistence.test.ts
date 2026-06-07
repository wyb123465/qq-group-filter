import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { MessageStore } from "../src/persistence.js";
import type { GroupMessage } from "../src/models.js";

function makeMsg(overrides: Partial<GroupMessage> = {}): GroupMessage {
  return {
    messageId: 1,
    groupId: 111,
    groupName: "技术群",
    userId: 9001,
    userNickname: "张三",
    message: "大家好",
    timestamp: Math.floor(Date.now() / 1000),
    ...overrides,
  };
}

describe("MessageStore", () => {
  let store: MessageStore;

  beforeEach(() => {
    store = new MessageStore(":memory:");
    store.init();
  });
  afterEach(() => store.close());

  it("should initialize without error", () => {
    expect(store).toBeDefined();
  });

  it("should save and search a message", () => {
    store.saveGroupMessage(makeMsg({ message: "有人知道哪里可以租GPU吗" }));
    const results = store.searchMessages({ query: "GPU" });
    expect(results).toHaveLength(1);
    expect(results[0].userNickname).toBe("张三");
  });

  it("should be idempotent on duplicate message_id", () => {
    const msg = makeMsg({ message: "重复消息测试" });
    store.saveGroupMessage(msg);
    store.saveGroupMessage(msg);
    const results = store.searchMessages({ query: "重复" });
    expect(results).toHaveLength(1);
  });

  it("should filter by time range", () => {
    const now = Math.floor(Date.now() / 1000);
    store.saveGroupMessage(makeMsg({ messageId: 1, message: "旧GPU讨论", timestamp: now - 200000 }));
    store.saveGroupMessage(makeMsg({ messageId: 2, message: "新GPU优惠", timestamp: now }));

    const results = store.searchMessages({ query: "GPU", startTime: now - 86400 });
    expect(results).toHaveLength(1);
    expect(results[0].messageId).toBe(2);
  });

  it("should filter by group ID", () => {
    store.saveGroupMessage(makeMsg({ messageId: 1, groupId: 111, message: "Python实习" }));
    store.saveGroupMessage(makeMsg({ messageId: 2, groupId: 222, message: "Java实习" }));

    const results = store.searchMessages({ query: "实习", groupIds: [111] });
    expect(results).toHaveLength(1);
    expect(results[0].groupId).toBe(111);
  });

  it("should handle Chinese text search", () => {
    store.saveGroupMessage(makeMsg({ message: "我在找深度学习相关的实习岗位" }));
    for (const kw of ["深度学习", "实习", "岗位"]) {
      expect(store.searchMessages({ query: kw })).toHaveLength(1);
    }
  });

  it("FTS should match non-adjacent terms", () => {
    store.saveGroupMessage(makeMsg({ messageId: 2, message: "GPU server rental is cheap today" }));
    const results = store.searchMessages({ query: "GPU cheap" });
    expect(results).toHaveLength(1);
  });

  it("should return empty for no matches", () => {
    expect(store.searchMessages({ query: "不存在的关键词xyz" })).toHaveLength(0);
  });

  it("should search all messages when query is empty", () => {
    store.saveGroupMessage(makeMsg({ messageId: 1, message: "消息一" }));
    store.saveGroupMessage(makeMsg({ messageId: 2, message: "消息二" }));
    const results = store.searchMessages({ query: "" });
    expect(results).toHaveLength(2);
  });
});

describe("MessageStore - interests", () => {
  let store: MessageStore;

  beforeEach(() => {
    store = new MessageStore(":memory:");
    store.init();
  });
  afterEach(() => store.close());

  it("should add and retrieve interests", () => {
    store.addInterest(123, "GPU租赁", "关注GPU信息");
    store.addInterest(123, "实习", "关注实习");
    const interests = store.getInterests(123);
    expect(interests).toHaveLength(2);
  });

  it("should remove (deactivate) an interest", () => {
    store.addInterest(123, "测试", "测试");
    const before = store.getInterests(123);
    store.removeInterest(before[0].id);
    expect(store.getInterests(123)).toHaveLength(0);
  });

  it("should list users with active interests", () => {
    store.addInterest(1001, "a", "");
    store.addInterest(1001, "b", "");
    store.addInterest(2002, "c", "");
    const users = store.getUsersWithInterests();
    expect(new Set(users)).toEqual(new Set([1001, 2002]));
  });
});
