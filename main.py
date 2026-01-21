import asyncio
import uuid
import hashlib
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import Database
from xui_api import XUIManager

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8551427639:AAGIpKZpos5Vo4LQ36G2cYJai6zLtt6g-L0")
# Прямая проверка переменной
DB_URL = os.environ.get("DATABASE_URL")

XUI_URL = "https://vpn.zendonko.work.gd/W9XDms4n5Imt"
XUI_USER = "kXDyzEGYOa"
XUI_PASS = "ie2WG8oHCJ"

MERCHANT_ID = "69272"
SECRET_1 = "Q3SATwU%AgCbOo*"
SECRET_2 = "1UW8e3g@o_doMfo"

SERVER_DOMAIN = "vpn.zendonko.work.gd"
PBK = "PeqZrXEpkounGNStMh77xxL6oILc_ZG93-ofIlvLRiU"
SID = "c3fd898a1e690531"
SNI = "sub.zendonko.work.gd"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ---
if not DB_URL:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Переменная DATABASE_URL не установлена в настройках Render!")

db = Database(DB_URL)
xui = XUIManager(XUI_URL, XUI_USER, XUI_PASS)

# --- ФУНКЦИИ ---
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
    await message.answer("Привет! После оплаты доступ активируется автоматически.", reply_markup=kb)

async def handle_webhook(request):
    try:
        data = await request.post()
        check_str = f"{data.get('MERCHANT_ID')}:{data.get('AMOUNT')}:{SECRET_2}:{data.get('MERCHANT_ORDER_ID')}"
        if hashlib.md5(check_str.encode()).hexdigest() == data.get('SIGN'):
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
        logging.error(f"Ошибка в вебхуке: {e}")
    return web.Response(text='error', status=400)

async def main():
    await db.setup() # Здесь теперь используется SSL для Neon
    
    app = web.Application()
    app.router.add_post('/freekassa/webhook', handle_webhook)
    app.router.add_get('/', lambda r: web.Response(text="Bot is online"))
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
