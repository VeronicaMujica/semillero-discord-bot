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
        url = f"{self.base_url}/list/{list_id}/task"

        payload = {
            "name": name,
            "description": description,
        }

        if assignees:
            payload["assignees"] = assignees

        if priority is not None:
            payload["priority"] = priority

        if due_date is not None:
            payload["due_date"] = due_date

        if tags:
            payload["tags"] = tags

        timeout = aiohttp.ClientTimeout(total=20)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=self.headers) as resp:
                text = await resp.text()

                if resp.status not in (200, 201):
                    raise ClickUpAPIError(f"ClickUp devolvió {resp.status}: {text}")

                return await resp.json()