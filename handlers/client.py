from aiogram import Dispatcher, types
from aiogram.utils.callback_data import CallbackData
from database.db import get_db
import config
from locales.strings import get_text
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# CallbackData
cb_lang = CallbackData("lang", "code")
cb_menu = CallbackData("menu", "action", "val")
cb_sched = CallbackData("sched", "comp", "queue")

def get_user_lang(user_id):
    with get_db() as conn:
        res = conn.execute("SELECT language FROM user_prefs WHERE user_id = ?", (user_id,)).fetchone()
        return res['language'] if res else 'uk'

def set_user_lang_db(user_id, lang):
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO user_prefs (user_id, language) VALUES (?, ?)", (user_id, lang))
        conn.commit()

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
    # If action is 'view' we need cb_sched (so we can receive comp and queue via callback_data)
    # If action is 'save' we use cb_menu with action='save' and val containing company:queue
    btns = []
    for q in queues:
        if action_type == 'view':
            btns.append(types.InlineKeyboardButton(q, callback_data=cb_sched.new(comp=company, queue=q)))
        else:
            btns.append(types.InlineKeyboardButton(q, callback_data=cb_menu.new(action='save', val=f"{company}:{q}")))
    kb.add(*btns)
    back_call = "back_view" if action_type == 'view' else "back_sub"
    kb.add(types.InlineKeyboardButton(get_text(lang, 'back'), callback_data=back_call))
    return kb

# --- Обробники ---

async def start_cmd(message: types.Message):
    await message.answer("Оберіть мову / Выберите язык:", reply_markup=lang_kb())

async def set_language(call: types.CallbackQuery, callback_data: dict):
    lang = callback_data['code']
    set_user_lang_db(call.from_user.id, lang)
    
    # ПОВЕРНУТО ПОВІДОМЛЕННЯ ПРО ПІДПИСКУ
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(get_text(lang, 'sub_btn'), url=config.CHANNEL_URL))
    kb.add(types.InlineKeyboardButton(get_text(lang, 'continue_btn'), callback_data="menu_start"))
    
    # try edit original message, fallback to answer if edit not allowed
    try:
        await call.message.edit_text(get_text(lang, 'lang_set'))
    except Exception as e:
        logger.exception("Failed to edit message in set_language: %s", e)
        await call.message.answer(get_text(lang, 'lang_set'))
    await call.message.answer(get_text(lang, 'sub_recommend'), reply_markup=kb)
    await call.answer()

async def show_main_menu(call: types.CallbackQuery):
    lang = get_user_lang(call.from_user.id)
    await call.message.answer(get_text(lang, 'menu_main'), reply_markup=main_menu_kb(lang))
    await call.answer()

async def view_schedules_start(message: types.Message):
    lang = get_user_lang(message.from_user.id)
    kb = types.InlineKeyboardMarkup()
    # Use readable labels for buttons but ASCII-safe callback_data prefixes
    # Keep company names in Cyrillic as labels so users see them correctly
    kb.add(types.InlineKeyboardButton("ДТЕК", callback_data="v_comp:ДТЕК"),
           types.InlineKeyboardButton("ЦЕК", callback_data="v_comp:ЦЕК"))
    await message.answer(get_text(lang, 'choose_comp'), reply_markup=kb)

async def add_queue_btn(message: types.Message):
    lang = get_user_lang(message.from_user.id)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("ДТЕК", callback_data="s_comp:ДТЕК"),
           types.InlineKeyboardButton("ЦЕК", callback_data="s_comp:ЦЕК"))
    await message.answer(get_text(lang, 'choose_comp'), reply_markup=kb)

async def handle_comp_selection(call: types.CallbackQuery):
    # Універсальний обробник для вибору компанії
    lang = get_user_lang(call.from_user.id)
    # Defensive parsing and robust behaviour: ensure we always answer the callback to stop spinner
    try:
        action, comp = call.data.split(":", 1)
    except Exception as e:
        logger.exception("Invalid callback data in handle_comp_selection: %s", e)
        await call.answer("Невірні дані", show_alert=True)
        return

    mode = 'view' if action == 'v_comp' else 'save'
    text = get_text(lang, 'choose_queue', company=comp)
    kb = queues_kb(mode, comp, lang)

    # Try to edit the message (preferred), if it fails send a new message instead.
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception as e:
        logger.exception("Failed to edit message in handle_comp_selection: %s", e)
        try:
            await call.message.answer(text, reply_markup=kb)
        except Exception as e2:
            logger.exception("Failed to send fallback message in handle_comp_selection: %s", e2)
            await call.answer(get_text(lang, 'error'), show_alert=True)
            return

    await call.answer()

