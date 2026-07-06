"""
规则兜底叙事：当比赛尚未生成 AI 卡片时，基于基础比分生成可读战报。
"""
from app.i18n import get_team_cn, get_stadium_cn, get_round_cn, get_status_cn
from app.models.match import Match


STYLE_NAMES = {
    "formal": "正经复盘",
    "funny": "段子手",
    "tactical": "战术党",
}
FALLBACK_MODEL_VERSION = "fallback-v1"
DETAIL_MODEL_VERSION = "detail-v1"
LOCAL_NARRATIVE_MODELS = {FALLBACK_MODEL_VERSION, DETAIL_MODEL_VERSION}


def _scoreline(match: Match) -> str:
    home = get_team_cn(match.home_team)
    away = get_team_cn(match.away_team)
    if match.home_score is None or match.away_score is None:
        return f"{home} vs {away}"
    return f"{home} {match.home_score}-{match.away_score} {away}"


def _result_sentence(match: Match) -> str:
    home = get_team_cn(match.home_team)
    away = get_team_cn(match.away_team)
    h_score = match.home_score
    a_score = match.away_score
    status = get_status_cn(match.status)

    if h_score is None or a_score is None:
        return f"{home} 与 {away} 的比赛目前状态为{status}，开球后这里会更新比分和战报。"

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
        return "本场暂时没有可用的球员明细数据，后续同步事件和球员表现后会补充关键人物。"
    return f"{scorer.player_name} 是目前最醒目的名字，贡献 {scorer.goals} 球。"


def _has_detail_data(match: Match) -> bool:
    return bool(match.events or match.stats or match.performances)


def get_local_narrative_model_version(match: Match) -> str:
    return DETAIL_MODEL_VERSION if _has_detail_data(match) else FALLBACK_MODEL_VERSION


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
    top_scorer = _top_scorer(match)

    if style == "funny":
        return [
            {
                "card_type": "opening",
                "title": "先看比分",
                "content": f"{scoreline}。先别急着问名场面，当前库里这场只有基础赛果，战报先走简洁版：{result}",
            },
            {
                "card_type": "key_moment",
                "title": "剧情入口",
                "content": f"{round_name}的戏份已经摆好，{home} 和 {away} 在 {stadium} 交手。等事件数据补齐后，进球、红黄牌和换人节点会在这里展开。",
            },
            {
                "card_type": "player_spotlight",
                "title": "谁最抢镜",
                "content": top_scorer,
            },
            {
                "card_type": "tactical",
                "title": "战术先占位",
                "content": "目前缺少控球率、射门、传球等技术统计，先不硬编阵型。等同步明细后，再把压迫、反击和边路攻防讲清楚。",
            },
            {
                "card_type": "data_story",
                "title": "数据不硬凑",
                "content": f"可确认的数据是比分、时间、场地和状态：{scoreline}，状态为{status}。其他进阶数据暂不展示，避免把战报写成玄学。",
            },
            {
                "card_type": "closing",
                "title": "等完整版",
                "content": "这是一版可读的基础战报。后续同步事件、统计和球员表现，或生成 AI 叙事后，这里会升级成完整复盘。",
            },
        ]

    if style == "tactical":
        return [
            {
                "card_type": "opening",
                "title": "战术结论",
                "content": f"{scoreline}。在缺少详细技术统计的情况下，当前只能给出基于比分和比赛状态的初步判断：{result}",
            },
            {
                "card_type": "key_moment",
                "title": "转折待补",
                "content": "关键转折需要依赖进球时间、换人和红黄牌事件。当前本地库尚未同步这些明细，因此先保留判断，避免用想象替代比赛过程。",
            },
            {
                "card_type": "player_spotlight",
                "title": "核心球员",
                "content": top_scorer,
            },
            {
                "card_type": "tactical",
                "title": "空间与节奏",
                "content": f"{home} 与 {away} 的战术复盘需要射门、控球率和传球数据支撑。现在可以确认的是比赛阶段为{round_name}，地点在{stadium}。",
            },
            {
                "card_type": "data_story",
                "title": "数据边界",
                "content": "当前只有基础赛果数据，不能可靠推断高位逼抢、攻防转换效率或边路推进质量。这里先呈现事实，等待下一次明细同步。",
            },
            {
                "card_type": "closing",
                "title": "复盘待升级",
                "content": "当事件和统计补齐后，可以进一步分析双方的压迫触发点、进攻三区选择和临场调整。",
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
            "content": "由于本地库暂缺事件和技术统计，暂不做过度战术推演。完整复盘需要结合进球时间线、射门质量和控球分布。",
        },
        {
            "card_type": "data_story",
            "title": "已知数据",
            "content": f"目前可用数据包括双方队名、比分、比赛阶段、场地和状态：{scoreline}，{round_name}，{status}。",
        },
        {
            "card_type": "closing",
            "title": "后续更新",
            "content": "这是一版基础战报。同步更完整的比赛明细或生成 AI 卡片后，将自动呈现更丰富的叙事内容。",
        },
    ]
