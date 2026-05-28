import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
});

export interface MatchSummary {
  id: string;
  fixture_id: number;
  home_team: string;
  away_team: string;
  home_score: number | null;
  away_score: number | null;
  match_date: string;
  round: string;
  group_name: string;
  stadium: string;
  status: string;
  hook: string;
  available_styles: string[];
}

export interface MatchDetail extends MatchSummary {
  city: string;
  events: MatchEvent[];
  stats: Record<string, Record<string, number>>;
  top_players: PlayerBrief[];
}

export interface MatchEvent {
  minute: number;
  extra_minute: number | null;
  event_type: string;
  detail: string;
  player_name: string;
  team: string;
  assist_player: string | null;
}

export interface PlayerBrief {
  name: string;
  team: string;
  position: string;
  rating: number;
  goals: number;
  assists: number;
}

export interface NarrativeCard {
  card_index: number;
  card_type: string;
  title: string;
  content: string;
}

export interface NarrativeResponse {
  match_id: string;
  style: string;
  style_name: string;
  cards: NarrativeCard[];
  card_count: number;
}

export async function fetchMatches(date?: string): Promise<MatchSummary[]> {
  const params = date ? { date } : {};
  const { data } = await api.get("/matches", { params });
  return data.matches;
}

export async function fetchMatchDetail(id: string): Promise<MatchDetail> {
  const { data } = await api.get(`/matches/${id}`);
  return data;
}

export async function fetchNarrative(
  matchId: string,
  style: string
): Promise<NarrativeResponse> {
  const { data } = await api.get(`/matches/${matchId}/narrative`, {
    params: { style },
  });
  return data;
}

// ===== 追问对话（SSE 流式） =====

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

/**
 * 流式聊天：通过 SSE 逐 token 接收 AI 回复。
 * onToken 回调在每收到一个 token 时触发，onDone 在流结束时触发。
 */
export async function chatWithAIStream(
  matchId: string,
  question: string,
  history: ChatMessage[],
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (error: string) => void
): Promise<void> {
  try {
    const response = await fetch(`/api/v1/matches/${matchId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history }),
    });

    if (!response.ok) {
      onError(`请求失败: ${response.status}`);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      onError("无法读取响应流");
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6).trim();

        if (payload === "[DONE]") {
          onDone();
          return;
        }

        try {
          const parsed = JSON.parse(payload);
          if (parsed.token) {
            onToken(parsed.token);
          }
        } catch {
          // 忽略解析错误
        }
      }
    }

    onDone();
  } catch (e) {
    onError(e instanceof Error ? e.message : "网络错误");
  }
}
