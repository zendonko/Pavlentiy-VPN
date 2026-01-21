import asyncio
import uuid
import hashlib
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# Импорт твоих модулей
from xui_api import XUIManager
from database import Database

DB_URL = "psql 'postgresql://neondb_owner:npg_LkspXe6fI8jT@ep-little-dew-abwfu4f9-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require'"

db = Database(DB_URL)
# --- НАСТРОЙКИ FREEKASSA ---
MERCHANT_ID = "69272"
SECRET_1 = "vhbFjXIE1^HCA.X"
SECRET_2 = "p6lYja5(OH-yHs]" # Секретное слово 2 для проверки оплаты

# --- НАСТРОЙКИ БОТА И X-UI ---
BOT_TOKEN = "8551427639:AAGIpKZpos5Vo4LQ36G2cYJai6zLtt6g-L0"
XUI_URL = "https://vpn.zendonko.work.gd/W9XDms4n5Imt"
XUI_USER = "kXDyzEGYOa"
XUI_PASS = "ie2WG8oHCJ"

# Параметры Reality
SERVER_DOMAIN = "vpn.zendonko.work.gd"
PORT = 443 
PBK = "PeqZrXEpkounGNStMh77xxL6oILc_ZG93-ofIlvLRiU"
SID = "c3fd898a1e690531"
SNI = "sub.zendonko.work.gd"

# Инициализация
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = Database()
xui = XUIManager(XUI_URL, XUI_USER, XUI_PASS)

# --- ЛОГИКА ОПЛАТЫ ---

def get_freekassa_url(amount, order_id):
    currency = "RUB"
    # Подпись: merchant_id:amount:secret_word_1:currency:order_id
    sign_str = f"{MERCHANT_ID}:{amount}:{SECRET_1}:{currency}:{order_id}"
    sign = hashlib.md5(sign_str.encode()).hexdigest()
    return f"https://pay.freekassa.ru/?m={MERCHANT_ID}&oa={amount}&currency={currency}&o={order_id}&s={sign}"

def buy_kb(user_id):
    url = get_freekassa_url(300, user_id) # Цена 300 руб
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить 300₽ (FreeKassa)", url=url)]
    ])

# --- ХЕНДЛЕРЫ БОТА ---

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Привет! Нажми кнопку ниже, чтобы оплатить подписку на 30 дней.\n"
        "После оплаты ключ придет автоматически.", 
        reply_markup=buy_kb(message.from_user.id)
    )

# --- ОБРАБОТКА ВЕБХУКА ОПЛАТЫ ---

async def handle_freekassa_webhook(request):
    data = await request.post()
    
    # Получаем данные от FreeKassa
    m_id = data.get('MERCHANT_ID')
    amount = data.get('AMOUNT')
    order_id = data.get('MERCHANT_ORDER_ID') # Здесь наш user_id
    fk_sign = data.get('SIGN')

    # Проверка подписи (Секретное слово 2): merchant_id:amount:secret_word_2:order_id
    sign_check_str = f"{m_id}:{amount}:{SECRET_2}:{order_id}"
    my_sign = hashlib.md5(sign_check_str.encode()).hexdigest()

    if my_sign == fk_sign:
        user_id = int(order_id)
        new_uuid = str(uuid.uuid4())
        email = f"tg_{user_id}"
        
        # 1. Добавляем в панель X-UI
        success = await xui.add_client(inbound_id=1, email=email, client_uuid=new_uuid)
        
        if success:
            # 2. Сохраняем в БД
            await db.add_or_update_user(user_id, new_uuid, email)
            
            # 3. Собираем ссылку
            vless_link = (
                f"vless://{new_uuid}@{SERVER_DOMAIN}:{PORT}?"
                f"security=reality&sni={SNI}&fp=chrome&pbk={PBK}&sid={SID}"
                f"&type=tcp&headerType=none&flow=xtls-rprx-vision#Павлентий_VPN"
            )
            
            await bot.send_message(
                user_id, 
                f"✅ **Оплата прошла!**\n\nТвой ключ доступа:\n`{vless_link}`", 
                parse_mode="Markdown"
            )
            return web.Response(text='YES') # Ответ для FreeKassa
    
    return web.Response(text='error', status=400)

# --- ЗАПУСК ---

async def main():
    await db.setup()
    
    # Запуск веб-сервера для приема платежей
    app = web.Application()
    app.router.add_post('/freekassa/webhook', handle_freekassa_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    
    logging.info("Webhook server started on port 8080")
    
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
