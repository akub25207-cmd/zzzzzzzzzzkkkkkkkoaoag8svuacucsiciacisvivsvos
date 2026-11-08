import asyncio 
import logging
import os
import re
import random
import uuid
import base64
import urllib.parse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from decimal import Decimal

import aiohttp
import aiosqlite
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    Message, CallbackQuery, LabeledPrice,
    PreCheckoutQuery, LinkPreviewOptions
)
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.types import (
    InputReportReasonSpam, InputReportReasonViolence,
    InputReportReasonChildAbuse, InputReportReasonOther
)
from telethon.errors import FloodWaitError, SessionPasswordNeededError

# ==================== НАСТРОЙКИ ====================
load_dotenv()
BOT_TOKEN = os.getenv("MAIN_BOT_TOKEN")
STARS_BOT_TOKEN = os.getenv("STARS_BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")
TONCENTER_API_KEY = os.getenv("TONCENTER_API_KEY")
TON_WALLET = os.getenv("TON_WALLET")

USDT_CONTRACT = "0:b113a994b5024a16719f69139328eb759596c38a25f59028b146fecdc3621dfe"
USDT_CONTRACT_USERFRIENDLY = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
TON_WALLET_RAW = None
STAR_TO_RUB = Decimal('1.5')

DEFAULT_TARIFFS = {
    "7d": {"stars": 250, "days": 7, "name": "7 дней"},
    "30d": {"stars": 400, "days": 30, "name": "30 дней"},
    "inf": {"stars": 800, "days": 99999, "name": "Навсегда"}
}

REPORT_REASONS = {
    "child": {
        "name": "Жестокое обращение с детьми",
        "sub": {
            "sexual": {"name": "Сексуальное насилие", "api": InputReportReasonChildAbuse()},
            "physical": {"name": "Физическое насилие", "api": InputReportReasonChildAbuse()}
        }
    },
    "violence": {
        "name": "Насилие",
        "sub": {
            "insults": {"name": "Оскорбления или клевета", "api": InputReportReasonViolence()},
            "images": {"name": "Изображение насилия, жестокости", "api": InputReportReasonViolence()},
            "extreme": {"name": "Крайняя жестокость, расчленение", "api": InputReportReasonViolence()},
            "hate": {"name": "Пропаганда ненависти", "api": InputReportReasonViolence()},
            "calls": {"name": "Призывы к насилию", "api": InputReportReasonViolence()},
            "crime": {"name": "Организованная преступность", "api": InputReportReasonViolence()},
            "terrorism": {"name": "Терроризм", "api": InputReportReasonViolence()},
            "animals": {"name": "Жестокое обращение с животными", "api": InputReportReasonViolence()}
        }
    },
    "illegal": {
        "name": "Незаконные товары и услуги",
        "sub": {
            "weapon": {"name": "Оружие", "api": InputReportReasonOther()},
            "drugs": {"name": "Наркотики, психоактивные вещества", "api": InputReportReasonOther()},
            "docs": {"name": "Подделка документов", "api": InputReportReasonOther()},
            "money": {"name": "Фальшивомонетничество", "api": InputReportReasonOther()},
            "malware": {"name": "Вредоносное ПО, средства взлома", "api": InputReportReasonOther()},
            "counterfeit": {"name": "Контрафактные товары", "api": InputReportReasonOther()},
            "other_goods": {"name": "Другие товары и услуги", "api": InputReportReasonOther()}
        }
    },
    "porn": {
        "name": "Порнографические материалы",
        "sub": {
            "child_porn": {"name": "Жестокое обращение с детьми", "api": InputReportReasonChildAbuse()},
            "illegal_intim": {"name": "Незаконные интимные услуги", "api": InputReportReasonOther()},
            "animal_porn": {"name": "Жестокое обращение с животными", "api": InputReportReasonOther()},
            "nonconsensual": {"name": "Интимные изображения без согласия", "api": InputReportReasonOther()},
            "porn_content": {"name": "Порнографический контент", "api": InputReportReasonOther()},
            "other_illegal": {"name": "Другие незаконные материалы", "api": InputReportReasonOther()}
        }
    },
    "personal": {
        "name": "Персональные данные",
        "sub": {
            "private_photo": {"name": "Личные изображения", "api": InputReportReasonOther()},
            "phone": {"name": "Номер телефона", "api": InputReportReasonOther()},
            "address": {"name": "Адрес", "api": InputReportReasonOther()},
            "stolen": {"name": "Украденные учётные и др. данные", "api": InputReportReasonOther()},
            "other_personal": {"name": "Другие личные данные", "api": InputReportReasonOther()}
        }
    },
    "scam": {
        "name": "Мошенничество",
        "sub": {
            "fake": {"name": "Выдача себя за другое лицо", "api": InputReportReasonOther()},
            "financial": {"name": "Ложные финансовые обещания", "api": InputReportReasonOther()},
            "phishing": {"name": "Вредоносное ПО, фишинг", "api": InputReportReasonOther()},
            "suspicious": {"name": "Сомнительный продавец, товар, услуга", "api": InputReportReasonOther()}
        }
    },
    "copyright": {
        "name": "Нарушение авторских прав",
        "sub": {
            "copyright_content": {"name": "Нарушение авторских прав", "api": InputReportReasonOther()}
        }
    },
    "spam": {
        "name": "Спам",
        "sub": {
            "illegal_ads": {"name": "Реклама незаконной продукции", "api": InputReportReasonSpam()},
            "other_ads": {"name": "Прочая реклама", "api": InputReportReasonSpam()}
        }
    },
    "other": {
        "name": "Другое",
        "sub": {
            "remove": {"name": "Не нарушает закон, но надо удалить", "api": InputReportReasonOther()}
        }
    }
}

EMOJI_WELCOME = "5431895003821513760"
EMOJI_CANCEL = "5895311993555915037"
EMOJI_PROFILE = "5920344347152224466"
EMOJI_SUB = "5936130851635990622"
EMOJI_STARS = "5958376256788502078"
EMOJI_CRYPTO = "5361836987642815474"
EMOJI_GRAM = "5350567049292719266"
EMOJI_USDT = "5771464597236092358"
EMOJI_BACK = "5877629862306385808"
EMOJI_RESURRECT = "5785326857587003471"
EMOJI_SUPPORT = "5877260593903177342"
EMOJI_SUPPORT_TEXT = "5879841310902324730"

PHOTO_MAIN = "https://i.imgur.com/Je5C8AR.jpg"
PHOTO_CANCEL = "https://i.imgur.com/923U5XL.jpg"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
stars_bot = Bot(token=STARS_BOT_TOKEN)

router = Router()
router_stars = Router()
dp = Dispatcher(storage=MemoryStorage())
dp_stars = Dispatcher(storage=MemoryStorage())
dp.include_router(router)
dp_stars.include_router(router_stars)

DB_FILE = "phyice.db"
CRYPTO_API = "https://pay.crypt.bot/api"

def e(eid):
    return f'<tg-emoji emoji-id="{eid}">⭐</tg-emoji>'

