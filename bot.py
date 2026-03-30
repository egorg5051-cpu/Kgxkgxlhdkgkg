import os
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from dotenv import load_dotenv

load_dotenv()

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(bot)

# Получаем ID администраторов из .env
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://твой-сайт.com")

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('bot_stats.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            start_date TIMESTAMP,
            last_active TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Проверка на администратора
def is_admin(user_id):
    return user_id in ADMIN_IDS

# Функция для добавления пользователя
def add_user(user_id, username, first_name, last_name):
    conn = sqlite3.connect('bot_stats.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, start_date, last_active)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name, datetime.now(), datetime.now()))
    
    conn.commit()
    conn.close()

# Функция для обновления активности
def update_activity(user_id):
    conn = sqlite3.connect('bot_stats.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET last_active = ? WHERE user_id = ?', (datetime.now(), user_id))
    conn.commit()
    conn.close()

# Функция для получения статистики
def get_stats():
    conn = sqlite3.connect('bot_stats.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE date(last_active) = date("now")')
    today_active = cursor.fetchone()[0]
    
    conn.close()
    return total_users, today_active

# Клавиатура администратора (Reply Keyboard - над клавиатурой)
def get_admin_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("📊 Статистика"),
        KeyboardButton("📢 Сделать рассылку")
    )
    keyboard.add(KeyboardButton("🔙 Выйти из админ-панели"))
    return keyboard

# Inline кнопка GO (под сообщением) - ТОЛЬКО GO, никаких других кнопок
def get_go_button():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(
            text="🎮 GO",
            web_app=WebAppInfo(url=WEB_APP_URL)
        )
    )
    return keyboard

# функция отправки старт-сообщения
async def send_start(message: types.Message):
    name = message.from_user.first_name or "друг"
    
    # Добавляем пользователя в базу
    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    # Обновляем активность
    update_activity(message.from_user.id)

    # Отправляем сообщение с inline-кнопкой GO
    await message.answer(
        f"""👋 Привет, {name}!

Нажми на кнопку ниже, чтобы испытать удачу и выиграть редкие подарки Telegram

/terms - условия использования""",
        reply_markup=get_go_button()
    )

# /start
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await send_start(message)

# /terms
@dp.message_handler(commands=['terms'])
async def terms(message: types.Message):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(
            text="📄 Политика конфиденциальности",
            url=f"{WEB_APP_URL}/privacy"
        )
    )
    keyboard.add(
        InlineKeyboardButton(
            text="📄 Условия использования",
            url=f"{WEB_APP_URL}/terms"
        )
    )

    await message.answer(
        "Ознакомьтесь с условиями использования нашего приложения прежде чем продолжить.",
        reply_markup=keyboard
    )

# /admin - команда для входа в админ-панель
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к админ-панели!")
        return
    
    total_users, today_active = get_stats()
    
    await message.answer(
        f"👑 **Админ-панель**\n\n"
        f"📊 **Статистика:**\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🌟 Активны сегодня: {today_active}\n\n"
        f"Выберите действие:",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown"
    )

