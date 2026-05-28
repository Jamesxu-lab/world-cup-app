import { useNavigate } from "react-router-dom";
import type { MatchSummary } from "../api/client";

interface Props {
  match: MatchSummary;
}

const FLAGS: Record<string, string> = {
  阿根廷: "🇦🇷", 法国: "🇫🇷", 英格兰: "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
  巴西: "🇧🇷", 德国: "🇩🇪", 西班牙: "🇪🇸",
  葡萄牙: "🇵🇹", 荷兰: "🇳🇱", 比利时: "🇧🇪",
  克罗地亚: "🇭🇷", 摩洛哥: "🇲🇦", 日本: "🇯🇵",
  韩国: "🇰🇷", 澳大利亚: "🇦🇺", 沙特阿拉伯: "🇸🇦",
  卡塔尔: "🇶🇦", 厄瓜多尔: "🇪🇨", 乌拉圭: "🇺🇾",
  加拿大: "🇨🇦", 美国: "🇺🇸", 墨西哥: "🇲🇽",
  加纳: "🇬🇭", 塞内加尔: "🇸🇳", 喀麦隆: "🇨🇲",
  突尼斯: "🇹🇳", 塞尔维亚: "🇷🇸", 瑞士: "🇨🇭",
  丹麦: "🇩🇰", 威尔士: "🏴󠁧󠁢󠁷󠁬󠁳󠁿", 波兰: "🇵🇱",
  意大利: "🇮🇹", 哥伦比亚: "🇨🇴", 智利: "🇨🇱",
  秘鲁: "🇵🇪", 瑞典: "🇸🇪",
};

export default function MatchCard({ match }: Props) {
  const navigate = useNavigate();

  const score =
    match.home_score !== null && match.away_score !== null
      ? `${match.home_score} - ${match.away_score}`
      : "vs";

  const roundLabel = match.round || "";
  const stadiumLabel = match.stadium || "";

  return (
    <div className="match-card" onClick={() => navigate(`/match/${match.id}`)}>
      {/* 赛事轮次 */}
      <div className="match-card-round">🏟 {roundLabel} · {stadiumLabel}</div>

      {/* 球队+比分 */}
      <div className="match-card-teams">
        <div className="match-card-team">
          <span className="flag">{FLAGS[match.home_team] || "🏳️"}</span>
          <span className="name">{match.home_team}</span>
        </div>
        <div className="match-card-score">
          <div className="score-num">{score}</div>
          {match.status === "PEN" && <div className="score-label">点球决胜</div>}
        </div>
        <div className="match-card-team">
          <span className="flag">{FLAGS[match.away_team] || "🏳️"}</span>
          <span className="name">{match.away_team}</span>
        </div>
      </div>

      {/* 钩子 */}
      {match.hook && (
        <div className="match-card-hook">💬 {match.hook}</div>
      )}
    </div>
  );
}
