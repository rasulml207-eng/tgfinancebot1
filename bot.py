import logging
import sqlite3
import csv
import io
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ВСТАВЬТЕ СЮДА ВАШ ТОКЕН
API_TOKEN = "8802150498:AAH8-jB4ATF6X9n5vq3n-ul6MOJvStWR-1Q"

logging.basicConfig(level=logging.INFO)

conn = sqlite3.connect("finance_bot.db", check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT,
    target_amount REAL,
    current_amount REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

DEFAULT_CATEGORIES = {
    "кофе": "🍕 Еда", "обед": "🍕 Еда", "ужин": "🍕 Еда", "продукты": "🍕 Еда", "ресторан": "🍕 Еда", "кафе": "🍕 Еда",
    "такси": "🚗 Транспорт", "автобус": "🚗 Транспорт", "бензин": "🚗 Транспорт", "метро": "🚗 Транспорт",
    "кино": "🎮 Развлечения", "игры": "🎮 Развлечения", "книги": "🎮 Развлечения", "подписка": "🎮 Развлечения",
    "аптека": "💊 Здоровье", "врач": "💊 Здоровье", "спортзал": "💊 Здоровье",
    "одежда": "🛍 Покупки", "обувь": "🛍 Покупки",
    "связь": "🏠 Коммуналка", "интернет": "🏠 Коммуналка", "квартира": "🏠 Коммуналка", "свет": "🏠 Коммуналка"
}

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
    markup.add(KeyboardButton("🎯 Цели"), KeyboardButton("💡 Советы"))
    markup.add(KeyboardButton("📅 Отчёт за месяц"), KeyboardButton("⚙️ Настройки"))
    return markup

def goals_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("➕ Создать цель", callback_data="new_goal"))
    markup.add(InlineKeyboardButton("💰 Пополнить цель", callback_data="add_money"))
    return markup

def settings_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💰 Изменить бюджет", callback_data="change_budget"))
    markup.add(InlineKeyboardButton("👤 Изменить имя", callback_data="change_name"))
    markup.add(InlineKeyboardButton("🗑 Удалить последнюю трату", callback_data="undo_last"))
    markup.add(InlineKeyboardButton("📥 Экспорт в CSV", callback_data="export_csv"))
    return markup

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    
    cursor.execute("SELECT name FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    name = row[0] if row else "Друг"
    
    text = (
        f"👋 Привет, {name}!\n\n"
        "Я твой личный финансовый помощник.\n\n"
        "💡 *Как пользоваться:*\n"
        "• Просто напиши: Кофе 200 или Такси 150\n"
        "• Я сам определю категорию и запишу трату\n"
        "• Используй меню ниже для управления бюджетом\n\n"
        "🎯 Хочешь копить на что-то? Создай цель в разделе «Цели»!"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=main_keyboard())
@dp.message_handler(lambda message: message.text == "⚙️ Настройки")
async def show_settings(message: types.Message):
    await message.answer("⚙️ *Настройки*\n\nЧто хочешь изменить?", parse_mode="Markdown", reply_markup=settings_keyboard())

@dp.callback_query_handler(lambda c: c.data == "change_budget")
async def cb_change_budget(callback: types.CallbackQuery):
    await callback.message.answer("Введите ваш месячный бюджет (например, 30000):")
    await Form.set_budget.set()
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "change_name")
async def cb_change_name(callback: types.CallbackQuery):
    await callback.message.answer("Как тебя зовут?")
    await Form.set_name.set()
    await callback.answer()

