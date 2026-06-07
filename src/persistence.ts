import Database from "better-sqlite3";
import { mkdirSync } from "fs";
import { dirname } from "path";
import type { GroupMessage, Interest } from "./models.js";

export class MessageStore {
  private db: Database.Database;

  constructor(dbPath: string) {
    if (dbPath !== ":memory:") {
      mkdirSync(dirname(dbPath), { recursive: true });
    }
    this.db = new Database(dbPath);
    this.db.pragma("journal_mode = WAL");
  }

  init(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS group_messages (
        message_id INTEGER PRIMARY KEY,
        group_id INTEGER NOT NULL,
        group_name TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        user_nickname TEXT NOT NULL,
        message TEXT NOT NULL,
        timestamp INTEGER NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_group_timestamp
        ON group_messages(group_id, timestamp);
      CREATE INDEX IF NOT EXISTS idx_timestamp
        ON group_messages(timestamp);

      CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
        message, tokenize='unicode61'
      );

      CREATE TABLE IF NOT EXISTS interests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        keyword TEXT NOT NULL,
        description TEXT,
        created_at INTEGER NOT NULL,
        active INTEGER DEFAULT 1
      );
      CREATE INDEX IF NOT EXISTS idx_user_active
        ON interests(user_id, active);
    `);
  }

  saveGroupMessage(msg: GroupMessage): void {
    this.db.prepare(`
      INSERT OR REPLACE INTO group_messages
      (message_id, group_id, group_name, user_id, user_nickname, message, timestamp)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(
      msg.messageId, msg.groupId, msg.groupName,
      msg.userId, msg.userNickname, msg.message, msg.timestamp
    );
    // Keep FTS in sync
    this.db.prepare("DELETE FROM messages_fts WHERE rowid = ?").run(msg.messageId);
    this.db.prepare("INSERT INTO messages_fts(rowid, message) VALUES (?, ?)").run(
      msg.messageId, msg.message
    );
  }

  searchMessages(opts: {
    query: string;
    groupIds?: number[] | null;
    startTime?: number | null;
    limit?: number;
  }): GroupMessage[] {
    const { query, groupIds, startTime, limit = 50 } = opts;

    // Try FTS first
    const ftsQuery = this.buildFtsQuery(query);
    if (ftsQuery) {
      const results = this.searchFts(ftsQuery, groupIds, startTime, limit);
      if (results.length > 0) return results;
    }

    // Fallback to LIKE
    return this.searchLike(query, groupIds, startTime, limit);
  }

  private buildFtsQuery(query: string): string {
    const tokens = query.match(/[\w一-鿿]+/g);
    return tokens ? tokens.join(" ") : "";
  }

  private searchFts(
    ftsQuery: string,
    groupIds?: number[] | null,
    startTime?: number | null,
    limit = 50
  ): GroupMessage[] {
    let sql = `
      SELECT gm.message_id, gm.group_id, gm.group_name, gm.user_id,
             gm.user_nickname, gm.message, gm.timestamp
      FROM messages_fts
      JOIN group_messages gm ON gm.message_id = messages_fts.rowid
      WHERE messages_fts MATCH ?
    `;
    const params: unknown[] = [ftsQuery];

    if (groupIds && groupIds.length > 0) {
      sql += ` AND gm.group_id IN (${groupIds.map(() => "?").join(",")})`;
      params.push(...groupIds);
    }
    if (startTime != null) {
      sql += " AND gm.timestamp >= ?";
      params.push(startTime);
    }
    sql += " ORDER BY gm.timestamp DESC LIMIT ?";
    params.push(limit);

    try {
      const rows = this.db.prepare(sql).all(...params) as any[];
      return rows.map(this.rowToMessage);
    } catch {
      return [];
    }
  }

  private searchLike(
    query: string,
    groupIds?: number[] | null,
    startTime?: number | null,
    limit = 50
  ): GroupMessage[] {
    let sql = `
      SELECT message_id, group_id, group_name, user_id,
             user_nickname, message, timestamp
      FROM group_messages
      WHERE message LIKE ?
    `;
    const params: unknown[] = [`%${query}%`];

    if (groupIds && groupIds.length > 0) {
      sql += ` AND group_id IN (${groupIds.map(() => "?").join(",")})`;
      params.push(...groupIds);
    }
    if (startTime != null) {
      sql += " AND timestamp >= ?";
      params.push(startTime);
    }
    sql += " ORDER BY timestamp DESC LIMIT ?";
    params.push(limit);

    const rows = this.db.prepare(sql).all(...params) as any[];
    return rows.map(this.rowToMessage);
  }

  private rowToMessage(row: any): GroupMessage {
    return {
      messageId: row.message_id,
      groupId: row.group_id,
      groupName: row.group_name,
      userId: row.user_id,
      userNickname: row.user_nickname,
      message: row.message,
      timestamp: row.timestamp,
    };
  }

  addInterest(userId: number, keyword: string, description: string): void {
    this.db.prepare(`
      INSERT INTO interests (user_id, keyword, description, created_at, active)
      VALUES (?, ?, ?, ?, 1)
    `).run(userId, keyword, description, Math.floor(Date.now() / 1000));
  }

  getInterests(userId: number): Interest[] {
    return this.db.prepare(`
      SELECT id, user_id, keyword, description, created_at, active
      FROM interests WHERE user_id = ? AND active = 1
      ORDER BY created_at DESC
    `).all(userId) as any[];
  }

  removeInterest(interestId: number): void {
    this.db.prepare("UPDATE interests SET active = 0 WHERE id = ?").run(interestId);
  }

  getUsersWithInterests(): number[] {
    const rows = this.db.prepare(
      "SELECT DISTINCT user_id FROM interests WHERE active = 1"
    ).all() as any[];
    return rows.map((r) => r.user_id);
  }

  close(): void {
    this.db.close();
  }
}
