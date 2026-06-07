/**
 * Extract plain text from a OneBot v11 message field.
 * Handles both string format and array-of-segments format.
 */
export function onebotMessageToText(message: unknown): string {
  if (typeof message === "string") return message;
  if (!Array.isArray(message)) return "";

  let text = "";
  for (const seg of message) {
    if (
      typeof seg === "object" &&
      seg !== null &&
      (seg as any).type === "text" &&
      typeof (seg as any).data?.text === "string"
    ) {
      text += (seg as any).data.text;
    }
  }
  return text.trim();
}
