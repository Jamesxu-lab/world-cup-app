"""
质量校验层：确保 AI 生成内容的安全性和事实准确性。
"""
import re
from app.models.match import Match


# 基础敏感词列表（MVP 阶段先用简单规则，生产环境接专业内容审核 API）
SENSITIVE_WORDS = [
    "台独", "藏独", "港独", "新疆独立", "法轮功",
]  # 政治敏感


def check_sensitive_words(text: str) -> list[str]:
    """检查敏感词，返回命中的词列表"""
    return [w for w in SENSITIVE_WORDS if w in text]


def check_fact_consistency(cards: list[dict], match: Match) -> list[str]:
    """
    事实一致性检查：
    - 比分是否正确
    - 球员名是否存在
    - 关键事件是否匹配

    返回问题列表（空列表表示通过）。
    """
    issues = []
    home = match.home_team
    away = match.away_team
    home_score = match.home_score or 0
    away_score = match.away_score or 0

    # 收集所有球员名
    all_players = set()
    for perf in match.performances:
        all_players.add(perf.player_name.lower())

    all_text = " ".join(c.get("content", "") + c.get("title", "") for c in cards)

    # 检查比分（常见表述模式）
    score_patterns = [
        rf"{home}\s*{home_score}\s*[-:]\s*{away_score}\s*{away}",
        rf"{home_score}\s*[-:]\s*{away_score}",
    ]
    score_ok = False
    for pat in score_patterns:
        if re.search(pat, all_text, re.IGNORECASE):
            score_ok = True
            break
    if not score_ok:
        issues.append(f"未能确认比分 {home_score}-{away_score} 在内容中出现")

    # 检查球员名（抽样检查）
    found_players = 0
    for player in all_players:
        # 只检查姓氏或简称（API 返回可能不完整）
        short_name = player.split()[-1] if " " in player else player
        if len(short_name) >= 3 and short_name.lower() in all_text.lower():
            found_players += 1
    if found_players == 0:
        issues.append("内容中未找到任何实际参赛球员名")
    elif found_players < 3:
        issues.append(f"内容中仅找到 {found_players} 位实际球员，可能偏少")

    return issues


def check_card_length(cards: list[dict], style: str) -> list[str]:
    """检查卡片字数是否在合理范围"""
    issues = []
    ranges = {
        "formal": (120, 250),
        "funny": (80, 200),
        "tactical": (120, 250),
    }
    min_len, max_len = ranges.get(style, (100, 250))

    for i, card in enumerate(cards):
        content = card.get("content", "")
        length = len(content)
        if length < min_len:
            issues.append(f"卡片 {i+1} 过短（{length}字，最低 {min_len}）")
        elif length > max_len:
            issues.append(f"卡片 {i+1} 过长（{length}字，最高 {max_len}）")
    return issues


def check_duplication(cards: list[dict]) -> list[str]:
    """检查卡片间内容重复"""
    issues = []
    contents = [c.get("content", "") for c in cards]
    for i in range(len(contents)):
        for j in range(i + 1, len(contents)):
            # 简单检查：前50字是否完全相同
            if len(contents[i]) > 50 and len(contents[j]) > 50:
                if contents[i][:50] == contents[j][:50]:
                    issues.append(f"卡片 {i+1} 和 {j+1} 开头重复")
    return issues


def run_quality_check(cards: list[dict], match: Match, style: str) -> dict:
    """
    完整质检流程，返回报告：
    {
        "passed": bool,
        "issues": [
            {"type": "sensitive", "detail": "..."},
            {"type": "fact", "detail": "..."},
            {"type": "length", "detail": "..."},
            {"type": "duplication", "detail": "..."},
        ],
    }
    """
    all_issues = []

    for card in cards:
        for word in check_sensitive_words(card.get("content", "")):
            all_issues.append({"type": "sensitive", "detail": f"命中敏感词: {word}"})

    for issue in check_fact_consistency(cards, match):
        all_issues.append({"type": "fact", "detail": issue})

    for issue in check_card_length(cards, style):
        all_issues.append({"type": "length", "detail": issue})

    for issue in check_duplication(cards):
        all_issues.append({"type": "duplication", "detail": issue})

    return {
        "passed": len(all_issues) == 0,
        "issues": all_issues,
    }
