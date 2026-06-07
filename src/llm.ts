export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export class LLMProvider {
  private baseUrl: string;
  private apiKey: string;
  private model: string;
  private timeout: number;

  constructor(opts: { baseUrl: string; apiKey: string; model: string; timeout?: number }) {
    this.baseUrl = opts.baseUrl.replace(/\/+$/, "");
    this.apiKey = opts.apiKey;
    this.model = opts.model;
    this.timeout = (opts.timeout ?? 30) * 1000;
  }

  async chatCompletion(
    messages: ChatMessage[],
    opts?: { temperature?: number; maxTokens?: number }
  ): Promise<string> {
    const { temperature = 0.7, maxTokens = 1000 } = opts ?? {};

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(`${this.baseUrl}/chat/completions`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: this.model,
          messages,
          temperature,
          max_tokens: maxTokens,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`LLM API error: ${response.status} ${response.statusText}`);
      }

      const data = (await response.json()) as any;
      return data.choices[0].message.content;
    } finally {
      clearTimeout(timer);
    }
  }
}
