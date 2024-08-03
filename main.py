import logging
import pyodbc
import asyncio
from threading import Thread
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types.message import ContentType
from aiogram.utils.exceptions import BotBlocked
import config

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=config.TOKEN)
dp = Dispatcher(bot)

# Подключение к базе данных MS SQL
conn_str = (
    'DRIVER={SQL Server};'
    'SERVER=ВАШ СЕРВЕР;' 
    'DATABASE=ВАША БАЗА;'
    'Trusted_Connection=yes;'
)
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Создание таблицы для хранения подписчиков (если не существует)
cursor.execute('''
    IF OBJECT_ID('subscribers', 'U') IS NULL
    CREATE TABLE subscribers (
        id INT IDENTITY(1,1) PRIMARY KEY,
        chat_id BIGINT UNIQUE
    )
''')
conn.commit()

# Цены
PRICE = types.LabeledPrice(label="Подписка на 1 месяц", amount=500*100)  # в копейках (руб)

# Обработчик команды /start
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    user_first_name = message.from_user.first_name
    await message.reply(f"Привет, {user_first_name} ")
    await message.reply(message.chat.id,"Добро пожаловать! Чтобы подписаться, пожалуйста, оплатите 500 рублей. Отправьте команду /pay чтобы продолжить.")

# Обработчик команды /pay
@dp.message_handler(commands=['pay'])
async def buy(message: types.Message):
    if config.PAYMENTS_TOKEN.split(':')[1] == 'TEST':
        await bot.send_message(message.chat.id, "Тестовый платеж!!!")

    await bot.send_invoice(message.chat.id,
                           title="Подписка на бота",
                           description="Активация подписки на бота на 1 месяц",
                           provider_token=config.PAYMENTS_TOKEN,
                           currency="rub",
                           photo_url="https://www.aroged.com/wp-content/uploads/2022/06/Telegram-has-a-premium-subscription.jpg",
                           photo_width=416,
                           photo_height=234,
                           photo_size=416,
                           is_flexible=False,
                           prices=[PRICE],
                           start_parameter="one-month-subscription",
                           payload="test-invoice-payload")

# Обработчик запроса предварительной проверки (должен быть дан ответ в течение 10 секунд)
@dp.pre_checkout_query_handler(lambda query: True)
async def pre_checkout_query(pre_checkout_q: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

# Обработчик успешного платежа
@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    logging.info("SUCCESSFUL PAYMENT:")
    payment_info = message.successful_payment.to_python()
    for k, v in payment_info.items():
        logging.info(f"{k} = {v}")

    chat_id = message.chat.id
    try:
        cursor.execute('INSERT INTO subscribers (chat_id) VALUES (?)', (chat_id,))
        conn.commit()
        await bot.send_message(message.chat.id,
                               f"Платеж на сумму {message.successful_payment.total_amount // 100} {message.successful_payment.currency} прошел успешно!!!")
        await bot.send_message(message.chat.id, "Спасибо за подписку! Вы будете получать сообщения каждую минуту.")
    except pyodbc.IntegrityError:
        await bot.send_message(message.chat.id, "Вы уже подписаны!")

# Асинхронная функция отправки сообщений по расписанию
async def send_scheduled_message():
    logging.info("Запуск отправки сообщений...")
    cursor.execute('SELECT chat_id FROM subscribers')
    subscribers = cursor.fetchall()
    logging.info(f"Найдено подписчиков: {len(subscribers)}")
    for subscriber in subscribers:
        try:
            logging.info(f"Отправка сообщения подписчику: {subscriber[0]}")
            await bot.send_message(subscriber[0], "ВАШ ТЕКСТ СООБЩЕНИЯ")
            with open('ВАШ ФАЙЛ.docx', 'rb') as doc:
                await bot.send_document(subscriber[0], doc)
        except BotBlocked:
            logging.warning(f"Бот заблокирован пользователем: {subscriber[0]}")
        except Exception as e:
            logging.error(f"Ошибка при отправке сообщения {subscriber[0]}: {e}")

# Планировщик для асинхронных задач
async def scheduler():
    while True:
        await send_scheduled_message()
        await asyncio.sleep(60)

if __name__ == '__main__':
    # Запуск планировщика
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler())

    # Запуск long-polling
    executor.start_polling(dp, skip_updates=True, loop=loop)

    # Закрытие подключения к базе данных при завершении работы бота
    conn.close()



