"""
规则兜底叙事：当比赛尚未生成 AI 卡片时，基于基础比分生成可读战报。
"""
from hashlib import sha1

from app.i18n import get_team_cn, get_stadium_cn, get_round_cn, get_status_cn
from app.models.match import Match
from app.services.scoreline import (
    format_penalty_result,
    format_scoreline,
    has_penalty_score,
    penalty_winner_name,
)


STYLE_NAMES = {
    "formal": "正经复盘",
    "funny": "段子手",
    "tactical": "战术党",
}
FALLBACK_MODEL_VERSION = "fallback-v2"
DETAIL_MODEL_VERSION = "detail-v1"
LOCAL_NARRATIVE_MODELS = {FALLBACK_MODEL_VERSION, DETAIL_MODEL_VERSION}
LOCAL_NARRATIVE_PREFIXES = ("fallback-v1", FALLBACK_MODEL_VERSION, DETAIL_MODEL_VERSION)


def _scoreline(match: Match) -> str:
    return format_scoreline(match)


def _result_sentence(match: Match) -> str:
    home = get_team_cn(match.home_team)
    away = get_team_cn(match.away_team)
    h_score = match.home_score
    a_score = match.away_score
    status = get_status_cn(match.status)

    if h_score is None or a_score is None:
        return f"{home} 与 {away} 的比赛目前状态为{status}，开球后这里会更新比分和战报。"

    if match.status == "PEN" and has_penalty_score(match):
        penalty_result = format_penalty_result(match)
        if penalty_result:
            return f"{home} 与 {away} 常规时间/加时后 {h_score}-{a_score} 战平，{penalty_result}，比赛状态为{status}。"

    result_verb = "击败" if match.status in {"FT", "AET", "PEN"} else "领先"
    if h_score > a_score:
        return f"{home} 以 {h_score}-{a_score} {result_verb} {away}，比赛状态为{status}。"
    if h_score < a_score:
        return f"{away} 以 {a_score}-{h_score} {result_verb} {home}，比赛状态为{status}。"
    return f"{home} 与 {away} 目前 {h_score}-{a_score} 战平，比赛状态为{status}。"


def _top_scorer(match: Match) -> str:
    scorer = None
    for perf in match.performances:
        if perf.goals and (scorer is None or perf.goals > scorer.goals):
            scorer = perf
    if not scorer:
        winner = _winner_name(match)
        if winner == "双方":
            return "关键人物线索暂时更适合放在团队层面：双方都需要从机会质量和终结选择里寻找突破口。"
        return f"关键人物线索暂时更适合放在团队层面：{winner} 把优势转化成比分，执行效率是最醒目的标签。"
    return f"{scorer.player_name} 是目前最醒目的名字，贡献 {scorer.goals} 球。"


def _has_detail_data(match: Match) -> bool:
    return bool(match.events or match.stats or match.performances)


def is_local_narrative_model(model_version: str | None) -> bool:
    if not model_version:
        return False
    return any(
        model_version == prefix or model_version.startswith(f"{prefix}:")
        for prefix in LOCAL_NARRATIVE_PREFIXES
    )


def get_local_narrative_model_version(match: Match) -> str:
    base_version = DETAIL_MODEL_VERSION if _has_detail_data(match) else FALLBACK_MODEL_VERSION
    fingerprint_source = "|".join([
        str(match.status or ""),
        str(match.home_score),
        str(match.away_score),
        str(match.penalty_home_score),
        str(match.penalty_away_score),
        str(match.match_date),
        str(match.round or ""),
        str(match.stadium or ""),
        str(len(match.events)),
        str(len(match.stats)),
        str(len(match.performances)),
    ])
    fingerprint = sha1(fingerprint_source.encode("utf-8")).hexdigest()[:8]
    return f"{base_version}:{fingerprint}"


def _minute_label(event) -> str:
    minute = str(event.minute)
    if event.extra_minute:
        minute += f"+{event.extra_minute}"
    return f"第{minute}分钟"


def _event_team(event) -> str:
    return get_team_cn(event.team) if event.team else "比赛一方"


