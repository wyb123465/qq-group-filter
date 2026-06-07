import { z } from "zod";

/** A stored group message. */
export const GroupMessageSchema = z.object({
  messageId: z.number(),
  groupId: z.number(),
  groupName: z.string(),
  userId: z.number(),
  userNickname: z.string(),
  message: z.string(),
  timestamp: z.number(), // unix seconds
});
export type GroupMessage = z.infer<typeof GroupMessageSchema>;

/** A user-defined interest topic. */
export const InterestSchema = z.object({
  id: z.number(),
  userId: z.number(),
  keyword: z.string(),
  description: z.string(),
  createdAt: z.number(),
  active: z.number(),
});
export type Interest = z.infer<typeof InterestSchema>;

/** Query result returned to user. */
export interface QueryResult {
  summary: string;
  sources: Array<{
    groupName: string;
    userNickname: string;
    timestamp: string;
    snippet: string;
  }>;
}
