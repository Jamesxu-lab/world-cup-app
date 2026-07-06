"""
API-Football v3 客户端
文档: https://www.api-football.com/documentation-v3
"""
import httpx
from app.core.config import get_settings

settings = get_settings()


class FootballAPIError(Exception):
    pass


class FootballAPI:
    def __init__(self):
        self.base_url = settings.api_football_base_url
        self.headers = {
            "x-apisports-key": settings.api_football_key,
            "Accept": "application/json",
        }

    async def _request(self, endpoint: str, params: dict = None) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                params=params or {},
            )
            data = response.json()
            if response.status_code != 200 or data.get("errors"):
                raise FootballAPIError(
                    f"API Error ({response.status_code}): {data.get('errors', data)}"
                )
            return data

    async def get_worldcup_fixtures(self, season: int = 2022) -> list[dict]:
        """
        获取世界杯全部比赛列表。
        league=1 (World Cup), season=2022 用于测试。
        2026 世界杯的 league id 待官方公布后更新。
        """
        data = await self._request("/fixtures", {
            "league": 1,
            "season": season,
        })
        return data.get("response", [])

    async def get_fixtures_by_date(self, date_str: str) -> list[dict]:
        """按日期获取比赛，date_str 格式: YYYY-MM-DD"""
        data = await self._request("/fixtures", {"date": date_str})
        return data.get("response", [])

    async def get_worldcup_fixtures_by_date(self, date_str: str, season: int | None = None) -> list[dict]:
        """按日期获取世界杯比赛，date_str 格式: YYYY-MM-DD"""
        if season is not None:
            data = await self._request("/fixtures", {
                "league": 1,
                "season": season,
                "date": date_str,
            })
            return data.get("response", [])

        fixtures = await self.get_fixtures_by_date(date_str)
        return [f for f in fixtures if f.get("league", {}).get("id") == 1]

    async def get_fixture_events(self, fixture_id: int) -> list[dict]:
        """获取单场比赛的事件流（进球/红黄牌/换人等）"""
        data = await self._request("/fixtures/events", {"fixture": fixture_id})
        return data.get("response", [])

    async def get_fixture_statistics(self, fixture_id: int) -> list[dict]:
        """获取单场比赛的技术统计数据"""
        data = await self._request("/fixtures/statistics", {"fixture": fixture_id})
        return data.get("response", [])

    async def get_fixture_players(self, fixture_id: int) -> list[dict]:
        """获取单场比赛的球员表现数据（评分/进球/助攻/传球等）"""
        data = await self._request("/fixtures/players", {"fixture": fixture_id})
        return data.get("response", [])

    async def get_fixture_lineups(self, fixture_id: int) -> list[dict]:
        """获取单场比赛的阵容"""
        data = await self._request("/fixtures/lineups", {"fixture": fixture_id})
        return data.get("response", [])

    async def get_teams_by_league(self, season: int = 2022) -> list[dict]:
        """获取世界杯参赛球队信息"""
        data = await self._request("/teams", {
            "league": 1,
            "season": season,
        })
        return data.get("response", [])

    async def get_full_match_data(self, fixture_id: int) -> dict:
        """
        一次性拉取单场比赛的全部数据：事件+统计+球员+阵容。
        返回聚合后的字典。
        """
        events = await self.get_fixture_events(fixture_id)
        stats = await self.get_fixture_statistics(fixture_id)
        players = await self.get_fixture_players(fixture_id)
        lineups = await self.get_fixture_lineups(fixture_id)
        return {
            "events": events,
            "statistics": stats,
            "players": players,
            "lineups": lineups,
        }
