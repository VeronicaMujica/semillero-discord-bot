import asyncio
import json
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
DEFAULT_TZ = "America/Argentina/Buenos_Aires"


class GoogleCalendarError(Exception):
    pass


class GoogleCalendarClient:
    def __init__(self):
        self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID")
        if not self.calendar_id:
            raise ValueError("Falta GOOGLE_CALENDAR_ID en el .env")

        creds_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

        if creds_file and os.path.isfile(creds_file):
            self._creds = service_account.Credentials.from_service_account_file(
                creds_file, scopes=SCOPES
            )
        elif creds_json:
            info = json.loads(creds_json)
            self._creds = service_account.Credentials.from_service_account_info(
                info, scopes=SCOPES
            )
        else:
            raise ValueError(
                "Configura GOOGLE_SERVICE_ACCOUNT_FILE (ruta al JSON) o "
                "GOOGLE_SERVICE_ACCOUNT_JSON (JSON crudo) en el .env"
            )

        self._service = build("calendar", "v3", credentials=self._creds, cache_discovery=False)

    def _create_event_sync(
        self,
        title: str,
        start_dt: datetime,
        end_dt: datetime,
        description: str | None,
        tz: str,
    ) -> dict:
        body = {
            "summary": title,
            "description": description or "",
            "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": tz},
        }
        try:
            return (
                self._service.events()
                .insert(calendarId=self.calendar_id, body=body)
                .execute()
            )
        except HttpError as e:
            raise GoogleCalendarError(f"Google Calendar API: {e}") from e

    async def create_event(
        self,
        *,
        title: str,
        start_dt: datetime,
        end_dt: datetime,
        description: str | None = None,
        tz: str = DEFAULT_TZ,
    ) -> dict:
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=ZoneInfo(tz))
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=ZoneInfo(tz))

        return await asyncio.to_thread(
            self._create_event_sync, title, start_dt, end_dt, description, tz
        )
