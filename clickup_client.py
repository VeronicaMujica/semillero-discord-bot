import os
import aiohttp


class ClickUpAPIError(Exception):
    pass


class ClickUpClient:
    def __init__(self):
        self.api_token = os.getenv("CLICKUP_API_TOKEN")
        self.base_url = "https://api.clickup.com/api/v2"

        if not self.api_token:
            raise ValueError("Falta CLICKUP_API_TOKEN en el .env")

    @property
    def headers(self):
        return {
            "Authorization": self.api_token,
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, *, params=None, json_body=None):
        url = f"{self.base_url}{path}"
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method, url, params=params, json=json_body, headers=self.headers
            ) as resp:
                text = await resp.text()
                if resp.status not in (200, 201):
                    raise ClickUpAPIError(f"ClickUp devolvió {resp.status}: {text}")
                return await resp.json()

    async def create_task(
        self,
        list_id: str,
        name: str,
        description: str = "",
        assignees: list[int] | None = None,
        priority: int | None = None,
        due_date: int | None = None,
        tags: list[str] | None = None,
    ):
        payload = {"name": name, "description": description}
        if assignees:
            payload["assignees"] = assignees
        if priority is not None:
            payload["priority"] = priority
        if due_date is not None:
            payload["due_date"] = due_date
        if tags:
            payload["tags"] = tags

        return await self._request("POST", f"/list/{list_id}/task", json_body=payload)

    async def get_team_tasks(
        self,
        team_id: str,
        *,
        assignee_ids: list[int] | None = None,
        due_date_lt: int | None = None,
        date_created_gt: int | None = None,
        date_closed_gt: int | None = None,
        include_closed: bool = False,
        page: int = 0,
    ) -> list[dict]:
        """Trae tareas a nivel team (workspace). Paginado."""
        params: list[tuple[str, str]] = [("page", str(page))]
        if include_closed:
            params.append(("include_closed", "true"))
        if assignee_ids:
            for aid in assignee_ids:
                params.append(("assignees[]", str(aid)))
        if due_date_lt is not None:
            params.append(("due_date_lt", str(due_date_lt)))
        if date_created_gt is not None:
            params.append(("date_created_gt", str(date_created_gt)))
        if date_closed_gt is not None:
            params.append(("date_closed_gt", str(date_closed_gt)))

        data = await self._request("GET", f"/team/{team_id}/task", params=params)
        return data.get("tasks", [])

    async def get_all_team_tasks(self, team_id: str, **filters) -> list[dict]:
        """Consume todas las páginas hasta que la API devuelva una vacía."""
        all_tasks: list[dict] = []
        page = 0
        while True:
            chunk = await self.get_team_tasks(team_id, page=page, **filters)
            if not chunk:
                break
            all_tasks.extend(chunk)
            if len(chunk) < 100:
                break
            page += 1
            if page > 20:  # safety
                break
        return all_tasks
