import json
import os
from pathlib import Path

MAPPING_FILE = Path(__file__).parent / "data" / "discord_clickup_map.json"

CLICKUP_TEAM = {
    "isabella": {"id": 81513581, "nombre": "Isabella"},
    "sofi": {"id": 120079719, "nombre": "Sofía"},
    "veronica": {"id": 156006388, "nombre": "Verónica"},
    "mary": {"id": 87398967, "nombre": "Mery"},
    "rochi": {"id": 87374445, "nombre": "Rocío"},
    "cami": {"id": 81593143, "nombre": "Camila"},
    "roggert": {"id": 81593142, "nombre": "Roggert"},
    "ronald": {"id": 81418149, "nombre": "Ronald"},
}

DISCORD_HANDLE_HINTS = {
    "veritoo.m": "veronica",
    "ronaldvargas01": "ronald",
    "meryofangels_34042": "mary",
    "rogber_656": "roggert",
    "camilaatorres": "cami",
    "ojedarocio": "rochi",
}


def _ensure_file():
    MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not MAPPING_FILE.exists():
        MAPPING_FILE.write_text("{}", encoding="utf-8")


def load_mapping() -> dict:
    _ensure_file()
    try:
        return json.loads(MAPPING_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_mapping(data: dict) -> None:
    _ensure_file()
    MAPPING_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def link(discord_id: int, clickup_key: str) -> None:
    if clickup_key not in CLICKUP_TEAM:
        raise ValueError(f"{clickup_key} no existe en CLICKUP_TEAM")
    data = load_mapping()
    data[str(discord_id)] = clickup_key
    save_mapping(data)


def get_clickup_key(discord_id: int) -> str | None:
    return load_mapping().get(str(discord_id))


def get_clickup_id(discord_id: int) -> int | None:
    key = get_clickup_key(discord_id)
    if not key:
        return None
    return CLICKUP_TEAM[key]["id"]


def get_discord_id_for_clickup(clickup_id: int) -> int | None:
    data = load_mapping()
    for d_id, ck_key in data.items():
        if CLICKUP_TEAM.get(ck_key, {}).get("id") == clickup_id:
            return int(d_id)
    return None


def display_name(clickup_id: int) -> str:
    for info in CLICKUP_TEAM.values():
        if info["id"] == clickup_id:
            return info["nombre"]
    return f"user {clickup_id}"


async def auto_link_from_guild(guild) -> int:
    """Intenta resolver handles de Discord → IDs mirando miembros del server.
    Devuelve cuántos vínculos nuevos creó."""
    data = load_mapping()
    new_links = 0
    for member in guild.members:
        if str(member.id) in data:
            continue
        handle = member.name.lower()
        clickup_key = DISCORD_HANDLE_HINTS.get(handle)
        if clickup_key:
            data[str(member.id)] = clickup_key
            new_links += 1
    if new_links:
        save_mapping(data)
    return new_links