async def save_subscription(call: types.CallbackQuery, callback_data: dict):
    lang = get_user_lang(call.from_user.id)
    # callback_data comes from cb_menu and has 'val' like "company:queue"
    comp, queue = callback_data['val'].split(":")
    with get_db() as conn:
        try:
            conn.execute("INSERT INTO users (user_id, company, queue) VALUES (?,?,?)", (call.from_user.id, comp, queue))
            conn.commit()
            await call.answer(f"✅ {comp} {queue} {get_text(lang, 'added')}", show_alert=True)
        except Exception as e:
            logger.debug("Error inserting subscription (probably exists): %s", e)
            await call.answer(get_text(lang, 'exists'), show_alert=True)

async def show_schedule_data(call: types.CallbackQuery, callback_data: dict):
    comp, queue = callback_data['comp'], callback_data['queue']
    lang = get_user_lang(call.from_user.id)
    today = datetime.now().strftime('%Y-%m-%d')
    with get_db() as conn:
        scheds = conn.execute(
            "SELECT off_time, on_time, created_at FROM schedules WHERE company=? AND queue=? AND date=?",
            (comp, queue, today)
        ).fetchall()
    if not scheds:
        await call.answer(get_text(lang, 'no_schedule'), show_alert=True)
        return
    res = "\n".join([f"🔴 {s['off_time']} - 🟢 {s['on_time']}" for s in scheds])
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(get_text(lang, 'back'), callback_data=f"v_comp:{comp}"))
    # If created_at is a datetime-like string, present it; otherwise fallback
    updated = scheds[0].get('created_at') if scheds and 'created_at' in scheds[0] else ''
    await call.message.edit_text(
        get_text(lang, 'schedule_view', company=comp, queue=queue, date=today, schedule=res, updated=updated),
        reply_markup=kb
    )
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
    # defensive parse
    try:
        sub_id = call.data.split("_", 1)[1]
    except Exception as e:
        logger.exception("Invalid delete callback data: %s", e)
        await call.answer("Невірні дані", show_alert=True)
        return
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE id=?", (sub_id,))
        conn.commit()
    await call.answer("Видалено", show_alert=True)
    # delete message with the inline button list (if allowed)
    try:
        await call.message.delete()
    except Exception:
        # ignore if cannot delete
        pass

# --- Реєстрація ---
def register_handlers(dp: Dispatcher):
    dp.register_message_handler(start_cmd, commands=['start'])
    dp.register_callback_query_handler(set_language, cb_lang.filter())
    dp.register_callback_query_handler(show_main_menu, text="menu_start")
    
    # Текстові кнопки (Графіки / Додати / Мої)
    dp.register_message_handler(view_schedules_start, lambda m: m.text and "рафік" in m.text.lower())
    dp.register_message_handler(add_queue_btn, lambda m: m.text and "одати" in m.text.lower())
    dp.register_message_handler(my_queues, lambda m: m.text and "ої чер" in m.text.lower())
    
    # Callback-и (Компанії) - generic handler for v_comp:... and s_comp:...
    dp.register_callback_query_handler(handle_comp_selection, lambda c: c.data and c.data.startswith(('v_comp:', 's_comp:')))
    dp.register_callback_query_handler(show_schedule_data, cb_sched.filter())
    dp.register_callback_query_handler(save_subscription, cb_menu.filter(action="save"))
    
    # Назад
    dp.register_callback_query_handler(view_schedules_start, text="back_view")
    dp.register_callback_query_handler(add_queue_btn, text="back_sub")
    
    # Видалення
    dp.register_callback_query_handler(delete_sub, lambda c: c.data and c.data.startswith('del_'))
