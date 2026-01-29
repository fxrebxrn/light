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
    kb.row(get_text(lang, 'btn_schedules'), get_text(lang, 'btn_settings'))
    return kb

def queues_kb(action_type, company, lang):
    queues = ["1.1", "1.2", "2.1", "2.2", "3.1", "3.2", "4.1", "4.2", "5.1", "5.2", "6.1", "6.2"]
    kb = types.InlineKeyboardMarkup(row_width=3)
    btns = [types.InlineKeyboardButton(q, callback_data=cb_sched.new(comp=company, queue=q) if action_type == 'view' else cb_menu.new(action='save', val=f"{company}_{q}")) for q in queues]
    kb.add(*btns)
    kb.add(types.InlineKeyboardButton(get_text(lang, 'back'), callback_data="back_view" if action_type == 'view' else "back_sub"))
    return kb

# --- Обробники ---

async def check_time_cmd(message: types.Message):
    """Команда для перевірки реального часу бота"""
    now_utc = datetime.now()
    now_ua = datetime.now(UA_TZ)
    await message.answer(
        f"🕒 <b>Перевірка часу:</b>\n\n"
        f"Системний (UTC): {now_utc.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Київський (UA): {now_ua.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Дата для бази: {now_ua.strftime('%Y-%m-%d')}"
    )

async def start_cmd(message: types.Message):
    await message.answer("Оберіть мову / Выберите язык:", reply_markup=lang_kb())

async def set_language(call: types.CallbackQuery, callback_data: dict):
    lang = callback_data['code']
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO user_prefs (user_id, language) VALUES (?, ?)", (call.from_user.id, lang))
        conn.commit()
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(get_text(lang, 'sub_btn'), url=config.CHANNEL_URL)).add(types.InlineKeyboardButton(get_text(lang, 'continue_btn'), callback_data="menu_start"))
    await call.message.edit_text(get_text(lang, 'lang_set'))
    await call.message.answer(get_text(lang, 'sub_recommend'), reply_markup=kb)
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
    action, comp = call.data.split("_")
    await call.message.edit_text(get_text(lang, 'choose_queue', company=comp), reply_markup=queues_kb('view' if action == 'vcomp' else 'save', comp, lang))
    await call.answer()

async def back_to_comp(call: types.CallbackQuery):
    lang = get_user_lang(call.from_user.id)
    prefix = "vcomp_" if "view" in call.data else "scomp_"
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("ДТЕК", callback_data=f"{prefix}ДТЕК"), types.InlineKeyboardButton("ЦЕК", callback_data=f"{prefix}ЦЕК"))
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
        except: await call.answer(get_text(lang, 'exists'), show_alert=True)
    await call.answer()

async def show_sched(call: types.CallbackQuery, callback_data: dict):
    comp, q = callback_data['comp'], callback_data['queue']
    lang = get_user_lang(call.from_user.id)
    today = datetime.now(UA_TZ).strftime('%Y-%m-%d')
    with get_db() as conn:
        rows = conn.execute("SELECT off_time, on_time, created_at FROM schedules WHERE company=? AND queue=? AND date=?", (comp, q, today)).fetchall()
    if not rows: return await call.answer(get_text(lang, 'no_schedule'), show_alert=True)
    res = "\n".join([f"🔴 {r['off_time']} - 🟢 {r['on_time']}" for r in rows])
    await call.message.edit_text(get_text(lang, 'schedule_view', company=comp, queue=q, date=today, schedule=res, updated=rows[0]['created_at']), reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(get_text(lang, 'back'), callback_data=f"vcomp_{comp}")))
    await call.answer()

async def my_queues(message: types.Message):
    lang = get_user_lang(message.from_user.id)
    with get_db() as conn:
        rows = conn.execute("SELECT id, company, queue FROM users WHERE user_id=?", (message.from_user.id,)).fetchall()
    if not rows: return await message.answer(get_text(lang, 'empty_list'))
    kb = types.InlineKeyboardMarkup()
    for r in rows:
        kb.add(types.InlineKeyboardButton(f"❌ {r['company']} {r['queue']}", callback_data=f"del_{r['id']}"))
    await message.answer(get_text(lang, 'btn_my_queues'), reply_markup=kb)

async def delete_sub(call: types.CallbackQuery):
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE id=?", (call.data.split("_")[1],))
        conn.commit()
    await call.answer("Видалено")
    await call.message.delete()

# --- Реєстрація ---
def register_handlers(dp: Dispatcher):
    dp.register_message_handler(check_time_cmd, commands=['check']) # Додано команду перевірки
    dp.register_message_handler(start_cmd, commands=['start'])
    dp.register_callback_query_handler(set_language, cb_lang.filter())
    dp.register_callback_query_handler(show_main_menu, text="menu_start")
    dp.register_message_handler(view_schedules_start, lambda m: any(x in m.text.lower() for x in ["графік", "график"]))
    dp.register_message_handler(add_queue_btn, lambda m: any(x in m.text.lower() for x in ["додати", "добавить"]))
    dp.register_message_handler(my_queues, lambda m: any(x in m.text.lower() for x in ["мої чер", "мои оче"]))
    dp.register_callback_query_handler(handle_comp_selection, lambda c: c.data.startswith(('vcomp_', 'scomp_')))
    dp.register_callback_query_handler(back_to_comp, text=["back_view", "back_sub"])
    dp.register_callback_query_handler(save_sub, cb_menu.filter(action="save"))
    dp.register_callback_query_handler(show_sched, cb_sched.filter())
    dp.register_callback_query_handler(delete_sub, lambda c: c.data.startswith('del_'))
