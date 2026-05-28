import { useEffect, useState } from "react";
import { fetchMatches } from "../api/client";
import type { MatchSummary } from "../api/client";
import MatchCard from "../components/MatchCard";

export default function HomePage() {
  const [matches, setMatches] = useState<MatchSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchMatches()
      .then(setMatches)
      .catch((e) => setError(e.message || "加载失败"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div>
        <AppHeader />
        <div className="p-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="match-card mb-3" style={{ cursor: "default" }}>
              <div className="shimmer" style={{ height: 20, width: "40%", marginBottom: 12 }} />
              <div className="shimmer" style={{ height: 40, marginBottom: 10 }} />
              <div className="shimmer" style={{ height: 14, width: "80%" }} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <AppHeader />
        <div className="empty-state">
          <div className="icon">😞</div>
          <h3>加载失败</h3>
          <p>{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="chat-send-btn"
            style={{ marginTop: 20 }}
          >
            重试
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ paddingBottom: 80 }}>
      <AppHeader />

      {matches.length === 0 ? (
        <div className="empty-state">
          <div className="icon">⚽</div>
          <h3>暂无比赛</h3>
          <p>世界杯开赛后这里会显示每日战报</p>
        </div>
      ) : (
        <>
          <div className="section-title">📅 今日战报</div>
          <div className="match-list">
            {matches.map((m) => (
              <MatchCard key={m.id} match={m} />
            ))}
          </div>
        </>
      )}

      <BottomNav active="home" />
    </div>
  );
}

function AppHeader() {
  return (
    <header className="app-header">
      <div className="app-logo">
        <div className="app-logo-icon">⚽</div>
        <div className="app-logo-text">
          <h1>晨报球搭子</h1>
          <p>AI 世界杯战报</p>
        </div>
      </div>
      <span className="app-badge">🏆 2026</span>
    </header>
  );
}

function BottomNav({ active }: { active: string }) {
  return (
    <nav className="bottom-nav">
      <button className={`bottom-nav-item ${active === "home" ? "active" : ""}`}>
        <span className="nav-icon">🏠</span>首页
      </button>
      <button className={`bottom-nav-item ${active === "events" ? "active" : ""}`}>
        <span className="nav-icon">🏆</span>赛事
      </button>
      <button className={`bottom-nav-item ${active === "me" ? "active" : ""}`}>
        <span className="nav-icon">👤</span>我的
      </button>
    </nav>
  );
}
