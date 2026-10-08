import logging
import sqlite3
import csv
import io
import random
import re
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ============ ВСТАВЬТЕ ВАШ ТОКЕН ============
API_TOKEN = "8802150498:AAH8-jB4ATF6X9n5vq3n-ul6MOJvStWR-1Q"

logging.basicConfig(level=logging.INFO)

conn = sqlite3.connect("finance_bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    budget REAL DEFAULT 0,
    name TEXT DEFAULT 'Друг'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount REAL,
    category TEXT,
    description TEXT,
    type TEXT DEFAULT 'expense',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT,
    target_amount REAL,
    current_amount REAL DEFAULT 0
)
""")
conn.commit()

# ============ УМНЫЙ СЛОВАРЬ (150+ слов) ============
CATEGORIES = {
    "🍕 Еда": ["кофе", "обед", "ужин", "продукты", "ресторан", "кафе", "шаурма", "пицца", "суши", "бургер", "чай", "сок", "хлеб", "молоко", "мясо", "овощи", "фрукты", "сладости", "мороженое", "фастфуд", "завтрак", "магнум", "глобус", "конфеты", "сыр", "колбаса", "курица", "рыба", "картошка", "рис", "йогурт", "торт"],
    "🚗 Транспорт": ["такси", "автобус", "бензин", "метро", "маршрутка", "поезд", "самолет", "проезд", "парковка", "заправка", "билет"],
    "🎮 Развлечения": ["кино", "игры", "книги", "подписка", "netflix", "spotify", "концерт", "театр", "боулинг", "караоке", "клуб", "подарок", "праздник"],
    "💊 Здоровье": ["аптека", "врач", "лекарство", "спортзал", "фитнес", "анализы", "больница", "стоматолог", "массаж", "витамины"],
    "🛍 Покупки": ["одежда", "обувь", "косметика", "техника", "телефон", "ноутбук", "наушники", "сумка", "часы", "посуда", "мебель"],
    "🏠 Коммуналка": ["связь", "интернет", "квартира", "свет", "вода", "газ", "отопление", "аренда", "коммуналка"],
    "📚 Образование": ["курсы", "обучение", "репетитор", "школа", "университет", "семинар", "тренинг"],
    "🐾 Питомцы": ["корм", "ветеринар", "кошка", "собака", "наполнитель"],
    "📦 Разное": []
}

INCOME_KEYWORDS = ["зарплата", "аванс", "премия", "доход", "приход", "перевод", "подарок", "стипендия", "пенсия", "кэшбэк", "возврат"]

class Form(StatesGroup):
    set_budget = State()
    set_name = State()
    set_goal_title = State()
    set_goal_amount = State()
    add_goal_money = State()

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

def main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("📊 Баланс"), KeyboardButton("📈 Аналитика"))
    markup.add(KeyboardButton("📅 Сегодня"), KeyboardButton("💡 Совет"))
    markup.add(KeyboardButton("🎯 Цели"), KeyboardButton("📅 Отчёт"))
    markup.add(KeyboardButton("⚙️ Настройки"))
    return markup

def settings_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💰 Бюджет", callback_data="change_budget"))
    markup.add(InlineKeyboardButton("👤 Имя", callback_data="change_name"))
    markup.add(InlineKeyboardButton("🗑 Удалить последнее", callback_data="undo_last"))
    markup.add(InlineKeyboardButton("📥 Экспорт CSV", callback_data="export_csv"))
    return markup

def goals_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("➕ Создать цель", callback_data="new_goal"))
    markup.add(InlineKeyboardButton("💰 Пополнить цель", callback_data="add_money"))
    return markup
def parse_amount(text):
    numbers = re.findall(r'\d+[\.,]?\d*', text.replace(" ", ""))
    if not numbers:
        return None
    try:
        return float(numbers[-1].replace(",", "."))
    except:
        return None

def find_category(text):
    text_lower = text.lower()
    best_match = "📦 Разное"
    max_matches = 0
    for category, keywords in CATEGORIES.items():
        matches = sum(1 for kw in keywords if kw in text_lower)
        if matches > max_matches:
            max_matches = matches
            best_match = category
    return best_match

def is_income(text):
    text_lower = text.lower()
    return any(kw in text_lower for kw in INCOME_KEYWORDS)

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    cursor.execute("SELECT name FROM users WHERE user_id = ?", (message.from_user.id,))
    row = cursor.fetchone()
    name = row[0] if row else "Друг"
    text = (
        f"👋 Привет, {name}!\n\n"
        "💸 *Finance bot* — умный помощник.\n\n"
        "💡 *Примеры:*\n"
        "• +600 — добавить в бюджет\n"
        "• -300 — вычесть из бюджета\n"
        "• Кофе 200 — записать расход\n"
        "• +Зарплата 30000 — записать доход\n\n"
        "🧠 Я сам определю категорию!"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=main_keyboard())

@dp.message_handler(lambda m: m.text == "⚙️ Настройки")
async def show_settings(message: types.Message):
    await message.answer("⚙️ *Настройки*", parse_mode="Markdown", reply_markup=settings_keyboard())

@dp.callback_query_handler(lambda c: c.data == "change_budget")
async def cb_budget(callback: types.CallbackQuery):
    await callback.message.answer("Введите бюджет (например, 30000):")
    await Form.set_budget.set()
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "change_name")
async def cb_name(callback: types.CallbackQuery):
    await callback.message.answer("Как тебя зовут?")
    await Form.set_name.set()
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "undo_last")
async def cb_undo(callback: types.CallbackQuery):
    cursor.execute("SELECT id, description, amount FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 1", (callback.from_user.id,))
    row = cursor.fetchone()
    if row:
        cursor.execute("DELETE FROM transactions WHERE id = ?", (row[0],))
        conn.commit()
        await callback.message.answer(f"🗑 Удалено: {row[1]} — {row[2]:,.2f}")
    else:
        await callback.message.answer("Нечего удалять.")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "export_csv")
async def cb_export(callback: types.CallbackQuery):
    cursor.execute("SELECT created_at, description, category, amount, type FROM transactions WHERE user_id = ? ORDER BY created_at DESC", (callback.from_user.id,))
    rows = cursor.fetchall()
    if not rows:
        await callback.message.answer("Нет данных.")
        await callback.answer()
        return
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Дата", "Описание", "Категория", "Сумма", "Тип"])
    for r in rows:
        writer.writerow(r)
    file_bytes = io.BytesIO(output.getvalue().encode('utf-8-sig'))
    file_bytes.name = "transactions.csv"
    await callback.message.answer_document(file_bytes, caption="📥 Ваши траты")
    await callback.answer()

@dp.message_handler(state=Form.set_name)
async def set_name(message: types.Message, state: FSMContext):
    cursor.execute("UPDATE users SET name = ? WHERE user_id = ?", (message.text.strip()[:30], message.from_user.id))
    conn.commit()
    await message.answer("✅ Приятно познакомиться!", reply_markup=main_keyboard())
    await state.finish()
@dp.message_handler(state=Form.set_budget)
async def set_budget(message: types.Message, state: FSMContext):
    try:
        budget = float(message.text.replace(",", "."))
        cursor.execute("UPDATE users SET budget = ? WHERE user_id = ?", (budget, message.from_user.id))
        conn.commit()
        await message.answer(f"✅ Бюджет: {budget:,.2f}", reply_markup=main_keyboard())
        await state.finish()
    except ValueError:
        await message.answer("Введите число.")

@dp.message_handler(lambda m: m.text == "📊 Баланс")
async def show_balance(message: types.Message):
    cursor.execute("SELECT budget FROM users WHERE user_id = ?", (message.from_user.id,))
    budget = cursor.fetchone()[0] or 0
    now = datetime.now()
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    fd = first_day.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = 'expense' AND created_at >= ?", (message.from_user.id, fd))
    spent = cursor.fetchone()[0] or 0
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = 'income' AND created_at >= ?", (message.from_user.id, fd))
    income = cursor.fetchone()[0] or 0
    balance = budget + income - spent
    days_left = max(1, 30 - now.day + 1)
    if budget > 0:
        percent = min(100, (spent / budget) * 100)
        bars = int(percent // 10)
        progress = "█" * bars + "░" * (10 - bars)
        daily = max(0, (budget + income - spent) / days_left)
        text = (
            "💳 *Баланс*\n\n"
            f"💰 Бюджет: {budget:,.2f}\n"
            f"📈 Доходы: {income:,.2f}\n"
            f"📉 Расходы: {spent:,.2f}\n"
            f"💵 Остаток: {balance:,.2f}\n\n"
            f"[{progress}] {percent:.1f}%\n"
            f"📅 Дней: {days_left}\n"
            f"🎯 Лимит: {daily:,.2f}"
        )
    else:
        text = (
            "💳 *Баланс*\n\n"
            f"📈 Доходы: {income:,.2f}\n"
            f"📉 Расходы: {spent:,.2f}\n"
            f"💵 Остаток: {balance:,.2f}\n\n"
            "💡 Установите бюджет в Настройках!"
        )
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "📅 Сегодня")
async def show_today(message: types.Message):
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT description, amount, type FROM transactions WHERE user_id = ? AND created_at LIKE ? ORDER BY id DESC", (message.from_user.id, f"{today}%"))
    rows = cursor.fetchall()
    if not rows:
        await message.answer("📅 Сегодня трат нет.")
        return
    text = "📅 *Сегодня:*\n\n"
    total_exp = sum(r[1] for r in rows if r[2] == 'expense')
    total_inc = sum(r[1] for r in rows if r[2] == 'income')
    for desc, amount, ttype in rows:
        sign = "🔻" if ttype == 'expense' else "🔺"
        text += f"{sign} {desc} — {amount:,.2f}\n"
    text += f"\n📉 Расходы: {total_exp:,.2f}\n📈 Доходы: {total_inc:,.2f}"
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "📈 Аналитика")
async def show_analytics(message: types.Message):
    now = datetime.now()
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cursor.execute("SELECT category, SUM(amount) FROM transactions WHERE user_id = ? AND type = 'expense' AND created_at >= ? GROUP BY category ORDER BY SUM(amount) DESC", (message.from_user.id, first_day.strftime("%Y-%m-%d %H:%M:%S")))
    rows = cursor.fetchall()
    if not rows:
        await message.answer("📊 Трат за месяц нет!")
        return
    total = sum(r[1] for r in rows)
    text = "📊 *Аналитика:*\n\n"
    for cat, amt in rows:
        percent = (amt / total) * 100
        bars = int(percent // 10)
        progress = "█" * bars + "░" * (10 - bars)
        text += f"{cat}\n[{progress}] {amt:,.2f} ({percent:.1f}%)\n\n"
    text += f"🔴 *Всего: {total:,.2f}*"
    await message.answer(text, parse_mode="Markdown")
@dp.message_handler(lambda m: m.text == "📅 Отчёт")
async def show_report(message: types.Message):
    now = datetime.now()
    first_day_now = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 1:
        prev_year, prev_month = now.year - 1, 12
    else:
        prev_year, prev_month = now.year, now.month - 1
    first_day_prev = datetime(prev_year, prev_month, 1)
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = 'expense' AND created_at >= ?", (message.from_user.id, first_day_now.strftime("%Y-%m-%d %H:%M:%S")))
    current = cursor.fetchone()[0] or 0
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = 'expense' AND created_at >= ? AND created_at < ?", (message.from_user.id, first_day_prev.strftime("%Y-%m-%d %H:%M:%S"), first_day_now.strftime("%Y-%m-%d %H:%M:%S")))
    previous = cursor.fetchone()[0] or 0
    if previous > 0:
        diff = current - previous
        percent = (diff / previous) * 100
        if diff > 0:
            trend = f"📈 Рост на {abs(diff):,.2f} ({abs(percent):.1f}%)"
        else:
            trend = f"📉 Снижение на {abs(diff):,.2f} ({abs(percent):.1f}%)"
    else:
        trend = "Нет данных для сравнения"
    text = f"📅 *Отчёт*\n\n🔹 Прошлый месяц: {previous:,.2f}\n🔸 Этот месяц: {current:,.2f}\n\n{trend}"
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "🎯 Цели")
async def show_goals(message: types.Message):
    cursor.execute("SELECT id, title, target_amount, current_amount FROM goals WHERE user_id = ?", (message.from_user.id,))
    goals = cursor.fetchall()
    if not goals:
        text = "🎯 *Цели*\n\nУ тебя пока нет целей."
    else:
        text = "🎯 *Твои цели:*\n\n"
        for g in goals:
            gid, title, target, current = g
            percent = min(100, (current / target) * 100) if target > 0 else 0
            bars = int(percent // 10)
            progress = "█" * bars + "░" * (10 - bars)
            text += f"📌 *{title}*\n[{progress}] {percent:.1f}%\n{current:,.2f} / {target:,.2f}\n\n"
    await message.answer(text, parse_mode="Markdown", reply_markup=goals_keyboard())

@dp.callback_query_handler(lambda c: c.data == "new_goal")
async def cb_new_goal(callback: types.CallbackQuery):
    await callback.message.answer("Как назовём цель?")
    await Form.set_goal_title.set()
    await callback.answer()

@dp.message_handler(state=Form.set_goal_title)
async def goal_title(message: types.Message, state: FSMContext):
    await state.update_data(goal_title=message.text.strip()[:50])
    await message.answer("Сколько нужно накопить?")
    await Form.set_goal_amount.set()

@dp.message_handler(state=Form.set_goal_amount)
async def goal_amount(message: types.Message, state: FSMContext):
    try:
        target = float(message.text.replace(",", "."))
        data = await state.get_data()
        title = data.get('goal_title', 'Без названия')
        cursor.execute("INSERT INTO goals (user_id, title, target_amount) VALUES (?, ?, ?)", (message.from_user.id, title, target))
        conn.commit()
        await message.answer(f"🎯 Цель «{title}» на {target:,.2f} создана!", reply_markup=main_keyboard())
        await state.finish()
    except ValueError:
        await message.answer("Введите число.")

@dp.callback_query_handler(lambda c: c.data == "add_money")
async def cb_add_money(callback: types.CallbackQuery):
    cursor.execute("SELECT id, title FROM goals WHERE user_id = ?", (callback.from_user.id,))
    goals = cursor.fetchall()
    if not goals:
        await callback.message.answer("Сначала создайте цель!")
        await callback.answer()
        return
    markup = InlineKeyboardMarkup()
    for gid, title in goals:
        markup.add(InlineKeyboardButton(f"💰 {title}", callback_data=f"add_to_{gid}"))
    await callback.message.answer("Куда добавить?", reply_markup=markup)
    await callback.answer()
@dp.callback_query_handler(lambda c: c.data.startswith("add_to_"))
async def cb_add_to_goal(callback: types.CallbackQuery, state: FSMContext):
    gid = int(callback.data.replace("add_to_", ""))
    await state.update_data(goal_id=gid)
    await callback.message.answer("Сколько добавляем?")
    await Form.add_goal_money.set()
    await callback.answer()

@dp.message_handler(state=Form.add_goal_money)
async def add_money_to_goal(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        data = await state.get_data()
        gid = data.get('goal_id')
        cursor.execute("UPDATE goals SET current_amount = current_amount + ? WHERE id = ?", (amount, gid))
        conn.commit()
        cursor.execute("SELECT title, target_amount, current_amount FROM goals WHERE id = ?", (gid,))
        title, target, current = cursor.fetchone()
        percent = min(100, (current / target) * 100) if target > 0 else 0
        await message.answer(f"✅ +{amount:,.2f} к «{title}»\nПрогресс: {current:,.2f} / {target:,.2f} ({percent:.1f}%)", reply_markup=main_keyboard())
        await state.finish()
    except ValueError:
        await message.answer("Введите число.")

@dp.message_handler(lambda m: m.text == "💡 Совет")
async def show_tips(message: types.Message):
    now = datetime.now()
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cursor.execute("SELECT category, SUM(amount) FROM transactions WHERE user_id = ? AND type = 'expense' AND created_at >= ? GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1", (message.from_user.id, first_day.strftime("%Y-%m-%d %H:%M:%S")))
    row = cursor.fetchone()
    if not row:
        await message.answer("💡 Начните вносить расходы!")
        return
    top_cat, top_amount = row
    savings_30 = top_amount * 0.30
    yearly = savings_30 * 12
    tips = [
        "Готовь дома вместо кафе — экономия до 50%.",
        "Отмени ненужные подписки.",
        "Перед покупкой подожди 24 часа.",
        "Используй кэшбэк-карты.",
        "Планируй покупки заранее.",
        "Веди список покупок.",
        "Замени такси на транспорт.",
        "Покупай продукты на неделю.",
        "Отключи лишние подписки.",
        "Ставь лимит на развлечения."
    ]
    tip = random.choice(tips)
    text = (
        f"💡 *Совет*\n\n"
        f"📊 Крупнейшая трата: *{top_cat}* ({top_amount:,.2f})\n\n"
        f"🔹 -30% = *{savings_30:,.2f}* в месяц.\n"
        f"🚀 За год: *{yearly:,.2f}*\n\n"
        f"💡 {tip}"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler()
async def process_expense(message: types.Message):
    if not message.text:
        return
    text = message.text.strip()
    buttons = ["📊 Баланс", "📈 Аналитика", "📅 Сегодня", "💡 Совет", "🎯 Цели", "📅 Отчёт", "⚙️ Настройки"]
    if text in buttons:
        return
    quick_match = re.match(r'^([+-])\s*(\d+[\.,]?\d*)$', text)
    if quick_match:
        sign = quick_match.group(1)
        amount = float(quick_match.group(2).replace(",", "."))
        user_id = message.from_user.id
        if sign == "+":
            cursor.execute("INSERT INTO transactions (user_id, amount, category, description, type) VALUES (?, ?, '📈 Доход', ?, 'income')", (user_id, amount, f"Пополнение +{amount:.0f}"))
        else:
            cursor.execute("INSERT INTO transactions (user_id, amount, category, description, type) VALUES (?, ?, '📦 Разное', ?, 'expense')", (user_id, amount, f"Списание -{amount:.0f}"))
        conn.commit()
        cursor.execute("SELECT budget FROM users WHERE user_id = ?", (user_id,))
        budget = cursor.fetchone()[0] or 0
        now = datetime.now()
        first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = 'income' AND created_at >= ?", (user_id, first_day.strftime("%Y-%m-%d %H:%M:%S")))
        income = cursor.fetchone()[0] or 0
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = 'expense' AND created_at >= ?", (user_id, first_day.strftime("%Y-%m-%d %H:%M:%S")))
        spent = cursor.fetchone()[0] or 0
        balance = budget + income - spent
        if sign == "+":
            await message.answer(f"✅ +{amount:,.2f}\n\n💵 Баланс: {balance:,.2f}")
        else:
            await message.answer(f"✅ -{amount:,.2f}\n\n💵 Баланс: {balance:,.2f}")
        return
    amount = parse_amount(text)
    if not amount or amount <= 0:
        await message.answer("Не вижу сумму. Примеры:\n• Кофе 200\n• +600\n• -300", parse_mode="Markdown")
        return
    user_id = message.from_user.id
    clean_text = text.lstrip("+").strip()
    if is_income(text):
        t_type = 'income'
        category = "📈 Доход"
    else:
        t_type = 'expense'
        category = find_category(clean_text)
    cursor.execute("INSERT INTO transactions (user_id, amount, category, description, type) VALUES (?, ?, ?, ?, ?)", (user_id, amount, category, clean_text, t_type))
    conn.commit()
    if t_type == 'income':
        response = f"✅ *Доход!*\n\n📌 {clean_text}\n💵 +{amount:,.2f}\n🏷 {category}"
    else:
        cursor.execute("SELECT budget FROM users WHERE user_id = ?", (user_id,))
        budget = cursor.fetchone()[0] or 0
        now = datetime.now()
        first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = 'expense' AND created_at >= ?", (user_id, first_day.strftime("%Y-%m-%d %H:%M:%S")))
        spent = cursor.fetchone()[0] or 0
        response = f"✅ *Записано!*\n\n📌 {clean_text}\n💵 {amount:,.2f}\n🏷 {category}\n\n"
        if budget > 0:
            remaining = budget - spent
            if remaining < 0:
                response += f"⚠️ Превышен на {abs(remaining):,.2f}!"
            elif remaining < budget * 0.2:
                response += f"⚠️ Осталось {remaining:,.2f}"
            else:
                response += f"📉 Остаток: {remaining:,.2f}"
    await message.answer(response, parse_mode="Markdown")

if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
