import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchMatchHistory } from "../api/client";
import type { MatchSummary } from "../api/client";
import MatchCard from "../components/MatchCard";
import { AppHeader, BottomNav } from "./HomePage";

export default function HistoryPage() {
  const navigate = useNavigate();
  const [matches, setMatches] = useState<MatchSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchMatchHistory()
      .then(setMatches)
      .catch((e) => setError(e.message || "历史比赛加载失败"))
      .finally(() => setLoading(false));
  }, []);

  const groupedMatches = useMemo(() => {
    const groups = new Map<string, MatchSummary[]>();
    for (const match of matches) {
      const day = match.match_day || match.match_date.slice(0, 10);
      groups.set(day, [...(groups.get(day) || []), match]);
    }
    return Array.from(groups.entries());
  }, [matches]);

  if (loading) {
    return (
      <div style={{ paddingBottom: 80 }}>
        <AppHeader />
        <div className="nav-back">
          <button onClick={() => navigate("/")}>← 返回首页</button>
        </div>
        <div className="p-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="match-card mb-3" style={{ cursor: "default" }}>
              <div className="shimmer" style={{ height: 18, width: "38%", marginBottom: 12 }} />
              <div className="shimmer" style={{ height: 38, marginBottom: 10 }} />
              <div className="shimmer" style={{ height: 14, width: "76%" }} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ paddingBottom: 80 }}>
        <AppHeader />
        <div className="empty-state">
          <div className="icon">📋</div>
          <h3>加载失败</h3>
          <p>{error}</p>
          <button className="chat-send-btn" onClick={() => window.location.reload()} style={{ marginTop: 20 }}>
            重试
          </button>
        </div>
        <BottomNav active="history" />
      </div>
    );
  }

  return (
    <div style={{ paddingBottom: 80 }}>
      <AppHeader />
      <div className="history-header">
        <button className="history-back" onClick={() => navigate("/")}>←</button>
        <div>
          <h2>历史比赛</h2>
          <p>已完赛场次回看</p>
        </div>
      </div>

      {groupedMatches.length === 0 ? (
        <div className="empty-state">
          <div className="icon">⚽</div>
          <h3>暂无历史比赛</h3>
          <p>完赛后会自动收录到这里</p>
        </div>
      ) : (
        groupedMatches.map(([day, dayMatches]) => (
          <section key={day}>
            <div className="section-title">📆 {formatDay(day)}</div>
            <div className="match-list">
              {dayMatches.map((match) => (
                <MatchCard key={match.id} match={match} />
              ))}
            </div>
          </section>
        ))
      )}

      <BottomNav active="history" />
    </div>
  );
}

function formatDay(day: string) {
  const [year, month, date] = day.split("-");
  return `${year}年${Number(month)}月${Number(date)}日`;
}
