import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { fetchMatchDetail, fetchNarrative } from "../api/client";
import type { MatchDetail, NarrativeResponse } from "../api/client";
import { useAppStore } from "../store/useAppStore";
import StyleSwitch from "../components/StyleSwitch";
import NarrativeCardView from "../components/NarrativeCardView";
import ChatPanel from "../components/ChatPanel";

export default function NarrativePage() {
  const { matchId } = useParams<{ matchId: string }>();
  const navigate = useNavigate();
  const currentStyle = useAppStore((s) => s.currentStyle);
  const setStyle = useAppStore((s) => s.setStyle);

  const [match, setMatch] = useState<MatchDetail | null>(null);
  const [narrative, setNarrative] = useState<NarrativeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [narrativeError, setNarrativeError] = useState("");

  useEffect(() => {
    if (!matchId) return;
    setLoading(true);
    setError("");
    setNarrativeError("");
    setNarrative(null);

    fetchMatchDetail(matchId)
      .then((m) => {
        setMatch(m);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message || "加载比赛数据失败");
        setLoading(false);
      });

    fetchNarrative(matchId, currentStyle)
      .then(setNarrative)
      .catch((e) => {
        if (e.response?.status === 404) {
          setNarrativeError("该风格的叙事尚未生成，切换风格试试");
        } else {
          setNarrativeError(e.message || "加载叙事失败");
        }
      });
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
              <span className="flag">{getFlag(match.home_team)}</span>
              <span className="name">{match.home_team}</span>
            </div>
            <div className="score-hero-center">
              <div className="score-hero-nums">
                {match.home_score ?? "-"} - {match.away_score ?? "-"}
              </div>
              {match.status === "PEN" && <div className="score-hero-vs">点球决胜</div>}
            </div>
            <div className="score-hero-team">
              <span className="flag">{getFlag(match.away_team)}</span>
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

      {/* 底部导航 */}
      <nav className="bottom-nav">
        <button className="bottom-nav-item" onClick={() => navigate("/")}>
          <span className="nav-icon">🏠</span>首页
        </button>
        <button className="bottom-nav-item">
          <span className="nav-icon">🏆</span>赛事
        </button>
        <button className="bottom-nav-item">
          <span className="nav-icon">👤</span>我的
        </button>
      </nav>
    </div>
  );
}

/** 简单的队名→国旗映射 */
function getFlag(team: string): string {
  const flags: Record<string, string> = {
    阿根廷: "🇦🇷", 法国: "🇫🇷", 英格兰: "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    巴西: "🇧🇷", 德国: "🇩🇪", 西班牙: "🇪🇸",
    葡萄牙: "🇵🇹", 荷兰: "🇳🇱", 比利时: "🇧🇪",
    克罗地亚: "🇭🇷", 摩洛哥: "🇲🇦", 日本: "🇯🇵",
    韩国: "🇰🇷", 澳大利亚: "🇦🇺", 沙特阿拉伯: "🇸🇦",
    卡塔尔: "🇶🇦", 厄瓜多尔: "🇪🇨", 乌拉圭: "🇺🇾",
    加拿大: "🇨🇦", 美国: "🇺🇸", 墨西哥: "🇲🇽",
    加纳: "🇬🇭", 塞内加尔: "🇸🇳", 喀麦隆: "🇨🇲",
    南非: "🇿🇦", 突尼斯: "🇹🇳", 塞尔维亚: "🇷🇸",
    瑞士: "🇨🇭", 丹麦: "🇩🇰", 威尔士: "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
    波兰: "🇵🇱", 意大利: "🇮🇹", 哥伦比亚: "🇨🇴",
    智利: "🇨🇱", 秘鲁: "🇵🇪", 瑞典: "🇸🇪",
  };
  return flags[team] || "🏳️";
}
