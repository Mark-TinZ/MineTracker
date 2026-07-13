import asyncio
from typing import Any, Callable, Dict, Awaitable, List

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject


class AlbumMiddleware(BaseMiddleware):
    """
    Middleware для сбора альбомов (MediaGroup).
    Перехватывает сообщения с media_group_id и собирает их в список `album` (List[Message]).
    Если сообщение одиночное - `album` будет содержать только его (или None, смотря как удобнее).
    """
    
    def __init__(self, latency: float = 0.6):
        self.latency = latency
        self.album_data: Dict[str, List[Message]] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        
        # Если это не сообщение с media_group_id, сразу пропускаем
        if not event.media_group_id:
            # Для унификации можем передавать альбом из одного элемента, либо просто None
            data["album"] = None
            return await handler(event, data)
            
        album_id = event.media_group_id

        if album_id not in self.album_data:
            self.album_data[album_id] = [event]
            
            # Ждем остальные части альбома
            await asyncio.sleep(self.latency)
            
            # После задержки достаем собранный альбом
            messages = self.album_data.pop(album_id)
            
            # Сортируем по message_id на всякий случай
            messages.sort(key=lambda x: x.message_id)
            
            # Добавляем в data и вызываем handler только 1 раз для первого сообщения альбома
            data["album"] = messages
            return await handler(event, data)
        else:
            # Если альбом уже собирается, просто добавляем в него это сообщение
            self.album_data[album_id].append(event)
            # Не вызываем handler для последующих сообщений альбома,
            # они обработаются вместе с первым!
            return None
