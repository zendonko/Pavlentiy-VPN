import asyncio
import uuid
import hashlib
import os
import logging
import time
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
SUPPORT_USER = "@gleynz" 
DOWNLOAD_URL = "https://disk.yandex.ru/d/H0tH71PepUsD7g"

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

# Клавиатура главного меню
def main_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Купить VPN (30 дней) - 150₽", url=get_pay_url(user_id))],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="check_profile")],
        [InlineKeyboardButton(text="📥 Скачать приложение", url=DOWNLOAD_URL)],
        [InlineKeyboardButton(text="Инструкция к применению", url="https://telegra.ph/Instrukciya-k-podklyucheniyu-Pavlentiy-VPN-01-21")]
    ])

# --- ЛОГИКА ОПЛАТЫ ---
def get_pay_url(user_id):
    amount = "150"
    currency = "RUB"
    sign = hashlib.md5(f"{MERCHANT_ID}:{amount}:{SECRET_1}:{currency}:{user_id}".encode()).hexdigest()
    return f"https://pay.freekassa.ru/?m={MERCHANT_ID}&oa={amount}&currency={currency}&o={user_id}&s={sign}"

# --- ХЕНДЛЕРЫ БОТА ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 **Добро пожаловать в ПавЛюций VPN!**\n\n"
        "Мы используем протокол VLESS Reality для стабильного доступа.\n"
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

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="check_profile")],
        [InlineKeyboardButton(text="💎 Продлить подписку", url=get_pay_url(user_id))],
        [InlineKeyboardButton(text="📥 Скачать клиент", url=DOWNLOAD_URL)]
    ])

    if not user_data:
        text = f"👤 **Профиль**\n\n🆔 ID: `{user_id}`\n📊 Статус: ⚪️ Не активен\n⏳ Осталось: **0 дней**"
    else:
        now = int(time.time())
        diff = user_data['expiry_date'] - now
        status = "✅ Активна" if diff > 0 else "❌ Истекла"
        rem = f"{max(0, diff // 86400)} дн. {max(0, (diff % 86400) // 3600)} ч."
        date_str = datetime.fromtimestamp(user_data['expiry_date']).strftime('%d.%m.%Y %H:%M')
        text = f"👤 **Профиль**\n\n🆔 ID: `{user_id}`\n📊 Статус: {status}\n⏳ Осталось: **{rem}**\n📅 До: {date_str}"

    if is_cb:
        try: await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except: await event.answer()
    else:
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")

# --- WEBHOOK ДЛЯ FREEKASSA ---
async def handle_webhook(request):
    data = await request.post()
    try:
        sign = hashlib.md5(f"{data.get('MERCHANT_ID')}:{data.get('AMOUNT')}:{SECRET_2}:{data.get('MERCHANT_ORDER_ID')}".encode()).hexdigest()
        if sign == data.get('SIGN'):
            user_id = int(data.get('MERCHANT_ORDER_ID'))
            u_uuid = str(uuid.uuid4())
            if await xui.add_client(1, f"tg_{user_id}", u_uuid):
                await db.add_or_update_user(user_id, u_uuid, f"tg_{user_id}")
                link = f"vless://{u_uuid}@{SERVER_DOMAIN}:443?security=reality&sni={SNI}&fp=chrome&pbk={PBK}&sid={SID}&type=tcp&headerType=none&flow=xtls-rprx-vision#Павлентий_VPN"
                
                success_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📥 Скачать приложение", url=DOWNLOAD_URL)]])
                
                await bot.send_message(
                    user_id, 
                    f"✅ **Оплата прошла успешно!**\n\n"
                    f"Ваш персональный ключ:\n`{link}`\n\n"
                    f"Скопируйте ключ и вставьте его в приложение. Скачать клиент можно по кнопке ниже.", 
                    reply_markup=success_kb,
                    parse_mode="Markdown"
                )
                return web.Response(text='YES')
    except Exception as e: logging.error(f"Webhook error: {e}")
    return web.Response(text='error', status=400)

# --- ПРОВЕРКА ИСТЕКШИХ (check_expired) и main() ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ ---
async def check_expired():
    expired = await db.get_expired_users()
    for row in expired:
        if await xui.delete_client(1, row['email']):
            await db.set_inactive(row['user_id'])
            try: await bot.send_message(row['user_id'], "🔴 Подписка истекла. Доступ ограничен.")
            except: pass

async def index_page(request):
    html = f"<html><body style='font-family:sans-serif;text-align:center;padding:50px;'><h1>ПавЛюций VPN</h1><p>Для покупки: <a href='https://t.me/pavlentiyVPN_bot'>@pavlentiyVPN_bot</a></p><p>Поддержка: {SUPPORT_USER}</p></body></html>"
    return web.Response(text=html, content_type='text/html')

async def main():
    await db.setup()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_expired, "interval", minutes=15)
    scheduler.start()
    app = web.Application()
    app.router.add_get('/', index_page)
    app.router.add_post('/freekassa/webhook', handle_webhook)
    app.router.add_get('/success', lambda r: web.HTTPFound('https://t.me/pavlentiyVPN_bot'))
    app.router.add_get('/favicon.ico', lambda r: web.Response(status=204))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())





