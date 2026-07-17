import asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from typing import Any, Dict
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.orm import selectinload
from mc_ping_bot.services.minecraft import MinecraftService
from mc_ping_bot.db.models import Chat, MonitoredServer, User
from mc_ping_bot.services.i18n import i18n_service, current_locale

def _render_tracker_message(tracker: MonitoredServer, data: Dict[str, Any], locale: str = "ru") -> str:
    """Генерация текста для закрепленного сообщения в группе."""
    title = tracker.custom_name if tracker.custom_name else f"Сервер: {tracker.server.ip_domain}"
    
    token = current_locale.set(locale)
    try:
        if not data.get("online"):
            return (
                f"📊 <b>{title}</b>\n\n"
                f"🔴 {i18n_service.get('status-offline')}\n"
                f"<i>{i18n_service.get('msg-last-update-recently')}</i>"
            )
            
        text = f"📊 <b>{title}</b>\n\n"
        text += f"🟢 {i18n_service.get('status-online')}\n"
        text += f"📡 {i18n_service.get('msg-ping')}: {data['latency']} ms\n"
        
        if tracker.show_players:
            text += f"👥 {i18n_service.get('msg-players')}: <b>{data['players_online']}/{data['players_max']}</b>\n"
            if data.get("player_names"):
                text += f"{i18n_service.get('msg-displayed')}: " + ", ".join(data["player_names"]) + "\n"
                
        if tracker.show_motd and data.get("motd"):
            text += f"\n💬 MOTD:\n<i>{data['motd']}</i>\n"
            
        if tracker.show_tps:
            # В классическом пинге TPS нет, задел на будущее (RCON/Плагины)
            text += f"\n⚙️ TPS: {i18n_service.get('msg-calculating')}..."
            
        text += f"\n\n<i>🔄 {i18n_service.get('msg-updated-automatically')}</i>"
        return text
    finally:
        current_locale.reset(token)

from mc_ping_bot.services.maintenance import MaintenanceService

async def start_monitoring_loop(bot: Bot, sessionmaker: async_sessionmaker, mc_service: MinecraftService, maintenance_service: MaintenanceService):
    """
    Основной цикл мониторинга (Background Heartbeat).
    Обновляет закрепленные сообщения в чатах каждые N секунд.
    """
    while True:
        await maintenance_service.wait_if_maintenance()
        
        try:
            async with sessionmaker() as session:
                # Получаем все активные трекеры вместе с привязанными Чатами и Серверами
                trackers_query = select(MonitoredServer).options(
                    selectinload(MonitoredServer.chat),
                    selectinload(MonitoredServer.server)
                ).where(MonitoredServer.is_paused == False)
                
                result = await session.execute(trackers_query)
                active_trackers = result.scalars().all()
                
                for tracker in active_trackers:
                    if not tracker.message_id:
                        continue
                        
                    # Получаем информацию о сервере (с Redis кешированием)
                    # Если у нас 100 трекеров одного IP, реально будет 1 пинг, а 99 возьмут из Redis
                    server_ip = tracker.server.ip_domain
                    data = await mc_service.get_server_info(server_ip, tracker.server.port)
                    
                    # Динамический рендер сообщения на основе флагов из БД
                    text = _render_tracker_message(tracker, data)
                    
                    try:
                        await bot.edit_message_text(
                            chat_id=tracker.chat.tg_chat_id,
                            message_id=tracker.message_id,
                            text=text,
                            parse_mode="HTML"
                        )
                    except TelegramBadRequest as e:
                        err_msg = e.message.lower()
                        if "message is not modified" in err_msg:
                            # Нормальное поведение (статус сервера не изменился)
                            pass
                        elif "message to edit not found" in err_msg or "chat not found" in err_msg or "bot was kicked" in err_msg:
                            # Сообщение удалено или бота кикнули -> ставим на паузу
                            tracker.is_paused = True
                            session.add(tracker)
                    except Exception as e:
                        # Сетевые сбои Telegram API игнорируем, попробуем в следующей итерации
                        pass
                
                # Коммитим все изменения (например, паузы)
                await session.commit()
                
        except Exception as e:
            # Защита лупа от полного краша при сбое БД
            print(f"[Monitoring Loop Error] {e}")
            import redis.exceptions
            import sqlalchemy.exc
            import asyncpg.exceptions
            if isinstance(e, (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, sqlalchemy.exc.OperationalError, asyncpg.exceptions.CannotConnectNowError, asyncpg.exceptions.ConnectionDoesNotExistError)):
                await maintenance_service.trigger_auto_maintenance(e)
            
        await asyncio.sleep(10)

async def subscription_downgrade_worker(sessionmaker: async_sessionmaker, maintenance_service: MaintenanceService):
    """
    Фоновый воркер, проверяющий истечение премиум-подписок у пользователей.
    Вызывается раз в час (3600 секунд).
    """
    while True:
        await maintenance_service.wait_if_maintenance()
        
        try:
            async with sessionmaker() as session:
                # Находим пользователей, у которых премиум-статус истек
                expired_users_query = select(User).where(
                    User.is_premium == True,
                    User.premium_until != None,
                    User.premium_until < func.now()
                )
                
                result = await session.execute(expired_users_query)
                expired_users = result.scalars().all()
                
                for user in expired_users:
                    # 1. Понижаем статус пользователя
                    user.is_premium = False
                    user.premium_until = None
                    
                    # 2. Получаем все трекеры (MonitoredServer) этого пользователя
                    # (Привязка через чаты. Для простоты считаем, что Chat.tg_chat_id = User.tg_id)
                    trackers_query = select(MonitoredServer).join(
                        Chat, MonitoredServer.chat_id == Chat.id
                    ).where(
                        Chat.tg_chat_id == user.tg_id
                    ).order_by(
                        # Сортировка по ID эквивалентна created_at, так как AUTOINCREMENT
                        MonitoredServer.id.asc()
                    )
                    
                    trackers_result = await session.execute(trackers_query)
                    trackers = trackers_result.scalars().all()
                    
                    if trackers:
                        # Самая старая запись остается активной, но interval_seconds понижается до 300
                        oldest_tracker = trackers[0]
                        oldest_tracker.interval_seconds = 300
                        oldest_tracker.is_paused = False
                        
                        # Остальным серверам юзера принудительно ставим паузу
                        for tracker in trackers[1:]:
                            tracker.is_paused = True
                            
                # Коммитим все изменения единой транзакцией
                await session.commit()
                
        except Exception as e:
            # В production здесь должно быть логгирование (structlog)
            print(f"[Worker Error] Subscription Downgrade: {e}")
            import redis.exceptions
            import sqlalchemy.exc
            import asyncpg.exceptions
            if isinstance(e, (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, sqlalchemy.exc.OperationalError, asyncpg.exceptions.CannotConnectNowError, asyncpg.exceptions.ConnectionDoesNotExistError)):
                await maintenance_service.trigger_auto_maintenance(e)
            
        # Спим 1 час
        await asyncio.sleep(3600)