def _important_events(match: Match) -> list:
    important_types = {"goal", "card", "var"}
    events = [
        event
        for event in match.events
        if event.event_type in important_types or event.detail == "Missed Penalty"
    ]
    return sorted(events, key=lambda e: (e.minute, e.extra_minute or 0))


def _event_sentence(event) -> str:
    minute = _minute_label(event)
    team = _event_team(event)
    player = event.player_name or "球员"
    detail = event.detail or ""

    if detail == "Missed Penalty":
        return f"{minute}，{player}（{team}）罚丢点球，比赛的势头从这里开始摇晃。"
    if event.event_type == "goal":
        if detail == "Penalty":
            return f"{minute}，{player}（{team}）点球命中。"
        assist = f"，助攻来自 {event.assist_player}" if event.assist_player else ""
        return f"{minute}，{player}（{team}）完成破门{assist}。"
    if event.event_type == "card":
        card_name = "黄牌" if detail == "Yellow Card" else detail or "黄牌"
        return f"{minute}，{player}（{team}）吃到{card_name}，对抗强度进一步抬高。"
    if event.event_type == "var":
        return f"{minute}，VAR 介入了 {player}（{team}）相关判罚。"
    return f"{minute}，{player}（{team}）制造了关键事件：{detail or event.event_type}。"


def _timeline_sentence(match: Match, limit: int = 6) -> str:
    events = _important_events(match)
    if not events:
        return "本场没有同步到明确的进球或判罚节点，复盘主要依据比分、统计和球员表现展开。"
    return " ".join(_event_sentence(event) for event in events[:limit])


def _stat_value(match: Match, team: str, stat_type: str) -> float | None:
    for stat in match.stats:
        if stat.team == team and stat.stat_type == stat_type:
            return stat.stat_value
    return None


def _format_stat_value(stat_type: str, value: float | None) -> str:
    if value is None:
        return "-"
    if stat_type in {"ball_possession", "passes_%"}:
        return f"{value:g}%"
    return f"{value:g}"


def _stat_pair(match: Match, stat_type: str, label: str) -> str | None:
    home_value = _stat_value(match, match.home_team, stat_type)
    away_value = _stat_value(match, match.away_team, stat_type)
    if home_value is None and away_value is None:
        return None
    home = get_team_cn(match.home_team)
    away = get_team_cn(match.away_team)
    return (
        f"{label}：{home} {_format_stat_value(stat_type, home_value)}，"
        f"{away} {_format_stat_value(stat_type, away_value)}"
    )


def _stats_sentence(match: Match) -> str:
    pairs = [
        _stat_pair(match, "ball_possession", "控球率"),
        _stat_pair(match, "total_shots", "射门"),
        _stat_pair(match, "shots_on_goal", "射正"),
        _stat_pair(match, "corner_kicks", "角球"),
        _stat_pair(match, "goalkeeper_saves", "门将扑救"),
    ]
    available = [pair for pair in pairs if pair]
    if not available:
        return "技术统计暂不完整，但事件和球员表现已经可以支撑基础复盘。"
    return "；".join(available[:4]) + "。"


def _top_players(match: Match, limit: int = 3) -> list:
    return sorted(
        match.performances,
        key=lambda p: (p.rating or 0, p.goals or 0, p.assists or 0),
        reverse=True,
    )[:limit]


def _player_sentence(match: Match) -> str:
    players = _top_players(match)
    if not players:
        return _top_scorer(match)

    parts = []
    for player in players:
        detail = []
        if player.rating:
            detail.append(f"评分 {player.rating:g}")
        if player.goals:
            detail.append(f"{player.goals} 球")
        if player.assists:
            detail.append(f"{player.assists} 助攻")
        suffix = "，".join(detail) if detail else "完成稳定输出"
        parts.append(f"{player.player_name}（{get_team_cn(player.team)}）{suffix}")
    return "；".join(parts) + "。"


def _winner_name(match: Match) -> str:
    if match.status == "PEN":
        penalty_winner = penalty_winner_name(match)
        if penalty_winner:
            return penalty_winner
    if match.home_score is None or match.away_score is None:
        return get_team_cn(match.home_team)
    if match.home_score > match.away_score:
        return get_team_cn(match.home_team)
    if match.away_score > match.home_score:
        return get_team_cn(match.away_team)
    return "双方"


