"""
Lightweight 2026 World Cup champion prediction model.

The first version keeps the model deterministic, dependency-free, and easy to
replace with live Elo/FIFA/squad feeds later.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from math import exp
from pathlib import Path
from random import Random
from statistics import mean
from typing import Literal

from app.core.database import SessionLocal
from app.i18n import get_team_cn
from app.models.match import Match


Stage = Literal["group", "round_of_32", "round_of_16", "quarter_final", "semi_final", "final", "champion"]


@dataclass(frozen=True)
class TeamProfile:
    name: str
    confederation: str
    elo: int
    squad: int
    recent_form: int
    tournament_experience: int
    defense: int
    coach_stability: int
    qualified: bool = True
    group: str | None = None
    name_en: str | None = None
    fifa_rank: int | None = None
    fifa_points: float | None = None
    squad_count: int | None = None
    unavailable_count: int = 0
    doubtful_count: int = 0
    availability_score: int = 100
    squad_quality_score: int | None = None
    recent_form_score: int | None = None
    elo_rating_change_3m: int | None = None
    elo_rating_change_6m: int | None = None
    elo_rating_change_1y: int | None = None
    played_matches: int = 0
    points_per_game: float | None = None
    goal_difference_per_game: float | None = None


@dataclass
class SimTeam:
    profile: TeamProfile
    score: float
    points: int = 0
    goals_for: int = 0
    goals_against: int = 0

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against


WEIGHTS = {
    "elo": 0.35,
    "squad": 0.20,
    "recent_form": 0.20,
    "tournament_experience": 0.10,
    "defense": 0.10,
    "coach_stability": 0.05,
}
MODEL_VERSION = "lightweight-v4-known-eliminations"

STAGE_LABELS: dict[Stage, str] = {
    "group": "小组赛",
    "round_of_32": "32 强",
    "round_of_16": "16 强",
    "quarter_final": "8 强",
    "semi_final": "4 强",
    "final": "决赛",
    "champion": "冠军",
}

SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "data" / "prediction_snapshot.json"
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "worldcup.db"
RESULTS_PATH = Path(__file__).resolve().parents[3] / "2026_World_Cup_Results.md"
COMPLETED_STATUSES = {"FT", "AET", "PEN"}
KNOCKOUT_ROUND_KEYWORDS = (
    "round of 32",
    "round of 16",
    "quarter",
    "semi",
    "final",
    "32强",
    "32 强",
    "十六",
    "八分之一",
    "四分之一",
    "半决赛",
    "决赛",
)


SEED_TEAMS: list[TeamProfile] = [
    TeamProfile("阿根廷", "CONMEBOL", 2140, 92, 88, 96, 86, 86),
    TeamProfile("法国", "UEFA", 2132, 96, 86, 92, 88, 82),
    TeamProfile("西班牙", "UEFA", 2075, 91, 91, 86, 89, 84),
    TeamProfile("英格兰", "UEFA", 2068, 94, 84, 82, 86, 76),
    TeamProfile("巴西", "CONMEBOL", 2058, 93, 78, 94, 82, 68),
    TeamProfile("葡萄牙", "UEFA", 2042, 90, 87, 82, 83, 78),
    TeamProfile("荷兰", "UEFA", 2024, 87, 83, 86, 88, 78),
    TeamProfile("德国", "UEFA", 2018, 88, 85, 92, 82, 74),
    TeamProfile("意大利", "UEFA", 1988, 84, 80, 88, 86, 72),
    TeamProfile("乌拉圭", "CONMEBOL", 1978, 82, 83, 82, 81, 80),
    TeamProfile("比利时", "UEFA", 1968, 84, 78, 78, 79, 72),
    TeamProfile("哥伦比亚", "CONMEBOL", 1958, 80, 86, 72, 78, 82),
    TeamProfile("克罗地亚", "UEFA", 1948, 79, 75, 90, 80, 80),
    TeamProfile("摩洛哥", "CAF", 1938, 78, 82, 76, 84, 82),
    TeamProfile("美国", "CONCACAF", 1898, 76, 78, 62, 74, 76),
    TeamProfile("墨西哥", "CONCACAF", 1888, 74, 76, 72, 76, 72),
    TeamProfile("日本", "AFC", 1884, 76, 84, 68, 78, 84),
    TeamProfile("瑞士", "UEFA", 1878, 75, 77, 76, 79, 80),
    TeamProfile("丹麦", "UEFA", 1870, 76, 74, 72, 80, 76),
    TeamProfile("塞内加尔", "CAF", 1865, 74, 78, 68, 78, 74),
    TeamProfile("奥地利", "UEFA", 1858, 74, 79, 62, 77, 78),
    TeamProfile("塞尔维亚", "UEFA", 1848, 76, 73, 64, 71, 70),
    TeamProfile("韩国", "AFC", 1838, 72, 74, 68, 72, 74),
    TeamProfile("澳大利亚", "AFC", 1818, 68, 72, 66, 73, 78),
    TeamProfile("加拿大", "CONCACAF", 1810, 70, 72, 56, 70, 70),
    TeamProfile("厄瓜多尔", "CONMEBOL", 1808, 72, 76, 58, 76, 72),
    TeamProfile("土耳其", "UEFA", 1802, 74, 76, 58, 70, 70),
    TeamProfile("波兰", "UEFA", 1798, 72, 69, 70, 70, 68),
    TeamProfile("威尔士", "UEFA", 1786, 68, 68, 66, 72, 70),
    TeamProfile("乌克兰", "UEFA", 1784, 72, 73, 64, 72, 72),
    TeamProfile("智利", "CONMEBOL", 1778, 70, 67, 74, 70, 66, qualified=False),
    TeamProfile("秘鲁", "CONMEBOL", 1768, 68, 66, 68, 72, 68, qualified=False),
    TeamProfile("瑞典", "UEFA", 1764, 71, 68, 70, 73, 68, qualified=False),
    TeamProfile("喀麦隆", "CAF", 1760, 68, 70, 66, 70, 68),
    TeamProfile("突尼斯", "CAF", 1756, 66, 70, 62, 72, 72),
    TeamProfile("加纳", "CAF", 1750, 69, 66, 66, 68, 62),
    TeamProfile("阿尔及利亚", "CAF", 1748, 70, 69, 60, 68, 66),
    TeamProfile("南非", "CAF", 1736, 64, 72, 58, 70, 74),
    TeamProfile("沙特阿拉伯", "AFC", 1728, 64, 68, 62, 66, 70),
    TeamProfile("卡塔尔", "AFC", 1718, 62, 66, 58, 65, 70),
    TeamProfile("乌兹别克斯坦", "AFC", 1712, 62, 72, 52, 68, 78),
    TeamProfile("约旦", "AFC", 1698, 60, 73, 50, 66, 76),
    TeamProfile("巴拿马", "CONCACAF", 1692, 60, 70, 52, 64, 74),
    TeamProfile("哥斯达黎加", "CONCACAF", 1688, 61, 66, 64, 66, 64),
    TeamProfile("牙买加", "CONCACAF", 1680, 64, 67, 50, 62, 62),
    TeamProfile("埃及", "CAF", 1772, 70, 72, 62, 72, 70),
    TeamProfile("捷克", "UEFA", 1782, 71, 70, 68, 73, 70, qualified=False),
    TeamProfile("波黑", "UEFA", 1706, 66, 63, 56, 64, 58, qualified=False),
]

SEED_BY_NAME = {team.name: team for team in SEED_TEAMS}

TEAM_NAME_ALIASES = {
    "阿根廷": "阿根廷",
    "法国": "法国",
    "英格兰": "英格兰",
    "巴西": "巴西",
    "德国": "德国",
    "西班牙": "西班牙",
    "葡萄牙": "葡萄牙",
    "荷兰": "荷兰",
    "比利时": "比利时",
    "克罗地亚": "克罗地亚",
    "摩洛哥": "摩洛哥",
    "日本": "日本",
    "南非": "南非",
    "乌拉圭": "乌拉圭",
    "韩国": "韩国",
    "加拿大": "加拿大",
    "美国": "美国",
    "墨西哥": "墨西哥",
    "哥伦比亚": "哥伦比亚",
    "瑞士": "瑞士",
    "塞内加尔": "塞内加尔",
    "挪威": "挪威",
    "捷克": "捷克",
    "卡塔尔": "卡塔尔",
    "海地": "海地",
    "土耳其": "土耳其",
    "突尼斯": "突尼斯",
    "约旦": "约旦",
    "巴拿马": "巴拿马",
    "库拉索": "库拉索",
    "伊拉克": "伊拉克",
    "新西兰": "新西兰",
    "苏格兰": "苏格兰",
    "乌兹别克斯坦": "乌兹别克斯坦",
    "伊朗": "伊朗",
    "沙特": "沙特阿拉伯",
    "沙特阿拉伯": "沙特阿拉伯",
    "刚果（金）": "刚果（金）",
    "民主刚果": "刚果（金）",
    "波黑": "波黑",
    "科特迪瓦": "科特迪瓦",
    "佛得角": "佛得角",
    "加纳": "加纳",
    "阿尔及利亚": "阿尔及利亚",
    "奥地利": "奥地利",
    "澳大利亚": "澳大利亚",
    "埃及": "埃及",
    "瑞典": "瑞典",
    "巴拉圭": "巴拉圭",
}


def _normalize_team_name(name: str | None) -> str | None:
    if not name:
        return None
    cleaned = re.sub(r"\*\*", "", name)
    cleaned = re.sub(r"[（(][^）)]*[）)]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return None
    cn_name = get_team_cn(cleaned)
    normalized = TEAM_NAME_ALIASES.get(cn_name) or TEAM_NAME_ALIASES.get(cleaned)
    if normalized:
        return normalized
    if cn_name in SEED_BY_NAME:
        return cn_name
    return None


def _load_snapshot() -> dict | None:
    if not SNAPSHOT_PATH.exists():
        return None
    try:
        return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _is_knockout_round(round_name: str | None, group_name: str | None = None) -> bool:
    value = f"{round_name or ''} {group_name or ''}".lower()
    if not value.strip():
        return False
    if "group" in value and not any(keyword in value for keyword in ("round of", "final")):
        return False
    return any(keyword in value for keyword in KNOCKOUT_ROUND_KEYWORDS)


def _eliminated_teams_from_db() -> set[str]:
    if not DB_PATH.exists():
        return set()

    eliminated: set[str] = set()
    db = SessionLocal()
    try:
        matches = db.query(Match).filter(
            Match.match_date >= datetime(2026, 1, 1),
            Match.match_date < datetime(2027, 1, 1),
            Match.status.in_(COMPLETED_STATUSES),
        ).all()
        for match in matches:
            if not _is_knockout_round(match.round, match.group_name):
                continue
            if match.home_score is None or match.away_score is None or match.home_score == match.away_score:
                continue
            loser = match.away_team if match.home_score > match.away_score else match.home_team
            normalized = _normalize_team_name(loser)
            if normalized:
                eliminated.add(normalized)
    finally:
        db.close()
    return eliminated


def _eliminated_teams_from_results_file() -> set[str]:
    if not RESULTS_PATH.exists():
        return set()

    try:
        text = RESULTS_PATH.read_text(encoding="utf-8")
    except OSError:
        return set()

    eliminated: set[str] = set()
    for line in text.splitlines():
        if "出局" not in line and "淘汰球队" not in line:
            continue
        if "|" in line:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if "淘汰球队" in cells:
                continue
            if len(cells) >= 5:
                normalized = _normalize_team_name(cells[4])
                if normalized:
                    eliminated.add(normalized)
            continue

        if ":" not in line and "：" not in line:
            continue
        _, names = re.split(r"[:：]", line, maxsplit=1)
        names = names.replace("**", "")
        for raw_name in re.split(r"[、,，]", names):
            normalized = _normalize_team_name(raw_name)
            if normalized:
                eliminated.add(normalized)
    return eliminated


def get_known_eliminated_teams() -> set[str]:
    return _eliminated_teams_from_results_file() | _eliminated_teams_from_db()


def get_prediction_inputs_mtime() -> float:
    paths = [SNAPSHOT_PATH, DB_PATH, RESULTS_PATH]
    return max((path.stat().st_mtime for path in paths if path.exists()), default=0.0)


def _value_from_elo(elo: int | None, low: int = 1600, high: int = 2150, floor: int = 48, ceiling: int = 92) -> int:
    if elo is None:
        return 62
    normalized = max(0.0, min(1.0, (elo - low) / (high - low)))
    return round(floor + normalized * (ceiling - floor))


def _profiles_from_snapshot(snapshot: dict | None) -> list[TeamProfile]:
    if not snapshot:
        return []

    profiles = []
    for item in snapshot.get("teams", []):
        name = item.get("name_cn") or item.get("name")
        seed = SEED_BY_NAME.get(name)
        elo = item.get("elo") or (seed.elo if seed else 1700)
        unavailable_count = item.get("unavailable_count") or 0
        doubtful_count = item.get("doubtful_count") or 0
        availability_score = item.get("availability_score") or max(40, 100 - unavailable_count * 6 - doubtful_count * 3)
        squad_count = item.get("squad_count") or 26

        if seed:
            squad = item.get("squad_quality_score") or seed.squad
            recent_form = item.get("recent_form_score") or seed.recent_form
            tournament_experience = seed.tournament_experience
            defense = seed.defense
            coach_stability = seed.coach_stability
        else:
            derived = _value_from_elo(elo)
            squad = item.get("squad_quality_score") or derived
            recent_form = item.get("recent_form_score") or derived
            tournament_experience = max(45, derived - 4)
            defense = max(45, derived - 2)
            coach_stability = 68

        squad = max(35, squad)
        profiles.append(TeamProfile(
            name=name,
            name_en=item.get("name"),
            confederation=item.get("confederation") or (seed.confederation if seed else "UNKNOWN"),
            elo=elo,
            squad=squad,
            recent_form=recent_form,
            tournament_experience=tournament_experience,
            defense=defense,
            coach_stability=coach_stability,
            qualified=True,
            group=item.get("group"),
            fifa_rank=item.get("fifa_rank"),
            fifa_points=item.get("fifa_points"),
            squad_count=squad_count,
            unavailable_count=unavailable_count,
            doubtful_count=doubtful_count,
            availability_score=availability_score,
            squad_quality_score=item.get("squad_quality_score"),
            recent_form_score=item.get("recent_form_score"),
            elo_rating_change_3m=item.get("elo_rating_change_3m"),
            elo_rating_change_6m=item.get("elo_rating_change_6m"),
            elo_rating_change_1y=item.get("elo_rating_change_1y"),
            played_matches=item.get("played_matches") or 0,
            points_per_game=item.get("points_per_game"),
            goal_difference_per_game=item.get("goal_difference_per_game"),
        ))

    return profiles


def _normalize_elo(elo: int, low: int = 1600, high: int = 2150) -> float:
    return max(0.0, min(100.0, (elo - low) / (high - low) * 100))


def team_score(team: TeamProfile) -> float:
    base_score = (
        WEIGHTS["elo"] * _normalize_elo(team.elo)
        + WEIGHTS["squad"] * team.squad
        + WEIGHTS["recent_form"] * team.recent_form
        + WEIGHTS["tournament_experience"] * team.tournament_experience
        + WEIGHTS["defense"] * team.defense
        + WEIGHTS["coach_stability"] * team.coach_stability
    )
    availability_adjust = (team.availability_score - 100) * 0.08
    return base_score + availability_adjust


def win_probability(team_a_score: float, team_b_score: float, context_adjust: float = 0) -> float:
    return 1 / (1 + exp(-((team_a_score - team_b_score + context_adjust) / 10)))


def matchup_context_adjust(team_a: TeamProfile, team_b: TeamProfile) -> float:
    availability_edge = (team_a.availability_score - team_b.availability_score) * 0.05
    recent_edge = ((team_a.recent_form_score or team_a.recent_form) - (team_b.recent_form_score or team_b.recent_form)) * 0.02
    squad_edge = ((team_a.squad_quality_score or team_a.squad) - (team_b.squad_quality_score or team_b.squad)) * 0.02
    return availability_edge + recent_edge + squad_edge


def _draw_probability(score_gap: float) -> float:
    return max(0.14, 0.27 - abs(score_gap) * 0.006)


def _sample_goals(expected: float, rng: Random) -> int:
    goals = 0
    chance = min(0.86, expected / 3.2)
    while rng.random() < chance and goals < 7:
        goals += 1
        chance *= 0.58
    return goals


def _play_group_match(team_a: SimTeam, team_b: SimTeam, rng: Random) -> None:
    score_gap = team_a.score - team_b.score
    draw_prob = _draw_probability(score_gap)
    context_adjust = matchup_context_adjust(team_a.profile, team_b.profile)
    a_win_prob = (1 - draw_prob) * win_probability(team_a.score, team_b.score, context_adjust)
    roll = rng.random()

    if roll < a_win_prob:
        a_goals = max(1, _sample_goals(1.55 + max(score_gap, 0) / 28, rng))
        b_goals = min(a_goals - 1, _sample_goals(0.92 + max(-score_gap, 0) / 40, rng))
        team_a.points += 3
    elif roll < a_win_prob + draw_prob:
        a_goals = b_goals = _sample_goals(1.08, rng)
        team_a.points += 1
        team_b.points += 1
    else:
        b_goals = max(1, _sample_goals(1.55 + max(-score_gap, 0) / 28, rng))
        a_goals = min(b_goals - 1, _sample_goals(0.92 + max(score_gap, 0) / 40, rng))
        team_b.points += 3

    team_a.goals_for += a_goals
    team_a.goals_against += b_goals
    team_b.goals_for += b_goals
    team_b.goals_against += a_goals


def _apply_group_result(team_a: SimTeam, team_b: SimTeam, a_goals: int, b_goals: int) -> None:
    if a_goals > b_goals:
        team_a.points += 3
    elif a_goals < b_goals:
        team_b.points += 3
    else:
        team_a.points += 1
        team_b.points += 1

    team_a.goals_for += a_goals
    team_a.goals_against += b_goals
    team_b.goals_for += b_goals
    team_b.goals_against += a_goals


def _play_knockout(
    team_a: TeamProfile,
    team_b: TeamProfile,
    rng: Random,
    eliminated_teams: set[str] | None = None,
) -> TeamProfile:
    eliminated_teams = eliminated_teams or set()
    team_a_eliminated = team_a.name in eliminated_teams
    team_b_eliminated = team_b.name in eliminated_teams
    if team_a_eliminated and not team_b_eliminated:
        return team_b
    if team_b_eliminated and not team_a_eliminated:
        return team_a

    a_score = team_score(team_a)
    b_score = team_score(team_b)
    return team_a if rng.random() < win_probability(a_score, b_score, matchup_context_adjust(team_a, team_b)) else team_b


def _seed_groups(teams: list[TeamProfile]) -> list[list[TeamProfile]]:
    if all(team.group for team in teams):
        groups_by_name = {group: [] for group in "ABCDEFGHIJKL"}
        for team in teams:
            groups_by_name.setdefault(team.group or "", []).append(team)
        groups = [groups_by_name[group] for group in "ABCDEFGHIJKL" if groups_by_name.get(group)]
        if len(groups) == 12 and all(len(group) == 4 for group in groups):
            return groups

    groups = [[] for _ in range(12)]
    ranked = sorted(teams, key=team_score, reverse=True)
    for index, team in enumerate(ranked):
        pot = index // 12
        position = index % 12
        group_index = position if pot % 2 == 0 else 11 - position
        groups[group_index].append(team)
    return groups


def _rank_group(group: list[TeamProfile], rng: Random, fixtures: list[dict] | None = None) -> list[SimTeam]:
    sim_group = [SimTeam(team, team_score(team)) for team in group]
    by_name = {team.profile.name_en or team.profile.name: team for team in sim_group}
    by_cn = {team.profile.name: team for team in sim_group}

    if fixtures:
        played_pairs = set()
        for fixture in fixtures:
            team_a = by_name.get(fixture.get("home")) or by_cn.get(fixture.get("home"))
            team_b = by_name.get(fixture.get("away")) or by_cn.get(fixture.get("away"))
            if not team_a or not team_b:
                continue
            played_pairs.add(frozenset((team_a.profile.name, team_b.profile.name)))
            score = fixture.get("score") or ""
            match = re.search(r"(\d+)\s*[–-]\s*(\d+)", score)
            if match:
                _apply_group_result(team_a, team_b, int(match.group(1)), int(match.group(2)))
            else:
                _play_group_match(team_a, team_b, rng)
        if played_pairs:
            return sorted(
                sim_group,
                key=lambda t: (t.points, t.goal_difference, t.goals_for, t.score),
                reverse=True,
            )

    for index, team_a in enumerate(sim_group):
        for team_b in sim_group[index + 1:]:
            _play_group_match(team_a, team_b, rng)
    return sorted(
        sim_group,
        key=lambda t: (t.points, t.goal_difference, t.goals_for, t.score),
        reverse=True,
    )


def _build_round_of_32(group_rankings: list[list[SimTeam]]) -> list[TeamProfile]:
    qualified: list[tuple[int, SimTeam]] = []
    third_place: list[SimTeam] = []

    for group_index, ranking in enumerate(group_rankings):
        qualified.append((1, ranking[0]))
        qualified.append((2, ranking[1]))
        third_place.append(ranking[2])

    best_thirds = sorted(
        third_place,
        key=lambda t: (t.points, t.goal_difference, t.goals_for, t.score),
        reverse=True,
    )[:8]
    qualified.extend((3, team) for team in best_thirds)

    return [
        team.profile
        for _rank, team in sorted(
            qualified,
            key=lambda item: (item[0], -item[1].points, -item[1].goal_difference, -item[1].score),
        )
    ]


def _pair_bracket(teams: list[TeamProfile]) -> list[tuple[TeamProfile, TeamProfile]]:
    top_half = teams[: len(teams) // 2]
    bottom_half = list(reversed(teams[len(teams) // 2:]))
    return list(zip(top_half, bottom_half))


def _fixtures_by_group(snapshot: dict | None) -> dict[str, list[dict]]:
    fixtures: dict[str, list[dict]] = {}
    for fixture in (snapshot or {}).get("fixtures", []):
        fixtures.setdefault(fixture.get("group", ""), []).append(fixture)
    return fixtures


def _simulate_once(
    teams: list[TeamProfile],
    rng: Random,
    snapshot: dict | None = None,
    eliminated_teams: set[str] | None = None,
) -> dict[Stage, list[str]]:
    fixtures = _fixtures_by_group(snapshot)
    group_rankings = [
        _rank_group(group, rng, fixtures.get(group[0].group or "") if group else None)
        for group in _seed_groups(teams)
    ]
    round_of_32 = _build_round_of_32(group_rankings)

    stages: dict[Stage, list[str]] = {
        "group": [team.name for team in teams],
        "round_of_32": [team.name for team in round_of_32],
        "round_of_16": [],
        "quarter_final": [],
        "semi_final": [],
        "final": [],
        "champion": [],
    }

    current = round_of_32
    for stage in ["round_of_16", "quarter_final", "semi_final", "final", "champion"]:
        winners = [_play_knockout(a, b, rng, eliminated_teams) for a, b in _pair_bracket(current)]
        stages[stage] = [team.name for team in winners]
        current = winners

    return stages


def build_prediction(iterations: int = 10000, seed: int = 2026) -> dict:
    rng = Random(seed)
    snapshot = _load_snapshot()
    snapshot_profiles = _profiles_from_snapshot(snapshot)
    teams = snapshot_profiles or sorted(SEED_TEAMS, key=team_score, reverse=True)[:48]
    eliminated_teams = get_known_eliminated_teams()
    counts: dict[str, dict[Stage, int]] = {
        team.name: {stage: 0 for stage in STAGE_LABELS}
        for team in teams
    }

    for _ in range(iterations):
        result = _simulate_once(teams, rng, snapshot, eliminated_teams)
        for stage, names in result.items():
            for name in names:
                counts[name][stage] += 1

    score_values = [team_score(team) for team in teams]
    rows = []
    for team in teams:
        if team.name in eliminated_teams:
            continue
        score = team_score(team)
        stage_probs = {
            stage: round(counts[team.name][stage] / iterations, 4)
            for stage in STAGE_LABELS
        }
        rows.append({
            "team": team.name,
            "confederation": team.confederation,
            "qualified": team.qualified,
            "group": team.group,
            "name_en": team.name_en,
            "team_score": round(score, 2),
            "score_index": round(score / max(score_values) * 100, 1),
            "title_probability": stage_probs["champion"],
            "final_probability": stage_probs["final"],
            "semi_final_probability": stage_probs["semi_final"],
            "quarter_final_probability": stage_probs["quarter_final"],
            "round_of_16_probability": stage_probs["round_of_16"],
            "round_of_32_probability": stage_probs["round_of_32"],
            "drivers": {
                "elo": round(_normalize_elo(team.elo), 1),
                "squad": team.squad,
                "recent_form": team.recent_form,
                "availability": team.availability_score,
                "tournament_experience": team.tournament_experience,
                "defense": team.defense,
                "coach_stability": team.coach_stability,
            },
            "data": {
                "elo": team.elo,
                "fifa_rank": team.fifa_rank,
                "fifa_points": team.fifa_points,
                "squad_count": team.squad_count,
                "unavailable_count": team.unavailable_count,
                "doubtful_count": team.doubtful_count,
                "availability_score": team.availability_score,
                "squad_quality_score": team.squad_quality_score,
                "recent_form_score": team.recent_form_score,
                "elo_rating_change_3m": team.elo_rating_change_3m,
                "elo_rating_change_6m": team.elo_rating_change_6m,
                "elo_rating_change_1y": team.elo_rating_change_1y,
                "played_matches": team.played_matches,
                "points_per_game": team.points_per_game,
                "goal_difference_per_game": team.goal_difference_per_game,
            },
        })

    rows.sort(key=lambda item: item["title_probability"], reverse=True)

    return {
        "model_version": MODEL_VERSION,
        "as_of": (snapshot or {}).get("updated_at", "2026-06-18"),
        "iterations": iterations,
        "format": "48 teams, 12 real groups, top 2 plus 8 best third-place teams",
        "data_note": (
            "已优先使用本地联网快照，并叠加本地数据库/赛果文件中的已知淘汰队；淘汰球队不会进入冠军候选榜。"
            if snapshot_profiles
            else "未找到联网快照，当前回退到内置轻量种子数据。"
        ),
        "weights": WEIGHTS,
        "using_live_snapshot": bool(snapshot_profiles),
        "known_eliminated_teams": sorted(eliminated_teams),
        "sources": (snapshot or {}).get("sources", []),
        "fifa_ranking": (snapshot or {}).get("fifa_ranking", {}),
        "field_strength": {
            "average_score": round(mean(score_values), 2),
            "top_score": round(max(score_values), 2),
            "score_spread": round(max(score_values) - min(score_values), 2),
        },
        "teams": rows,
    }
