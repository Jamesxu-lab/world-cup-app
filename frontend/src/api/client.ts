import axios from "axios";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, "");

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

function apiUrl(path: string) {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

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

// ===== 冠军预测 =====

export interface PredictionTeam {
  team: string;
  confederation: string;
  qualified: boolean;
  team_score: number;
  score_index: number;
  title_probability: number;
  final_probability: number;
  semi_final_probability: number;
  quarter_final_probability: number;
  round_of_16_probability: number;
  round_of_32_probability: number;
  drivers: {
    elo: number;
    squad: number;
    recent_form: number;
    availability: number;
    tournament_experience: number;
    defense: number;
    coach_stability: number;
  };
}

export interface ChampionPredictionResponse {
  model_version: string;
  as_of: string;
  iterations: number;
  format: string;
  data_note: string;
  weights: Record<string, number>;
  field_strength: {
    average_score: number;
    top_score: number;
    score_spread: number;
  };
  teams: PredictionTeam[];
}

export async function fetchChampionPrediction(
  iterations = 10000
): Promise<ChampionPredictionResponse> {
  const { data } = await api.get("/predictions/champion", {
    params: { iterations },
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
    const response = await fetch(apiUrl(`/matches/${matchId}/chat`), {
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
      const answer = await chatWithAI(matchId, question, history);
      onToken(answer);
      onDone();
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
    try {
      const answer = await chatWithAI(matchId, question, history);
      onToken(answer);
      onDone();
    } catch (fallbackError) {
      onError(fallbackError instanceof Error ? fallbackError.message : e instanceof Error ? e.message : "网络错误");
    }
  }
}

export async function chatWithAI(
  matchId: string,
  question: string,
  history: ChatMessage[]
): Promise<string> {
  const { data } = await api.post(`/matches/${matchId}/chat/plain`, {
    question,
    history,
  });
  return data.answer;
}
