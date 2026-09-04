"""
Resumen automático de los reportes semanales de Mesa Alta.

Qué hace: lee en ClickUp las páginas de la semana (Doc "Informes semanales" →
Mes → Semana → una página por persona), descarta las que siguen con la
plantilla vacía, y le pasa al modelo SOLO lo que la gente escribió para que
devuelva un resumen corto de lo más relevante.

Reparto de responsabilidades (a propósito):
  • Los datos duros —quién cargó y quién no— se calculan acá, con código.
    Nunca se le pregunta eso al modelo: es un dato, no una opinión.
  • Lo cualitativo —qué pasó, qué trabó, qué destacar— lo resume el modelo (OpenAI).

Reutiliza la estructura y las convenciones de `informes_service.py` (una semana
pertenece al mes de su LUNES, alias de títulos históricos, etc.). Es de SOLO
LECTURA: si falta el Doc o la página, devuelve vacío — nunca crea nada. Para
crear/reparar está `asegurar_mes`.
"""
from __future__ import annotations

import datetime as dt
import logging
import re

from informes_service import (
    DOC_SEMANALES,
    MESES,
    PERSONAS,
    TEAM_ID,
    _find_child,          # matchea nicks históricos (Roggert → Rog)
    _norm_titulo,
    page_url,
    semana_actual,
)

log = logging.getLogger(__name__)

# Un reporte más corto que esto es ruido (un "ok", una fecha suelta).
MIN_CARACTERES_UTILES = 25

# Texto que en la plantilla significa "no escribí nada acá".
_VACIOS = {"", "…", "...", "-", "--", "n/a", "na", "nada", "ninguna", "ninguno"}

_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s*")
_TAREA = re.compile(r"^\s*[-*+]\s*\[[ xX]?\]\s*")


def _es_vacia(linea: str) -> bool:
    """¿Esta línea es plantilla/decoración y no contenido real?"""
    t = linea.strip()
    if not t or t.startswith("---") or t.startswith("**") or t.startswith("`"):
        return True
    if t.startswith("#"):
        return True  # encabezados: se tratan aparte
    cuerpo = _BULLET.sub("", _TAREA.sub("", t)).strip().strip("*_ ").casefold()
    return cuerpo in _VACIOS


def limpiar_reporte(md: str) -> str:
    """
    Deja solo las secciones (`## …`) que tienen contenido escrito por la persona.

    Saca el header de la plantilla, las viñetas placeholder (`- …`) y las
    secciones que quedaron enteras sin completar. Devuelve "" si no hay nada.
    """
    secciones: list[tuple[str, list[str]]] = []
    actual: tuple[str, list[str]] | None = None

    for linea in (md or "").splitlines():
        if linea.strip().startswith("#"):
            titulo = linea.strip().lstrip("#").strip()
            # El H1 del header de la plantilla no es una sección de contenido.
            if linea.strip().startswith("# "):
                actual = None
                continue
            actual = (titulo, [])
            secciones.append(actual)
        elif actual is not None and not _es_vacia(linea):
            actual[1].append(linea.rstrip())

    partes = [
        f"## {titulo}\n" + "\n".join(cuerpo)
        for titulo, cuerpo in secciones
        if cuerpo
    ]
    texto = "\n\n".join(partes).strip()
    return texto if len(re.sub(r"\W", "", texto)) >= MIN_CARACTERES_UTILES else ""


def _buscar_nodo(nodos: list[dict] | None, nombre: str) -> dict | None:
    """Busca una página hija por nombre: exacto primero, después por prefijo.

    El prefijo importa porque en ClickUp renombran páginas a mano agregando
    emojis al final (ya pasó con los Docs: "Informes semanales 📝"). Esto es
    solo lectura, así que ser tolerante no puede duplicar nada — al revés, evita
    que el resumen salga vacío por un emoji.
    """
    exacto = _find_child(nodos, nombre)
    if exacto is not None:
        return exacto
    key = _norm_titulo(nombre)
    for n in nodos or []:
        if _norm_titulo(n.get("name") or "").startswith(key):
            return n
    return None


def _lunes_de(hoy: dt.date, semanas_atras: int = 0) -> dt.date:
    _, lun, _ = semana_actual(hoy)
    return lun - dt.timedelta(days=7 * semanas_atras)


async def _buscar_doc_id(client, nombre: str) -> str | None:
    """Como `_ensure_doc` pero de solo lectura: si no está, devuelve None."""
    objetivo = nombre.strip().casefold()
    for d in await client.search_docs(TEAM_ID):
        vivo = (d.get("name") or "").strip().casefold()
        if vivo == objetivo or vivo.startswith(objetivo):
            return d["id"]
    return None


