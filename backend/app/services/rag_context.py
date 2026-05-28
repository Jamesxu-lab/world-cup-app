"""
RAG 知识库服务：基于关键词匹配的轻量知识检索。
MVP 阶段用简单字符串匹配代替向量检索，知识库 ~40 条，效果够用。
"""
import json
import os
import re

from app.core.config import get_settings

settings = get_settings()

# 内存缓存
_knowledge_cache: list[dict] | None = None


def _get_knowledge_path() -> str:
    persist_dir = settings.chroma_persist_dir
    os.makedirs(persist_dir, exist_ok=True)
    return os.path.join(persist_dir, "knowledge_base.json")


def store_knowledge(items: list[dict]):
    """将知识条目存为 JSON 文件"""
    global _knowledge_cache
    _knowledge_cache = items
    path = _get_knowledge_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def load_knowledge() -> list[dict]:
    """加载知识库到内存"""
    global _knowledge_cache
    if _knowledge_cache is not None:
        return _knowledge_cache

    path = _get_knowledge_path()
    if not os.path.exists(path):
        _knowledge_cache = []
        return _knowledge_cache

    with open(path, "r", encoding="utf-8") as f:
        _knowledge_cache = json.load(f)
    return _knowledge_cache


def _extract_keywords(text: str) -> set[str]:
    """从查询文本中提取关键词"""
    keywords = set()
    # 球队名（中英文）
    team_map = {
        "巴西": "brazil", "阿根廷": "argentina", "法国": "france",
        "英格兰": "england", "德国": "germany", "西班牙": "spain",
        "葡萄牙": "portugal", "荷兰": "netherlands",
        "克罗地亚": "croatia", "摩洛哥": "morocco",
        "日本": "japan", "沙特": "saudi", "厄瓜多尔": "ecuador",
        "卡塔尔": "qatar", "乌拉圭": "uruguay", "加拿大": "canada",
        "美国": "usa", "比利时": "belgium", "意大利": "italy",
    }
    for cn, en in team_map.items():
        if cn in text or en in text.lower():
            keywords.add(en)
            keywords.add(cn)

    # 球员名
    player_names = [
        "姆巴佩", "梅西", "C罗", "内马尔", "贝林厄姆", "哈兰德",
        "维尼修斯", "穆西亚拉", "佩德里", "福登", "萨卡", "凯恩",
        "莫德里奇", "格里兹曼", "巴尔韦德", "戴维斯", "普利西奇",
        "维尔茨", "亚马尔", "罗德里", "齐达内", "马拉多纳", "罗纳尔多",
        "克洛泽", "伊涅斯塔", "哈维", "克鲁伊夫", "贝克汉姆",
    ]
    for name in player_names:
        if name in text:
            keywords.add(name)

    # 关键词
    extra = ["决赛", "半决赛", "世界杯", "点球", "红牌", "帽子戏法",
             "冷门", "爆冷", "历史", "纪录", "冠军", "战术"]
    for w in extra:
        if w in text:
            keywords.add(w)

    return keywords


def search_knowledge(query: str, n_results: int = 5) -> str:
    """
    基于关键词匹配检索知识库，返回拼接后的文本。
    """
    items = load_knowledge()
    if not items:
        return ""

    keywords = _extract_keywords(query)

    scored = []
    for item in items:
        score = 0
        item_text = item.get("text", "")
        item_id = item.get("id", "")
        item_type = item.get("type", "")

        # 关键词匹配计分
        for kw in keywords:
            if kw.lower() in item_text.lower() or kw.lower() in item_id.lower():
                score += 1

        # 类型加权
        if item_type in ("team", "player"):
            score += 1

        if score > 0:
            scored.append((score, item))

    # 按分数降序排列
    scored.sort(key=lambda x: x[0], reverse=True)

    top_items = [item for _, item in scored[:n_results]]
    if not top_items:
        return ""

    return "\n\n".join(f"[{item.get('type', '')}] {item.get('text', '')}" for item in top_items)
