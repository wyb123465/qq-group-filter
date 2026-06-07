import { describe, it, expect } from "vitest";
import { QueryHandler } from "../src/query.js";

const handler = new QueryHandler(null as any, null as any);

describe("QueryHandler — keyword extraction", () => {
  it("should strip time words and stop words", () => {
    const kw = handler.extractKeywords("最近群里有讨论GPU租赁吗");
    const tokens = new Set(kw.split(" "));
    expect(tokens.has("GPU")).toBe(true);
    expect(tokens.has("租赁")).toBe(true);
    expect(tokens.has("最近")).toBe(false);
    expect(tokens.has("群里")).toBe(false);
    expect(tokens.has("讨论")).toBe(false);
  });

  it("should handle pure Chinese", () => {
    const kw = handler.extractKeywords("昨天有人聊到实习机会吗");
    expect(kw).toContain("实习");
    expect(kw).toContain("机会");
    expect(kw).not.toContain("昨天");
  });

  it("should pass English through", () => {
    const kw = handler.extractKeywords("any news about Kubernetes");
    expect(kw).toContain("Kubernetes");
    expect(kw).toContain("news");
  });

  it("should return empty for only stop words", () => {
    expect(handler.extractKeywords("最近群里有讨论吗")).toBe("");
  });
});

describe("QueryHandler — time range", () => {
  it("最近 → ~24h", () => {
    const now = Math.floor(Date.now() / 1000);
    const start = handler.extractTimeRange("最近群里讨论了什么");
    expect(now - start).toBeGreaterThan(86000);
    expect(now - start).toBeLessThan(87000);
  });

  it("no time word → ~7d default", () => {
    const now = Math.floor(Date.now() / 1000);
    const start = handler.extractTimeRange("GPU 租赁有讨论吗");
    const delta = now - start;
    expect(delta).toBeGreaterThan(86400 * 6.9);
    expect(delta).toBeLessThan(86400 * 7.1);
  });
});
