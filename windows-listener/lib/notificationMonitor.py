"""
Notification Monitor Library
----------------------------
Library untuk monitoring Windows notifications dengan async support
menggunakan WinRT API (native, tanpa PowerShell).
"""

import asyncio
import logging
from typing import Optional, Callable, List, Dict
from dataclasses import dataclass
from datetime import datetime, timezone

try:
    import winsdk.windows.ui.notifications as notifications
    import winsdk.windows.ui.notifications.management as management
    WINRT_AVAILABLE = True
except ImportError:
    WINRT_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class NotificationData:
    id: str
    app_name: str
    app_id: str
    time: str
    texts: List[str]

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "app_name": self.app_name,
            "app_id": self.app_id,
            "time": self.time,
            "texts": self.texts,
        }


class NotificationMonitor:
    def __init__(self, check_interval: float = 1.0):
        if not WINRT_AVAILABLE:
            raise ImportError(
                "WinRT not available. Install:\n"
                "pip install winsdk"
            )

        self.check_interval = check_interval
        self.is_running = False

        self._listener: Optional[
            management.UserNotificationListener
        ] = None
        self._last_check: datetime = datetime.now(timezone.utc)

        self._seen_notifications = set()
        self._current_notifications: List[NotificationData] = []
        self._notification_callbacks: List[Callable] = []
        self._monitor_task: Optional[asyncio.Task] = None

    # ================= Public API =================

    def on_notification(self, callback: Callable[[NotificationData], None]):
        self._notification_callbacks.append(callback)
        return self

    async def start(self) -> bool:
        if self.is_running:
            return True

        try:
            self._listener = management.UserNotificationListener.current
            access = await self._listener.request_access_async()

            if access != management.UserNotificationListenerAccessStatus.ALLOWED:
                logger.error(f"Notification access denied: {access}")
                return False

            self._last_check = datetime.now(timezone.utc)
            self.is_running = True
            self._monitor_task = asyncio.create_task(self._loop())
            return True

        except Exception as e:
            logger.exception("Failed to start notification monitor")
            await self.stop()
            return False

    async def stop(self):
        self.is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        self._monitor_task = None
        self._listener = None

    def get_notifications(self) -> List[NotificationData]:
        return self._current_notifications.copy()

    def clear_notifications(self):
        self._seen_notifications.clear()
        self._current_notifications.clear()

    # ================= Internal =================

    async def _loop(self):
        try:
            while self.is_running:
                await self._check_notifications()
                await asyncio.sleep(self.check_interval)
        except asyncio.CancelledError:
            pass

    async def _check_notifications(self):
        if not self._listener:
            return

        notifs = await self._listener.get_notifications_async(
            notifications.NotificationKinds.TOAST
        )

        now = datetime.now(timezone.utc)

        for notif in notifs:
            creation_time = notif.creation_time

            if hasattr(creation_time, "astimezone"):
                creation_time = creation_time.astimezone(timezone.utc)

            if creation_time <= self._last_check:
                continue

            await self._process_notification(notif)

        self._last_check = now

    async def _process_notification(self, notif):
        notif_id = str(notif.id)
        if notif_id in self._seen_notifications:
            return

        self._seen_notifications.add(notif_id)

        app_info = notif.app_info
        app_name = app_info.display_info.display_name
        app_id = app_info.id
        time_str = notif.creation_time.strftime("%Y-%m-%d %H:%M:%S")

        texts: List[str] = []

        try:
            visual = notif.notification.visual
            for binding in visual.bindings:
                for text_el in binding.get_text_elements():
                    if text_el.text:
                        texts.append(text_el.text)
        except Exception:
            pass

        data = NotificationData(
            id=notif_id,
            app_name=app_name,
            app_id=app_id,
            time=time_str,
            texts=texts,
        )

        self._current_notifications.append(data)
        await self._trigger_callbacks(data)

    async def _trigger_callbacks(self, notif: NotificationData):
        for cb in self._notification_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(notif)
                else:
                    cb(notif)
            except Exception:
                logger.exception("Notification callback error")
