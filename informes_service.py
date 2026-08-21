"""
Generación automática e idempotente de los Docs de informes en ClickUp (Mesa Alta).

Estructura creada:

  Informes semanales   (Doc en el Space "MESA ALTA")
    └─ Agosto           (página mes)
        └─ Semana del 3 al 7   (página semana, Lun–Vie)
            ├─ Vero  ├─ Rog ├─ Rochi ├─ Cami ├─ Sofi ├─ Ron ├─ Isa ├─ Nicky

  Informes mensuales
    └─ Agosto
        ├─ Vero  ├─ Rog ├─ Rochi ├─ Cami ├─ Sofi ├─ Ron ├─ Isa ├─ Nicky

Cada página de persona nace con una plantilla (semanal o mensual) ya
personalizada con su nombre completo y la fecha de la semana/mes.

Idempotente: antes de crear cualquier página se consulta el árbol existente y
solo se crea lo que falta. NUNCA edita páginas ya existentes (para no pisar lo
que la gente ya cargó). Es clave porque la API v3 de ClickUp NO permite borrar
Docs (DELETE → 405).

Para la corrida automática de los lunes se usa `asegurar_mes`, que NO regenera
si el mes ya existe: devuelve el DEEP LINK a la página de la semana en curso
(ej. .../v/dc/{doc}/{pagina-semana}). `generar_mes` queda para forzar/crear a
mano (comando de admin).

Notas de formato ClickUp (aprendidas probando):
  • Los encabezados `##` generan el índice lateral navegable del Doc.
  • Una viñeta vacía `- ` se renderiza como "null." → usar SIEMPRE placeholder.
  • Hay que dejar línea en blanco entre bloques o se fusionan con el encabezado.
"""
from __future__ import annotations

import datetime as dt
import logging
import os

log = logging.getLogger(__name__)

# --- Configuración (con override por env, siguiendo el patrón del bot) ---
TEAM_ID = os.getenv("CLICKUP_TEAM_ID", "9011755800")              # ronisa
SPACE_ID = os.getenv("CLICKUP_INFORMES_SPACE_ID", "90112750025")  # MESA ALTA

# Nombre canónico de cada Doc. OJO: en ClickUp los renombraron a mano con un
# sufijo de emoji (ej. "Informes semanales 📝"). Para reutilizarlos y NO crear
# duplicados, `_ensure_doc` matchea por prefijo (ignora ese sufijo).
DOC_SEMANALES = "Informes semanales"
DOC_MENSUALES = "Informes mensuales"

# Nombre corto (título de la página) -> nombre completo (dentro del reporte).
PERSONAS: dict[str, str] = {
    "Vero": "Verónica Mujica",
    "Rog": "Roggert Bernal",
    "Rochi": "Rocío Ojeda",
    "Cami": "Camila Torres",
    "Sofi": "Sofía Lantieri",
    "Ron": "Ronald Vargas",
    "Isa": "Isabella Lantieri",
    # Nicky todavía no se unió a ClickUp → aún no tenemos su nombre completo.
    # Placeholder para crear su espacio de agosto ya mismo. Cuando entre a
    # ClickUp, reemplazá "Nicky" por su nombre completo: los meses siguientes lo
    # usarán solos. Agosto queda como está (el generador es idempotente y nunca
    # repisa una página ya creada).
    "Nicky": "Nicky",
}

# Alias de títulos históricos: algunas páginas viejas quedaron con otro nick para
# la MISMA persona (ej. "Rogger" / "Roggert", hoy unificado como "Rog"). Se
# normalizan solo para RECONOCER la página existente y no duplicarla.
TITULO_ALIAS: dict[str, str] = {
    "rogger": "rog",
    "roggert": "rog",
}

MESES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

# Placeholder de cada viñeta (evita el "null." de las viñetas vacías).
_PH = "- …"