async def recolectar_semana(client, hoy: dt.date, semanas_atras: int = 0) -> dict:
    """
    Junta los reportes de una semana.

    Devuelve:
      semana / lunes / viernes / url
      reportes   → [{corto, nombre, texto, url}]  (solo los que tienen contenido)
      sin_cargar → [corto]  (la página existe pero sigue con la plantilla vacía)
      faltantes  → [corto]  (ni siquiera existe la página)
    """
    lun = _lunes_de(hoy, semanas_atras)
    vie = lun + dt.timedelta(days=4)
    label, _, _ = semana_actual(lun)

    base = {
        "semana": label, "lunes": lun, "viernes": vie,
        "url": None, "reportes": [], "sin_cargar": [], "faltantes": list(PERSONAS),
    }

    doc_id = await _buscar_doc_id(client, DOC_SEMANALES)
    if not doc_id:
        log.warning("resumen_reportes: no existe el Doc '%s'.", DOC_SEMANALES)
        return base

    arbol = await client.get_doc_page_listing(TEAM_ID, doc_id)
    # La semana vive bajo el mes de su LUNES (convención de informes_service).
    mes_node = _buscar_nodo(arbol, MESES[lun.month])
    semana_node = _buscar_nodo(mes_node.get("pages") if mes_node else None, label)
    if not semana_node:
        log.warning("resumen_reportes: no existe la página '%s'.", label)
        base["url"] = page_url(doc_id, mes_node["id"]) if mes_node else None
        return base

    base["url"] = page_url(doc_id, semana_node["id"])
    base["faltantes"] = []

    for corto, nombre in PERSONAS.items():
        nodo = _buscar_nodo(semana_node.get("pages"), corto)
        if not nodo:
            base["faltantes"].append(corto)
            continue
        try:
            pagina = await client.get_doc_page(TEAM_ID, doc_id, nodo["id"])
        except Exception:
            log.exception("resumen_reportes: no se pudo leer la página de %s", corto)
            base["faltantes"].append(corto)
            continue

        texto = limpiar_reporte(pagina.get("content") or "")
        if texto:
            base["reportes"].append({
                "corto": corto, "nombre": nombre, "texto": texto,
                "url": page_url(doc_id, nodo["id"]),
            })
        else:
            base["sin_cargar"].append(corto)

    log.info(
        "resumen_reportes %s: %d cargados, %d vacíos, %d sin página.",
        label, len(base["reportes"]), len(base["sin_cargar"]), len(base["faltantes"]),
    )
    return base


# --------------------------------------------------------------------------- #
# Prompt                                                                       #
# --------------------------------------------------------------------------- #
SYSTEM = """Sos el Dealer: el bot que le lee las cartas al equipo de Mesa Alta, \
un estudio creativo argentino. Recibís los reportes semanales que cada persona \
escribió sobre su propia semana y devolvés un resumen para el canal de Discord \
del equipo.

Cómo escribís:
- Castellano rioplatense, directo y cálido. Tono de crupier que reparte la mano: \
cercano, con humor seco, nunca cursi ni corporativo.
- Vas al grano. Nada de "en resumen", "cabe destacar", "es importante mencionar".

Reglas duras:
- NO inventes. Si algo no está en los reportes, no existe. No completes huecos.
- No cuentes quién entregó y quién no: eso lo agrega el bot aparte.
- No repitas literal lo que escribió cada uno: destilá lo relevante.
- Nombrá a la gente por su nombre corto, tal como viene en el reporte.
- Priorizá: bloqueos y cosas que necesitan decisión primero, logros después.
- Las "sensaciones" tratalas con cuidado y en general: si alguien la pasó mal, \
mencionalo con respeto y sin exponer detalles íntimos.

Formato de salida (markdown de Discord, sin encabezados `#`, máximo 1500 caracteres):

**🎯 La mano de esta semana**
2 o 3 líneas con el panorama general.

**👥 Uno por uno**
• **Nombre** — lo más relevante de su semana, en una línea.

**⛔ Trabas sobre la mesa**
• Lo que está frenado y por qué. Si no hay nada trabado, escribí "• Nada trabado."

**🌟 Carta ganadora**
• Lo mejor que pasó esta semana, en una línea.

Devolvés solo eso. Sin preámbulo, sin cierre, sin explicar lo que hiciste."""


def construir_prompt(datos: dict) -> str:
    lun, vie = datos["lunes"], datos["viernes"]
    cabecera = (
        f"Reportes de la {datos['semana']} "
        f"({lun.strftime('%d/%m/%Y')} al {vie.strftime('%d/%m/%Y')}).\n"
        f"Entregaron {len(datos['reportes'])} personas.\n"
    )
    cuerpos = [
        f"\n\n===== {r['corto']} ({r['nombre']}) =====\n{r['texto']}\n"
        for r in datos["reportes"]
    ]
    return cabecera + "".join(cuerpos)
