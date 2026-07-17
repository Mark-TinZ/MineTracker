import asyncio
import logging
import time
from typing import Dict
from aiogram import Bot
from sqlalchemy import text
from redis.asyncio import Redis
from mc_ping_bot.services.i18n import i18n_service, current_locale

logger = logging.getLogger(__name__)

class MaintenanceService:
    def __init__(self, bot: Bot, redis: Redis, sessionmaker, admin_id: int):
        self.bot = bot
        self.redis = redis
        self.sessionmaker = sessionmaker
        self.admin_id = admin_id
        
        # State flags
        self.is_manual_maintenance = False
        self.is_auto_maintenance = False
        
        # Smart Pause Event
        # Set when DB is OK, cleared when in maintenance
        self._db_recovered_event = asyncio.Event()
        self._db_recovered_event.set() 
        
        # Anti-Flap counters
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.MAX_FLAP_THRESHOLD = 3
        
        # Rate Limit (Anti-Spam)
        self.notified_users: Dict[int, float] = {}
        self.NOTIFY_COOLDOWN = 10.0 # seconds

    def is_maintenance(self) -> bool:
        return self.is_manual_maintenance or self.is_auto_maintenance

    async def wait_if_maintenance(self):
        """Workers will call this. Blocks if we are in maintenance mode."""
        if self.is_maintenance():
            # Wait until the event is set (i.e. DB recovers and manual maintenance is off)
            await self._db_recovered_event.wait()
            
    def _update_event_state(self):
        if self.is_maintenance():
            self._db_recovered_event.clear()
        else:
            self._db_recovered_event.set()

    def set_manual_maintenance(self, state: bool):
        self.is_manual_maintenance = state
        self._update_event_state()

    def can_notify_user(self, user_id: int) -> bool:
        """Rate limit checks: max 1 notification per 10 seconds per user."""
        current_time = time.time()
        last_notified = self.notified_users.get(user_id, 0)
        
        if current_time - last_notified >= self.NOTIFY_COOLDOWN:
            self.notified_users[user_id] = current_time
            return True
        return False
        
    async def trigger_auto_maintenance(self, error: Exception = None):
        """Triggered from Middlewares or Background tasks upon DB error."""
        if self.is_auto_maintenance:
            return # Already in auto maintenance
            
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        
        if self.consecutive_failures >= self.MAX_FLAP_THRESHOLD:
            self.is_auto_maintenance = True
            self._update_event_state()
            logger.error(f"Database failed {self.consecutive_failures} times. Entering auto maintenance.")
            
            try:
                error_msg = f"<code>{type(error).__name__}: {error}</code>" if error else "Unknown"
                
                token = current_locale.set("ru") # Admin messages in default language
                try:
                    text_alert = (
                        f"{i18n_service.get('msg-admin-alert-db-error')}\n\n"
                        f"{i18n_service.get('msg-admin-alert-db-error-count', count=self.consecutive_failures)}:\n"
                        f"{error_msg}"
                    )
                finally:
                    current_locale.reset(token)

                await self.bot.send_message(self.admin_id, text_alert)
            except Exception as e:
                logger.error(f"Failed to send maintenance alert to admin: {e}")

    async def _check_db_health(self) -> bool:
        try:
            # Check Redis
            await self.redis.ping()
            
            # Check PostgreSQL
            async with self.sessionmaker() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def health_check_worker(self):
        """Background worker that periodically checks DB health and auto-recovers."""
        logger.info("Maintenance health check worker started.")
        while True:
            # We only actively check if we are in auto maintenance mode
            if self.is_auto_maintenance:
                is_healthy = await self._check_db_health()
                
                if is_healthy:
                    self.consecutive_successes += 1
                    logger.info(f"Database is responding... (Success count: {self.consecutive_successes})")
                    
                    if self.consecutive_successes >= self.MAX_FLAP_THRESHOLD:
                        self.is_auto_maintenance = False
                        self.consecutive_failures = 0
                        self.consecutive_successes = 0
                        self._update_event_state()
                        
                        logger.info("Database recovered! Exiting auto maintenance.")
                        try:
                            token = current_locale.set("ru")
                            try:
                                text_ok = i18n_service.get("msg-admin-alert-db-ok")
                            finally:
                                current_locale.reset(token)
                                
                            await self.bot.send_message(self.admin_id, text_ok)
                        except Exception:
                            pass
                else:
                    self.consecutive_successes = 0
            
            # Run checks every 5 seconds
            await asyncio.sleep(5)
