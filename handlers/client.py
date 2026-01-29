from aiogram import Dispatcher, types
from aiogram.utils.callback_data import CallbackData
from database.db import get_db
import config
from locales.strings import get_text
from datetime import datetime

# Оголошення форматів CallbackData
cb_lang = CallbackData("lang", "code")
cb_menu = CallbackData("menu", "action", "val")
cb_sched = CallbackData("sched", "comp", "queue")

# --- Допоміжні функції ---
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

def settings_kb(lang):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(get_text(lang, 'btn_lang_switch'), callback_data="change_lang_sett"))
    return kb

def queues_kb(action_type, company, lang):
    queues = ["1.1", "1.2", "2.1", "2.2", "3.1", "3.2", "4.1", "4.2", "5.1", "5.2", "6.1", "6.2"]
    kb = types.InlineKeyboardMarkup(row_width=3)
    btns = []
    for q in queues:
        if action_type == 'view':
            btns.append(types.InlineKeyboardButton(q, callback_data=cb_sched.new(comp=company, queue=q)))
        else:
            btns.append(types.InlineKeyboardButton(q, callback_data=cb_menu.new(action='save', val=f"{company}:{q}")))
    kb.add(*btns)
    # Кнопки повернення з унікальними callback_data
    back_call = "back_to_comp_view" if action_type == 'view' else "back_to_comp_sub"
    kb.add(types.InlineKeyboardButton(get_text(lang, 'back'), callback_data=back_call))
    return kb

# --- Обробники (Handlers) ---

async def start_cmd(message: types.Message):
    await message.answer("Оберіть мову / Выберите язык:", reply_markup=lang_kb())

async def set_language(call: types.CallbackQuery, callback_data: dict):
    lang = callback_data['code']
    set_user_lang_db(call.from_user.id, lang)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(get_text(lang, 'continue_btn'), callback_data="menu_start"))
    await call.message.edit_text(get_text(lang, 'lang_set'), reply_markup=kb)
    await call.answer()

async def show_main_menu(call: types.CallbackQuery):
    lang = get_user_lang(call.from_user.id)
    await call.message.delete()
    await call.message.answer(get_text(lang, 'menu_main'), reply_markup=main_menu_kb(lang))
    await call.answer()

# --- ЛОГІКА ПЕРЕГЛЯДУ ---
async def view_schedules_start(message: types.Message):
    lang = get_user_lang(message.from_user.id)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("ДТЕК", callback_data="view_comp:ДТЕК"),
           types.InlineKeyboardButton("ЦЕК", callback_data="view_comp:ЦЕК"))
    await message.answer(get_text(lang, 'choose_comp'), reply_markup=kb)

async def view_comp_queues(call: types.CallbackQuery):
    comp = call.data.split(":")[1]
    lang = get_user_lang(call.from_user.id)
    await call.message.edit_text(get_text(lang, 'choose_queue', company=comp), 
                                 reply_markup=queues_kb('view', comp, lang))
    await call.answer()

# --- ЛОГІКА ПІДПИСКИ ---
async def add_queue_btn(message: types.Message):
    lang = get_user_lang(message.from_user.id)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("ДТЕК", callback_data="sub_comp:ДТЕК"),
           types.InlineKeyboardButton("ЦЕК", callback_data="sub_comp:ЦЕК"))
    await message.answer(get_text(lang, 'choose_comp'), reply_markup=kb)

async def sub_comp_queues(call: types.CallbackQuery):
    comp = call.data.split(":")[1]
    lang = get_user_lang(call.from_user.id)
    await call.message.edit_text(get_text(lang, 'choose_queue', company=comp), 
                                 reply_markup=queues_kb('save', comp, lang))
    await call.answer()

async def save_subscription(call: types.CallbackQuery, callback_data: dict):
    lang = get_user_lang(call.from_user.id)
    comp, queue = callback_data['val'].split(":")
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) as c FROM users WHERE user_id = ?", (call.from_user.id,)).fetchone()['c']
        if count >= 5:
            await call.answer(get_text(lang, 'limit_error'), show_alert=True)
            return
        try:
            conn.execute("INSERT INTO users (user_id, company, queue) VALUES (?,?,?)", (call.from_user.id, comp, queue))
            conn.commit()
            await call.answer(get_text(lang, 'added', company=comp, queue=queue), show_alert=True)
        except:
            await call.answer(get_text(lang, 'exists'), show_alert=True)
    await call.answer()

async def show_schedule_data(call: types.CallbackQuery, callback_data: dict):
    comp, queue = callback_data['comp'], callback_data['queue']
    lang, today = get_user_lang(call.from_user.id), datetime.now().strftime('%Y-%m-%d')
    with get_db() as conn:
        scheds = conn.execute("SELECT off_time, on_time, created_at FROM schedules WHERE company=? AND queue=? AND date=?", 
                              (comp, queue, today)).fetchall()
    if not scheds:
        await call.answer(get_text(lang, 'no_schedule'), show_alert=True)
        return
    lines = [f"🔴 {s['off_time']} - 🟢 {s['on_time']}" for s in scheds]
    text = get_text(lang, 'schedule_view', company=comp, queue=queue, date=today, 
                    schedule="\n".join(lines), updated=scheds[0]['created_at'])
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(get_text(lang, 'back'), callback_data=f"view_comp:{comp}"))
    await call.message.edit_text(text, reply_markup=kb)
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
    rid = call.data.split("_")[1]
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE id=?", (rid,))
        conn.commit()
    await call.answer("Видалено / Удалено")
    await call.message.delete()

# --- Реєстрація ---
def register_handlers(dp: Dispatcher):
    dp.register_message_handler(start_cmd, commands=['start'])
    dp.register_callback_query_handler(set_language, cb_lang.filter())
    dp.register_callback_query_handler(show_main_menu, text="menu_start")
    
    # ПЕРЕГЛЯД
    dp.register_message_handler(view_schedules_start, lambda m: any(x in m.text for x in ["Графіки", "Графики"]))
    dp.register_callback_query_handler(view_comp_queues, lambda c: c.data.startswith("view_comp:"))
    dp.register_callback_query_handler(show_schedule_data, cb_sched.filter())
    dp.register_callback_query_handler(view_schedules_start, text="back_to_comp_view") # Повернення до вибору ДТЕК/ЦЕК
    
    # ПІДПИСКА
    dp.register_message_handler(add_queue_btn, lambda m: any(x in m.text for x in ["Додати чергу", "Добавить очередь"]))
    dp.register_callback_query_handler(sub_comp_queues, lambda c: c.data.startswith("sub_comp:"))
    dp.register_callback_query_handler(save_subscription, cb_menu.filter(action="save"))
    dp.register_callback_query_handler(add_queue_btn, text="back_to_comp_sub") # Повернення до вибору ДТЕК/ЦЕК
    
    # МОЇ ЧЕРГИ ТА ІНШЕ
    dp.register_message_handler(my_queues, lambda m: any(x in m.text for x in ["Мої черги", "Мои очереди"]))
    dp.register_callback_query_handler(delete_sub, lambda c: c.data.startswith("del_"))
    dp.register_message_handler(lambda m: m.answer("Налаштування..."), lambda m: "Налаштування" in m.text)
    dp.register_message_handler(lambda m: m.answer(get_text(get_user_lang(m.from_user.id), 'support', user=config.SUPPORT_USER, url=config.DONATE_URL)), 
                                lambda m: any(x in m.text for x in ["Зв'язок", "Связь", "Підтримка"]))
