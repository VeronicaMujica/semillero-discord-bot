"""
Cliente de OpenAI para el Dealer Bot.

Se usa para tareas de lenguaje que no se pueden resolver con reglas: hoy, el
resumen semanal de los reportes de Mesa Alta (`resumen_reportes_service.py`).

Por qué OpenAI: el estudio ya tiene cuenta con crédito andando (la misma que
usan los chatbots de Kommo en n8n), así que no hay que abrir ni cargar una
cuenta nueva.

Decisiones:
  • SDK oficial `openai` (AsyncOpenAI) — el bot es 100% asyncio, así que el
    cliente async evita bloquear el event loop de discord.py.
  • Chat Completions y no la Responses API: es la superficie más estable y la
    que soporta cualquier modelo de la cuenta.
  • Modelo por defecto `gpt-4.1-mini` (la variante barata), override por
    `OPENAI_MODEL`. Si el resumen sale flojo, se sube a `gpt-4.1` cambiando
    esa sola variable — no hay que tocar código.
  • Si falta `OPENAI_API_KEY` el cliente NO explota al importarse: queda
    `disponible = False` y quien lo use avisa por Discord. Así un deploy sin la
    key no tira abajo el bot entero.
"""
from __future__ import annotations

import logging
import os

import openai

log = logging.getLogger(__name__)

MODELO_DEFAULT = "gpt-4.1-mini"


class IAError(Exception):
    """Cualquier fallo hablando con la API, ya traducido a castellano."""


class OpenAIClient:
    def __init__(self, api_key: str | None = None, modelo: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.modelo = modelo or os.getenv("OPENAI_MODEL") or MODELO_DEFAULT
        self._client: openai.AsyncOpenAI | None = None

    @property
    def disponible(self) -> bool:
        return bool(self.api_key)

    def _cliente(self) -> openai.AsyncOpenAI:
        if not self.disponible:
            raise IAError(
                "Falta `OPENAI_API_KEY` en el .env (y en los secrets de GitHub)."
            )
        if self._client is None:
            # Timeout generoso: esto corre en un cron, no en una UI.
            self._client = openai.AsyncOpenAI(api_key=self.api_key, timeout=180.0)
        return self._client

    async def responder(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 2000,
    ) -> str:
        """Un turno simple: system + prompt → texto. Levanta `IAError`."""
        client = self._cliente()
        try:
            resp = await client.chat.completions.create(
                model=self.modelo,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
        except openai.AuthenticationError as e:
            raise IAError(f"API key de OpenAI inválida o vencida: {e}") from e
        except openai.PermissionDeniedError as e:
            raise IAError(f"La API key no tiene permisos para esto: {e}") from e
        except openai.NotFoundError as e:
            raise IAError(
                f"El modelo `{self.modelo}` no existe o la cuenta no lo tiene "
                f"habilitado. Cambiá `OPENAI_MODEL` en el .env. Detalle: {e}"
            ) from e
        except openai.RateLimitError as e:
            # Ojo: OpenAI usa 429 tanto para rate limit como para saldo agotado.
            raise IAError(
                f"OpenAI devolvió 429 (rate limit o crédito agotado): {e}"
            ) from e
        except openai.APIStatusError as e:
            raise IAError(f"OpenAI devolvió {e.status_code}: {e.message}") from e
        except openai.APIConnectionError as e:
            raise IAError(f"No se pudo conectar con OpenAI: {e}") from e

        choice = resp.choices[0]
        texto = (choice.message.content or "").strip()
        if not texto:
            raise IAError("OpenAI devolvió una respuesta vacía.")
        if choice.finish_reason == "length":
            # No es fatal, pero el resumen sale cortado: que quede en el log.
            log.warning(
                "OpenAI cortó la respuesta por max_tokens (%s).", max_tokens
            )

        uso = resp.usage
        log.info(
            "OpenAI %s: in=%s out=%s tokens (finish=%s)",
            self.modelo,
            getattr(uso, "prompt_tokens", "?"),
            getattr(uso, "completion_tokens", "?"),
            choice.finish_reason,
        )
        return texto
