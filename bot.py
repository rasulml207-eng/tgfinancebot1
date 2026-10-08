import asyncio
import logging
import os
import re
import requests
from datetime import datetime
from collections import defaultdict
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Получаем токен из переменных окружения
TOKEN = os.getenv("8802150498:AAH8-jB4ATF6X9n5vq3n-ul6MOJvStWR-1Q")
if not TOKEN:
    raise ValueError("Токен BOT_TOKEN не найден в переменных окружения Railway!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Хранилище данных (в памяти, сбрасывается при перезапуске) ---
# Структура: {user_id: [{'type': 'income/expense', 'amount': 500, 'category': 'еда', 'date': '...'}]}
user_history = defaultdict(list)

# --- Вспомогательные функции ---

def get_currency_rates():
    """Получает актуальные курсы валют к рублю."""
    try:
        # Используем бесплатный API
        response = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5)
        data = response.json()
        usd = data['rates']['RUB']
        
        response_eur = requests.get("https://api.exchangerate-api.com/v4/latest/EUR", timeout=5)
        data_eur = response_eur.json()
        eur = data_eur['rates']['RUB']
        
        return f"💵 <b>Курс доллара:</b> {usd:.2f} ₽\n💶 <b>Курс евро:</b> {eur:.2f} ₽"
    except Exception as e:
        logging.error(f"Ошибка получения курсов: {e}")
        return "⚠️ Не удалось получить курсы валют. Попробуйте позже."

def get_balance(user_id):
    """Считает текущий баланс пользователя."""
    total = 0
    for op in user_history[user_id]:
        if op['type'] == 'income':
            total += op['amount']
        else:
            total -= op['amount']
    return total

def format_history(user_id, limit=5):
    """Форматирует последние операции для вывода."""
    if not user_history[user_id]:
        return "📭 История пуста. Добавьте первую операцию!"
    
    # Берем последние limit операций и переворачиваем (сначала новые)
    recent = user_history[user_id][-limit:][::-1]
    result = "<b>📜 Последние операции:</b>\n\n"
    
    for op in recent:
        sign = "➕" if op['type'] == 'income' else "➖"
        result += f"{sign} <b>{op['amount']} ₽</b> — {op['category']}\n"
        result += f"   <i>{op['date']}</i>\n\n"
    
    return result

# --- Обработчики команд ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Я — твой личный финансовый помощник. Вот что я умею:\n\n"
        "🔹 <b>Добавить доход:</b> <code>+500 зарплата</code>\n"
        "🔹 <b>Добавить расход:</b> <code>-300 еда</code>\n"
        "🔹 <b>Показать баланс:</b> /balance\n"
        "🔹 <b>История операций:</b> /history\n"
        "🔹 <b>Курсы валют:</b> /rates\n"
        "🔹 <b>Очистить историю:</b> /reset\n\n"
        "Просто напиши мне сумму с плюсом или минусом, и я всё запишу!",
        parse_mode="HTML"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 <b>Помощь по командам:</b>\n\n"
        "• <code>+1000</code> — добавить доход (можно указать категорию: <code>+1000 аванс</code>)\n"
        "• <code>-500</code> — добавить расход (например: <code>-500 продукты</code>)\n"
        "• /balance — показать текущий баланс\n"
        "• /history — последние 5 операций\n"
        "• /rates — курсы доллара и евро\n"
        "• /reset — удалить все ваши записи (осторожно!)",
        parse_mode="HTML"
    )

@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    user_id = message.from_user.id
    bal = get_balance(user_id)
    
    if bal > 0:
        emoji = "🟢"
    elif bal < 0:
        emoji = "🔴"
    else:
        emoji = "⚪"
        
    await message.answer(
        f"{emoji} <b>Твой текущий баланс:</b>\n\n"
        f"<b>{bal} ₽</b>",
        parse_mode="HTML"
    )
@dp.message(Command("history"))
async def cmd_history(message: types.Message):
    user_id = message.from_user.id
    history_text = format_history(user_id)
    await message.answer(history_text, parse_mode="HTML")

@dp.message(Command("rates"))
async def cmd_rates(message: types.Message):
    await message.answer("⏳ Загружаю актуальные курсы...")
    rates = get_currency_rates()
    await message.answer(rates, parse_mode="HTML")

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    user_id = message.from_user.id
    user_history[user_id].clear()
    await message.answer("🧹 История операций очищена. Начинаем с чистого листа!")

# --- Главный обработчик всех текстовых сообщений ---

@dp.message()
async def handle_message(message: types.Message):
    text = message.text.strip()
    user_id = message.from_user.id
    current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    # Ищем шаблон: знак + или -, за которым идут цифры, и опционально текст (категория)
    # Пример: "+500 еда" или "-300" или "+ 1000 зарплата"
    match = re.match(r'^([+-])\s*(\d+)\s*(.*)$', text)
    
    if match:
        sign = match.group(1)
        amount = int(match.group(2))
        category = match.group(3).strip() if match.group(3).strip() else ("Доход" if sign == '+' else "Расход")
        
        # Определяем тип операции
        op_type = 'income' if sign == '+' else 'expense'
        
        # Сохраняем операцию
        user_history[user_id].append({
            'type': op_type,
            'amount': amount,
            'category': category,
            'date': current_date
        })
        
        # Формируем красивый ответ
        if op_type == 'income':
            emoji = "✅"
            action = "Доход"
        else:
            emoji = "💸"
            action = "Расход"
            
        new_balance = get_balance(user_id)
        
        await message.answer(
            f"{emoji} <b>{action} добавлен!</b>\n\n"
            f"💰 Сумма: <b>{amount} ₽</b>\n"
            f"📁 Категория: <b>{category}</b>\n"
            f"📅 Дата: {current_date}\n\n"
            f"📊 <b>Текущий баланс:</b> {new_balance} ₽",
            parse_mode="HTML"
        )
        
    elif text.startswith('/'):
        # Если это неизвестная команда
        await message.answer("🤔 Я не знаю такой команды. Напиши /help, чтобы увидеть список доступных команд.")
        
    else:
        # Если это просто текст, не похожий на операцию
        await message.answer(
            "🤔 Я не понял твоё сообщение.\n\n"
            "Чтобы добавить операцию, напиши сумму с плюсом или минусом:\n"
            "• <code>+1000 зарплата</code> — доход\n"
            "• <code>-500 продукты</code> — расход\n\n"
            "Или используй /help для списка команд.",
            parse_mode="HTML"
        )

# --- Запуск бота ---

async def main():
    print("Бот запущен и работает...")
    # Удаляем вебхуки (на случай, если они были установлены) и запускаем polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
