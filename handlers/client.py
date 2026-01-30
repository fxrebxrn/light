from aiogram import Dispatcher, types
from aiogram.utils.callback_data import CallbackData
from database.db import get_db
import config
from locales.strings import get_text
from datetime import datetime
import pytz

# Часовой пояс Киева
UA_TZ = pytz.timezone('Europe/Kyiv')

# CallbackData
cb_lang = CallbackData("lang", "code")
cb_menu = CallbackData("menu", "action", "val")
cb_sched = CallbackData("sched", "comp", "queue")

def get_user_lang(user_id):
    with get_db() as conn:
        res = conn.execute("SELECT language FROM user_prefs WHERE user_id = ?", (user_id,)).fetchone()
        return res['language'] if res else 'uk'

# --- Клавіатури ---
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

def queues_kb(action_type, company, lang):
    queues = ["1.1", "1.2", "2.1", "2.2", "3.1", "3.2", "4.1", "4.2", "5.1", "5.2", "6.1", "6.2"]
    kb = types.InlineKeyboardMarkup(row_width=3)
    btns = []
    for q in queues:
        # При сохранении используем '_' как разделитель (как в original)
        if action_type == 'view':
            btns.append(types.InlineKeyboardButton(q, callback_data=cb_sched.new(comp=company, queue=q)))
        else:
            btns.append(types.InlineKeyboardButton(q, callback_data=cb_menu.new(action='save', val=f"{company}_{q}")))
    kb.add(*btns)
    back_call = "back_view" if action_type == 'view' else "back_sub"
    kb.add(types.InlineKeyboardButton(get_text(lang, 'back'), callback_data=back_call))
    return kb

# --- Обработчики ---
async def check_time_cmd(message: types.Message):
    now_ua = datetime.now(UA_TZ)
    await message.answer(f"🕒 <b>Київський час:</b> {now_ua.strftime('%Y-%m-%d %H:%M:%S')}")

async def start_cmd(message: types.Message):
    await message.answer("Оберіть мову / Выберите язык:", reply_markup=lang_kb())

async def set_language(call: types.CallbackQuery, callback_data: dict):
    lang = callback_data['code']
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO user_prefs (user_id, language) VALUES (?, ?)", (call.from_user.id, lang))
        conn.commit()
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(get_text(lang, 'sub_btn'), url=config.CHANNEL_URL)).add(types.InlineKeyboardButton(get_text(lang, 'continue_btn'), callback_data="menu_start"))
    # Попытка редактирования сообщения; если не получается — отправим новый
    try:
        await call.message.edit_text(get_text(lang, 'lang_set'))
    except Exception:
        await call.message.answer(get_text(lang, 'lang_set'))
    await call.message.answer(get_text(lang, 'sub_recommend'), reply_markup=kb, disable_web_page_preview=True)
    await call.answer()

async def show_main_menu(call: types.CallbackQuery):
    lang = get_user_lang(call.from_user.id)
    await call.message.answer(get_text(lang, 'menu_main'), reply_markup=main_menu_kb(lang))
    await call.answer()

async def view_schedules_start(message: types.Message):
    lang = get_user_lang(message.from_user.id)
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("ДТЕК", callback_data="vcomp_ДТЕК"), types.InlineKeyboardButton("ЦЕК", callback_data="vcomp_ЦЕК"))
    await message.answer(get_text(lang, 'choose_comp'), reply_markup=kb)

async def add_queue_btn(message: types.Message):
    lang = get_user_lang(message.from_user.id)
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("ДТЕК", callback_data="scomp_ДТЕК"), types.InlineKeyboardButton("ЦЕК", callback_data="scomp_ЦЕК"))
    await message.answer(get_text(lang, 'choose_comp'), reply_markup=kb)

async def handle_comp_selection(call: types.CallbackQuery):
    lang = get_user_lang(call.from_user.id)
    # Ожидаем формат vcomp_ДТЕК или scomp_ДТЕК
    try:
        action, comp = call.data.split("_", 1)
    except Exception:
        await call.answer("Невірні дані", show_alert=True)
        return
    mode = 'view' if action == 'vcomp' else 'save'
    await call.message.edit_text(get_text(lang, 'choose_queue', company=comp), reply_markup=queues_kb(mode, comp, lang))
    await call.answer()

async def back_to_comp(call: types.CallbackQuery):
    lang = get_user_lang(call.from_user.id)
    is_view = "view" in call.data
    prefix = "vcomp_" if is_view else "scomp_"
    kb = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("ДТЕК", callback_data=f"{prefix}ДТЕК"),
        types.InlineKeyboardButton("ЦЕК", callback_data=f"{prefix}ЦЕК")
    )
    await call.message.edit_text(get_text(lang, 'choose_comp'), reply_markup=kb)
    await call.answer()

async def save_sub(call: types.CallbackQuery, callback_data: dict):
    lang = get_user_lang(call.from_user.id)
    comp, q = callback_data['val'].split("_")
    with get_db() as conn:
        try:
            conn.execute("INSERT INTO users (user_id, company, queue) VALUES (?,?,?)", (call.from_user.id, comp, q))
            conn.commit()
            await call.answer(get_text(lang, 'added'), show_alert=True)
        except Exception:
            await call.answer(get_text(lang, 'exists'), show_alert=True)
    # Уже ответили с show_alert, но удостоверимся, что callback закрыт
    try:
        await call.answer()
    except Exception:
        pass