SECCIONES_SEMANAL = [
    "🎯 Objetivos de la semana",
    "✅ Tareas finalizadas",
    "🔄 Tareas en proceso",
    "⛔ Tareas estancadas (y por qué)",
    "🚀 Tareas por empezar",
    "🌟 ¿Qué ha ido bien esta semana?",
    "🔧 ¿Qué puedo mejorar esta semana?",
    "💭 Sensaciones de la semana",
]

SECCIONES_MENSUAL = [
    "🎯 Objetivos del mes",
    "✅ Tareas finalizadas",
    "🔄 Tareas en proceso",
    "⛔ Tareas estancadas y por qué",
    "🚀 Tareas por empezar",
    "🌟 ¿Qué ha ido bien este mes?",
    "🔧 ¿Qué puedo mejorar este mes?",
    "💭 Sensaciones del mes",
]


def doc_url(doc_id: str) -> str:
    """Link web al Doc completo (formato ClickUp 3.0)."""
    return f"https://app.clickup.com/{TEAM_ID}/docs/{doc_id}"


def page_url(doc_id: str, page_id: str) -> str:
    """Deep link a una página puntual dentro de un Doc (vista 'v/dc' de ClickUp).

    Ej.: https://app.clickup.com/9011755800/v/dc/8cj8yrr-4431/8cj8yrr-6611
    """
    return f"https://app.clickup.com/{TEAM_ID}/v/dc/{doc_id}/{page_id}"


# --------------------------------------------------------------------------- #
# Plantillas (Markdown → ClickUp Docs)                                        #
# --------------------------------------------------------------------------- #
def _cuerpo(secciones: list[str]) -> str:
    return "".join(f"## {s}\n\n{_PH}\n\n" for s in secciones)


def plantilla_semanal(nombre: str, lunes: dt.date, viernes: dt.date) -> str:
    fecha = lunes.strftime("%d/%m/%Y")
    rango = f"{lunes.day:02d}/{lunes.month:02d} – {viernes.day:02d}/{viernes.month:02d}"
    header = (
        f"# 🃏 Reporte semanal | Mesa Alta\n\n"
        f"**{nombre}**\n\n"
        f"`#weekly` · {fecha}  ·  Semana {rango}\n\n"
        f"---\n\n"
    )
    return (header + _cuerpo(SECCIONES_SEMANAL)).rstrip() + "\n"


def plantilla_mensual(nombre: str, mes: str, year: int) -> str:
    header = (
        f"# 🃏 Reporte mensual | Mesa Alta\n\n"
        f"**{nombre}**\n\n"
        f"`#monthly` · {mes} {year}\n\n"
        f"---\n\n"
    )
    return (header + _cuerpo(SECCIONES_MENSUAL)).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# Cálculo de semanas Lun–Vie                                                   #
# --------------------------------------------------------------------------- #
def _label_semana(lun: dt.date, vie: dt.date) -> str:
    if lun.month == vie.month:
        return f"Semana del {lun.day} al {vie.day}"
    return f"Semana del {lun.day}/{lun.month} al {vie.day}/{vie.month}"


def semanas_del_mes(year: int, month: int) -> list[tuple[str, dt.date, dt.date]]:
    """
    Devuelve [(label, lunes, viernes)] para cada semana cuyo LUNES cae en el mes.
    Regla: la semana pertenece al mes de su lunes. Si el viernes cae en otro mes,
    el label incluye el mes (ej. "Semana del 31/8 al 4/9").
    """
    d = dt.date(year, month, 1)
    while d.weekday() != 0:          # 0 = lunes → primer lunes del mes
        d += dt.timedelta(days=1)

    semanas: list[tuple[str, dt.date, dt.date]] = []
    while d.month == month:
        vie = d + dt.timedelta(days=4)
        semanas.append((_label_semana(d, vie), d, vie))
        d += dt.timedelta(days=7)
    return semanas


