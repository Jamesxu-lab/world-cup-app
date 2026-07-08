import { Link } from "react-router-dom";
import type { MatchSummary } from "../api/client";
import { getTeamFlag } from "../utils/teamFlags";

interface Props {
  match: MatchSummary;
  interactive?: boolean;
}

export default function MatchCard({ match, interactive = true }: Props) {
  const score =
    match.home_score !== null && match.away_score !== null
      ? `${match.home_score} - ${match.away_score}`
      : "vs";
  const penaltyScore =
    match.penalty_home_score !== null && match.penalty_away_score !== null
      ? `点球 ${match.penalty_home_score} - ${match.penalty_away_score}`
      : "";
  const scoreLabel = match.status_code === "PEN" ? penaltyScore || "点球决胜" : "";

  const roundLabel = match.round || "";
  const stadiumLabel = match.stadium || "";
  const matchLabel = `${match.home_team} ${score} ${match.away_team}${scoreLabel ? `，${scoreLabel}` : ""}，${roundLabel}，${stadiumLabel}`;

  const content = (
    <>
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
          {scoreLabel && <div className="score-label">{scoreLabel}</div>}
        </div>
        <div className="match-card-team">
          <span className="flag">{getTeamFlag(match.away_team)}</span>
          <span className="name">{match.away_team}</span>
        </div>
      </div>
    </>
  );

  if (!interactive) {
    return (
      <article className="match-card match-card-static" aria-label={`比赛结果：${matchLabel}`}>
        {content}
      </article>
    );
  }

  return (
    <Link
      className="match-card"
      to={`/match/${match.id}`}
      aria-label={`查看比赛详情：${matchLabel}`}
    >
      {content}
    </Link>
  );
}
