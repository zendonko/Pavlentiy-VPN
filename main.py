import asyncio
import uuid
import hashlib
import os
import logging
import time
import hmac
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import Database
from xui_api import XUIManager

# --- КОНФИГУРАЦИЯ ---
# Замени значения в кавычках на свои данные, если они отличаются
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8551427639:AAGIpKZpos5Vo4LQ36G2cYJai6zLtt6g-L0")
DB_URL = os.environ.get("DATABASE_URL")
SUPPORT_USER = "@gleynz" 
DOWNLOAD_URL = "https://disk.yandex.ru/d/H0tH71PepUsD7g"

# Lava API (Project ID и Secret Key берешь из кабинета Lava.ru)
LAVA_PROJECT_ID = "твой_project_id" 
LAVA_SECRET_KEY = "твой_secret_key" 

# X-UI Config (Твои данные панели)
XUI_URL = "https://vpn.zendonko.work.gd/W9XDms4n5Imt"
XUI_USER = "kXDyzEGYOa"
XUI_PASS = "ie2WG8oHCJ"

# Настройки Reality
SERVER_DOMAIN = "vpn.zendonko.work.gd"
PBK = "PeqZrXEpkounGNStMh77xxL6oILc_ZG93-ofIlvLRiU"
SID = "c3fd898a1e690531"
SNI = "sub.zendonko.work.gd"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = Database(DB_URL)
xui = XUIManager(XUI_URL, XUI_USER, XUI_PASS)

# --- КЛАВИАТУРЫ ---
def main_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Купить VPN (30 дней) - 150₽", url=get_lava_pay_url(user_id))],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="check_profile")],
        [InlineKeyboardButton(text="📥 Скачать приложение", url=DOWNLOAD_URL)],
        [InlineKeyboardButton(text="📖 Инструкция", url="https://telegra.ph/Instrukciya-k-podklyucheniyu-Pavlentiy-VPN-01-21")]
    ])

# --- ЛОГИКА ОПЛАТЫ LAVA ---
def get_lava_pay_url(user_id):
    amount = 150.00
    order_id = f"{user_id}_{int(time.time())}"
    
    # Формирование подписи HMAC-SHA256 для Lava
    sorted_payload = f"orderId={order_id}&shopId={LAVA_PROJECT_ID}&sum={amount:.2f}"
    signature = hmac.new(
        LAVA_SECRET_KEY.encode(),
        sorted_payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return f"https://lava.ru/invoice/create?shopId={LAVA_PROJECT_ID}&sum={amount}&orderId={order_id}&signature={signature}"

# --- ХЕНДЛЕРЫ БОТА ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 **Добро пожаловать в ПавЛюций VPN!**\n\n"
        "Скоростной и безопасный доступ через протокол VLESS Reality.\n"
        "Выберите действие в меню ниже:",
        reply_markup=main_kb(message.from_user.id), 
        parse_mode="Markdown"
    )

@dp.message(Command("profile"))
@dp.callback_query(F.data == "check_profile")
async def show_profile(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    user_data = await db.get_user_status(user_id)
    is_cb = isinstance(event, types.CallbackQuery)
    target = event.message if is_cb else event

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="check_profile")],
        [InlineKeyboardButton(text="💎 Продлить подписку", url=get_lava_pay_url(user_id))],
        [InlineKeyboardButton(text="📥 Скачать клиент", url=DOWNLOAD_URL)]
    ])

    if not user_data:
        text = (f"👤 **Профиль**\n\n🆔 ID: `{user_id}`\n"
                f"📊 Статус: ⚪️ Не активен\n⏳ Осталось: **0 дней**")
    else:
        now = int(time.time())
        diff = user_data['expiry_date'] - now
        status = "✅ Активна" if diff > 0 else "❌ Истекла"
        rem = f"{max(0, diff // 86400)} дн. {max(0, (diff % 86400) // 3600)} ч."
        date_str = datetime.fromtimestamp(user_data['expiry_date']).strftime('%d.%m.%Y %H:%M')
        text = (f"👤 **Профиль**\n\n🆔 ID: `{user_id}`\n📊 Статус: {status}\n"
                f"⏳ Осталось: **{rem}**\n📅 До: {date_str}")

    if is_cb:
        try:
            await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except:
            await event.answer()
    else:
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")

# --- WEB И WEBHOOKS ---
async def handle_lava_webhook(request):
    try:
        data = await request.json()
        # Проверяем статус успешной оплаты
        if data.get('status') in ['success', 200, 'paid']:
            order_id = data.get('orderId')
            user_id = int(order_id.split('_')[0])
            u_uuid = str(uuid.uuid4())
            email = f"tg_{user_id}"
            
            if await xui.add_client(1, email, u_uuid):
                await db.add_or_update_user(user_id, u_uuid, email)
                link = f"vless://{u_uuid}@{SERVER_DOMAIN}:443?security=reality&sni={SNI}&fp=chrome&pbk={PBK}&sid={SID}&type=tcp&headerType=none&flow=xtls-rprx-vision#ПавЛюций_VPN"
                
                success_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📥 Скачать приложение", url=DOWNLOAD_URL)]
                ])
                await bot.send_message(
                    user_id, 
                    f"✅ **Оплата прошла успешно!**\n\nВаш ключ:\n`{link}`\n\nСкопируйте его и вставьте в приложение.",
                    reply_markup=success_kb,
                    parse_mode="Markdown"
                )
                return web.Response(text='OK')
    except Exception as e:
        logging.error(f"Webhook error: {e}")
    return web.Response(text='error', status=400)

async def index_page(request):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><title>ПавЛюций VPN</title></head>
    <body style='font-family:sans-serif;text-align:center;padding:50px;'>
        <h1>ПавЛюций VPN</h1>
        <p>Персональный VPN сервис на базе Reality.</p>
        <p><a href='https://t.me/pavlentiyVPN_bot' style='color:#0088cc;text-decoration:none;font-weight:bold;'>Открыть Telegram Бота</a></p>
        <hr style='max-width:300px;margin:20px auto;'>
        <p style='font-size:0.9em;color:#666;'>Поддержка: {SUPPORT_USER}</p>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

async def main():
    await db.setup()
    
    # Планировщик проверки истекших подписок
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: asyncio.create_task(check_expired()), "interval", minutes=15)
    scheduler.start()

    app = web.Application()
    
    # --- МАРШРУТЫ (ROUTES) ---
    app.router.add_get('/', index_page)
    app.router.add_get('/ping', lambda r: web.Response(text="OK"))
    
    # Верификация Lava (тот самый файл)
    app.router.add_get('/lava-verify_f455c369be8691b2.html', lambda r: web.Response(text="lava-verify_f455c369be8691b2"))
    
    # Платежный вебхук
    app.router.add_post('/lava/webhook', handle_lava_webhook)
    
    # Редирект после оплаты
    app.router.add_get('/success', lambda r: web.HTTPFound('https://t.me/pavlentiyVPN_bot'))
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Запуск сервера на порту Render
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    
    # Запуск бота
    await dp.start_polling(bot)

async def check_expired():
    expired = await db.get_expired_users()
    for row in expired:
        if await xui.delete_client(1, row['email']):
            await db.set_inactive(row['user_id'])
            try:
                await bot.send_message(row['user_id'], "🔴 Ваша подписка на VPN истекла. Доступ ограничен.")
            except:
                pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
