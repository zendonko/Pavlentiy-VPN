import asyncio
import uuid
import hashlib
import os
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import Database
from xui_api import XUIManager

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8551427639:AAGIpKZpos5Vo4LQ36G2cYJai6zLtt6g-L0")
DB_URL = os.environ.get("DATABASE_URL")
SUPPORT_USER = "@gleynz" # ВАЖНО: Укажи свой ник для модераторов

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
db = Database(DB_URL)
xui = XUIManager(XUI_URL, XUI_USER, XUI_PASS)

# --- ЛОГИКА ОПЛАТЫ ---
def get_pay_url(user_id):
    amount = "300"
    currency = "RUB"
    sign_str = f"{MERCHANT_ID}:{amount}:{SECRET_1}:{currency}:{user_id}"
    sign = hashlib.md5(sign_str.encode()).hexdigest()
    return f"https://pay.freekassa.ru/?m={MERCHANT_ID}&oa={amount}&currency={currency}&o={user_id}&s={sign}"

# --- ХЕНДЛЕРЫ БОТА ---
@dp.message(Command("start"))
async def start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Купить VPN (30 дней) - 300₽", url=get_pay_url(message.from_user.id))],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="check_profile")]
    ])
    await message.answer(
        "👋 **Добро пожаловать в Pavlently VPN!**\n\n"
        "Мы предоставляем быстрый доступ по протоколу VLESS Reality.\n"
        "• Работает на всех устройствах\n"
        "• Высокая скорость и низкий пинг\n"
        "• Активация сразу после оплаты\n\n"
        "Используйте кнопки ниже для покупки или проверки статуса.",
        reply_markup=kb, parse_mode="Markdown"
    )

@dp.message(Command("profile"))
@dp.callback_query(F.data == "check_profile")
async def show_profile(event: types.Message | types.CallbackQuery):
    # Работаем и с командой, и с кнопкой
    user_id = event.from_user.id
    user_data = await db.get_user_status(user_id)
    
    text_target = event if isinstance(event, types.Message) else event.message

    if not user_data:
        await text_target.answer("У вас пока нет активной подписки. Нажмите /start для покупки.")
        return

    expiry = datetime.fromtimestamp(user_data['expiry_date']).strftime('%d.%m.%Y %H:%M')
    status = "✅ Активна" if user_data['is_active'] else "❌ Истекла"
    
    await text_target.answer(
        f"👤 **Ваш профиль**\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"📊 Статус: {status}\n"
        f"📅 Срок действия: {expiry}\n\n"
        f"Нужна помощь? Пишите {SUPPORT_USER}",
        parse_mode="Markdown"
    )

# --- КРАСИВАЯ СТРАНИЦА ДЛЯ RENDER (WEB) ---
async def index_page(request):
    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pavlently VPN - Сервис личных VPN</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; color: #333; text-align: center; padding: 50px 20px; }}
            .card {{ background: white; max-width: 500px; margin: 0 auto; padding: 30px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
            h1 {{ color: #0088cc; }}
            p {{ line-height: 1.6; color: #666; }}
            .btn {{ display: inline-block; background: #0088cc; color: white; padding: 12px 25px; text-decoration: none; border-radius: 8px; font-weight: bold; margin-top: 20px; transition: 0.3s; }}
            .btn:hover {{ background: #006699; }}
            .footer {{ margin-top: 30px; font-size: 13px; color: #999; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Pavlently VPN</h1>
            <p>Ваш персональный доступ к свободному интернету без ограничений. Используем современный протокол <b>VLESS Reality</b> для максимальной маскировки трафика.</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
            <p>Тариф: <b>300 руб / 30 дней</b></p>
            <a href="https://t.me/pavlentlyVPN_bot" class="btn">Подключиться через Telegram</a>
            <div class="footer">
                Поддержка: {SUPPORT_USER} | Работает на протоколах нового поколения
            </div>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

async def success_page(request):
    return web.HTTPFound(location='https://t.me/pavlentlyVPN_bot')

# --- WEBHOOK ДЛЯ FREEKASSA ---
async def handle_webhook(request):
    try:
        data = await request.post()
        # Проверка: m_id:amount:secret2:order_id
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
                await bot.send_message(user_id, f"✅ **Оплата прошла!**\n\nТвой ключ доступа:\n`{link}`", parse_mode="Markdown")
                return web.Response(text='YES')
    except Exception as e:
        logging.error(f"Webhook error: {e}")
    return web.Response(text='error', status=400)

async def main():
    await db.setup()
    
    app = web.Application()
    app.router.add_get('/', index_page)
    app.router.add_post('/freekassa/webhook', handle_webhook)
    app.router.add_get('/success', success_page)
    app.router.add_get('/fail', success_page)
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