def semana_actual(hoy: dt.date) -> tuple[str, dt.date, dt.date]:
    """(label, lunes, viernes) de la semana que contiene a `hoy`."""
    lun = hoy - dt.timedelta(days=hoy.weekday())
    vie = lun + dt.timedelta(days=4)
    return _label_semana(lun, vie), lun, vie


# --------------------------------------------------------------------------- #
# Helpers de árbol (pageListing)                                              #
# --------------------------------------------------------------------------- #
def _norm_titulo(nombre: str) -> str:
    """casefold + alias, para reconocer nicks históricos (ej. Roggert→Rog)."""
    key = nombre.strip().casefold()
    return TITULO_ALIAS.get(key, key)


def _find_child(nodes: list[dict] | None, nombre: str) -> dict | None:
    key = _norm_titulo(nombre)
    for n in nodes or []:
        if _norm_titulo(n.get("name") or "") == key:
            return n
    return None


async def _ensure_doc(client, nombre: str) -> tuple[str, bool]:
    """Devuelve (doc_id, creado?). Reutiliza por nombre; si no existe, lo crea.

    Match por prefijo (casefold): el Doc vivo puede tener un sufijo agregado a
    mano (ej. "Informes semanales 📝"). Si matcheáramos exacto, no lo encontraría
    y crearía un Doc DUPLICADO en cada corrida. Por eso aceptamos que el nombre
    vivo EMPIECE con el nombre canónico.
    """
    objetivo = nombre.strip().casefold()
    docs = await client.search_docs(TEAM_ID)
    for d in docs:
        vivo = (d.get("name") or "").strip().casefold()
        if vivo == objetivo or vivo.startswith(objetivo):
            return d["id"], False
    d = await client.create_doc(TEAM_ID, nombre, SPACE_ID, parent_type=4)
    log.info("Doc creado: %s (%s)", nombre, d.get("id"))
    return d["id"], True


async def _ensure_page(
    client, doc_id: str, siblings: list[dict], nombre: str,
    parent_page_id: str | None, content: str, stats: dict,
) -> dict:
    """
    Busca `nombre` entre `siblings`; si no está, crea la página y la agrega al
    árbol en memoria (para no duplicar dentro de la misma corrida). Devuelve el nodo.
    """
    node = _find_child(siblings, nombre)
    if node is not None:
        return node
    page = await client.create_doc_page(
        TEAM_ID, doc_id, nombre, parent_page_id=parent_page_id, content=content,
    )
    node = {"id": page["id"], "name": nombre, "pages": []}
    siblings.append(node)
    stats["creadas"] += 1
    return node


# --------------------------------------------------------------------------- #
# Construcción                                                                 #
# --------------------------------------------------------------------------- #
async def construir_semanales(client, year: int, month: int) -> dict:
    stats = {"creadas": 0, "doc": DOC_SEMANALES}
    doc_id, stats["doc_creado"] = await _ensure_doc(client, DOC_SEMANALES)
    stats["doc_id"] = doc_id
    stats["url"] = doc_url(doc_id)
    arbol = await client.get_doc_page_listing(TEAM_ID, doc_id)

    mes_node = await _ensure_page(client, doc_id, arbol, MESES[month], None, "", stats)
    mes_node.setdefault("pages", [])

    for label, lun, vie in semanas_del_mes(year, month):
        sem_node = await _ensure_page(
            client, doc_id, mes_node["pages"], label, mes_node["id"], "", stats
        )
        sem_node.setdefault("pages", [])
        for corto, completo in PERSONAS.items():
            await _ensure_page(
                client, doc_id, sem_node["pages"], corto, sem_node["id"],
                plantilla_semanal(completo, lun, vie), stats,
            )
    return stats