def _build_detail_narrative(match: Match, style: str) -> list[dict]:
    home = get_team_cn(match.home_team)
    away = get_team_cn(match.away_team)
    scoreline = _scoreline(match)
    result = _result_sentence(match)
    round_name = get_round_cn(match.round) if match.round else "小组赛"
    stadium = get_stadium_cn(match.stadium) if match.stadium else "比赛场地"
    timeline = _timeline_sentence(match)
    stats = _stats_sentence(match)
    players = _player_sentence(match)
    winner = _winner_name(match)

    if style == "funny":
        return [
            {
                "card_type": "opening",
                "title": "这剧本够狠",
                "content": f"{scoreline}。这场不是只看比分就能讲完的比赛：{result} 明细里最扎眼的是这些节点：{timeline}",
            },
            {
                "card_type": "key_moment",
                "title": "拐点来了",
                "content": timeline,
            },
            {
                "card_type": "player_spotlight",
                "title": "谁在C",
                "content": players,
            },
            {
                "card_type": "tactical",
                "title": "场面会说话",
                "content": f"{stats} 从这些数字看，{winner} 的胜负手不是玄学，而是把关键回合转化成了比分。",
            },
            {
                "card_type": "data_story",
                "title": "数据不嘴硬",
                "content": f"{round_name}，{stadium}，{home} 对 {away}。{stats} 这组对比足够解释为什么比赛后段的每一次攻防都显得更重。",
            },
            {
                "card_type": "closing",
                "title": "赛后锐评",
                "content": f"{scoreline} 的背后，是关键球员、关键判罚和临门一脚共同写出的结果。{winner} 把机会攥住了。",
            },
        ]

    if style == "tactical":
        return [
            {
                "card_type": "opening",
                "title": "胜负手清楚",
                "content": f"{scoreline}。从明细看，这场的战术结论先落在两点：关键事件的处理质量，以及攻防数据里的效率差。{result}",
            },
            {
                "card_type": "key_moment",
                "title": "转折节点",
                "content": timeline,
            },
            {
                "card_type": "player_spotlight",
                "title": "体系关键人",
                "content": players,
            },
            {
                "card_type": "tactical",
                "title": "节奏与空间",
                "content": f"{stats} 如果只看控球或射门总数容易误判，真正决定走势的是谁能把进入危险区域后的回合变成高质量终结。",
            },
            {
                "card_type": "data_story",
                "title": "数据解释",
                "content": f"{home} 与 {away} 在 {round_name} 的这场对抗，已经同步到事件、技术统计和球员评分。{stats}",
            },
            {
                "card_type": "closing",
                "title": "后续启示",
                "content": f"对 {winner} 来说，这场最有价值的是关键时段执行力；对另一方来说，复盘重点应放在机会转化和防守专注度。",
            },
        ]

    return [
        {
            "card_type": "opening",
            "title": f"{winner}笑到最后",
            "content": f"{scoreline}。{result} 这不是空泛的赛果播报，本场已经同步到事件、技术统计和球员表现，可以还原比赛的主要脉络。",
        },
        {
            "card_type": "key_moment",
            "title": "关键时间线",
            "content": timeline,
        },
        {
            "card_type": "player_spotlight",
            "title": "关键人物",
            "content": players,
        },
        {
            "card_type": "tactical",
            "title": "比赛走势",
            "content": f"{stats} 这些指标说明比赛并不只是比分上的一球差距，双方在控球、射门和门前处理上各有侧重。",
        },
        {
            "card_type": "data_story",
            "title": "数据侧写",
            "content": f"比赛阶段为{round_name}，地点在{stadium}。{stats} 结合时间线看，比分变化来自关键节点的执行效率。",
        },
        {
            "card_type": "closing",
            "title": "赛后结语",
            "content": f"{scoreline} 会被记成一个结果，但复盘里更重要的是：谁在压力时段完成了决定性动作，谁又错过了改写比赛的窗口。",
        },
    ]


