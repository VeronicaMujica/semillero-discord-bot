import os
import time
import aiohttp


class ClickUpAPIError(Exception):
    pass


class ClickUpClient:
    def __init__(self):
        self.api_token = os.getenv("CLICKUP_API_TOKEN")
        self.base_url = "https://api.clickup.com/api/v2"
        self._cache: dict[str, tuple] = {}
        self._cache_ttl = 300  # 5 minutos

        if not self.api_token:
            raise ValueError("Falta CLICKUP_API_TOKEN en el .env")

    @property
    def headers(self):
        return {
            "Authorization": self.api_token,
            "Content-Type": "application/json",
        }

    def _get_cache(self, key: str):
        if key in self._cache:
            data, expires_at = self._cache[key]
            if time.time() < expires_at:
                return data
            del self._cache[key]
        return None

    def _set_cache(self, key: str, data):
        self._cache[key] = (data, time.time() + self._cache_ttl)

    async def _get(self, path: str):
        cached = self._get_cache(path)
        if cached is not None:
            return cached

        url = f"{self.base_url}{path}"
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise ClickUpAPIError(f"ClickUp devolvió {resp.status}: {text}")
                data = await resp.json()
                self._set_cache(path, data)
                return data

    async def get_teams(self) -> list:
        data = await self._get("/team")
        return data.get("teams", [])

    async def get_spaces(self, team_id: str) -> list:
        data = await self._get(f"/team/{team_id}/space?archived=false")
        return data.get("spaces", [])

    async def get_folders(self, space_id: str) -> list:
        data = await self._get(f"/space/{space_id}/folder?archived=false")
        return data.get("folders", [])

    async def get_lists_in_folder(self, folder_id: str) -> list:
        data = await self._get(f"/folder/{folder_id}/list?archived=false")
        return data.get("lists", [])

    async def get_folderless_lists(self, space_id: str) -> list:
        data = await self._get(f"/space/{space_id}/list?archived=false")
        return data.get("lists", [])

    async def get_all_lists(self, team_id: str) -> list[dict]:
        """Devuelve todas las listas del workspace, con nombre de carpeta y espacio."""
        result = []
        spaces = await self.get_spaces(team_id)
        for space in spaces:
            folders = await self.get_folders(space["id"])
            for folder in folders:
                lists = await self.get_lists_in_folder(folder["id"])
                for lst in lists:
                    result.append({
                        "id": lst["id"],
                        "name": lst["name"],
                        "folder": folder["name"],
                        "space": space["name"],
                    })
            folderless = await self.get_folderless_lists(space["id"])
            for lst in folderless:
                result.append({
                    "id": lst["id"],
                    "name": lst["name"],
                    "folder": None,
                    "space": space["name"],
                })
        return result

    async def get_members(self, team_id: str) -> list[dict]:
        """Devuelve los miembros del workspace (sin duplicados)."""
        teams = await self.get_teams()
        for team in teams:
            if str(team["id"]) == str(team_id):
                seen: set[int] = set()
                members = []
                for m in team.get("members", []):
                    user = m["user"]
                    uid = user["id"]
                    if uid not in seen:
                        seen.add(uid)
                        members.append({
                            "id": uid,
                            "name": user["username"],
                        })
                return members
        return []

    async def create_task(
        self,
        list_id: str,
        name: str,
        description: str = "",
        assignees: list[int] | None = None,
        priority: int | None = None,
        due_date: int | None = None,
    ) -> dict:
        url = f"{self.base_url}/list/{list_id}/task"

        payload: dict = {"name": name, "description": description}
        if assignees:
            payload["assignees"] = assignees
        if priority is not None:
            payload["priority"] = priority
        if due_date is not None:
            payload["due_date"] = due_date

        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=self.headers) as resp:
                text = await resp.text()
                if resp.status not in (200, 201):
                    raise ClickUpAPIError(f"ClickUp devolvió {resp.status}: {text}")
                return await resp.json()
