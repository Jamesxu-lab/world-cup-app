"""
数据接入服务：从 API-Football 拉取数据 → 解析 → 入库
"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.match import Match, MatchEvent, MatchStat, PlayerPerformance
from app.services.football_api import FootballAPI

api = FootballAPI()


def parse_fixture_to_match(fixture_data: dict) -> dict:
    """将 API 返回的 fixture 对象解析为 Match 字段"""
    fixture = fixture_data["fixture"]
    league = fixture_data["league"]
    teams = fixture_data["teams"]
    goals = fixture_data["goals"]

    return {
        "fixture_id": fixture["id"],
        "home_team": teams["home"]["name"],
        "away_team": teams["away"]["name"],
        "home_score": goals.get("home"),
        "away_score": goals.get("away"),
        "match_date": datetime.fromisoformat(fixture["date"].replace("Z", "+00:00")),
        "group_name": league.get("round", "").replace("Group ", ""),
        "round": league.get("round", "group_stage"),
        "stadium": fixture.get("venue", {}).get("name"),
        "city": fixture.get("venue", {}).get("city"),
        "status": fixture["status"]["short"],
    }


def parse_events(api_events: list[dict]) -> list[dict]:
    """将 API 事件列表解析为 MatchEvent 字段"""
    result = []
    for event in api_events:
        result.append({
            "minute": event["time"]["elapsed"],
            "extra_minute": event["time"].get("extra"),
            "event_type": event["type"].lower(),
            "detail": event.get("detail"),
            "player_name": event.get("player", {}).get("name"),
            "team": event.get("team", {}).get("name"),
            "assist_player": event.get("assist", {}).get("name"),
        })
    return result


def parse_statistics(api_stats: list[dict]) -> list[dict]:
    """将 API 统计列表解析为 MatchStat 字段"""
    result = []
    for team_stat in api_stats:
        team_name = team_stat["team"]["name"]
        for stat in team_stat.get("statistics", []):
            value = stat.get("value")
            if value is not None and value != "null":
                try:
                    value = float(value) if "%" not in str(value) else float(str(value).replace("%", ""))
                except (ValueError, TypeError):
                    continue
                result.append({
                    "team": team_name,
                    "stat_type": stat["type"].lower().replace(" ", "_").replace("/", "_"),
                    "stat_value": value,
                })
    return result


def parse_player_performances(api_players: list[dict]) -> list[dict]:
    """将 API 球员数据解析为 PlayerPerformance 字段"""
    result = []
    for team_players in api_players:
        team_name = team_players["team"]["name"]
        for player_data in team_players.get("players", []):
            player_info = player_data["player"]
            stats_list = player_data.get("statistics", [{}])
            stats = stats_list[0] if stats_list else {}

            games = stats.get("games", {})
            goals = stats.get("goals", {})
            shots = stats.get("shots", {})
            passes = stats.get("passes", {})
            tackles = stats.get("tackles", {})
            dribbles = stats.get("dribbles", {})

            result.append({
                "player_name": player_info.get("name"),
                "team": team_name,
                "position": games.get("position"),
                "rating": float(games.get("rating")) if games.get("rating") else None,
                "goals": goals.get("total") or 0,
                "assists": goals.get("assists") or 0,
                "stats_json": {
                    "minutes": games.get("minutes"),
                    "shots_total": shots.get("total"),
                    "shots_on": shots.get("on"),
                    "passes_total": passes.get("total"),
                    "passes_key": passes.get("key"),
                    "passes_accuracy": passes.get("accuracy"),
                    "tackles_total": tackles.get("total"),
                    "tackles_interceptions": tackles.get("interceptions"),
                    "dribbles_attempts": dribbles.get("attempts"),
                    "dribbles_success": dribbles.get("success"),
                },
            })
    return result


def save_match_to_db(db: Session, fixture_data: dict, match_data: dict) -> Match:
    """
    将一场比赛的全部数据入库。
    fixture_data: /fixtures 返回的单个对象
    match_data: get_full_match_data 返回的聚合数据
    """
    match_dict = parse_fixture_to_match(fixture_data)

    # 检查是否已存在
    existing = db.query(Match).filter(Match.fixture_id == match_dict["fixture_id"]).first()
    if existing:
        return existing

    match = Match(**match_dict)
    db.add(match)
    db.flush()

    # 入库事件
    for evt in parse_events(match_data.get("events", [])):
        evt["match_id"] = match.id
        db.add(MatchEvent(**evt))

    # 入库统计
    for stat in parse_statistics(match_data.get("statistics", [])):
        stat["match_id"] = match.id
        db.add(MatchStat(**stat))

    # 入库球员表现
    for perf in parse_player_performances(match_data.get("players", [])):
        perf["match_id"] = match.id
        db.add(PlayerPerformance(**perf))

    db.commit()
    db.refresh(match)
    return match
