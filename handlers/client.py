from aiogram import Dispatcher, types
from aiogram.utils.callback_data import CallbackData
from database.db import get_db
import config
from locales.strings import get_text
from datetime import datetime
import pytz

UA_TZ = pytz.timezone('Europe/Kyiv')
cb_lang = CallbackData("lang", "code")
cb_menu = CallbackData("menu", "action", "val")
cb_sched = CallbackData("sched", "comp", "queue")

def get_user_lang(user_id):
    with get_db() as conn:
        res = conn.execute("SELECT language FROM user_prefs WHERE user_id = ?", (user_id,)).fetchone()
        return res['language'] if res else 'uk'

def lang_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🇺🇦 Українська", callback_data=cb_lang.new(code="uk")),
           types.InlineKeyboardButton("🇷🇺 Русский", callback_data=cb_lang.new(code="ru")))
    return kb

def main_menu_kb(lang):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(get_text(lang, 'btn_add_queue'), get_text(lang, 'btn_my_queues'))
    kb.row(get_text(lang, 'btn_schedules'))
    kb.row(get_text(lang, 'btn_settings'), get_text(lang, 'btn_support'))
    return kb

# ... (остальные функции без изменений) ...

async def support_cmd(message: types.Message):
    lang = get_user_lang(message.from_user.id)
    # В locales добавлен ключ 'support_text'
    await message.answer(get_text(lang, 'support_text', user=config.SUPPORT_USER, url=config.DONATE_URL))

async def settings_cmd(message: types.Message):
    lang = get_user_lang(message.from_user.id)
    # Для примера - просто отправляем текст из локалей. Добавьте реальные опции по необходимости.
    await message.answer(get_text(lang, 'settings_text'))

# --- Реєстрація ---
def register_handlers(dp: Dispatcher):
    dp.register_message_handler(start_cmd, commands=['start'])
    dp.register_callback_query_handler(set_language, cb_lang.filter())
    dp.register_callback_query_handler(show_main_menu, text="menu_start")
    
    # Покращені фільтри для текстових кнопок
    dp.register_message_handler(view_schedules_start, lambda m: bool(m.text) and any(x in m.text.lower() for x in ["графік", "график"]))
    dp.register_message_handler(add_queue_btn, lambda m: bool(m.text) and any(x in m.text.lower() for x in ["додати", "добавить"]))
    dp.register_message_handler(my_queues, lambda m: bool(m.text) and any(x in m.text.lower() for x in ["мої чер", "мои оче"]))

    # Надёжная регистрация для Support и Settings: сравниваем с локализованными подписями обеих языков
    support_labels = (get_text('uk', 'btn_support'), get_text('ru', 'btn_support'))
    settings_labels = (get_text('uk', 'btn_settings'), get_text('ru', 'btn_settings'))
    dp.register_message_handler(support_cmd, lambda m: bool(m.text) and m.text in support_labels)
    dp.register_message_handler(settings_cmd, lambda m: bool(m.text) and m.text in settings_labels)
    
    # Callback-и (Компанії) - generic handler for vcomp_... and scomp_...
    dp.register_callback_query_handler(handle_comp_selection, lambda c: c.data and c.data.startswith(('vcomp_', 'scomp_')))
    dp.register_callback_query_handler(show_sched, cb_sched.filter())
    dp.register_callback_query_handler(save_sub, cb_menu.filter(action="save"))
    
    # Назад
    dp.register_callback_query_handler(back_to_comp, text=["back_view", "back_sub"])
    
    # Видалення
    dp.register_callback_query_handler(delete_sub, lambda c: c.data and c.data.startswith('del_'))
