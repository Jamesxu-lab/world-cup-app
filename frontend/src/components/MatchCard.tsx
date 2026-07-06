import { Link } from "react-router-dom";
import type { MatchSummary } from "../api/client";
import { getTeamFlag } from "../utils/teamFlags";

interface Props {
  match: MatchSummary;
}

export default function MatchCard({ match }: Props) {
  const score =
    match.home_score !== null && match.away_score !== null
      ? `${match.home_score} - ${match.away_score}`
      : "vs";

  const roundLabel = match.round || "";
  const stadiumLabel = match.stadium || "";
  const matchLabel = `${match.home_team} ${score} ${match.away_team}，${roundLabel}，${stadiumLabel}`;

  return (
    <Link
      className="match-card"
      to={`/match/${match.id}`}
      aria-label={`查看比赛详情：${matchLabel}`}
    >
      {/* 赛事轮次 */}
      <div className="match-card-round">🏟 {roundLabel} · {stadiumLabel}</div>

      {/* 球队+比分 */}
      <div className="match-card-teams">
        <div className="match-card-team">
          <span className="flag">{getTeamFlag(match.home_team)}</span>
          <span className="name">{match.home_team}</span>
        </div>
        <div className="match-card-score">
          <div className="score-num">{score}</div>
          {match.status === "PEN" && <div className="score-label">点球决胜</div>}
        </div>
        <div className="match-card-team">
          <span className="flag">{getTeamFlag(match.away_team)}</span>
          <span className="name">{match.away_team}</span>
        </div>
      </div>

      {/* 钩子 */}
      {match.hook && (
        <div className="match-card-hook">💬 {match.hook}</div>
      )}
    </Link>
  );
}
