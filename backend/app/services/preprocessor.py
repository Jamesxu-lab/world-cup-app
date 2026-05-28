"""
数据预处理器：将原始比赛数据转换为结构化的中文摘要，作为 LLM Prompt 输入。
"""
from sqlalchemy.orm import Session
from app.models.match import Match


EVENT_LABELS = {
    "goal": "进球",
    "card": "黄牌",
    "subst": "换人",
    "var": "VAR",
}


def _event_icon(event_type: str) -> str:
    icons = {
        "goal": "⚽",
        "card": "🟨",
        "subst": "🔄",
        "var": "📺",
    }
    return icons.get(event_type, "•")


def build_timeline(match: Match) -> list[str]:
    """构建比赛时间线（中文）"""
    lines = []
    for evt in sorted(match.events, key=lambda e: (e.minute, e.extra_minute or 0)):
        minute = f"{evt.minute}"
        if evt.extra_minute:
            minute += f"+{evt.extra_minute}"
        icon = _event_icon(evt.event_type)
        label = EVENT_LABELS.get(evt.event_type, evt.event_type)
        player = evt.player_name or ""
        detail = evt.detail or ""
        assist = evt.assist_player or ""
        if assist:
            detail += f"（助攻：{assist}）"
        lines.append(f"[{minute}'] {icon} {label}：{player} - {detail}")
    return lines


def build_stat_comparison(match: Match) -> dict[str, dict[str, float]]:
    """构建技术统计对比表"""
    comparison = {}
    for stat in match.stats:
        if stat.stat_type not in comparison:
            comparison[stat.stat_type] = {}
        comparison[stat.stat_type][stat.team] = stat.stat_value
    return comparison


def translate_stat_name(stat_type: str) -> str:
    """翻译统计项名称为中文"""
    mapping = {
        "shots_on_goal": "射正",
        "shots_off_goal": "射偏",
        "total_shots": "总射门",
        "blocked_shots": "被封堵",
        "shots_insidebox": "禁区内射门",
        "shots_outsidebox": "禁区外射门",
        "fouls": "犯规",
        "corner_kicks": "角球",
        "offsides": "越位",
        "ball_possession": "控球率",
        "yellow_cards": "黄牌",
        "red_cards": "红牌",
        "goalkeeper_saves": "门将扑救",
        "total_passes": "总传球",
        "passes_accurate": "传球成功",
        "passes_%": "传球成功率",
    }
    return mapping.get(stat_type, stat_type.replace("_", " "))


def build_top_players(match: Match, top_n: int = 5) -> list[dict]:
    """提取评分最高的 TOP N 球员"""
    sorted_players = sorted(
        match.performances,
        key=lambda p: (p.rating or 0, p.goals or 0),
        reverse=True,
    )
    result = []
    for p in sorted_players[:top_n]:
        result.append({
            "name": p.player_name,
            "team": p.team,
            "position": p.position or "未知",
            "rating": p.rating,
            "goals": p.goals,
            "assists": p.assists,
            "stats": p.stats_json or {},
        })
    return result


def build_match_summary(match: Match) -> dict:
    """
    构建完整的结构化中文摘要。

    返回：
    {
        "match_info": {home_team, away_team, home_score, away_score, date, stadium, city, round},
        "result_summary": "阿根廷爆冷1-2不敌沙特阿拉伯",
        "timeline": ["[5'] ...", ...],
        "stat_comparison": {"射正": {"Argentina": 5, "Saudi Arabia": 2}, ...},
        "top_players": [{name, team, rating, goals, assists, stats}, ...],
    }
    """
    home = match.home_team
    away = match.away_team
    h_score = match.home_score or 0
    a_score = match.away_score or 0

    # 结果简述
    if h_score > a_score:
        result_summary = f"{home} {h_score}-{a_score} 战胜 {away}"
    elif h_score < a_score:
        result_summary = f"{away} {a_score}-{h_score} 战胜 {home}"
    else:
        result_summary = f"{home} {h_score}-{a_score} 战平 {away}"

    # 判断比赛类型
    is_upset = False
    if h_score != a_score:
        # 简单冷门判断：进球多的一方评分均值与对方差距
        pass

    timeline = build_timeline(match)
    stat_comparison_raw = build_stat_comparison(match)
    stat_comparison = {translate_stat_name(k): v for k, v in stat_comparison_raw.items()}
    top_players = build_top_players(match)

    return {
        "match_info": {
            "home_team": home,
            "away_team": away,
            "home_score": h_score,
            "away_score": a_score,
            "date": str(match.match_date),
            "stadium": match.stadium or "未知",
            "city": match.city or "未知",
            "round": match.round or "小组赛",
            "group_name": match.group_name or "",
        },
        "result_summary": result_summary,
        "timeline": timeline,
        "stat_comparison": stat_comparison,
        "top_players": top_players,
    }


def format_summary_as_text(match: Match) -> str:
    """将结构化摘要格式化为纯文本，方便塞入 Prompt"""
    s = build_match_summary(match)
    info = s["match_info"]

    lines = [
        f"## 比赛概况",
        f"{info['home_team']} {info['home_score']}-{info['away_score']} {info['away_team']}",
        f"阶段：{info['round']}",
        f"时间：{info['date']}",
        f"场地：{info['stadium']}，{info['city']}",
        f"结果：{s['result_summary']}",
        "",
        "## 比赛时间线",
    ]
    for tl in s["timeline"]:
        lines.append(tl)

    lines.append("")
    lines.append("## 技术统计对比")
    for stat_name, teams in s["stat_comparison"].items():
        team_str = " vs ".join(f"{t}: {v}" for t, v in teams.items())
        lines.append(f"- {stat_name}：{team_str}")

    lines.append("")
    lines.append("## 球员表现 TOP 5")
    for i, p in enumerate(s["top_players"], 1):
        lines.append(f"{i}. {p['name']}（{p['team']}）— 评分 {p['rating']} | {p['goals']}球{p['assists']}助 | 位置 {p['position']}")

    return "\n".join(lines)
