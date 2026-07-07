import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchMatches } from "../api/client";
import type { MatchSummary } from "../api/client";
import MatchCard from "../components/MatchCard";

const PRODUCT_TIME_ZONE = "Asia/Shanghai";

export default function HomePage() {
  const navigate = useNavigate();
  const [todayMatches, setTodayMatches] = useState<MatchSummary[]>([]);
  const [yesterdayMatches, setYesterdayMatches] = useState<MatchSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const today = getRelativeDate(0);
    Promise.all([
      fetchMatches(today, { includeUnfinished: true }),
      fetchMatches(getRelativeDate(-1)),
    ])
      .then(([today, yesterday]) => {
        setTodayMatches(today);
        setYesterdayMatches(yesterday);
      })
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

  const hasTodayMatches = todayMatches.length > 0;
  const hasYesterdayMatches = yesterdayMatches.length > 0;

  return (
    <div style={{ paddingBottom: 80 }}>
      <AppHeader />
      <div className="home-quick-actions">
        <button className="home-history-entry" onClick={() => navigate("/history")}>
          <span>🗓</span>
          历史比赛
        </button>
      </div>

      {!hasTodayMatches && !hasYesterdayMatches ? (
        <div className="empty-state">
          <div className="icon">⚽</div>
          <h3>暂无比赛</h3>
          <p>世界杯开赛后这里会显示每日战报</p>
        </div>
      ) : (
        <>
          {hasTodayMatches && (
            <>
              <div className="section-title">📅 今日赛程与战报</div>
              <div className="match-list">
                {todayMatches.map((m) => (
                  <MatchCard key={m.id} match={m} />
                ))}
              </div>
            </>
          )}

          {hasYesterdayMatches && (
            <>
              <div className="section-title">📆 昨日回顾</div>
              <div className="match-list">
                {yesterdayMatches.map((m) => (
                  <MatchCard key={m.id} match={m} />
                ))}
              </div>
            </>
          )}
        </>
      )}

      <BottomNav active="home" />
    </div>
  );
}

function getRelativeDate(offsetDays: number): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + offsetDays);
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: PRODUCT_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);

  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function AppHeader() {
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

export function BottomNav({ active }: { active: string }) {
  const navigate = useNavigate();

  return (
    <nav className="bottom-nav">
      <button className={`bottom-nav-item ${active === "home" ? "active" : ""}`} onClick={() => navigate("/")}>
        <span className="nav-icon">🏠</span>首页
      </button>
      <button className={`bottom-nav-item ${active === "predictions" ? "active" : ""}`} onClick={() => navigate("/predictions")}>
        <span className="nav-icon">🏆</span>预测
      </button>
      <button className={`bottom-nav-item ${active === "history" ? "active" : ""}`} onClick={() => navigate("/history")}>
        <span className="nav-icon">🗓</span>历史
      </button>
    </nav>
  );
}
