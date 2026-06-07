import { describe, it, expect } from "vitest";
import { onebotMessageToText } from "../src/onebot-message.js";

describe("onebotMessageToText", () => {
  it("should return string messages unchanged", () => {
    expect(onebotMessageToText("大家好")).toBe("大家好");
  });

  it("should concatenate text segments from array messages", () => {
    const msg = [
      { type: "text", data: { text: "实习机会：" } },
      { type: "image", data: { url: "http://example.com/img.jpg" } },
      { type: "text", data: { text: "字节跳动" } },
    ];
    expect(onebotMessageToText(msg)).toBe("实习机会：字节跳动");
  });

  it("should return empty for array without text segments", () => {
    const msg = [{ type: "image", data: { url: "..." } }];
    expect(onebotMessageToText(msg)).toBe("");
  });

  it("should return empty for non-string/non-array", () => {
    expect(onebotMessageToText(123)).toBe("");
    expect(onebotMessageToText(null)).toBe("");
  });
});
