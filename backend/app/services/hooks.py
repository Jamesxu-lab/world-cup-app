"""
一句话钩子生成器：为比赛列表生成吸引人的摘要。
MVP 策略：优先用叙事卡片的开篇标题；没有叙事数据时用规则兜底。
"""
from app.models.match import Match, Narrative
from app.i18n import get_team_cn
from app.services.fallback_narrative import is_local_narrative_model
from app.services.scoreline import format_penalty_result, has_penalty_score


def generate_hook(match: Match) -> str:
    """
    为一场比赛生成一句话钩子。
    优先级：叙事卡片开篇 > 规则生成
    """
    # 尝试从已生成的 AI 叙事中获取开篇标题；规则兜底卡片不适合作为列表钩子。
    for narrative in match.narratives:
        if _is_fallback_narrative(narrative):
            continue
        if narrative.style == "funny" and narrative.card_index == 1 and narrative.title:
            return narrative.title
    for narrative in match.narratives:
        if _is_fallback_narrative(narrative):
            continue
        if narrative.style == "formal" and narrative.card_index == 1 and narrative.title:
            return narrative.title

    # 规则兜底
    return _rule_based_hook(match)


def _is_fallback_narrative(narrative: Narrative) -> bool:
    return is_local_narrative_model(narrative.model_version)


def _rule_based_hook(match: Match) -> str:
    home = get_team_cn(match.home_team)
    away = get_team_cn(match.away_team)
    h_score = match.home_score
    a_score = match.away_score

    if h_score is None or a_score is None:
        return f"{home} 对阵 {away}"

    if match.status == "PEN" and has_penalty_score(match):
        result = format_penalty_result(match)
        if result:
            return f"{home} {h_score}-{a_score} {away}，{result}"

    # 查找进球最多的球员
    top_scorer = None
    for perf in match.performances:
        if perf.goals and perf.goals > 0:
            if top_scorer is None or perf.goals > top_scorer.goals:
                top_scorer = perf

    if h_score > a_score:
        diff = h_score - a_score
        if diff >= 3:
            text = f"{home} {h_score}-{a_score} 大胜{away}"
        else:
            text = f"{home} {h_score}-{a_score} 击败{away}"
    elif a_score > h_score:
        diff = a_score - h_score
        if diff >= 3:
            text = f"{away} {a_score}-{h_score} 大胜{home}"
        elif diff == 1 and h_score == 0:
            text = f"{away} {a_score}-{h_score} 小胜{home}"
        else:
            text = f"{away} {a_score}-{h_score} 战胜{home}"
    else:
        text = f"{home} {h_score}-{a_score} 战平{away}"

    if top_scorer:
        text += f"，{top_scorer.player_name}独进{top_scorer.goals}球"

    return text
