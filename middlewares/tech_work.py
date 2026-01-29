from aiogram import types, Dispatcher
from aiogram.dispatcher.handler import CancelHandler
from aiogram.dispatcher.middlewares import BaseMiddleware
from database.db import get_tech_mode
from config import ADMIN_ID
from locales.strings import get_text # Використаємо дефолтну uk

class TechWorkMiddleware(BaseMiddleware):
    async def on_process_message(self, message: types.Message, data: dict):
        if message.from_user.id == ADMIN_ID:
            return # Адміна не чіпаємо

        if get_tech_mode():
            # Можна спробувати дізнатись мову юзера, але для тех робіт достатньо дефолтної
            await message.answer(get_text('uk', 'tech_work'))
            raise CancelHandler()
    
    async def on_process_callback_query(self, call: types.CallbackQuery, data: dict):
        if call.from_user.id == ADMIN_ID: return
        if get_tech_mode():
            await call.answer(get_text('uk', 'tech_work'), show_alert=True)
            raise CancelHandler()