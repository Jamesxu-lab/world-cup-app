"""
球队和球场的中英文名称映射。
"""

TEAM_NAMES: dict[str, str] = {
    "Argentina": "阿根廷",
    "France": "法国",
    "England": "英格兰",
    "Brazil": "巴西",
    "Germany": "德国",
    "Spain": "西班牙",
    "Portugal": "葡萄牙",
    "Netherlands": "荷兰",
    "Belgium": "比利时",
    "Croatia": "克罗地亚",
    "Morocco": "摩洛哥",
    "Japan": "日本",
    "South Korea": "韩国",
    "Australia": "澳大利亚",
    "Saudi Arabia": "沙特阿拉伯",
    "Qatar": "卡塔尔",
    "Ecuador": "厄瓜多尔",
    "Uruguay": "乌拉圭",
    "Canada": "加拿大",
    "USA": "美国",
    "Mexico": "墨西哥",
    "Ghana": "加纳",
    "Senegal": "塞内加尔",
    "Cameroon": "喀麦隆",
    "South Africa": "南非",
    "Tunisia": "突尼斯",
    "Serbia": "塞尔维亚",
    "Switzerland": "瑞士",
    "Denmark": "丹麦",
    "Wales": "威尔士",
    "Poland": "波兰",
    "Italy": "意大利",
    "Colombia": "哥伦比亚",
    "Chile": "智利",
    "Peru": "秘鲁",
    "Sweden": "瑞典",
}

STADIUM_NAMES: dict[str, str] = {
    "Lusail Iconic Stadium": "卢赛尔体育场",
    "Al Bayt Stadium": "海湾球场",
    "Al Thumama Stadium": "阿图玛玛球场",
    "Khalifa International Stadium": "哈利法国际体育场",
    "Stadium 974": "974球场",
    "Education City Stadium": "教育城球场",
    "Ahmad Bin Ali Stadium": "艾哈迈德·本·阿里球场",
    "Al Janoub Stadium": "贾努布球场",
}

CITY_NAMES: dict[str, str] = {
    "Lusail": "卢赛尔",
    "Al Khor": "豪尔",
    "Doha": "多哈",
    "Ar-Rayyan": "赖扬",
    "Al Wakrah": "沃克拉",
}

ROUND_NAMES: dict[str, str] = {
    "Final": "决赛",
    "Third Place": "季军赛",
    "Semi-final": "半决赛",
    "Semi-finals": "半决赛",
    "Quarter-final": "四分之一决赛",
    "Quarter-finals": "四分之一决赛",
    "Round of 16": "八分之一决赛",
    "Group Stage": "小组赛",
    "Group Stage - 1": "小组赛",
    "Group Stage - 2": "小组赛",
    "Group Stage - 3": "小组赛",
    "group_stage": "小组赛",
}

STATUS_NAMES: dict[str, str] = {
    "FT": "全场结束",
    "AET": "加时赛结束",
    "PEN": "点球决胜",
    "NS": "未开始",
    "LIVE": "进行中",
    "HT": "半场",
}


def get_team_cn(name: str) -> str:
    return TEAM_NAMES.get(name, name)


def get_stadium_cn(name: str) -> str:
    return STADIUM_NAMES.get(name, name)


def get_city_cn(name: str) -> str:
    return CITY_NAMES.get(name, name)


def get_round_cn(name: str) -> str:
    return ROUND_NAMES.get(name, name)


def get_status_cn(status: str) -> str:
    return STATUS_NAMES.get(status, status)