# ==================== БАЗА ДАННЫХ ====================
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, sub_until TEXT, is_forever INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS sponsor_channels (channel_id INTEGER PRIMARY KEY, channel_link TEXT, title TEXT)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS sessions (phone TEXT PRIMARY KEY, session_string TEXT)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS emails (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, password TEXT, smtp_server TEXT, smtp_port INTEGER)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS pending_deposits (code TEXT PRIMARY KEY, user_id INTEGER, amount_rub REAL, amount_crypto REAL, currency TEXT, tariff_key TEXT)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS mirrors (token TEXT PRIMARY KEY)''')
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('support_username', 'swordSar')")
        await db.commit()

async def get_setting(key):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as c:
            row = await c.fetchone()
            return row[0] if row else None

async def set_setting(key, value):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
        await db.commit()

async def get_tariff(tariff_key):
    db_price = await get_setting(f"price_{tariff_key}")
    days = DEFAULT_TARIFFS[tariff_key]["days"]
    name = DEFAULT_TARIFFS[tariff_key]["name"]
    if db_price:
        return {"stars": int(db_price), "days": days, "name": name}
    return DEFAULT_TARIFFS[tariff_key]

async def give_subscription(user_id: int, tariff_key: str):
    t = await get_tariff(tariff_key)
    days = t["days"]
    async with aiosqlite.connect(DB_FILE) as db:
        if tariff_key == "inf":
            await db.execute("UPDATE users SET is_forever = 1 WHERE user_id = ?", (user_id,))
        else:
            until = (datetime.now() + timedelta(days=days)).isoformat()
            await db.execute("UPDATE users SET sub_until = ? WHERE user_id = ?", (until, user_id))
        await db.commit()
    try: 
        await bot.send_message(user_id, f"Подписка на {t['name']} активирована!")
    except: pass

class UserStates(StatesGroup): 
    waiting_for_target = State()
    waiting_for_bot_check = State()
    waiting_for_link = State()
    waiting_for_main_reason = State()
    waiting_for_sub_reason = State()
    waiting_for_comment = State()

class AdminStates(StatesGroup):
    waiting_for_channel_id = State()
    waiting_for_channel_link = State()
    waiting_for_broadcast = State()
    confirming_broadcast = State()
    waiting_for_sessions = State()
    waiting_for_emails = State()
    waiting_for_support_username = State()
    waiting_for_mirror_token = State()
    waiting_for_new_price = State()
    waiting_for_admin_sub_user = State()
    waiting_for_admin_sub_tariff = State()
    waiting_for_admin_unsub_user = State()
    waiting_for_login_phone = State()
    waiting_for_login_code = State()
    waiting_for_login_password = State()
    waiting_for_channel_broadcast = State()

async def check_user_sub(user_id: int) -> bool:
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT sub_until, is_forever FROM users WHERE user_id = ?", (user_id,)) as c:
            row = await c.fetchone()
            if not row: return False
            if row[1]: return True
            if row[0] and datetime.fromisoformat(row[0]) > datetime.now(): return True
            return False

async def check_channel_sub(user_id: int) -> bool:
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT channel_id FROM sponsor_channels") as c:
            channels = await c.fetchall()
    if not channels: return True
    for ch in channels:
        try:
            m = await bot.get_chat_member(ch[0], user_id)
            if m.status not in ['creator', 'administrator', 'member']: return False
        except: pass
    return True

# ==================== TON & CRYPTO ====================
def convert_address_to_raw(address):
    try:
        if ":" in address: return address
        b = base64.urlsafe_b64decode(address + "=" * (-len(address) % 4))
        return f"0:{b[2:34].hex()}" if len(b) >= 34 else address
    except: return address

def create_tonkeeper_link(amount, comment, jetton=None):
    base = "https://app.tonkeeper.com/transfer/" + TON_WALLET
    if jetton is None:
        return f"{base}?amount={int(Decimal(str(amount)) * Decimal('1000000000'))}&text={urllib.parse.quote(comment)}"
    return f"{base}?jetton={jetton}&amount={int(Decimal(str(amount)) * Decimal('1000000'))}&text={urllib.parse.quote(comment)}"

async def get_crypto_rate():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{CRYPTO_API}/getExchangeRates", headers={"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}) as r:
                res = await r.json()
                if res.get("ok"):
                    for rate in res["result"]:
                        if rate["source"] == "TON" and rate["target"] == "RUB" and rate["is_valid"]:
                            return Decimal(rate["rate"])
        return Decimal('120')
    except: return Decimal('120')

def extract_usdt_comment(transfer):
    try:
        decoded_fp = transfer.get("decoded_forward_payload")
        if decoded_fp and isinstance(decoded_fp, dict):
            val = decoded_fp.get("comment") or decoded_fp.get("text") or decoded_fp.get("value")
            if val and isinstance(val, str): return val.strip()
        fp_b64 = transfer.get("forward_payload")
        if fp_b64:
            try:
                pb = base64.b64decode(fp_b64)
                if pb[:4] == b'\x00\x00\x00\x00':
                    text = pb[4:].decode('utf-8', errors='ignore').strip()
                    if text: return text
            except: pass
        return ""
    except: return ""

async def check_ton_transaction(chat_code, is_usdt=False, needed_amount=0):
    global TON_WALLET_RAW
    if not TON_WALLET_RAW: TON_WALLET_RAW = convert_address_to_raw(TON_WALLET)
    headers = {"X-API-Key": TONCENTER_API_KEY}
    try:
        async with aiohttp.ClientSession() as s:
            if is_usdt:
                url = f"https://toncenter.com/api/v3/jetton/transfers?owner_address={TON_WALLET_RAW}&direction=in&limit=100"
                async with s.get(url, headers=headers) as r:
                    res = await r.json()
                    for transfer in res.get("jetton_transfers", []):
                        if transfer.get("jetton_master", "").lower() != USDT_CONTRACT.lower(): continue
                        comment = extract_usdt_comment(transfer)
                        if comment != chat_code: continue
                        raw_amount = transfer.get("amount")
                        if raw_amount is None: continue
                        try: amount = int(raw_amount)
                        except: continue
                        usdt_amount = Decimal(amount) / Decimal('1000000')
                        if usdt_amount >= Decimal(str(needed_amount)) * Decimal('0.99'):
                            return True
                return False
            else:
                url = f"https://toncenter.com/api/v3/transactions?account={TON_WALLET_RAW}&limit=100"
                async with s.get(url, headers=headers) as r:
                    res = await r.json()
                    for tx in res.get("transactions", []):
                        if not tx.get("success"): continue
                        comment = tx.get("in_msg", {}).get("message_content", {}).get("decoded", {}).get("comment", "")
                        if comment != chat_code: continue
                        raw_value = tx.get("in_msg", {}).get("value")
                        if raw_value is None: continue
                        try: value = int(raw_value)
                        except: continue
                        gram_amount = Decimal(value) / Decimal('1000000000')
                        if gram_amount >= Decimal(str(needed_amount)) * Decimal('0.99'):
                            return True
                return False
    except: return False

async def monitor_usdt():
    global TON_WALLET_RAW
    while True:
        try:
            await asyncio.sleep(15)
            if not TON_WALLET_RAW: TON_WALLET_RAW = convert_address_to_raw(TON_WALLET)
            headers = {"X-API-Key": TONCENTER_API_KEY}
            async with aiohttp.ClientSession() as s:
                url = f"https://toncenter.com/api/v3/jetton/transfers?owner_address={TON_WALLET_RAW}&direction=in&limit=100"
                async with s.get(url, headers=headers) as r:
                    res = await r.json()
                    for transfer in res.get("jetton_transfers", []):
                        if transfer.get("jetton_master", "").lower() != USDT_CONTRACT.lower(): continue
                        comment = extract_usdt_comment(transfer)
                        if not comment: continue
                        async with aiosqlite.connect(DB_FILE) as db:
                            async with db.execute("SELECT user_id, tariff_key, amount_crypto FROM pending_deposits WHERE code = ? AND currency = 'USDT'", (comment,)) as c:
                                dep = await c.fetchone()
                                if dep:
                                    raw_amount = transfer.get("amount")
                                    if raw_amount is None: continue
                                    try: amount = int(raw_amount)
                                    except: continue
                                    received = Decimal(amount) / Decimal('1000000')
                                    needed = Decimal(str(dep[2]))
                                    if received < needed * Decimal('0.99'):
                                        await db.execute("DELETE FROM pending_deposits WHERE code = ?", (comment,))
                                        await db.commit()
                                        try:
                                            await bot.send_message(dep[0], f"❌ <b>Недоплата!</b>\n\nВы отправили: <code>{received:.4f} USDT</code>\nНужно было: <code>{needed:.4f} USDT</code>")
                                        except: pass
                                    else:
                                        await db.execute("DELETE FROM pending_deposits WHERE code = ?", (comment,))
                                        await db.commit()
                                        await give_subscription(dep[0], dep[1])
        except: pass

async def monitor_ton():
    global TON_WALLET_RAW
    while True:
        try:
            await asyncio.sleep(15)
            if not TON_WALLET_RAW: TON_WALLET_RAW = convert_address_to_raw(TON_WALLET)
            headers = {"X-API-Key": TONCENTER_API_KEY}
            async with aiohttp.ClientSession() as s:
                async with s.get(f"https://toncenter.com/api/v3/transactions?account={TON_WALLET_RAW}&limit=50", headers=headers) as r:
                    res = await r.json()
                    for tx in res.get("transactions", []):
                        if not tx.get("success"): continue
                        comment = tx.get("in_msg", {}).get("message_content", {}).get("decoded", {}).get("comment", "")
                        if not comment: continue
                        async with aiosqlite.connect(DB_FILE) as db:
                            async with db.execute("SELECT user_id, tariff_key, amount_crypto FROM pending_deposits WHERE code = ? AND currency = 'GRAM'", (comment,)) as c:
                                dep = await c.fetchone()
                                if dep:
                                    try:
                                        raw_value = int(tx.get("in_msg", {}).get("value", 0))
                                        received = Decimal(raw_value) / Decimal('1000000000')
                                        needed = Decimal(str(dep[2]))
                                    except: continue
                                    if received < needed * Decimal('0.99'):
                                        await db.execute("DELETE FROM pending_deposits WHERE code = ?", (comment,))
                                        await db.commit()
                                        try:
                                            await bot.send_message(dep[0], f"❌ <b>Недоплата!</b>\n\nВы отправили: <code>{received:.4f} TON</code>\nНужно было: <code>{needed:.4f} TON</code>")
                                        except: pass
                                    else:
                                        await db.execute("DELETE FROM pending_deposits WHERE code = ?", (comment,))
                                        await db.commit()
                                        await give_subscription(dep[0], dep[1])
        except: pass

async def crypto_create_invoice(amount_rub: Decimal, payload: str):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{CRYPTO_API}/getExchangeRates", headers={"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}) as r:
                res = await r.json()
                usdt_rate = Decimal('95')
                if res.get("ok"):
                    for rate in res["result"]:
                        if rate["source"] == "USDT" and rate["target"] == "RUB" and rate["is_valid"]:
                            usdt_rate = Decimal(rate["rate"])
                            break
                amount_usdt = (amount_rub / usdt_rate).quantize(Decimal('0.01'))
            async with s.post(f"{CRYPTO_API}/createInvoice", headers={"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}, json={"currency_type": "crypto", "asset": "USDT", "amount": str(amount_usdt), "description": "Подписка Фиайс", "payload": payload, "allow_comments": False, "allow_anonymous": True, "expires_in": 3600}) as r:
                data = await r.json()
                return data["result"] if data.get("ok") else None
    except: return None

async def crypto_get_invoice(invoice_id: int):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{CRYPTO_API}/getInvoices", headers={"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}, params={"invoice_ids": str(invoice_id)}) as r:
                data = await r.json()
                return data["result"]["items"][0] if data.get("ok") and data["result"].get("items") else None
    except: return None

async def monitor_crypto_invoices():
    while True:
        try:
            await asyncio.sleep(20)
            async with aiosqlite.connect(DB_FILE) as db:
                async with db.execute("SELECT code, user_id, tariff_key FROM pending_deposits WHERE currency = 'CRYPTO'") as c:
                    pending = await c.fetchall()
                    for code, user_id, tariff_key in pending:
                        if not code.startswith("crypto_"): continue
                        try: invoice_id = int(code.split("_", 1)[1])
                        except: continue
                        inv = await crypto_get_invoice(invoice_id)
                        if inv and inv.get("status") == "paid":
                            async with aiosqlite.connect(DB_FILE) as db2:
                                await db2.execute("DELETE FROM pending_deposits WHERE code = ?", (code,))
                                await db2.commit()
                            await give_subscription(user_id, tariff_key)
        except: pass

# ==================== ЖАЛОБЫ ====================
async def get_sessions():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT session_string FROM sessions") as c:
            return [row[0] for row in await c.fetchall()]

async def send_report_single(sess_str, chat, msg_id, reason_obj, comment, is_bot=False):
    try:
        client = TelegramClient(StringSession(sess_str), API_ID, API_HASH)
        await client.connect()
        if await client.is_user_authorized():
            entity = await client.get_entity(chat)
            if is_bot or msg_id == 0:
                await client(ReportPeerRequest(
                    peer=entity,
                    reason=reason_obj,
                    message=comment
                ))
            else:
                await client(ReportRequest(
                    peer=entity,
                    id=[msg_id],
                    reason=reason_obj,
                    message=comment
                ))
            await client.disconnect()
            return True
    except FloodWaitError as e: await asyncio.sleep(e.seconds)
    except Exception as ex: logging.error(f"Report error: {ex}")
    return False

async def execute_method(method, chat, msg_id, reason_obj, comment_text, is_bot=False):
    sessions = await get_sessions()
    ok, fail = 0, 0
    if not sessions and method != "mail": return 0, 1

    if method == "express":
        for s in random.sample(sessions, min(2, len(sessions))):
            if await send_report_single(s, chat, msg_id, reason_obj, comment_text, is_bot): ok += 1
            else: fail += 1
            await asyncio.sleep(random.uniform(4, 12))
    elif method == "vip":
        if sessions:
            if await send_report_single(random.choice(sessions), chat, msg_id, reason_obj, comment_text, is_bot): ok += 1
            else: fail += 1
    elif method == "botnet":
        sem = asyncio.Semaphore(3)
        async def worker(sess):
            nonlocal ok, fail
            async with sem:
                if await send_report_single(sess, chat, msg_id, reason_obj, comment_text, is_bot): ok += 1
                else: fail += 1
                await asyncio.sleep(random.uniform(5, 15))
        await asyncio.gather(*(worker(s) for s in sessions))
    elif method == "mail":
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT email, password, smtp_server, smtp_port FROM emails LIMIT 5") as c:
                emails = await c.fetchall()
        for email, pwd, server, port in emails:
            try:
                msg = MIMEMultipart()
                msg['From'], msg['To'] = email, "abuse@telegram.org"
                msg['Subject'] = f"Report: Violation - {chat}"
                msg.attach(MIMEText(f"Target: {chat}\nMessage ID: {msg_id}\nReason: {reason_obj.__class__.__name__}\nComment: {comment_text}", 'plain'))
                with smtplib.SMTP(server, port) as smtp:
                    smtp.starttls()
                    smtp.login(email, pwd)
                    smtp.send_message(msg)
                ok += 1
            except: fail += 1
            await asyncio.sleep(random.uniform(5, 10))
    return ok, fail

# ==================== МЕНЮ ====================
def get_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Аннулирование", callback_data="menu_cancel", style="primary", icon_custom_emoji_id=EMOJI_CANCEL)],
        [
            InlineKeyboardButton(text="Профиль", callback_data="menu_profile", icon_custom_emoji_id=EMOJI_PROFILE), 
            InlineKeyboardButton(text="FAQ", callback_data="menu_faq")
        ],
        [InlineKeyboardButton(text="Реснуть акк", callback_data="menu_resurrect", style="primary", icon_custom_emoji_id=EMOJI_RESURRECT)],
        [InlineKeyboardButton(text="Поддержка", callback_data="menu_support", icon_custom_emoji_id=EMOJI_SUPPORT)]
    ])

async def show_main_menu(obj):
    text = f"{e(EMOJI_WELCOME)} <b>Добро пожаловать в Фиайс</b>"
    kb = get_main_kb()
    preview = LinkPreviewOptions(url=PHOTO_MAIN, prefer_large_media=True, show_above_text=False)
    
    if isinstance(obj, CallbackQuery):
        try: await obj.message.delete()
        except: pass
        await obj.bot.send_message(obj.from_user.id, text, parse_mode="HTML", reply_markup=kb, link_preview_options=preview)
        await obj.answer()
    else:
        await obj.answer(text, parse_mode="HTML", reply_markup=kb, link_preview_options=preview)

@router.message(CommandStart())
async def cmd_start(message: Message):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT INTO users (user_id, username) VALUES (?, ?) ON CONFLICT (user_id) DO UPDATE SET username = ?", (message.from_user.id, message.from_user.username, message.from_user.username))
        await db.commit()
    if not await check_channel_sub(message.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[])
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT channel_id, channel_link, title FROM sponsor_channels") as c:
                for ch in await c.fetchall():
                    try:
                        me = await bot.get_me()
                        m = await bot.get_chat_member(ch[0], me.id)
                        if m.status in ['administrator', 'creator']:
                            kb.inline_keyboard.append([InlineKeyboardButton(text=ch[2], url=ch[1], style="primary")])
                    except: pass
        kb.inline_keyboard.append([InlineKeyboardButton(text="Я подписался", callback_data="check_sub_btn", style="success")])
        await message.answer("<b>Для доступа к Фиайс подпишитесь на наши каналы:</b>\n\n<blockquote>После подписки нажмите кнопку «Я подписался» ниже.</blockquote>", parse_mode="HTML", reply_markup=kb)
        return
    await show_main_menu(message)

@router.callback_query(F.data == "check_sub_btn")
async def check_sub_cb(call: CallbackQuery):
    if await check_channel_sub(call.from_user.id):
        await call.message.delete()
        await show_main_menu(call)
    else: await call.answer("Вы подписались не на все каналы!", show_alert=True)

@router.callback_query(F.data == "menu_profile")
async def menu_profile(call: CallbackQuery):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT sub_until, is_forever FROM users WHERE user_id = ?", (call.from_user.id,)) as c:
            row = await c.fetchone()
    status = "Да" if await check_user_sub(call.from_user.id) else "Нет"
    days = "∞" if (row and row[1]) else (max(0, (datetime.fromisoformat(row[0]) - datetime.now()).days) if row and row[0] else 0)
    text = f"Ваш профиль\n\nID: {call.from_user.id}\nСтатус подписки: {status}\nДней до окончания: {days}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подписка", callback_data="menu_sub", style="primary", icon_custom_emoji_id=EMOJI_SUB)],
        [InlineKeyboardButton(text="Назад", callback_data="menu_back_main", icon_custom_emoji_id=EMOJI_BACK)]
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()

@router.callback_query(F.data == "menu_faq")
async def menu_faq(call: CallbackQuery):
    text = (
        "<b>Обязательно к ознакомлению:</b>\n\n"
        "<blockquote>1. Удаление аккаунта не гарантировано. Всё зависит от того, как быстро отреагирует поддержка Telegram — она внимательно рассматривает жалобы и принимает решение по каждой.\n"
        "2. Если не следовать инструкциям бота, шанс на удаление будет нулевым.\n"
        "3. Я не несу ответственности за действия пользователей бота.</blockquote>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="menu_back_main", icon_custom_emoji_id=EMOJI_BACK)]])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()

@router.callback_query(F.data == "menu_resurrect")
async def menu_resurrect(call: CallbackQuery):
    await call.message.edit_text("Это функция ещё в разработке", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="menu_back_main", icon_custom_emoji_id=EMOJI_BACK)]]))
    await call.answer()

@router.callback_query(F.data == "menu_support")
async def menu_support(call: CallbackQuery):
    sup = await get_setting('support_username')
    text = f"{e(EMOJI_SUPPORT_TEXT)} Служба поддержки\n\nВозникли вопросы? Мы на связи 24/7."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Написать в поддержку", url=f"https://t.me/{sup}", style="primary")],
        [InlineKeyboardButton(text="Назад", callback_data="menu_back_main", icon_custom_emoji_id=EMOJI_BACK)]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()

@router.callback_query(F.data == "menu_back_main")
async def menu_back_main(call: CallbackQuery):
    await call.message.delete()
    await show_main_menu(call)

@router.callback_query(F.data == "menu_cancel")
async def menu_cancel(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Экспресс", callback_data="method_express", style="primary")],
        [InlineKeyboardButton(text="VIP", callback_data="method_vip", style="primary")],
        [InlineKeyboardButton(text="Ботнет", callback_data="method_botnet", style="primary")],
        [InlineKeyboardButton(text="Почтовый", callback_data="method_mail", style="primary")],
        [InlineKeyboardButton(text="Назад", callback_data="menu_back_main", icon_custom_emoji_id=EMOJI_BACK)]
    ])
    preview = LinkPreviewOptions(url=PHOTO_CANCEL, prefer_large_media=True, show_above_text=False)
    await call.message.delete()
    await call.bot.send_message(call.from_user.id, "<b>Выберите тип сноса:</b>", parse_mode="HTML", reply_markup=kb, link_preview_options=preview)
    await call.answer()

@router.callback_query(F.data.startswith("method_"))
async def method_sel(call: CallbackQuery, state: FSMContext):
    method = call.data.replace("method_", "")
    await state.update_data(method=method)
    text = f"<b>способ: {method.capitalize()}</b>\n\n<blockquote>Отправьте никнейм, ID или ссылку на аккаунт/канал.</blockquote>"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="menu_cancel", icon_custom_emoji_id=EMOJI_BACK)]])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(UserStates.waiting_for_target)
    await call.answer()

@router.message(UserStates.waiting_for_target)
async def process_target(message: Message, state: FSMContext):
    if not await check_user_sub(message.from_user.id):
        await message.answer("<b>У вас нету подписки</b>", parse_mode="HTML")
        await state.clear()
        return
    
    target = message.text.strip()
    await state.update_data(target=target)
    
    # Спрашиваем, бот это или нет
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Это бот", callback_data="is_bot_yes", style="primary")],
        [InlineKeyboardButton(text="Это аккаунт/канал", callback_data="is_bot_no", style="primary")]
    ])
    await message.answer("Уточните, на кого вы жалуетесь?", reply_markup=kb)
    await state.set_state(UserStates.waiting_for_bot_check)

@router.callback_query(UserStates.waiting_for_bot_check, F.data.startswith("is_bot_"))
async def process_bot_check(call: CallbackQuery, state: FSMContext):
    is_bot = call.data == "is_bot_yes"
    await state.update_data(is_bot=is_bot)
    
    if is_bot:
        # Если бот, сразу идем к причинам
        kb = InlineKeyboardMarkup(inline_keyboard=[])
        for key, reason in REPORT_REASONS.items():
            kb.inline_keyboard.append([InlineKeyboardButton(text=reason["name"], callback_data=f"reason_{key}")])
        await call.message.edit_text("<b>Что не так с этим сообщением?</b>", parse_mode="HTML", reply_markup=kb)
        await state.set_state(UserStates.waiting_for_main_reason)
    else:
        # Если не бот, просим ссылку
        await call.message.edit_text("Отправьте ссылку на сообщение (например, https://t.me/username/123):")
        await state.set_state(UserStates.waiting_for_link)
    await call.answer()

@router.message(UserStates.waiting_for_link)
async def process_link(message: Message, state: FSMContext):
    match = re.search(r't\.me/([^/]+)/(\d+)', message.text)
    if not match:
        await message.answer("Отправьте корректную ссылку.")
        return
    
    chat, msg_id = match.group(1), int(match.group(2))
    await state.update_data(chat=chat, msg_id=msg_id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for key, reason in REPORT_REASONS.items():
        kb.inline_keyboard.append([InlineKeyboardButton(text=reason["name"], callback_data=f"reason_{key}")])
    
    await message.answer("<b>Что не так с этим сообщением?</b>", parse_mode="HTML", reply_markup=kb)
    await state.set_state(UserStates.waiting_for_main_reason)

@router.callback_query(UserStates.waiting_for_main_reason, F.data.startswith("reason_"))
async def process_main_reason(call: CallbackQuery, state: FSMContext):
    reason_key = call.data.replace("reason_", "")
    reason = REPORT_REASONS.get(reason_key)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for sub_key, sub_reason in reason["sub"].items():
        kb.inline_keyboard.append([InlineKeyboardButton(text=sub_reason["name"], callback_data=f"subreason_{reason_key}_{sub_key}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Назад", callback_data="menu_cancel", icon_custom_emoji_id=EMOJI_BACK)])
    
    await call.message.edit_text(f"<b>{reason['name']}</b>\n\nЧто не так с этим сообщением?", parse_mode="HTML", reply_markup=kb)
    await state.set_state(UserStates.waiting_for_sub_reason)
    await call.answer()

@router.callback_query(UserStates.waiting_for_sub_reason, F.data.startswith("subreason_"))
async def process_sub_reason(call: CallbackQuery, state: FSMContext):
    _, reason_key, sub_key = call.data.split("_")
    sub_reason = REPORT_REASONS[reason_key]["sub"][sub_key]
    await state.update_data(reason_api=sub_reason["api"], reason_name=sub_reason["name"])
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_comment", style="primary")]
    ])
    await call.message.edit_text("Напишите комментарий (минимум 10 слов) или нажмите «Пропустить»:", reply_markup=kb)
    await state.set_state(UserStates.waiting_for_comment)
    await call.answer()

@router.callback_query(UserStates.waiting_for_comment, F.data == "skip_comment")
async def skip_comment(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    comment = "Нарушение правил"
    
    await call.message.edit_text("⏳ Отправляю жалобы...")
    ok, fail = await execute_method(
        data['method'], 
        data.get('target', data.get('chat')), 
        data.get('msg_id', 0), 
        data['reason_api'], 
        comment, 
        data['is_bot']
    )
    await call.message.edit_text(f"Работа завершена.\nУспешно: {ok}\nНе успешно: {fail}")
    await state.clear()
    await call.answer()

@router.message(UserStates.waiting_for_comment)
async def process_comment(message: Message, state: FSMContext):
    text = message.text.strip()
    words = text.split()
    
    if len(words) < 10:
        await message.answer(f"❌ Комментарий слишком короткий. Нужно минимум 10 слов, у тебя {len(words)}. Напиши подробнее или нажми «Пропустить».")
        return
    
    data = await state.get_data()
    await message.answer("⏳ Отправляю жалобы...")
    ok, fail = await execute_method(
        data['method'], 
        data.get('target', data.get('chat')), 
        data.get('msg_id', 0), 
        data['reason_api'], 
        text, 
        data['is_bot']
    )
    await message.answer(f"Работа завершена.\nУспешно: {ok}\nНе успешно: {fail}")
    await state.clear()

# ==================== ОПЛАТА ====================
@router.callback_query(F.data == "menu_sub")
async def menu_sub(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Telegram Stars", callback_data="pay_stars", style="primary", icon_custom_emoji_id=EMOJI_STARS)],
        [InlineKeyboardButton(text="CryptoBot", callback_data="pay_crypto", style="primary", icon_custom_emoji_id=EMOJI_CRYPTO)],
        [InlineKeyboardButton(text="GRAM", callback_data="pay_gram", style="primary", icon_custom_emoji_id=EMOJI_GRAM)],
        [InlineKeyboardButton(text="USDT (TON)", callback_data="pay_usdt", style="primary", icon_custom_emoji_id=EMOJI_USDT)],
        [InlineKeyboardButton(text="Назад", callback_data="menu_profile", icon_custom_emoji_id=EMOJI_BACK)]
    ])
    await call.message.edit_text("<b>Способы оплаты</b>", parse_mode="HTML", reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.in_({"pay_stars", "pay_crypto", "pay_gram", "pay_usdt"}))
async def select_tariff(call: CallbackQuery):
    method = call.data.replace("pay_", "")
    t7 = await get_tariff("7d")
    t30 = await get_tariff("30d")
    tinf = await get_tariff("inf")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{t7['stars']} (7 дней)", callback_data=f"buy_{method}_7d", style="primary")],
        [InlineKeyboardButton(text=f"{t30['stars']} (30 дней)", callback_data=f"buy_{method}_30d", style="primary")],
        [InlineKeyboardButton(text=f"{tinf['stars']} (Навсегда)", callback_data=f"buy_{method}_inf", style="primary")],
        [InlineKeyboardButton(text="Назад", callback_data="menu_sub", icon_custom_emoji_id=EMOJI_BACK)]
    ])
    await call.message.edit_text("<b>Выберите тариф:</b>", parse_mode="HTML", reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("buy_"))
async def process_buy(call: CallbackQuery):
    _, method, tariff_key = call.data.split("_")
    t = await get_tariff(tariff_key)
    
    if method == "stars":
        try:
            invoice_link = await stars_bot.create_invoice_link(
                title=f"Подписка {t['name']}",
                description="Доступ к функциям Фиайс",
                payload=f"sub_{tariff_key}_{call.from_user.id}",
                currency="XTR",
                prices=[LabeledPrice(label=t["name"], amount=t["stars"])]
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оплатить звёздами", url=invoice_link, style="primary")]
            ])
            await call.message.edit_text(
                f"<b>Счёт на {t['name']} создан!</b>\n\nНажмите кнопку ниже, чтобы оплатить.",
                parse_mode="HTML",
                reply_markup=kb
            )
            await call.answer()
        except Exception as e: 
            await call.answer(f"Ошибка: {e}", show_alert=True)
            
    elif method in ["gram", "usdt"]:
        amount_rub = t["stars"] * STAR_TO_RUB
        rate = await get_crypto_rate()
        amt_crypto = amount_rub / rate
        code = f"phyice-{uuid.uuid4().hex[:8]}"
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("INSERT INTO pending_deposits (code, user_id, amount_rub, amount_crypto, currency, tariff_key) VALUES (?, ?, ?, ?, ?, ?)", (code, call.from_user.id, float(amount_rub), float(amt_crypto), method.upper(), tariff_key))
            await db.commit()
        link = create_tonkeeper_link(amt_crypto, code, USDT_CONTRACT_USERFRIENDLY if method == "usdt" else None)
        text = f"<b>К оплате:</b> {amt_crypto:.4f} {method.upper()}\n<b>Комментарий:</b> <code>{code}</code>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить", url=link, style="primary")],
            [InlineKeyboardButton(text="Проверить оплату", callback_data=f"check_{method}_{code}", style="success")]
        ])
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        
    elif method == "crypto":
        amount_rub = Decimal(str(t["stars"])) * STAR_TO_RUB
        payload = f"crypto_{call.from_user.id}_{tariff_key}"
        inv = await crypto_create_invoice(amount_rub, payload)
        if inv:
            async with aiosqlite.connect(DB_FILE) as db:
                await db.execute("INSERT INTO pending_deposits (code, user_id, amount_rub, amount_crypto, currency, tariff_key) VALUES (?, ?, ?, ?, ?, ?)", (f"crypto_{inv['invoice_id']}", call.from_user.id, float(amount_rub), float(inv['amount']), "CRYPTO", tariff_key))
                await db.commit()
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оплатить в CryptoBot", url=inv['bot_invoice_url'], style="primary")],
                [InlineKeyboardButton(text="Проверить оплату", callback_data=f"check_crypto_{inv['invoice_id']}", style="success")]
            ])
            await call.message.edit_text(f"<b>Счет создан!</b>\nК оплате: {inv['amount']} USDT", parse_mode="HTML", reply_markup=kb)
        else: await call.answer("Ошибка создания счета", show_alert=True)

@router.callback_query(F.data.startswith("check_gram_") | F.data.startswith("check_usdt_"))
async def manual_check_payment(call: CallbackQuery):
    data = call.data.split("_")
    method = data[1]
    code = data[2]
    
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT user_id, tariff_key, amount_crypto FROM pending_deposits WHERE code = ?", (code,)) as c:
            dep = await c.fetchone()
            
    if not dep:
        await call.answer("Платёж не найден или уже обработан.", show_alert=True)
        return
        
    await call.answer("Проверяю блокчейн, подождите...", show_alert=True)
    
    needed = Decimal(str(dep[2]))
    is_paid = await check_ton_transaction(code, is_usdt=(method=="usdt"), needed_amount=needed)
    
    if is_paid:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("DELETE FROM pending_deposits WHERE code = ?", (code,))
            await db.commit()
        await give_subscription(dep[0], dep[1])
        await call.message.edit_text("Оплата подтверждена! Подписка активирована.", reply_markup=None)
    else:
        await call.answer("Транзакция на нужную сумму пока не найдена в сети. Если вы оплатили, подождите 1-2 минуты и нажмите снова.", show_alert=True)

@router.callback_query(F.data.startswith("check_crypto_"))
async def manual_check_crypto(call: CallbackQuery):
    invoice_id = call.data.replace("check_crypto_", "")
    await call.answer("Проверяю статус счета...", show_alert=True)
    
    inv = await crypto_get_invoice(int(invoice_id))
    if inv and inv.get("status") == "paid":
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT user_id, tariff_key FROM pending_deposits WHERE code = ?", (f"crypto_{invoice_id}",)) as c:
                dep = await c.fetchone()
        if dep:
            async with aiosqlite.connect(DB_FILE) as db:
                await db.execute("DELETE FROM pending_deposits WHERE code = ?", (f"crypto_{invoice_id}",))
                await db.commit()
            await give_subscription(dep[0], dep[1])
            await call.message.edit_text("Оплата подтверждена! Подписка активирована.", reply_markup=None)
        else:
            await call.message.edit_text("Подписка уже была активирована ранее.", reply_markup=None)
    else:
        await call.answer("Счет еще не оплачен.", show_alert=True)

@router_stars.pre_checkout_query()
async def pre_checkout_stars(query: PreCheckoutQuery):
    await query.answer(ok=True)

@router_stars.message(F.successful_payment)
async def success_pay_stars(message: Message):
    payload = message.successful_payment.invoice_payload
    parts = payload.split("_")
    if len(parts) >= 3:
        tariff_key = parts[1]
        user_id = int(parts[2])
        await give_subscription(user_id, tariff_key)
        await message.answer("Оплата получена! Подписка активирована.")

# ==================== АДМИНКА ====================
@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != OWNER_ID: return
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c: total = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE sub_until > ? AND is_forever = 0", (datetime.now().isoformat(),)) as c: active = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_forever = 1") as c: forever = (await c.fetchone())[0]
    stats = f"<b>Статистика</b>\n\nВсего: <b>{total}</b>\nАктивных: <b>{active}</b>\nНавсегда: <b>{forever}</b>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить канал", callback_data="admin_add_ch", style="primary")],
        [InlineKeyboardButton(text="Рассылка", callback_data="admin_broadcast", style="primary")],
        [InlineKeyboardButton(text="Добавить зеркало", callback_data="admin_add_mirror", style="primary")],
        [InlineKeyboardButton(text="Загрузить сессии", callback_data="admin_upload_sessions", style="primary")],
        [InlineKeyboardButton(text="Добавить 1 сессию", callback_data="admin_add_session_one", style="primary")],
        [InlineKeyboardButton(text="Сессии: список/удаление", callback_data="admin_list_sessions", style="primary")],
        [InlineKeyboardButton(text="Загрузить почты", callback_data="admin_upload_emails", style="primary")],
        [InlineKeyboardButton(text="Настройки цен", callback_data="admin_prices", style="primary")],
        [InlineKeyboardButton(text="Выдать подписку", callback_data="admin_give_sub", style="primary")],
        [InlineKeyboardButton(text="Снять подписку", callback_data="admin_unsub", style="primary")],
        [InlineKeyboardButton(text="Добавить по номеру", callback_data="admin_add_phone", style="primary")],
        [InlineKeyboardButton(text="Рассылка по каналам", callback_data="admin_broadcast_channels", style="primary")],
        [InlineKeyboardButton(text="Сменить ник поддержки", callback_data="admin_support", style="primary")]
    ])
    await message.answer(stats, parse_mode="HTML", reply_markup=kb)

async def render_prices_menu(message: Message):
    t7 = await get_tariff("7d")
    t30 = await get_tariff("30d")
    tinf = await get_tariff("inf")
    text = (
        f"<b>Текущие цены (в звездах):</b>\n\n"
        f"7 дней: <b>{t7['stars']}</b>\n"
        f"30 дней: <b>{t30['stars']}</b>\n"
        f"Навсегда: <b>{tinf['stars']}</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить 7 дней", callback_data="set_price_7d", style="primary")],
        [InlineKeyboardButton(text="Изменить 30 дней", callback_data="set_price_30d", style="primary")],
        [InlineKeyboardButton(text="Изменить Навсегда", callback_data="set_price_inf", style="primary")],
        [InlineKeyboardButton(text="Назад", callback_data="admin_back_main", icon_custom_emoji_id=EMOJI_BACK)]
    ])
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "admin_prices")
async def admin_prices(call: CallbackQuery):
    if call.from_user.id != OWNER_ID: return
    await call.message.delete()
    await render_prices_menu(call.message)
    await call.answer()

@router.callback_query(F.data.startswith("set_price_"))
async def set_price_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != OWNER_ID: return
    tariff_key = call.data.replace("set_price_", "")
    await state.update_data(tariff_key=tariff_key)
    await call.message.edit_text(f"Введите новую цену в звездах для тарифа <b>{DEFAULT_TARIFFS[tariff_key]['name']}</b>:")
    await state.set_state(AdminStates.waiting_for_new_price)
    await call.answer()

@router.message(AdminStates.waiting_for_new_price)
async def save_new_price(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID: return
    try:
        price = int(message.text)
        if price <= 0: raise ValueError
    except ValueError:
        await message.answer("Ошибка: введите целое положительное число.")
        return
    
    data = await state.get_data()
    tariff_key = data['tariff_key']
    
    await set_setting(f"price_{tariff_key}", str(price))
    
    await message.answer(f"Цена для тарифа <b>{DEFAULT_TARIFFS[tariff_key]['name']}</b> изменена на <b>{price}</b> звезд.", parse_mode="HTML")
    await state.clear()
    
    await render_prices_menu(message)

@router.callback_query(F.data == "admin_back_main")
async def admin_back_main(call: CallbackQuery):
    if call.from_user.id != OWNER_ID: return
    await call.message.delete()
    await admin_panel(call.message)

@router.callback_query(F.data == "admin_add_mirror")
async def admin_add_mirror(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != OWNER_ID: return
    await call.message.answer("Отправьте токен нового бота (зеркала):")
    await state.set_state(AdminStates.waiting_for_mirror_token)
    await call.answer()

@router.message(AdminStates.waiting_for_mirror_token)
async def save_mirror_token(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID: return
    token = message.text.strip()
    try:
        new_bot = Bot(token=token)
        me = await new_bot.get_me()
        
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("INSERT OR IGNORE INTO mirrors (token) VALUES (?)", (token,))
            await db.commit()
            
        await message.answer(f"Зеркало @{me.username} сохранено! Перезапустите бота на хостинге, чтобы оно заработало.")
    except Exception as e:
        await message.answer(f"Ошибка сохранения: {e}")
    await state.clear()

@router.callback_query(F.data == "admin_add_ch")
async def admin_add_ch(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != OWNER_ID: return
    await call.message.answer("Введите ID канала:")
    await state.set_state(AdminStates.waiting_for_channel_id)
    await call.answer()

@router.message(AdminStates.waiting_for_channel_id)
async def admin_ch_id(message: Message, state: FSMContext):
    try:
        await state.update_data(ch_id=int(message.text))
        await message.answer("Введите ссылку:")
        await state.set_state(AdminStates.waiting_for_channel_link)
    except: await message.answer("ID должен быть числом")

@router.message(AdminStates.waiting_for_channel_link)
async def admin_ch_link(message: Message, state: FSMContext):
    d = await state.get_data()
    try:
        me = await bot.get_me()
        m = await bot.get_chat_member(d['ch_id'], me.id)
        if m.status not in ['administrator', 'creator']:
            await message.answer("Бот не админ!")
            await state.clear()
            return
        chat = await bot.get_chat(d['ch_id'])
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("INSERT INTO sponsor_channels (channel_id, channel_link, title) VALUES (?, ?, ?) ON CONFLICT DO NOTHING", (d['ch_id'], message.text, chat.title))
            await db.commit()
        await message.answer(f"Канал {chat.title} добавлен!")
    except Exception as e: await message.answer(f"Ошибка: {e}")
    await state.clear()

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != OWNER_ID: return
    await call.message.answer("Отправьте сообщение для рассылки:")
    await state.set_state(AdminStates.waiting_for_broadcast)
    await call.answer()

@router.message(AdminStates.waiting_for_broadcast, F.text | F.photo)
async def admin_broadcast_confirm(message: Message, state: FSMContext):
    await state.update_data(msg_id=message.message_id, chat_id=message.chat.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Начать", callback_data="bc_confirm", style="success")], [InlineKeyboardButton(text="Отмена", callback_data="bc_cancel", style="danger")]])
    await message.answer("Подтвердите:", reply_markup=kb)
    await state.set_state(AdminStates.confirming_broadcast)

@router.callback_query(F.data == "bc_cancel", AdminStates.confirming_broadcast)
async def bc_cancel(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Отменено.")
    await state.clear()

@router.callback_query(F.data == "bc_confirm", AdminStates.confirming_broadcast)
async def bc_execute(call: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    await state.clear()
    status = await call.message.edit_text("Рассылка...")
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT user_id FROM users") as c: users = await c.fetchall()
    ok, fail = 0, 0
    for i, (uid,) in enumerate(users, 1):
        try:
            await bot.copy_message(chat_id=uid, from_chat_id=d['chat_id'], message_id=d['msg_id'])
            ok += 1
        except: fail += 1
        if i % 20 == 0:
            try: await status.edit_text(f"{i}/{len(users)} | Успешно: {ok} | Ошибок: {fail}")
            except: pass
        await asyncio.sleep(0.05)
    await status.edit_text(f"Готово!\nУспешно: {ok}\nОшибок: {fail}")

def parse_session_line(line: str):
    line = line.strip()
    if not line: return None
    for sep in ("|", ":", "\t"):
        if sep in line:
            left, right = line.split(sep, 1)
            left, right = left.strip(), right.strip()
            if right.startswith("1") and len(right) > 100: return (left if left else f"unknown_{uuid.uuid4().hex[:8]}"), right
            if left.startswith("1") and len(left) > 100: return (right if right else f"unknown_{uuid.uuid4().hex[:8]}"), left
    parts = line.split(None, 1)
    if len(parts) == 2:
        a, b = parts[0].strip(), parts[1].strip()
        if b.startswith("1") and len(b) > 100: return a, b
        if a.startswith("1") and len(a) > 100: return b, a
    if line.startswith("1") and len(line) > 100: return f"unknown_{uuid.uuid4().hex[:8]}", line
    return None

# ==================== ПРОВЕРКА ЖИВОСТИ СЕССИИ ====================
async def check_session_alive(session_string: str) -> bool:
    """Проверяет, жива ли сессия (авторизована и не забанена)."""
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        if await client.is_user_authorized():
            await client.disconnect()
            return True
        await client.disconnect()
        return False
    except Exception as ex:
        logging.error(f"Session check failed: {ex}")
        return False

@router.callback_query(F.data == "admin_upload_sessions")
async def admin_upload_sessions(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != OWNER_ID: return
    await call.message.answer("Отправьте сессии (каждая с новой строки) или .txt файлом.\nФорматы:\nphone|session_string\nphone:session_string\nphone session_string\nsession_string")
    await state.set_state(AdminStates.waiting_for_sessions)
    await call.answer()

@router.callback_query(F.data == "admin_add_session_one")
async def admin_add_session_one(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != OWNER_ID: return
    await call.message.answer("Отправьте одну сессию в любом формате.")
    await state.set_state(AdminStates.waiting_for_sessions)
    await call.answer()

@router.message(AdminStates.waiting_for_sessions)
async def admin_save_sessions(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID: return
    raw_lines = []
    if message.text: raw_lines = message.text.splitlines()
    elif message.document:
        try:
            file = await bot.get_file(message.document.file_id)
            data = await bot.download_file(file.file_path)
            raw_lines = data.read().decode("utf-8", errors="ignore").splitlines()
        except Exception as ex:
            await message.answer(f"Ошибка чтения файла: {ex}")
            await state.clear()
            return
    else:
        await message.answer("Отправьте текст или .txt файл.")
        return

    ok, fail, dead = 0, 0, 0
    async with aiosqlite.connect(DB_FILE) as db:
        for line in raw_lines:
            parsed = parse_session_line(line)
            if not parsed:
                if line.strip(): fail += 1
                continue
            phone, sess = parsed

            # Проверяем, жива ли сессия перед сохранением
            if not await check_session_alive(sess):
                dead += 1
                logging.warning(f"Dead session skipped: {phone}")
                continue

            try:
                await db.execute("INSERT INTO sessions (phone, session_string) VALUES (?, ?) ON CONFLICT(phone) DO UPDATE SET session_string = excluded.session_string", (phone, sess))
                ok += 1
            except: fail += 1
        await db.commit()
        async with db.execute("SELECT COUNT(*) FROM sessions") as c: total = (await c.fetchone())[0]
    await message.answer(
        f"Загрузка сессий завершена.\n"
        f"✅ Добавлено живых: <b>{ok}</b>\n"
        f"❌ Мёртвых/невалидных: <b>{dead}</b>\n"
        f"⚠️ Ошибок парсинга: <b>{fail}</b>\n"
        f"📦 Всего в базе: <b>{total}</b>",
        parse_mode="HTML"
    )
    await state.clear()

@router.callback_query(F.data == "admin_list_sessions")
async def admin_list_sessions(call: CallbackQuery):
    if call.from_user.id != OWNER_ID: return
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT phone FROM sessions ORDER BY phone") as c: rows = await c.fetchall()
    if not rows:
        await call.message.answer("Сессий в базе нет.")
        await call.answer()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for (phone,) in rows[:50]:
        safe_phone = phone.replace("+", "_")
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"Удалить {phone}", callback_data=f"del_session_{safe_phone}", style="danger")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Удалить ВСЕ", callback_data="del_session_ALL", style="danger")])
    await call.message.answer(f"Всего сессий: {len(rows)}\nНажмите для удаления:", parse_mode="HTML", reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("del_session_"))
async def admin_del_session(call: CallbackQuery):
    if call.from_user.id != OWNER_ID: return
    target = call.data.replace("del_session_", "")
    if target != "ALL": target = target.replace("_", "+")
    async with aiosqlite.connect(DB_FILE) as db:
        if target == "ALL":
            await db.execute("DELETE FROM sessions")
            msg = "Все сессии удалены."
        else:
            await db.execute("DELETE FROM sessions WHERE phone = ?", (target,))
            msg = f"Удалена сессия {target}."
        await db.commit()
    await call.message.edit_text(msg, parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "admin_upload_emails")
async def admin_upload_emails(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != OWNER_ID: return
    await call.message.answer("Отправьте почты (каждая с новой строки) или .txt файлом.\nФормат: email:password:smtp_server:port")
    await state.set_state(AdminStates.waiting_for_emails)
    await call.answer()

@router.message(AdminStates.waiting_for_emails)
async def admin_save_emails(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID: return
    raw_lines = []
    if message.text: raw_lines = message.text.splitlines()
    elif message.document:
        try:
            file = await bot.get_file(message.document.file_id)
            data = await bot.download_file(file.file_path)
            raw_lines = data.read().decode("utf-8", errors="ignore").splitlines()
        except Exception as ex:
            await message.answer(f"Ошибка чтения файла: {ex}")
            await state.clear()
            return
    else:
        await message.answer("Отправьте текст или .txt файл.")
        return

    ok, fail = 0, 0
    async with aiosqlite.connect(DB_FILE) as db:
        for line in raw_lines:
            line = line.strip()
            if not line: continue
            parts = line.split(":")
            if len(parts) != 4:
                fail += 1
                continue
            email, pwd, server, port = [p.strip() for p in parts]
            try: port_i = int(port)
            except ValueError:
                fail += 1
                continue
            try:
                await db.execute("INSERT INTO emails (email, password, smtp_server, smtp_port) VALUES (?, ?, ?, ?)", (email, pwd, server, port_i))
                ok += 1
            except: fail += 1
        await db.commit()
        async with db.execute("SELECT COUNT(*) FROM emails") as c: total = (await c.fetchone())[0]
    await message.answer(f"Загрузка почт завершена.\nДобавлено: <b>{ok}</b>\nОшибок: <b>{fail}</b>\nВсего в базе: <b>{total}</b>", parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data == "admin_support")
async def admin_support(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != OWNER_ID: return
    current = await get_setting('support_username')
    await call.message.answer(f"Текущий ник поддержки: {current}\nВведите новый ник (без @):", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_support_username)
    await call.answer()

@router.message(AdminStates.waiting_for_support_username)
async def admin_save_support(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID: return
    new_nick = (message.text or "").strip().lstrip("@")
    if not new_nick:
        await message.answer("Пустой ник.")
        return
    await set_setting('support_username', new_nick)
    await message.answer(f"Ник поддержки изменён на {new_nick}", parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data == "admin_give_sub")
async def admin_give_sub(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != OWNER_ID: return
    await call.message.answer("Введите ID пользователя:")
    await state.set_state(AdminStates.waiting_for_admin_sub_user)
    await call.answer()

@router.message(AdminStates.waiting_for_admin_sub_user)
async def admin_give_sub_user(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
        await state.update_data(uid=uid)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="7 дней", callback_data="admin_sub_7d")],
            [InlineKeyboardButton(text="30 дней", callback_data="admin_sub_30d")],
            [InlineKeyboardButton(text="Навсегда", callback_data="admin_sub_inf")]
        ])
        await message.answer("Выберите тариф:", reply_markup=kb)
        await state.set_state(AdminStates.waiting_for_admin_sub_tariff)
    except:
        await message.answer("Ошибка: ID должен быть числом.")

@router.callback_query(AdminStates.waiting_for_admin_sub_tariff, F.data.startswith("admin_sub_"))
async def admin_give_sub_tariff(call: CallbackQuery, state: FSMContext):
    tariff_key = call.data.replace("admin_sub_", "")
    data = await state.get_data()
    uid = data.get("uid")
    await give_subscription(uid, tariff_key)
    await call.message.edit_text(f"Подписка выдана пользователю {uid}.")
    await state.clear()

@router.callback_query(F.data == "admin_unsub")
async def admin_unsub(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != OWNER_ID: return
    await call.message.answer("Введите ID пользователя для снятия подписки:")
    await state.set_state(AdminStates.waiting_for_admin_unsub_user)
    await call.answer()

@router.message(AdminStates.waiting_for_admin_unsub_user)
async def admin_unsub_user(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("UPDATE users SET sub_until = NULL, is_forever = 0 WHERE user_id = ?", (uid,))
            await db.commit()
        await message.answer(f"Подписка пользователя {uid} снята.")
    except:
        await message.answer("Ошибка: ID должен быть числом.")
    await state.clear()

@router.callback_query(F.data == "admin_add_phone")
async def admin_add_phone(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != OWNER_ID: return
    await call.message.answer("Введите номер телефона (например, +79991234567):")
    await state.set_state(AdminStates.waiting_for_login_phone)
    await call.answer()

@router.message(AdminStates.waiting_for_login_phone)
async def admin_login_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        sent = await client.send_code_request(phone)
        await state.update_data(phone=phone, code_hash=sent.phone_code_hash)
        await message.answer("Код отправлен в Telegram. Введите его сюда:")
        await state.set_state(AdminStates.waiting_for_login_code)
        await state.update_data(client=client)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
        await state.clear()

@router.message(AdminStates.waiting_for_login_code)
async def admin_login_code(message: Message, state: FSMContext):
    code = message.text.strip()
    data = await state.get_data()
    phone = data.get("phone")
    client = data.get("client")
    code_hash = data.get("code_hash")
    try:
        await client.sign_in(phone, code, phone_code_hash=code_hash)
        session_str = client.session.save()
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("INSERT OR REPLACE INTO sessions (phone, session_string) VALUES (?, ?)", (phone, session_str))
            await db.commit()
        await message.answer(f"Сессия для {phone} успешно добавлена!")
        await client.disconnect()
        await state.clear()
    except SessionPasswordNeededError:
        await message.answer("Введите пароль 2FA:")
        await state.set_state(AdminStates.waiting_for_login_password)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
        await state.clear()

@router.message(AdminStates.waiting_for_login_password)
async def admin_login_password(message: Message, state: FSMContext):
    password = message.text.strip()
    data = await state.get_data()
    phone = data.get("phone")
    client = data.get("client")
    try:
        await client.sign_in(password=password)
        session_str = client.session.save()
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("INSERT OR REPLACE INTO sessions (phone, session_string) VALUES (?, ?)", (phone, session_str))
            await db.commit()
        await message.answer(f"Сессия для {phone} успешно добавлена!")
        await client.disconnect()
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
    await state.clear()

@router.callback_query(F.data == "admin_broadcast_channels")
async def admin_broadcast_channels(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != OWNER_ID: return
    await call.message.answer("Отправьте сообщение для рассылки по каналам, где бот админ:")
    await state.set_state(AdminStates.waiting_for_channel_broadcast)
    await call.answer()

@router.message(AdminStates.waiting_for_channel_broadcast, F.text | F.photo)
async def admin_broadcast_channels_exec(message: Message, state: FSMContext):
    await state.clear()
    status = await message.answer("🔄 Собираю каналы...")
    
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT channel_id FROM sponsor_channels") as c:
            channels = await c.fetchall()
    
    ok, fail = 0, 0
    for (ch_id,) in channels:
        try:
            await bot.copy_message(chat_id=ch_id, from_chat_id=message.chat.id, message_id=message.message_id)
            ok += 1
        except:
            fail += 1
        await asyncio.sleep(0.1)
        
    await status.edit_text(f"✅ Рассылка по каналам завершена.\nУспешно: {ok}\nОшибок: {fail}")

async def main():
    await init_db()
    logging.info("Бот запущен!")
    asyncio.create_task(monitor_ton())
    asyncio.create_task(monitor_usdt())
    asyncio.create_task(monitor_crypto_invoices())
    
    bots = [bot]
    
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT token FROM mirrors") as c:
            for (m_token,) in await c.fetchall():
                try:
                    bots.append(Bot(token=m_token))
                    logging.info(f"Зеркало {m_token[:10]}... готово к запуску!")
                except Exception as e:
                    logging.error(f"Ошибка создания зеркала: {e}")
                    
    await asyncio.gather(
        dp.start_polling(*bots, allowed_updates=["message", "callback_query", "pre_checkout_query"]),
        dp_stars.start_polling(stars_bot, allowed_updates=["message", "callback_query", "pre_checkout_query"])
    )

if __name__ == "__main__":
    asyncio.run(main())