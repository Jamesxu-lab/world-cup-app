import { useEffect, useLayoutEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { fetchMatchDetail, fetchNarrative } from "../api/client";
import type { MatchDetail, NarrativeResponse } from "../api/client";
import { useAppStore } from "../store/useAppStore";
import StyleSwitch from "../components/StyleSwitch";
import NarrativeCardView from "../components/NarrativeCardView";
import ChatPanel from "../components/ChatPanel";
import { getTeamFlag } from "../utils/teamFlags";
import { BottomNav } from "./HomePage";

type MatchState = {
  matchId: string;
  data: MatchDetail | null;
  error: string;
};

type NarrativeState = {
  key: string;
  data: NarrativeResponse | null;
  error: string;
};

export default function NarrativePage() {
  const { matchId } = useParams<{ matchId: string }>();
  const navigate = useNavigate();
  const currentStyle = useAppStore((s) => s.currentStyle);
  const setStyle = useAppStore((s) => s.setStyle);

  const [matchState, setMatchState] = useState<MatchState>({
    matchId: "",
    data: null,
    error: "",
  });
  const [narrativeState, setNarrativeState] = useState<NarrativeState>({
    key: "",
    data: null,
    error: "",
  });

  const narrativeKey = matchId ? `${matchId}:${currentStyle}` : "";
  const match = matchState.matchId === matchId ? matchState.data : null;
  const error = matchState.matchId === matchId ? matchState.error : "";
  const narrative = narrativeState.key === narrativeKey ? narrativeState.data : null;
  const narrativeError = narrativeState.key === narrativeKey ? narrativeState.error : "";
  const loading = Boolean(matchId && !match && !error);

  useLayoutEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [matchId]);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;

    fetchMatchDetail(matchId)
      .then((m) => {
        if (!cancelled) {
          setMatchState({ matchId, data: m, error: "" });
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setMatchState({
            matchId,
            data: null,
            error: e.message || "加载比赛数据失败",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [matchId]);

  useEffect(() => {
    if (!matchId) return;
    const key = `${matchId}:${currentStyle}`;
    let cancelled = false;

    fetchNarrative(matchId, currentStyle)
      .then((data) => {
        if (!cancelled) {
          setNarrativeState({ key, data, error: "" });
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setNarrativeState({
            key,
            data: null,
            error: e.response?.status === 404
              ? "该风格的叙事尚未生成，切换风格试试"
              : e.message || "加载叙事失败",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [matchId, currentStyle]);

  const handleStyleSwitch = (style: string) => {
    setStyle(style as "formal" | "funny" | "tactical");
  };

  if (loading && !match) {
    return (
      <div style={{ padding: 16 }}>
        <div style={{ height: 20, marginBottom: 16 }} className="shimmer" />
        <div className="shimmer" style={{ height: 120, borderRadius: 20, marginBottom: 16 }} />
        <div className="shimmer" style={{ height: 48, borderRadius: 14, marginBottom: 16 }} />
        <div className="shimmer" style={{ height: 300, borderRadius: 20 }} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="empty-state">
        <div className="icon">😞</div>
        <h3>{error}</h3>
        <button onClick={() => navigate("/")} className="chat-send-btn" style={{ marginTop: 16 }}>
          返回首页
        </button>
      </div>
    );
  }

  const roundLabel = match?.round || "";
  const penaltyScore =
    match?.penalty_home_score !== null &&
    match?.penalty_home_score !== undefined &&
    match?.penalty_away_score !== null &&
    match?.penalty_away_score !== undefined
      ? `点球 ${match.penalty_home_score} - ${match.penalty_away_score}`
      : "";

  return (
    <div style={{ paddingBottom: 80 }}>
      {/* 浮动装饰 */}
      <div className="deco-stars">
        <span className="deco-star" style={{ left: "10%", animationDelay: "0s" }}>⚽</span>
        <span className="deco-star" style={{ left: "30%", animationDelay: "2s" }}>⭐</span>
        <span className="deco-star" style={{ left: "55%", animationDelay: "4s" }}>⚽</span>
        <span className="deco-star" style={{ left: "75%", animationDelay: "1s" }}>🏆</span>
        <span className="deco-star" style={{ left: "90%", animationDelay: "3s" }}>⭐</span>
      </div>

      {/* 返回按钮 */}
      <div className="nav-back">
        <button onClick={() => navigate("/")}>← 返回首页</button>
      </div>

      {/* 比分英雄区 */}
      {match && (
        <div className="score-hero">
          <div className="score-hero-round">🏆 {roundLabel} · {match.stadium}</div>
          <div className="score-hero-teams">
            <div className="score-hero-team">
              <span className="flag">{getTeamFlag(match.home_team)}</span>
              <span className="name">{match.home_team}</span>
            </div>
            <div className="score-hero-center">
              <div className="score-hero-nums">
                {match.home_score ?? "-"} - {match.away_score ?? "-"}
              </div>
              {match.status_code === "PEN" && (
                <div className="score-hero-vs">{penaltyScore || "点球决胜"}</div>
              )}
            </div>
            <div className="score-hero-team">
              <span className="flag">{getTeamFlag(match.away_team)}</span>
              <span className="name">{match.away_team}</span>
            </div>
          </div>
        </div>
      )}

      {/* 风格切换器 */}
      <StyleSwitch onSwitch={handleStyleSwitch} />

      {/* 叙事文章 */}
      {narrative ? (
        <div className="narrative-article">
          {/* 文章头 */}
          <div className="article-header">
            <div className="article-meta">
              <span className="article-meta-dot" />
              <span className="article-meta-style">AI 战报 · {narrative.style_name}</span>
            </div>
            {narrative.cards.length > 0 && (
              <>
                <h2 className="article-title">{narrative.cards[0].title}</h2>
                <p className="article-subtitle">
                  {match?.home_team} vs {match?.away_team} · {roundLabel} · {match?.stadium}
                </p>
              </>
            )}
          </div>

          {/* 第一张卡片：开篇 */}
          {narrative.cards.length > 0 && (
            <div className="article-section">
              <span className="section-badge type-opening">
                <span className="badge-dot" />
                开篇
              </span>
              <p className="section-body">{narrative.cards[0].content}</p>
            </div>
          )}

          {/* 后续卡片 */}
          {narrative.cards.slice(1).map((card) => (
            <div key={card.card_index}>
              <div className="section-divider" />
              <NarrativeCardView card={card} isLast={false} />
            </div>
          ))}
        </div>
      ) : narrativeError ? (
        <div className="empty-state" style={{ padding: "40px 20px" }}>
          <div className="icon">📝</div>
          <p>{narrativeError}</p>
        </div>
      ) : (
        <div style={{ margin: "12px 14px", padding: 24 }}>
          {[1, 2, 3].map((i) => (
            <div key={i} className="shimmer" style={{ height: 20, marginBottom: 12 }} />
          ))}
        </div>
      )}

      {/* 追问对话 */}
      {matchId && (
        <ChatPanel matchId={matchId} />
      )}

      <BottomNav active="" />
    </div>
  );
}