async def show_sched(call: types.CallbackQuery, callback_data: dict):
    comp, q = callback_data['comp'], callback_data['queue']
    lang = get_user_lang(call.from_user.id)
    today = datetime.now(UA_TZ).strftime('%Y-%m-%d')
    with get_db() as conn:
        rows = conn.execute("SELECT off_time, on_time, created_at FROM schedules WHERE company=? AND queue=? AND date=?", (comp, q, today)).fetchall()
    if not rows:
        return await call.answer(get_text(lang, 'no_schedule'), show_alert=True)
    res = "\n".join([f"🔴 {r['off_time']} - 🟢 {r['on_time']}" for r in rows])
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(get_text(lang, 'back'), callback_data=f"vcomp_{comp}"))
    await call.message.edit_text(get_text(lang, 'schedule_view', company=comp, queue=q, date=today, schedule=res, updated=rows[0]['created_at']), reply_markup=kb)
    await call.answer()

async def my_queues(message: types.Message):
    lang = get_user_lang(message.from_user.id)
    with get_db() as conn:
        rows = conn.execute("SELECT id, company, queue FROM users WHERE user_id=?", (message.from_user.id,)).fetchall()
    if not rows:
        return await message.answer(get_text(lang, 'empty_list'))
    kb = types.InlineKeyboardMarkup()
    for r in rows:
        kb.add(types.InlineKeyboardButton(f"❌ {r['company']} {r['queue']}", callback_data=f"del_{r['id']}"))
    await message.answer(get_text(lang, 'btn_my_queues'), reply_markup=kb)

async def delete_sub(call: types.CallbackQuery):
    try:
        sub_id = call.data.split("_", 1)[1]
    except Exception:
        await call.answer("Невірні дані", show_alert=True)
        return
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE id=?", (sub_id,))
        conn.commit()
    await call.answer("Видалено", show_alert=True)
    try:
        await call.message.delete()
    except Exception:
        pass

async def support_cmd(message: types.Message):
    lang = get_user_lang(message.from_user.id)
    # Подставим SUPPORT_USER и DONATE_URL
    await message.answer(get_text(lang, 'support_text', user=config.SUPPORT_USER, url=config.DONATE_URL), disable_web_page_preview=True, parse_mode=types.ParseMode.HTML)

async def settings_cmd(message: types.Message):
    lang = get_user_lang(message.from_user.id)
    # Отправляем текст настроек и кнопку "Змінити мову" (используем локализованный лейбл btn_lang_switch)
    kb = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton(get_text(lang, 'btn_lang_switch'), callback_data="open_lang")
    )
    await message.answer(get_text(lang, 'settings_text'), reply_markup=kb)

# Новый callback для открытия меню смены языка
async def open_language_menu(call: types.CallbackQuery):
    lang = get_user_lang(call.from_user.id)
    # отправляем сообщение с выбором языка (inline keyboard)
    try:
        await call.message.answer(get_text(lang, 'select_lang'), reply_markup=lang_kb())
    except Exception:
        # если нельзя отправить ответ к тому сообщению, просто редактируем (fallback)
        try:
            await call.message.edit_text(get_text(lang, 'select_lang'), reply_markup=lang_kb())
        except Exception:
            pass
    await call.answer()

# --- Реєстрація ---
def register_handlers(dp: Dispatcher):
    dp.register_message_handler(check_time_cmd, commands=['check'])
    dp.register_message_handler(start_cmd, commands=['start'])
    dp.register_callback_query_handler(set_language, cb_lang.filter())
    dp.register_callback_query_handler(show_main_menu, text="menu_start")

    # Текстові кнопки
    dp.register_message_handler(view_schedules_start, lambda m: bool(m.text) and any(x in m.text.lower() for x in ["графік", "график"]))
    dp.register_message_handler(add_queue_btn, lambda m: bool(m.text) and any(x in m.text.lower() for x in ["додати", "добавить"]))
    dp.register_message_handler(my_queues, lambda m: bool(m.text) and any(x in m.text.lower() for x in ["мої чер", "мои оче"]))

    # Support и Settings — сравниваем с локализованными подписями (укр/ру)
    support_labels = (get_text('uk', 'btn_support'), get_text('ru', 'btn_support'))
    settings_labels = (get_text('uk', 'btn_settings'), get_text('ru', 'btn_settings'))
    dp.register_message_handler(support_cmd, lambda m: bool(m.text) and m.text in support_labels)
    dp.register_message_handler(settings_cmd, lambda m: bool(m.text) and m.text in settings_labels)

    # Callback-и (Компанії)
    dp.register_callback_query_handler(handle_comp_selection, lambda c: c.data and c.data.startswith(('vcomp_', 'scomp_')))
    dp.register_callback_query_handler(show_sched, cb_sched.filter())
    dp.register_callback_query_handler(save_sub, cb_menu.filter(action="save"))

    # Обработчик открытия меню смены языка
    dp.register_callback_query_handler(open_language_menu, text="open_lang")

    # Назад
    dp.register_callback_query_handler(back_to_comp, text=["back_view", "back_sub"])

    # Видалення
    dp.register_callback_query_handler(delete_sub, lambda c: c.data and c.data.startswith('del_'))
