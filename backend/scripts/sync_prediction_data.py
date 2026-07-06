"""
Sync live-ish prediction inputs into a local JSON snapshot.

Sources intentionally stay dependency-light:
- World Football Elo Ratings TSV for current national-team Elo.
- FIFA ranking page for official ranking update metadata and headline cards.
- Local 2026_World_Cup_Results.md for current groups and match results.
- Wikipedia squads page for final squad counts and player names.

Run from repository root or backend directory:
    PYTHONPATH=backend .venv/bin/python backend/scripts/sync_prediction_data.py
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx


ELO_RATINGS_URL = "https://www.eloratings.net/World.tsv"
ELO_TEAMS_URL = "https://www.eloratings.net/en.teams.tsv"
FIFA_RANKING_URL = "https://inside.fifa.com/fifa-world-ranking/men"
WIKI_WORLD_CUP_URL = "https://en.wikipedia.org/api/rest_v1/page/html/2026_FIFA_World_Cup"
WIKI_SQUADS_URL = "https://en.wikipedia.org/api/rest_v1/page/html/2026_FIFA_World_Cup_squads"
WIKI_GROUP_URL = "https://en.wikipedia.org/api/rest_v1/page/html/2026_FIFA_World_Cup_Group_{group}"

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
DEFAULT_OUTPUT = ROOT / "data" / "prediction_snapshot.json"
LOCAL_RESULTS_PATH = PROJECT_ROOT / "2026_World_Cup_Results.md"
MIN_EXPECTED_TEAMS = 48
MIN_EXPECTED_FIXTURES = 60

TEAM_ALIASES = {
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    "Czech Republic": "Czechia",
    "Congo DR": "DR Congo",
    "Congo DR national football team": "DR Congo",
    "Côte d'Ivoire": "Ivory Coast",
    "Iran": "Iran",
    "Korea Republic": "South Korea",
    "Türkiye": "Turkey",
    "United States": "USA",
}

TEAM_CN = {
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
    "Algeria": "阿尔及利亚",
    "Austria": "奥地利",
    "Jordan": "约旦",
    "DR Congo": "刚果（金）",
    "Panama": "巴拿马",
    "Uzbekistan": "乌兹别克斯坦",
    "Czechia": "捷克",
    "Bosnia & Herzegovina": "波黑",
    "Senegal": "塞内加尔",
    "South Africa": "南非",
    "Tunisia": "突尼斯",
    "Serbia": "塞尔维亚",
    "Switzerland": "瑞士",
    "Denmark": "丹麦",
    "Wales": "威尔士",
    "Poland": "波兰",
    "Italy": "意大利",
    "Colombia": "哥伦比亚",
    "Sweden": "瑞典",
    "Norway": "挪威",
    "Iraq": "伊拉克",
    "Paraguay": "巴拉圭",
    "Haiti": "海地",
    "Scotland": "苏格兰",
    "Turkey": "土耳其",
    "Ivory Coast": "科特迪瓦",
    "Cape Verde": "佛得角",
    "Iran": "伊朗",
    "New Zealand": "新西兰",
    "Egypt": "埃及",
    "Curaçao": "库拉索",
}

CONFEDERATION = {
    "Argentina": "CONMEBOL",
    "Brazil": "CONMEBOL",
    "Colombia": "CONMEBOL",
    "Ecuador": "CONMEBOL",
    "Paraguay": "CONMEBOL",
    "Uruguay": "CONMEBOL",
    "Mexico": "CONCACAF",
    "USA": "CONCACAF",
    "Canada": "CONCACAF",
    "Panama": "CONCACAF",
    "Haiti": "CONCACAF",
    "Curaçao": "CONCACAF",
    "Costa Rica": "CONCACAF",
    "Jamaica": "CONCACAF",
    "France": "UEFA",
    "Spain": "UEFA",
    "England": "UEFA",
    "Portugal": "UEFA",
    "Netherlands": "UEFA",
    "Germany": "UEFA",
    "Italy": "UEFA",
    "Croatia": "UEFA",
    "Switzerland": "UEFA",
    "Denmark": "UEFA",
    "Austria": "UEFA",
    "Turkey": "UEFA",
    "Poland": "UEFA",
    "Czechia": "UEFA",
    "Norway": "UEFA",
    "Scotland": "UEFA",
    "Sweden": "UEFA",
    "Bosnia & Herzegovina": "UEFA",
    "Belgium": "UEFA",
    "Morocco": "CAF",
    "Senegal": "CAF",
    "Egypt": "CAF",
    "South Africa": "CAF",
    "Ghana": "CAF",
    "Algeria": "CAF",
    "Tunisia": "CAF",
    "Ivory Coast": "CAF",
    "Cape Verde": "CAF",
    "DR Congo": "CAF",
    "Japan": "AFC",
    "South Korea": "AFC",
    "Australia": "AFC",
    "Iran": "AFC",
    "Saudi Arabia": "AFC",
    "Qatar": "AFC",
    "Uzbekistan": "AFC",
    "Jordan": "AFC",
    "Iraq": "AFC",
    "New Zealand": "OFC",
}

FALLBACK_GROUPS = {
    "A": ["Mexico", "South Africa", "South Korea", "Czechia"],
    "B": ["Canada", "Bosnia & Herzegovina", "Qatar", "Switzerland"],
    "C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "D": ["USA", "Paraguay", "Australia", "Turkey"],
    "E": ["Germany", "Curaçao", "Ivory Coast", "Ecuador"],
    "F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
    "I": ["France", "Senegal", "Iraq", "Norway"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}


@dataclass
class SourceStatus:
    name: str
    url: str
    ok: bool
    detail: str = ""


@dataclass
class TeamSnapshot:
    name: str
    name_cn: str
    confederation: str
    group: str | None = None
    elo: int | None = None
    elo_rank: int | None = None
    fifa_rank: int | None = None
    fifa_points: float | None = None
    elo_rating_change_3m: int | None = None
    elo_rating_change_6m: int | None = None
    elo_rating_change_1y: int | None = None
    played_matches: int = 0
    points_per_game: float | None = None
    goal_difference_per_game: float | None = None
    squad_count: int | None = None
    squad_players: list[str] = field(default_factory=list)
    squad_quality_score: int | None = None
    recent_form_score: int | None = None
    availability_score: int | None = None
    unavailable_count: int = 0
    unavailable_players: list[str] = field(default_factory=list)
    doubtful_count: int = 0
    doubtful_players: list[str] = field(default_factory=list)


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return " ".join(self.parts)


class WikiTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._capture_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
            self._capture_cell = True

    def handle_data(self, data: str) -> None:
        if self._capture_cell and self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            text = clean_text(" ".join(self._cell))
            self._row.append(text)
            self._cell = None
            self._capture_cell = False
        elif tag == "tr" and self._row is not None and self._table is not None:
            if any(self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._table:
                self.tables.append(self._table)
            self._table = None


def clean_text(value: str) -> str:
    value = unescape(value)
    value = re.sub(r"\[[^\]]+\]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def clamp(value: float, low: int = 0, high: int = 100) -> int:
    return round(max(low, min(high, value)))


def parse_signed_int(value: str) -> int | None:
    value = value.strip().replace("−", "-").replace("+", "")
    if value in {"", "-"}:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def canonical_team(name: str) -> str:
    name = clean_text(name)
    name = re.sub(r"\s*\([^)]*\)", "", name)
    name = re.sub(r"^and\s+", "", name)
    name = re.sub(r"^(the|The)\s+", "", name)
    name = re.sub(r"\s+national football team$", "", name)
    return TEAM_ALIASES.get(name, name)


def fetch_text(client: httpx.Client, url: str) -> str:
    try:
        response = client.get(url, follow_redirects=True)
        response.raise_for_status()
        return response.text
    except httpx.HTTPError:
        if "wikipedia.org" not in url:
            raise
        result = subprocess.run(
            ["curl", "-sL", url],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout


def parse_elo(client: httpx.Client) -> tuple[dict[str, dict[str, Any]], SourceStatus]:
    teams_tsv = fetch_text(client, ELO_TEAMS_URL)
    code_to_name = {}
    for line in teams_tsv.splitlines():
        cols = line.split("\t")
        if len(cols) >= 2:
            code_to_name[cols[0]] = canonical_team(cols[1])

    world_tsv = fetch_text(client, ELO_RATINGS_URL)
    data: dict[str, dict[str, Any]] = {}
    for line in world_tsv.splitlines():
        cols = line.split("\t")
        if len(cols) < 4:
            continue
        rank = int(cols[0])
        code = cols[2]
        name = code_to_name.get(code, code)
        data[name] = {
            "elo_rank": rank,
            "elo": int(cols[3]),
            "elo_rating_change_3m": parse_signed_int(cols[13]) if len(cols) > 13 else None,
            "elo_rating_change_6m": parse_signed_int(cols[15]) if len(cols) > 15 else None,
            "elo_rating_change_1y": parse_signed_int(cols[17]) if len(cols) > 17 else None,
        }
    return data, SourceStatus("World Football Elo Ratings", ELO_RATINGS_URL, True, f"{len(data)} teams")


def parse_fifa_metadata(client: httpx.Client) -> tuple[dict[str, Any], SourceStatus]:
    html = fetch_text(client, FIFA_RANKING_URL)
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
    if not match:
        return {}, SourceStatus("FIFA ranking page", FIFA_RANKING_URL, False, "__NEXT_DATA__ not found")
    next_data = json.loads(match.group(1))
    ranking = next_data["props"]["pageProps"]["pageData"]["ranking"]
    cards = ranking.get("boldCards", [])
    return {
        "last_update_date": ranking.get("lastUpdateDate"),
        "next_update_date": ranking.get("nextUpdateDate"),
        "available_dates": ranking.get("allAvailableDates", [])[:5],
        "headline_cards": [
            {
                "label": card.get("worldRankingCardTypeLabel"),
                "country": canonical_team(card.get("countryName", "")),
                "value": card.get("cardValue"),
                "country_code": card.get("countryCode"),
            }
            for card in cards
        ],
    }, SourceStatus("FIFA ranking page", FIFA_RANKING_URL, True, "metadata parsed; full table API not exposed")


def parse_groups(client: httpx.Client) -> tuple[dict[str, list[str]], list[dict[str, Any]], SourceStatus]:
    groups: dict[str, list[str]] = {}
    fixtures: list[dict[str, Any]] = []
    for group in "ABCDEFGHIJKL":
        url = WIKI_GROUP_URL.format(group=group)
        html = fetch_text(client, url)
        extractor = TextExtractor()
        extractor.feed(html)
        text = extractor.text()
        match = re.search(rf"Group {group} .*? The group consists of (.*?) \.", text)
        if not match:
            match = re.search(r"The group consists of (.*?) \.", text)
        if match:
            raw_teams = match.group(1).replace("Bosnia and Herzegovina", "Bosnia & Herzegovina")
            raw_teams = re.sub(r"\s*,\s*and\s+", ", ", raw_teams)
            teams = re.split(r"\s*,\s*", raw_teams)
            groups[group] = [canonical_team(team) for team in teams if team]

        parser = WikiTableParser()
        parser.feed(html)
        for table in parser.tables:
            for row in table:
                if len(row) < 3:
                    continue
                home = canonical_team(row[0])
                away = canonical_team(row[2])
                group_teams = set(groups.get(group, []))
                if home in group_teams and away in group_teams:
                    fixtures.append({
                        "group": group,
                        "home": home,
                        "away": away,
                        "score": clean_text(row[1]) or None,
                        "raw": " | ".join(row),
                    })
    for group, teams in FALLBACK_GROUPS.items():
        if len(groups.get(group, [])) != 4:
            groups[group] = teams
    return groups, fixtures, SourceStatus("Wikipedia group pages", WIKI_GROUP_URL.format(group="A"), True, f"{len(groups)} groups, {len(fixtures)} fixtures")


def parse_local_results(path: Path = LOCAL_RESULTS_PATH) -> tuple[dict[str, list[str]], list[dict[str, Any]], SourceStatus]:
    """Parse group fixtures and known knockout results from the local results markdown."""
    if not path.exists():
        return {}, [], SourceStatus("Local World Cup results file", str(path), False, "file not found")

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {}, [], SourceStatus("Local World Cup results file", str(path), False, str(exc))

    groups = {group: list(teams) for group, teams in FALLBACK_GROUPS.items()}
    fixtures: list[dict[str, Any]] = []
    current_group: str | None = None
    in_group_results = False
    in_completed_knockout = False

    group_fixture_pattern = re.compile(
        r"^-\s+\*\*(\d{4}-\d{2}-\d{2})\*\*:\s+(.+?)\s+(\d+)-(\d+)\s+(.+?)\s*$"
    )

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## 3."):
            in_group_results = True
            in_completed_knockout = False
            current_group = None
            continue
        if line.startswith("## 4."):
            in_group_results = False
            current_group = None
            continue
        if line.startswith("### 4.1"):
            in_completed_knockout = True
            continue
        if line.startswith("### 4.2"):
            in_completed_knockout = False
            continue

        if in_group_results:
            group_match = re.match(r"^###\s+Group\s+([A-L])\b", line)
            if group_match:
                current_group = group_match.group(1)
                continue

            fixture_match = group_fixture_pattern.match(line)
            if fixture_match and current_group:
                match_date, home, home_goals, away_goals, away = fixture_match.groups()
                fixtures.append({
                    "group": current_group,
                    "stage": "group",
                    "date": match_date,
                    "home": canonical_team(home),
                    "away": canonical_team(away),
                    "score": f"{home_goals}-{away_goals}",
                    "source": "2026_World_Cup_Results.md",
                    "raw": line,
                })
            continue

        if in_completed_knockout and line.startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 5 or cells[0] in {"日期", "------"}:
                continue
            date_value, matchup, score, winner, loser = cells[:5]
            if "vs" not in matchup or not re.search(r"\d+\s*-\s*\d+", score):
                continue
            home, away = [canonical_team(part) for part in matchup.split("vs", 1)]
            fixtures.append({
                "group": "knockout",
                "stage": "round_of_32",
                "date": date_value,
                "home": home,
                "away": away,
                "score": score.replace(" ", ""),
                "winner": canonical_team(winner),
                "loser": canonical_team(loser),
                "source": "2026_World_Cup_Results.md",
                "raw": line,
            })

    detail = f"{len(groups)} groups, {len(fixtures)} fixtures"
    ok = len(groups) == 12 and len(fixtures) >= MIN_EXPECTED_FIXTURES
    return groups, fixtures, SourceStatus("Local World Cup results file", str(path), ok, detail)


def parse_squads(client: httpx.Client, team_names: set[str]) -> tuple[dict[str, dict[str, Any]], SourceStatus]:
    html = fetch_text(client, WIKI_SQUADS_URL)
    if "too many requests" in html.lower() or "rate_limits" in html:
        return {}, SourceStatus("Wikipedia squads page", WIKI_SQUADS_URL, False, "rate limited")

    parser = WikiTableParser()
    parser.feed(html)
    squads: dict[str, dict[str, Any]] = {}

    current_team = None
    heading_pattern = re.compile(r"<h3[^>]*>(.*?)</h3>", re.S)
    headings = [(m.start(), canonical_team(re.sub("<.*?>", "", m.group(1)))) for m in heading_pattern.finditer(html)]
    heading_index = 0

    table_pattern = re.compile(r"<table[\s\S]*?</table>")
    for table_match in table_pattern.finditer(html):
        while heading_index + 1 < len(headings) and headings[heading_index + 1][0] < table_match.start():
            heading_index += 1
        if headings:
            current_team = headings[heading_index][1]
        if current_team not in team_names:
            continue

        table_parser = WikiTableParser()
        table_parser.feed(table_match.group(0))
        if not table_parser.tables:
            continue
        rows = table_parser.tables[0]
        header = " ".join(rows[0]).lower() if rows else ""
        if "player" not in header or "club" not in header:
            continue
        players = []
        for row in rows[1:]:
            if len(row) < 3:
                continue
            player = canonical_team(row[2] if row[0].isdigit() else row[min(1, len(row) - 1)])
            if player and player not in {"Player", "No."}:
                players.append(player)
        if players:
            squads[current_team] = {"squad_count": len(players), "squad_players": players[:26]}

    return squads, SourceStatus("Wikipedia squads page", WIKI_SQUADS_URL, True, f"{len(squads)} squads parsed")


def load_injuries(path: Path | None) -> tuple[dict[str, dict[str, Any]], SourceStatus | None]:
    if not path:
        return {}, None
    if not path.exists():
        return {}, SourceStatus("Injury feed", str(path), False, "file not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data, SourceStatus("Injury feed", str(path), True, f"{len(data)} teams")


def score_group_form(fixtures: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    form: dict[str, dict[str, Any]] = {}
    for fixture in fixtures:
        match = re.search(r"(\d+)\s*[–-]\s*(\d+)", fixture.get("score") or "")
        if not match:
            continue
        home = fixture["home"]
        away = fixture["away"]
        home_goals = int(match.group(1))
        away_goals = int(match.group(2))
        for name in (home, away):
            form.setdefault(name, {"played": 0, "points": 0, "goal_difference": 0})
        form[home]["played"] += 1
        form[away]["played"] += 1
        form[home]["goal_difference"] += home_goals - away_goals
        form[away]["goal_difference"] += away_goals - home_goals
        if home_goals > away_goals:
            form[home]["points"] += 3
        elif home_goals < away_goals:
            form[away]["points"] += 3
        else:
            form[home]["points"] += 1
            form[away]["points"] += 1
    return form


def build_availability_score(squad_count: int | None, unavailable_count: int, doubtful_count: int) -> int:
    missing_squad_slots = max(0, 26 - (squad_count or 26))
    return clamp(100 - unavailable_count * 6 - doubtful_count * 3 - missing_squad_slots * 2, 40, 100)


def build_squad_quality_score(elo: int | None, squad_count: int | None, availability_score: int) -> int:
    if elo is None:
        base = 58
    else:
        base = 48 + max(0, min(1, (elo - 1500) / 650)) * 47
    depth_bonus = min(5, max(0, (squad_count or 26) - 23))
    availability_drag = (100 - availability_score) * 0.35
    return clamp(base + depth_bonus - availability_drag, 35, 98)


def build_recent_form_score(elo_data: dict[str, Any], group_form: dict[str, Any] | None) -> int:
    change_3m = elo_data.get("elo_rating_change_3m") or 0
    change_6m = elo_data.get("elo_rating_change_6m") or 0
    change_1y = elo_data.get("elo_rating_change_1y") or 0
    elo_momentum = change_3m * 0.35 + change_6m * 0.25 + change_1y * 0.15

    tournament_boost = 0.0
    if group_form and group_form["played"]:
        ppg = group_form["points"] / group_form["played"]
        gd_per_game = group_form["goal_difference"] / group_form["played"]
        tournament_boost = (ppg - 1.33) * 8 + gd_per_game * 3

    return clamp(55 + elo_momentum * 0.25 + tournament_boost, 35, 96)


def build_snapshot(injury_file: Path | None = None) -> dict[str, Any]:
    statuses: list[SourceStatus] = []
    with httpx.Client(timeout=30, headers={"User-Agent": "Mozilla/5.0 worldcup-prediction-sync/1.0"}) as client:
        elo, status = parse_elo(client)
        statuses.append(status)

        fifa_meta, status = parse_fifa_metadata(client)
        statuses.append(status)

        groups, fixtures, status = parse_local_results()
        statuses.append(status)
        if not status.ok:
            groups, fixtures, status = parse_groups(client)
            statuses.append(status)

        team_names = {team for teams in groups.values() for team in teams}
        squads, status = parse_squads(client, team_names)
        statuses.append(status)

    injuries, injury_status = load_injuries(injury_file)
    if injury_status:
        statuses.append(injury_status)

    group_form = score_group_form(fixtures)
    teams: dict[str, TeamSnapshot] = {}
    for group, group_teams in groups.items():
        for name in group_teams:
            unavailable = injuries.get(name, {}).get("unavailable_players", [])
            doubtful = injuries.get(name, {}).get("doubtful_players", [])
            squad_count = squads.get(name, {}).get("squad_count") or 26
            availability_score = build_availability_score(squad_count, len(unavailable), len(doubtful))
            recent_form = group_form.get(name)
            elo_data = elo.get(name, {})
            team = TeamSnapshot(
                name=name,
                name_cn=TEAM_CN.get(name, name),
                confederation=CONFEDERATION.get(name, "UNKNOWN"),
                group=group,
                squad_count=squad_count,
                squad_players=squads.get(name, {}).get("squad_players", []),
                unavailable_count=len(unavailable),
                unavailable_players=unavailable,
                doubtful_count=len(doubtful),
                doubtful_players=doubtful,
                availability_score=availability_score,
                squad_quality_score=build_squad_quality_score(elo_data.get("elo"), squad_count, availability_score),
                recent_form_score=build_recent_form_score(elo_data, recent_form),
            )
            if name in elo:
                team.elo = elo[name]["elo"]
                team.elo_rank = elo[name]["elo_rank"]
                team.elo_rating_change_3m = elo[name].get("elo_rating_change_3m")
                team.elo_rating_change_6m = elo[name].get("elo_rating_change_6m")
                team.elo_rating_change_1y = elo[name].get("elo_rating_change_1y")
            if recent_form:
                team.played_matches = recent_form["played"]
                team.points_per_game = round(recent_form["points"] / recent_form["played"], 2)
                team.goal_difference_per_game = round(recent_form["goal_difference"] / recent_form["played"], 2)
            teams[name] = team

    return {
        "version": "prediction-inputs-v1",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [asdict(status) for status in statuses],
        "fifa_ranking": fifa_meta,
        "groups": groups,
        "fixtures": fixtures,
        "teams": [asdict(team) for team in sorted(teams.values(), key=lambda item: (item.group or "", item.name))],
        "notes": [
            "Elo ratings are live from eloratings.net World.tsv.",
            "FIFA ranking metadata is parsed from the official FIFA ranking page; full ranking table endpoint is not exposed in the static page.",
            "Match results are parsed first from local 2026_World_Cup_Results.md; Wikipedia group pages are only a fallback when the local file is missing or invalid.",
            "Final squads are parsed from current Wikipedia pages that cite FIFA squad sources.",
            "Squad quality, recent form, and availability scores are derived into the snapshot and used by the win-probability model.",
            "Injury data is optional. Pass --injuries path/to/file.json with unavailable_players and doubtful_players per team when a vetted feed is available.",
        ],
    }


def validate_snapshot(snapshot: dict[str, Any]) -> list[str]:
    """Return data-quality errors that should block replacing a good snapshot."""
    errors = []
    teams_count = len(snapshot.get("teams", []))
    fixtures_count = len(snapshot.get("fixtures", []))
    if teams_count < MIN_EXPECTED_TEAMS:
        errors.append(f"expected at least {MIN_EXPECTED_TEAMS} teams, got {teams_count}")
    if fixtures_count < MIN_EXPECTED_FIXTURES:
        errors.append(f"expected at least {MIN_EXPECTED_FIXTURES} fixtures, got {fixtures_count}")

    sources = snapshot.get("sources", [])
    failed_sources = [source for source in sources if not source.get("ok")]
    if len(failed_sources) >= max(1, len(sources) // 2):
        errors.append(f"too many failed sources: {len(failed_sources)}/{len(sources)}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--injuries", type=Path, default=None)
    args = parser.parse_args()

    snapshot = build_snapshot(args.injuries)
    validation_errors = validate_snapshot(snapshot)
    if validation_errors:
        raise SystemExit("Snapshot validation failed: " + "; ".join(validation_errors))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Teams: {len(snapshot['teams'])}, fixtures: {len(snapshot['fixtures'])}")
    for source in snapshot["sources"]:
        print(f"- {source['name']}: {'ok' if source['ok'] else 'failed'} ({source['detail']})")


if __name__ == "__main__":
    main()