def build_fallback_narrative(match: Match, style: str) -> list[dict]:
    """生成 6 张兜底卡片，结构与 AI 叙事卡片一致。"""
    if _has_detail_data(match):
        return _build_detail_narrative(match, style)

    home = get_team_cn(match.home_team)
    away = get_team_cn(match.away_team)
    scoreline = _scoreline(match)
    result = _result_sentence(match)
    round_name = get_round_cn(match.round) if match.round else "小组赛"
    stadium = get_stadium_cn(match.stadium) if match.stadium else "比赛场地"
    status = get_status_cn(match.status)
    winner = _winner_name(match)
    top_scorer = _top_scorer(match)

    if style == "funny":
        return [
            {
                "card_type": "opening",
                "title": "先看比分",
                "content": f"{scoreline}。先看最硬的结果：{result} 这场的剧情先从比分和比赛阶段说起。",
            },
            {
                "card_type": "key_moment",
                "title": "剧情入口",
                "content": f"{round_name}的戏份已经摆好，{home} 和 {away} 在 {stadium} 交手。比分已经把比赛方向写得很直接，后面的复盘重点是机会转化和临场执行。",
            },
            {
                "card_type": "player_spotlight",
                "title": "谁最抢镜",
                "content": top_scorer,
            },
            {
                "card_type": "tactical",
                "title": "比赛走势",
                "content": f"从比分看，{winner} 在关键回合里的处理更有效。没有必要把胜负说复杂：领先方把压力变成了结果，落后方则需要更高质量的终结回应。",
            },
            {
                "card_type": "data_story",
                "title": "数据不硬凑",
                "content": f"可确认的数据是比分、时间、场地和状态：{scoreline}，状态为{status}。其他进阶数据暂不展示，避免把战报写成玄学。",
            },
            {
                "card_type": "closing",
                "title": "赛后锐评",
                "content": f"{scoreline} 已经给出主线。真正值得追问的是，{home} 与 {away} 在压力时段谁更果断、谁又错过了改写走势的窗口。",
            },
        ]

    if style == "tactical":
        return [
            {
                "card_type": "opening",
                "title": "战术结论",
                "content": f"{scoreline}。战术结论先落在执行效率上：{result} 比分说明优势方在关键回合里更能把局面转成结果。",
            },
            {
                "card_type": "key_moment",
                "title": "转折方向",
                "content": f"这场的转折方向已经体现在比分上。{winner} 的优势不是单纯场面占优，而是把有限的决定性回合兑现成领先。",
            },
            {
                "card_type": "player_spotlight",
                "title": "核心球员",
                "content": top_scorer,
            },
            {
                "card_type": "tactical",
                "title": "空间与节奏",
                "content": f"{home} 与 {away} 的对抗发生在{round_name}，地点是{stadium}。从赛果看，节奏管理和门前选择是这场最值得复盘的两条线。",
            },
            {
                "card_type": "data_story",
                "title": "赛果侧写",
                "content": f"可确认的主线是：{scoreline}，状态为{status}。比分差距已经足够说明双方在关键机会处理上的差异。",
            },
            {
                "card_type": "closing",
                "title": "后续启示",
                "content": f"对 {winner} 来说，这场最有价值的是执行力；对另一方来说，复盘重点应放在机会质量、攻防切换和防守专注度。",
            },
        ]

    return [
        {
            "card_type": "opening",
            "title": "比赛概览",
            "content": f"{scoreline}。{result}",
        },
        {
            "card_type": "key_moment",
            "title": "赛程信息",
            "content": f"这场比赛属于{round_name}，比赛地点是{stadium}。当前状态为{status}。",
        },
        {
            "card_type": "player_spotlight",
            "title": "人物线索",
            "content": top_scorer,
        },
        {
            "card_type": "tactical",
            "title": "比赛脉络",
            "content": f"从赛果看，{winner} 在关键阶段更好地控制了比赛方向。比分不是孤立数字，它反映的是机会把握、攻防选择和临场执行的综合结果。",
        },
        {
            "card_type": "data_story",
            "title": "已知数据",
            "content": f"目前可用数据包括双方队名、比分、比赛阶段、场地和状态：{scoreline}，{round_name}，{status}。",
        },
        {
            "card_type": "closing",
            "title": "赛后结语",
            "content": f"{scoreline} 会被记成一个结果，但复盘里更重要的是：谁在压力时段完成了决定性动作，谁又错过了改写比赛的窗口。",
        },
    ]