@dp.message_handler(state=Form.set_name)
async def set_name(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    name = message.text.strip()[:30]
    cursor.execute("UPDATE users SET name = ? WHERE user_id = ?", (name, user_id))
    conn.commit()
    await message.answer(f"✅ Приятно познакомиться, {name}!", reply_markup=main_keyboard())
    await state.finish()

@dp.message_handler(state=Form.set_budget)
async def set_budget_finish(message: types.Message, state: FSMContext):
    try:
        budget = float(message.text.replace(",", "."))
        user_id = message.from_user.id
        cursor.execute("UPDATE users SET budget = ? WHERE user_id = ?", (budget, user_id))
        conn.commit()
        await message.answer(f"✅ Бюджет установлен: {budget:,.2f}", reply_markup=main_keyboard())
        await state.finish()
    except ValueError:
        await message.answer("Пожалуйста, введите число.")

@dp.callback_query_handler(lambda c: c.data == "undo_last")
async def cb_undo_last(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT id, description, amount FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        await callback.message.answer("Нечего удалять — трат пока нет.")
        await callback.answer()
        return
    
    tid, desc, amount = row
    cursor.execute("DELETE FROM transactions WHERE id = ?", (tid,))
    conn.commit()
    await callback.message.answer(f"🗑 Удалено: {desc} — {amount:,.2f}")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "export_csv")
async def cb_export_csv(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT created_at, description, category, amount FROM transactions WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = cursor.fetchall()
    
    if not rows:
        await callback.message.answer("Нет данных для экспорта.")
        await callback.answer()
        return
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Дата", "Описание", "Категория", "Сумма"])
    for r in rows:
        writer.writerow(r)
    
    file_bytes = io.BytesIO(output.getvalue().encode('utf-8-sig'))
    file_bytes.name = "transactions.csv"
    
    await callback.message.answer_document(file_bytes, caption="📥 Ваши траты в CSV")
    await callback.answer()

@dp.message_handler(lambda message: message.text == "📊 Баланс")
async def show_balance(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT budget FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    budget = row[0] if row else 0

    now = datetime.now()
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    cursor.execute(
        "SELECT SUM(amount) FROM transactions WHERE user_id = ? AND created_at >= ?",
        (user_id, first_day.strftime("%Y-%m-%d %H:%M:%S"))
    )
    spent_row = cursor.fetchone()
    spent = spent_row[0] if spent_row and spent_row[0] else 0
    remaining = budget - spent
    if budget > 0:
        percent = min(100, (spent / budget) * 100)
        bars = int(percent // 10)
        progress = "█" * bars + "░" * (10 - bars)
        days_left = max(1, 30 - now.day + 1)
        daily_limit = max(0, remaining / days_left)
        
        text = (
            "💳 *Ваш баланс*\n\n"
            f"💰 Бюджет: {budget:,.2f}\n"
            f"📉 Потрачено: {spent:,.2f}\n"
            f"💵 Остаток: {remaining:,.2f}\n\n"
            f"Прогресс: [{progress}] {percent:.1f}%\n\n"
            f"📅 Дней осталось: {days_left}\n"
            f"🎯 Лимит на день: {daily_limit:,.2f}"
        )
    else:
        text = (
            "💳 *Ваш баланс*\n\n"
            f"💰 Бюджет: не установлен\n"
            f"📉 Потрачено: {spent:,.2f}\n\n"
            "💡 Установите бюджет в Настройках!"
        )
    
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(lambda message: message.text == "📈 Аналитика")
async def show_analytics(message: types.Message):
    user_id = message.from_user.id
    now = datetime.now()
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    cursor.execute(
        "SELECT category, SUM(amount) FROM transactions WHERE user_id = ? AND created_at >= ? GROUP BY category ORDER BY SUM(amount) DESC",
        (user_id, first_day.strftime("%Y-%m-%d %H:%M:%S"))
    )
    rows = cursor.fetchall()

    if not rows:
        await message.answer("📊 За этот месяц трат пока нет!\n\nНапиши что-нибудь вроде Кофе 200", parse_mode="Markdown")
        return

    total = sum(r[1] for r in rows)
    text = "📊 *Аналитика за месяц:*\n\n"
    for cat, amt in rows:
        percent = (amt / total) * 100
        bars = int(percent // 10)
        progress = "█" * bars + "░" * (10 - bars)
        text += f"{cat}\n[{progress}] {amt:,.2f} ({percent:.1f}%)\n\n"
    text += f"🔴 *Всего: {total:,.2f}*"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(lambda message: message.text == "📅 Отчёт за месяц")
async def show_monthly_report(message: types.Message):
    user_id = message.from_user.id
    now = datetime.now()
    
    # Текущий месяц
    first_day_now = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Прошлый месяц
    if now.month == 1:
        prev_year, prev_month = now.year - 1, 12
    else:
        prev_year, prev_month = now.year, now.month - 1
    first_day_prev = datetime(prev_year, prev_month, 1)
    last_day_prev = first_day_now
    
    cursor.execute(
        "SELECT SUM(amount) FROM transactions WHERE user_id = ? AND created_at >= ?",
        (user_id, first_day_now.strftime("%Y-%m-%d %H:%M:%S"))
    )
    current = cursor.fetchone()[0] or 0
    
    cursor.execute(
        "SELECT SUM(amount) FROM transactions WHERE user_id = ? AND created_at >= ? AND created_at < ?",
        (user_id, first_day_prev.strftime("%Y-%m-%d %H:%M:%S"), last_day_prev.strftime("%Y-%m-%d %H:%M:%S"))
    )
    previous = cursor.fetchone()[0] or 0
    
    if previous > 0:
        diff = current - previous
        percent = (diff / previous) * 100
        if diff > 0:
            trend = f"📈 Рост на {abs(diff):,.2f} ({abs(percent):.1f}%)"
            advice = "⚠️ Расходы растут! Стоит пересмотреть траты."
        else:
            trend = f"📉 Снижение на {abs(diff):,.2f} ({abs(percent):.1f}%)"
            advice = "🎉 Отлично! Так держать!"
    else:
        trend = "Нет данных для сравнения"
        advice = "Продолжайте записывать траты."
    
    text = (
        "📅 *Отчёт за месяц*\n\n"
        f"🔹 Прошлый месяц: {previous:,.2f}\n"
        f"🔸 Этот месяц: {current:,.2f}\n\n"
        f"{trend}\n\n"
        f"{advice}"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(lambda message: message.text == "🎯 Цели")
async def show_goals(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT id, title, target_amount, current_amount FROM goals WHERE user_id = ?", (user_id,))
    goals = cursor.fetchall()
    if not goals:
        text = "🎯 *Финансовые цели*\n\nУ тебя пока нет целей.\nСоздай первую — например, «Отпуск» или «Новый телефон»!"
    else:
        text = "🎯 *Твои финансовые цели:*\n\n"
        for g in goals:
            gid, title, target, current = g
            percent = min(100, (current / target) * 100) if target > 0 else 0
            bars = int(percent // 10)
            progress = "█" * bars + "░" * (10 - bars)
            text += f"📌 *{title}*\n[{progress}] {percent:.1f}%\n{current:,.2f} / {target:,.2f}\n\n"

    await message.answer(text, parse_mode="Markdown", reply_markup=goals_keyboard())

@dp.callback_query_handler(lambda c: c.data == "new_goal")
async def cb_new_goal(callback: types.CallbackQuery):
    await callback.message.answer("Как назовём цель? (например, «Отпуск в Турции»)")
    await Form.set_goal_title.set()
    await callback.answer()

@dp.message_handler(state=Form.set_goal_title)
async def goal_title(message: types.Message, state: FSMContext):
    await state.update_data(goal_title=message.text.strip()[:50])
    await message.answer("Сколько нужно накопить? (например, 100000)")
    await Form.set_goal_amount.set()

@dp.message_handler(state=Form.set_goal_amount)
async def goal_amount(message: types.Message, state: FSMContext):
    try:
        target = float(message.text.replace(",", "."))
        data = await state.get_data()
        title = data.get('goal_title', 'Без названия')
        user_id = message.from_user.id
        
        cursor.execute("INSERT INTO goals (user_id, title, target_amount) VALUES (?, ?, ?)", (user_id, title, target))
        conn.commit()
        
        await message.answer(f"🎯 Цель «{title}» на {target:,.2f} создана!", reply_markup=main_keyboard())
        await state.finish()
    except ValueError:
        await message.answer("Пожалуйста, введите число.")

@dp.callback_query_handler(lambda c: c.data == "add_money")
async def cb_add_money(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT id, title FROM goals WHERE user_id = ?", (user_id,))
    goals = cursor.fetchall()
    
    if not goals:
        await callback.message.answer("Сначала создайте цель!")
        await callback.answer()
        return
    
    text = "Куда добавить деньги?\n\n"
    markup = InlineKeyboardMarkup()
    for gid, title in goals:
        text += f"• {title}\n"
        markup.add(InlineKeyboardButton(f"💰 {title}", callback_data=f"add_to_{gid}"))
    
    await callback.message.answer(text, reply_markup=markup)
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
        row = cursor.fetchone()
        title, target, current = row
        percent = min(100, (current / target) * 100) if target > 0 else 0
        
        await message.answer(
            f"✅ Добавлено {amount:,.2f} к цели «{title}»\n\n"
            f"Прогресс: {current:,.2f} / {target:,.2f} ({percent:.1f}%)",
            reply_markup=main_keyboard()
        )
        await state.finish()
    except ValueError:
        await message.answer("Введите число.")
@dp.message_handler(lambda message: message.text == "💡 Советы")
async def show_tips(message: types.Message):
    user_id = message.from_user.id
    now = datetime.now()
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    cursor.execute(
        "SELECT category, SUM(amount) FROM transactions WHERE user_id = ? AND created_at >= ? GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        (user_id, first_day.strftime("%Y-%m-%d %H:%M:%S"))
    )
    row = cursor.fetchone()

    if not row:
        await message.answer("💡 Начните вносить расходы, чтобы получать советы!")
        return

    top_cat, top_amount = row
    savings_30 = top_amount * 0.30
    yearly_savings = savings_30 * 12

    tips = [
        "Попробуй готовить дома вместо кафе — экономия до 50%.",
        "Отмени подписки, которыми не пользуешься.",
        "Перед покупкой подожди 24 часа — часто желание пропадает.",
        "Используй кэшбэк-карты для повседневных трат.",
        "Планируй крупные покупки заранее и ищи скидки."
    ]
    import random
    tip = random.choice(tips)

    text = (
        "💡 *Совет по экономии*\n\n"
        f"📊 Крупнейшая трата: *{top_cat}* ({top_amount:,.2f})\n\n"
        f"🔹 Сократив её на 30%, сэкономишь *{savings_30:,.2f}* в месяц.\n"
        f"🚀 За год это *{yearly_savings:,.2f}*!\n\n"
        f"💡 *Совет:* {tip}"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler()
async def process_expense(message: types.Message):
    if not message.text:
        return

    text = message.text.strip()
    
    # Пропускаем команды и кнопки
    if text.startswith('/') or text in ["📊 Баланс", "📈 Аналитика", "🎯 Цели", "💡 Советы", "📅 Отчёт за месяц", "⚙️ Настройки"]:
        return

    parts = text.split()
    
    if len(parts) < 2:
        await message.answer("Напишите в формате: Кофе 200")
        return

    try:
        amount = float(parts[-1].replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Не вижу сумму. Напишите: Кофе 200")
        return

    desc = " ".join(parts[:-1])
    user_id = message.from_user.id

    category = "📦 Разное"
    for key, cat in DEFAULT_CATEGORIES.items():
        if key in desc.lower():
            category = cat
            break

    cursor.execute(
        "INSERT INTO transactions (user_id, amount, category, description) VALUES (?, ?, ?, ?)",
        (user_id, amount, category, desc)
    )
    conn.commit()

    cursor.execute("SELECT budget FROM users WHERE user_id = ?", (user_id,))
    b_row = cursor.fetchone()
    budget = b_row[0] if b_row else 0

    now = datetime.now()
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cursor.execute(
        "SELECT SUM(amount) FROM transactions WHERE user_id = ? AND created_at >= ?",
        (user_id, first_day.strftime("%Y-%m-%d %H:%M:%S"))
    )
    spent_row = cursor.fetchone()
    spent = spent_row[0] if spent_row and spent_row[0] else 0

    response = (
        f"✅ *Записано!*\n\n"
        f"📌 {desc}\n"
        f"💵 {amount:,.2f}\n"
        f"🏷 {category}\n\n"
    )

    if budget > 0:
        remaining = budget - spent
        if remaining < 0:
            response += f"⚠️ Вы превысили бюджет на {abs(remaining):,.2f}!"
        elif remaining < budget * 0.2:
            response += f"⚠️ Осталось всего {remaining:,.2f} (меньше 20% бюджета)!"
        else:
            response += f"📉 Остаток: {remaining:,.2f}"

    await message.answer(response, parse_mode="Markdown")

if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)