# Обработка кнопок админ-панели (Reply Keyboard)
@dp.message_handler(lambda message: message.text in ["📊 Статистика", "📢 Сделать рассылку", "🔙 Выйти из админ-панели"])
async def admin_buttons(message: types.Message):
    # Проверяем, админ ли пользователь
    if not is_admin(message.from_user.id):
        await send_start(message)
        return
    
    if message.text == "📊 Статистика":
        total_users, today_active = get_stats()
        
        # Получаем последних 5 пользователей
        conn = sqlite3.connect('bot_stats.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, first_name, username, start_date FROM users ORDER BY start_date DESC LIMIT 5')
        recent_users = cursor.fetchall()
        conn.close()
        
        stats_text = f"📊 **Подробная статистика**\n\n"
        stats_text += f"👥 Всего пользователей: {total_users}\n"
        stats_text += f"🌟 Активны сегодня: {today_active}\n\n"
        stats_text += f"🆕 **Последние 5 пользователей:**\n"
        
        for user in recent_users:
            stats_text += f"• {user[1]} (@{user[2] or 'нет юзернейма'}) - {user[3][:10]}\n"
        
        await message.answer(stats_text, parse_mode="Markdown", reply_markup=get_admin_keyboard())
    
    elif message.text == "📢 Сделать рассылку":
        await message.answer(
            "📢 **Режим рассылки**\n\n"
            "Отправьте мне фото с подписью или просто текст для рассылки.\n"
            "Кнопка **GO** будет автоматически добавлена внизу сообщения.\n\n"
            "После отправки я попрошу подтверждение.\n\n"
            "Для выхода из режима рассылки нажмите 🔙 Выйти из админ-панели",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
        # Устанавливаем состояние ожидания рассылки
        dp.data['waiting_for_broadcast'] = message.from_user.id
    
    elif message.text == "🔙 Выйти из админ-панели":
        await message.answer(
            "🔙 Вы вышли из админ-панели",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await send_start(message)

# Обработка рассылки (фото + текст или просто текст)
@dp.message_handler(content_types=['photo', 'text'])
async def handle_broadcast(message: types.Message):
    # Проверяем, ожидает ли админ рассылку
    if dp.data.get('waiting_for_broadcast') != message.from_user.id:
        return
    
    # Проверяем, админ ли пользователь
    if not is_admin(message.from_user.id):
        return
    
    # Сохраняем контент для рассылки
    broadcast_content = {}
    
    if message.photo:
        broadcast_content['type'] = 'photo'
        broadcast_content['photo'] = message.photo[-1].file_id
        broadcast_content['caption'] = message.caption or ""
    elif message.text:
        broadcast_content['type'] = 'text'
        broadcast_content['text'] = message.text
    
    # Сохраняем в dp.data
    dp.data['broadcast_content'] = broadcast_content
    
    # Показываем превью с inline-кнопками подтверждения
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Отправить", callback_data="confirm_broadcast"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel_broadcast")
    )
    
    # Показываем превью того, как будет выглядеть рассылка
    if broadcast_content['type'] == 'photo':
        # Сначала показываем как будет выглядеть сообщение с кнопкой GO
        await message.answer_photo(
            broadcast_content['photo'],
            caption=f"📢 **Превью рассылки:**\n\n{broadcast_content['caption']}\n\n⬇️ Внизу будет кнопка GO ⬇️",
            reply_markup=get_go_button(),
            parse_mode="Markdown"
        )
        # Затем спрашиваем подтверждение
        await message.answer(
            "✅ Отправить эту рассылку всем пользователям?",
            reply_markup=keyboard
        )
    else:
        # Сначала показываем как будет выглядеть сообщение с кнопкой GO
        await message.answer(
            f"📢 **Превью рассылки:**\n\n{broadcast_content['text']}\n\n⬇️ Внизу будет кнопка GO ⬇️",
            reply_markup=get_go_button(),
            parse_mode="Markdown"
        )
        # Затем спрашиваем подтверждение
        await message.answer(
            "✅ Отправить эту рассылку всем пользователям?",
            reply_markup=keyboard
        )
    
    # Удаляем состояние ожидания
    del dp.data['waiting_for_broadcast']

# Обработка подтверждения рассылки
@dp.callback_query_handler(lambda call: call.data in ['confirm_broadcast', 'cancel_broadcast'])
async def broadcast_confirmation(call: types.CallbackQuery):
    # Проверяем, админ ли пользователь
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    
    if call.data == 'cancel_broadcast':
        await call.message.edit_text("❌ Рассылка отменена")
        await call.answer()
        return
    
    # Получаем всех пользователей
    conn = sqlite3.connect('bot_stats.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    conn.close()
    
    broadcast_content = dp.data.get('broadcast_content')
    if not broadcast_content:
        await call.message.edit_text("❌ Ошибка: контент для рассылки не найден")
        return
    
    # Кнопка GO для рассылки (ТОЛЬКО GO, как на скриншоте)
    go_button = get_go_button()
    
    # Отправляем рассылку
    success_count = 0
    for user in users:
        try:
            if broadcast_content['type'] == 'photo':
                await bot.send_photo(
                    user[0],
                    broadcast_content['photo'],
                    caption=broadcast_content['caption'],
                    reply_markup=go_button  # Только кнопка GO под сообщением
                )
            else:
                await bot.send_message(
                    user[0],
                    broadcast_content['text'],
                    reply_markup=go_button  # Только кнопка GO под сообщением
                )
            success_count += 1
        except Exception as e:
            print(f"Ошибка отправки пользователю {user[0]}: {e}")
    
    # Сообщаем админу о результате
    await call.message.edit_text(
        f"✅ **Рассылка завершена!**\n\n"
        f"📊 **Статистика:**\n"
        f"👥 Отправлено: {success_count}/{len(users)}\n"
        f"❌ Ошибок: {len(users) - success_count}\n\n"
        f"🎮 Кнопка GO была добавлена к каждому сообщению",
        parse_mode="Markdown"
    )
    
    # Очищаем данные рассылки
    if 'broadcast_content' in dp.data:
        del dp.data['broadcast_content']
    await call.answer()

# Ловит только не команды (для обычных пользователей)
@dp.message_handler(lambda message: not message.text.startswith('/') and message.text not in ["📊 Статистика", "📢 Сделать рассылку", "🔙 Выйти из админ-панели"])
async def all_messages(message: types.Message):
    # Обновляем активность пользователя
    update_activity(message.from_user.id)
    await send_start(message)

if __name__ == "__main__":
    # Проверяем наличие необходимых переменных
    if not os.getenv("BOT_TOKEN"):
        print("❌ Ошибка: BOT_TOKEN не найден в .env файле!")
        exit(1)
    
    if not ADMIN_IDS:
        print("⚠️ Предупреждение: ADMIN_IDS не указан в .env файле!")
    
    # Инициализируем словарь для хранения временных данных
    dp.data = {}
    print("🚀 Бот запущен")
    print(f"👥 Администраторы: {ADMIN_IDS}")
    print(f"🌐 Web App URL: {WEB_APP_URL}")
    executor.start_polling(dp, skip_updates=True)
