import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchChampionPrediction } from "../api/client";
import type { ChampionPredictionResponse, PredictionTeam } from "../api/client";
import { BottomNav } from "./HomePage";

const driverLabels: Record<keyof PredictionTeam["drivers"], string> = {
  elo: "长期实力",
  squad: "阵容质量",
  recent_form: "近期状态",
  availability: "伤病可用",
  tournament_experience: "大赛经验",
  defense: "防守稳定",
  coach_stability: "教练稳定",
};

export default function PredictionPage() {
  const [prediction, setPrediction] = useState<ChampionPredictionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchChampionPrediction()
      .then(setPrediction)
      .catch((e) => setError(e.message || "预测模型加载失败"))
      .finally(() => setLoading(false));
  }, []);

  const topTeams = useMemo(() => prediction?.teams.slice(0, 3) ?? [], [prediction]);
  const leader = topTeams[0];

  if (loading) {
    return (
      <div style={{ paddingBottom: 80 }}>
        <PredictionHeader />
        <div className="prediction-panel">
          <div className="shimmer" style={{ height: 28, width: "62%", marginBottom: 16 }} />
          <div className="shimmer" style={{ height: 96, borderRadius: 16, marginBottom: 12 }} />
          {[1, 2, 3, 4].map((item) => (
            <div key={item} className="shimmer" style={{ height: 54, marginBottom: 10 }} />
          ))}
        </div>
      </div>
    );
  }

  if (error || !prediction) {
    return (
      <div>
        <PredictionHeader />
        <div className="empty-state">
          <div className="icon">🏆</div>
          <h3>预测加载失败</h3>
          <p>{error || "暂无模型结果"}</p>
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
      <PredictionHeader />

      {leader && (
        <section className="prediction-hero">
          <div className="prediction-eyebrow">Monte Carlo · {prediction.iterations.toLocaleString()} 次模拟</div>
          <div className="prediction-leader">
            <div>
              <span className="prediction-trophy">🏆</span>
              <h2>{leader.team}</h2>
              <p>当前模型最可能冠军</p>
            </div>
            <strong>{formatPercent(leader.title_probability)}</strong>
          </div>
          <div className="prediction-meter">
            <span style={{ width: `${Math.max(leader.title_probability * 100, 5)}%` }} />
          </div>
        </section>
      )}

      <section className="prediction-panel">
        <div className="prediction-section-head">
          <h3>冠军概率 Top 3</h3>
          <span>{prediction.as_of}</span>
        </div>
        <div className="prediction-list">
          {topTeams.map((team, index) => (
            <TeamProbabilityRow key={team.team} team={team} rank={index + 1} />
          ))}
        </div>
      </section>

      {leader && (
        <section className="prediction-panel">
          <div className="prediction-section-head">
            <h3>{leader.team} 晋级路径</h3>
            <span>路径概率</span>
          </div>
          <div className="stage-grid">
            <StageItem label="32强" value={leader.round_of_32_probability} />
            <StageItem label="16强" value={leader.round_of_16_probability} />
            <StageItem label="8强" value={leader.quarter_final_probability} />
            <StageItem label="4强" value={leader.semi_final_probability} />
            <StageItem label="决赛" value={leader.final_probability} />
            <StageItem label="冠军" value={leader.title_probability} />
          </div>
        </section>
      )}

      {leader && (
        <section className="prediction-panel">
          <div className="prediction-section-head">
            <h3>模型因子</h3>
            <span>综合评分 {leader.score_index}</span>
          </div>
          <div className="driver-list">
            {(Object.keys(leader.drivers) as Array<keyof PredictionTeam["drivers"]>).map((key) => (
              <div className="driver-row" key={key}>
                <span>{driverLabels[key]}</span>
                <div className="driver-bar">
                  <span style={{ width: `${leader.drivers[key]}%` }} />
                </div>
                <strong>{leader.drivers[key]}</strong>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="prediction-note">
        <p>{prediction.data_note}</p>
        <p>{prediction.format}</p>
        <p className="prediction-disclaimer">
          预测结果基于公开数据、球队评分与蒙特卡洛模拟，仅用于赛事分析与娱乐参考，不构成投注、竞猜或任何收益承诺。
        </p>
      </section>

      <BottomNav active="predictions" />
    </div>
  );
}

function PredictionHeader() {
  const navigate = useNavigate();

  return (
    <header className="app-header">
      <button className="prediction-back" onClick={() => navigate("/")}>←</button>
      <div className="app-logo-text">
        <h1>冠军预测模型</h1>
        <p>球队实力评分 × 赛程模拟</p>
      </div>
      <span className="app-badge">v1</span>
    </header>
  );
}

function TeamProbabilityRow({ team, rank }: { team: PredictionTeam; rank: number }) {
  return (
    <article className="prediction-row">
      <div className="prediction-rank">{rank}</div>
      <div className="prediction-team-main">
        <div className="prediction-team-title">
          <strong>{team.team}</strong>
          <span>{team.confederation}</span>
        </div>
        <div className="prediction-meter compact">
          <span style={{ width: `${Math.max(team.title_probability * 100, 2)}%` }} />
        </div>
      </div>
      <div className="prediction-prob">{formatPercent(team.title_probability)}</div>
    </article>
  );
}

function StageItem({ label, value }: { label: string; value: number }) {
  return (
    <div className="stage-item">
      <span>{label}</span>
      <strong>{formatPercent(value)}</strong>
    </div>
  );
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(value >= 0.1 ? 1 : 2)}%`;
}
