from app.i18n import get_team_cn
from app.models.match import Match


def has_penalty_score(match: Match) -> bool:
    return match.penalty_home_score is not None and match.penalty_away_score is not None


def penalty_winner_name(match: Match) -> str | None:
    if not has_penalty_score(match):
        return None
    if match.penalty_home_score > match.penalty_away_score:
        return get_team_cn(match.home_team)
    if match.penalty_away_score > match.penalty_home_score:
        return get_team_cn(match.away_team)
    return None


def format_scoreline(match: Match) -> str:
    home = get_team_cn(match.home_team)
    away = get_team_cn(match.away_team)
    if match.home_score is None or match.away_score is None:
        return f"{home} vs {away}"

    scoreline = f"{home} {match.home_score}-{match.away_score} {away}"
    if match.status == "PEN" and has_penalty_score(match):
        scoreline += f"（点球 {match.penalty_home_score}-{match.penalty_away_score}）"
    return scoreline


def format_penalty_result(match: Match) -> str | None:
    winner = penalty_winner_name(match)
    if not winner or not has_penalty_score(match):
        return None
    if match.penalty_home_score > match.penalty_away_score:
        winner_score = match.penalty_home_score
        loser_score = match.penalty_away_score
    else:
        winner_score = match.penalty_away_score
        loser_score = match.penalty_home_score
    return f"{winner} 点球大战 {winner_score}-{loser_score} 胜出"