async def construir_mensuales(client, year: int, month: int) -> dict:
    stats = {"creadas": 0, "doc": DOC_MENSUALES}
    doc_id, stats["doc_creado"] = await _ensure_doc(client, DOC_MENSUALES)
    stats["doc_id"] = doc_id
    stats["url"] = doc_url(doc_id)
    arbol = await client.get_doc_page_listing(TEAM_ID, doc_id)

    mes_node = await _ensure_page(client, doc_id, arbol, MESES[month], None, "", stats)
    mes_node.setdefault("pages", [])

    for corto, completo in PERSONAS.items():
        await _ensure_page(
            client, doc_id, mes_node["pages"], corto, mes_node["id"],
            plantilla_mensual(completo, MESES[month], year), stats,
        )
    return stats


async def generar_mes(client, year: int, month: int) -> dict:
    """Genera/asegura ambos Docs para el mes indicado. Idempotente.

    Fuerza el recorrido completo (crea lo que falte). Para la corrida de los
    lunes usar `asegurar_mes`, que ni siquiera recorre si el mes ya existe.
    """
    sem = await construir_semanales(client, year, month)
    men = await construir_mensuales(client, year, month)
    total = sem["creadas"] + men["creadas"]
    log.info(
        "Informes %s %s: %d páginas nuevas (semanales=%d, mensuales=%d).",
        MESES[month], year, total, sem["creadas"], men["creadas"],
    )
    return {"mes": MESES[month], "year": year, "semanales": sem, "mensuales": men,
            "total_creadas": total, "ya_existia": total == 0}


# --------------------------------------------------------------------------- #
# Corrida de los lunes: link a la semana en curso, sin regenerar               #
# --------------------------------------------------------------------------- #
async def asegurar_mes(client, hoy: dt.date) -> dict:
    """
    Devuelve los links para el aviso del lunes SIN regenerar si el mes ya existe.

    • semanal → DEEP LINK a la página de la semana en curso (según `hoy`).
    • mensual → deep link a la página del mes.
    Si el mes todavía no existe (primer lunes del mes), lo genera una sola vez
    con `generar_mes` (idempotente) y recién ahí arma los links.
    Fallback defensivo: si no encuentra la página puntual, cae a la del mes y,
    en último caso, al Doc completo.
    """
    year, month = hoy.year, hoy.month
    label, _lun, _vie = semana_actual(hoy)

    sem_id, _ = await _ensure_doc(client, DOC_SEMANALES)
    men_id, _ = await _ensure_doc(client, DOC_MENSUALES)

    sem_mes = _find_child(await client.get_doc_page_listing(TEAM_ID, sem_id), MESES[month])
    men_mes = _find_child(await client.get_doc_page_listing(TEAM_ID, men_id), MESES[month])

    if sem_mes and men_mes:
        ya_existia, creadas = True, 0
    else:
        creadas = (await generar_mes(client, year, month))["total_creadas"]
        ya_existia = False
        sem_mes = _find_child(await client.get_doc_page_listing(TEAM_ID, sem_id), MESES[month])
        men_mes = _find_child(await client.get_doc_page_listing(TEAM_ID, men_id), MESES[month])

    # Semanal → página de la semana en curso (fallback: página del mes → Doc).
    semana_node = _find_child(sem_mes.get("pages") if sem_mes else None, label)
    if semana_node:
        sem_url = page_url(sem_id, semana_node["id"])
    elif sem_mes:
        sem_url = page_url(sem_id, sem_mes["id"])
    else:
        sem_url = doc_url(sem_id)

    # Mensual → página del mes (fallback: Doc).
    men_url = page_url(men_id, men_mes["id"]) if men_mes else doc_url(men_id)

    log.info(
        "asegurar_mes %s %s: ya_existia=%s, semana='%s' → %s",
        MESES[month], year, ya_existia, label, sem_url,
    )
    return {
        "mes": MESES[month], "year": year, "semana": label,
        "ya_existia": ya_existia, "total_creadas": creadas,
        "semanales": {"url": sem_url, "doc_id": sem_id},
        "mensuales": {"url": men_url, "doc_id": men_id},
    }
