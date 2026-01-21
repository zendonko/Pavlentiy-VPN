import asyncio
import uuid
import hashlib
import os
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import Database
from xui_api import XUIManager

# --- КОНФИГУРАЦИЯ ---
# Пытаемся взять из переменных окружения Render, если нет - берем дефолт
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8551427639:AAGIpKZpos5Vo4LQ36G2cYJai6zLtt6g-L0")
DB_URL = os.environ.get("psql 'postgresql://neondb_owner:npg_LkspXe6fI8jT@ep-little-dew-abwfu4f9-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require'") # Ссылка от Neon.tech

XUI_URL = "https://vpn.zendonko.work.gd/W9XDms4n5Imt"
XUI_USER = "kXDyzEGYOa"
XUI_PASS = "ie2WG8oHCJ"

# FreeKassa (новые ключи)
MERCHANT_ID = "69272"
SECRET_1 = "Q3SATwU%AgCbOo*"
SECRET_2 = "1UW8e3g@o_doMfo"

# Reality
SERVER_DOMAIN = "vpn.zendonko.work.gd"
PBK = "PeqZrXEpkounGNStMh77xxL6oILc_ZG93-ofIlvLRiU"
SID = "c3fd898a1e690531"
SNI = "sub.zendonko.work.gd"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ИСПРАВЛЕНО: передаем DB_URL в конструктор
if not DB_URL:
    logging.error("DATABASE_URL не найдена в переменных окружения!")
db = Database(DB_URL)

xui = XUIManager(XUI_URL, XUI_USER, XUI_PASS)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_pay_url(user_id):
    amount = "300"
    currency = "RUB"
    sign_str = f"{MERCHANT_ID}:{amount}:{SECRET_1}:{currency}:{user_id}"
    sign = hashlib.md5(sign_str.encode()).hexdigest()
    return f"https://pay.freekassa.ru/?m={MERCHANT_ID}&oa={amount}&currency={currency}&o={user_id}&s={sign}"

@dp.message(Command("start"))
async def start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💎 Купить VPN - 300₽", url=get_pay_url(message.from_user.id))
    ]])
    await message.answer("Привет! После оплаты доступ активируется автоматически в течение пары минут.", reply_markup=kb)

# --- WEBHOOKS & REDIRECTS ---
async def handle_webhook(request):
    try:
        data = await request.post()
        sign_check = hashlib.md5(f"{data.get('MERCHANT_ID')}:{data.get('AMOUNT')}:{SECRET_2}:{data.get('MERCHANT_ORDER_ID')}".encode()).hexdigest()
        
        if sign_check == data.get('SIGN'):
            user_id = int(data.get('MERCHANT_ORDER_ID'))
            u_uuid = str(uuid.uuid4())
            email = f"tg_{user_id}"
            
            if await xui.add_client(1, email, u_uuid):
                await db.add_or_update_user(user_id, u_uuid, email)
                link = (f"vless://{u_uuid}@{SERVER_DOMAIN}:443?security=reality&sni={SNI}"
                        f"&fp=chrome&pbk={PBK}&sid={SID}&type=tcp&headerType=none"
                        f"&flow=xtls-rprx-vision#Павлентий_VPN")
                await bot.send_message(user_id, f"✅ Оплата подтверждена!\n\nТвой ключ:\n`{link}`", parse_mode="Markdown")
                return web.Response(text='YES')
    except Exception as e:
        logging.error(f"Ошибка вебхука: {e}")
    return web.Response(text='error', status=400)

async def success_page(request):
    return web.HTTPFound(location='https://t.me/pavlentlyVPN_bot')

async def main():
    # Запуск БД
    await db.setup()
    
    # Запуск планировщика проверок
    scheduler = AsyncIOScheduler()
    # Здесь нужно добавить функцию check_subs, если она тебе нужна
    scheduler.start()

    # Веб-сервер
    app = web.Application()
    app.router.add_post('/freekassa/webhook', handle_webhook)
    app.router.add_get('/success', success_page)
    app.router.add_get('/fail', success_page)
    app.router.add_get('/', lambda r: web.Response(text="VPN Bot is running", content_type='text/html'))
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    
    # Запуск Polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
