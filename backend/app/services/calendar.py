"""
Google Calendar integration for checking availability and booking meetings.

Uses service account credentials to access the calendar and auto-book slots.
This allows the voice agent to propose available times and confirm bookings
without human intervention.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CalendarManager:
    """Manages Google Calendar operations: availability checks and bookings."""

    def __init__(self):
        """Initialize the Google Calendar service."""
        settings = get_settings()
        self.settings = settings
        self.service = None
        self.calendar_id = None

        if settings.google_calendar_credentials_json:
            try:
                self._initialize_service()
            except Exception as e:
                logger.error(f"Failed to initialize Google Calendar service: {e}")
                self.service = None

    def _initialize_service(self):
        """Build the Google Calendar service from credentials."""
        credentials_json = self.settings.google_calendar_credentials_json
        if not credentials_json:
            raise ValueError("google_calendar_credentials_json not configured")

        try:
            credentials_dict = json.loads(credentials_json)
        except json.JSONDecodeError:
            raise ValueError("google_calendar_credentials_json is not valid JSON")

        # Create credentials from service account JSON
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )

        # Refresh credentials to ensure they're valid
        credentials.refresh(Request())

        self.service = build("calendar", "v3", credentials=credentials)
        self.calendar_id = credentials_dict.get("calendar_id", "primary")

    def get_available_slots(
        self,
        duration_minutes: int = 30,
        days_ahead: int = 7,
        business_hours_start: int = 9,
        business_hours_end: int = 17,
    ) -> list[dict]:
        """
        Find available slots in the calendar for the next N days.

        Args:
            duration_minutes: Length of the meeting (default 30 min)
            days_ahead: How many days forward to check (default 7)
            business_hours_start: Start hour (24-h format, default 9 AM)
            business_hours_end: End hour (24-h format, default 5 PM)

        Returns:
            List of available slots with start/end times, e.g.
            [
                {"start": "2026-07-15T10:00:00", "end": "2026-07-15T10:30:00"},
                {"start": "2026-07-15T14:00:00", "end": "2026-07-15T14:30:00"},
                ...
            ]
        """
        if not self.service:
            logger.warning("Calendar service not initialized")
            return []

        try:
            now = datetime.now(timezone.utc)
            end_date = now + timedelta(days=days_ahead)

            # Fetch all events in the date range
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=now.isoformat(),
                timeMax=end_date.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            busy_times = []
            for event in events_result.get("items", []):
                start = event.get("start", {}).get("dateTime")
                end = event.get("end", {}).get("dateTime")
                if start and end:
                    busy_times.append(
                        (datetime.fromisoformat(start), datetime.fromisoformat(end))
                    )

            # Generate potential slots and filter out conflicts
            available_slots = []
            current = now.replace(hour=business_hours_start, minute=0, second=0, microsecond=0)
            if current < now:
                current += timedelta(days=1)

            while current < end_date:
                slot_end = current + timedelta(minutes=duration_minutes)

                # Check if slot is within business hours
                if slot_end.hour <= business_hours_end:
                    # Check if slot conflicts with any busy time
                    is_available = True
                    for busy_start, busy_end in busy_times:
                        if not (slot_end <= busy_start or current >= busy_end):
                            is_available = False
                            break

                    if is_available:
                        available_slots.append(
                            {
                                "start": current.isoformat(),
                                "end": slot_end.isoformat(),
                                "display": current.strftime("%A, %B %d at %I:%M %p"),
                            }
                        )

                current += timedelta(minutes=30)

                # Move to next day if past business hours
                if current.hour >= business_hours_end:
                    current = current.replace(hour=business_hours_start, minute=0) + timedelta(days=1)

            logger.info(f"Found {len(available_slots)} available slots")
            return available_slots[:5]  # Return top 5 available slots

        except Exception as e:
            logger.error(f"Error fetching available slots: {e}")
            return []

    def book_meeting(
        self,
        title: str,
        start_time: str,
        end_time: str,
        attendee_email: str,
        description: str = "",
    ) -> Optional[str]:
        """
        Create a calendar event for the meeting.

        Args:
            title: Meeting title
            start_time: ISO format start time (e.g., "2026-07-15T10:00:00+00:00")
            end_time: ISO format end time
            attendee_email: Email of the person being interviewed
            description: Meeting description/notes

        Returns:
            Event ID if successful, None if failed
        """
        if not self.service:
            logger.warning("Calendar service not initialized, cannot book")
            return None

        try:
            event = {
                "summary": title,
                "description": description,
                "start": {"dateTime": start_time},
                "end": {"dateTime": end_time},
                "attendees": [
                    {"email": self.settings.owner_email},
                    {"email": attendee_email},
                ],
                "reminders": {
                    "useDefault": True,
                },
            }

            # Add Google Meet link if configured
            if self.settings.google_meet_url:
                event["conferenceData"] = {
                    "entryPoints": [
                        {
                            "entryPointType": "video",
                            "uri": self.settings.google_meet_url,
                        }
                    ]
                }

            result = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event,
                sendUpdates="all",
            ).execute()

            event_id = result.get("id")
            logger.info(f"Booked meeting: {event_id}")
            return event_id

        except Exception as e:
            logger.error(f"Error booking meeting: {e}")
            return None

    def is_available(self) -> bool:
        """Check if calendar service is properly initialized."""
        return self.service is not None


# Singleton instance
_calendar_manager: Optional[CalendarManager] = None


def get_calendar_manager() -> CalendarManager:
    """Get or create the singleton calendar manager."""
    global _calendar_manager
    if _calendar_manager is None:
        _calendar_manager = CalendarManager()
    return _calendar_manager
