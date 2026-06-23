# -*- coding: utf-8 -*-
"""
ربات گیمیفیکیشن جام جهانی ۲۰۲۶ برای پیام‌رسان بله.
نسخه با زمان تهران، نفرات برتر، و بازگشت خودکار.
"""
import random
import string
import time
from datetime import datetime

import pytz
import telebot
from telebot import apihelper
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

import config
import database as db

# ★ تغییر آدرس سرور از تلگرام به بله
apihelper.API_URL = "https://tapi.bale.ai/bot{0}/{1}"

bot = telebot.TeleBot(config.BOT_TOKEN)

db.init_db()

# منطقه زمانی تهران
TEHRAN_TZ = pytz.timezone("Asia/Tehran")

CHANNEL = getattr(config, "REQUIRED_CHANNEL", None) or getattr(config, "CHANNEL_USERNAME", "")
BOT_USERNAME = getattr(config, "BOT_USERNAME", "").lstrip("@")


# ============== ابزارهای کمکی ==============
def tehran_now():
    """زمان فعلی به وقت تهران (بدون اطلاعات منطقه زمانی، برای مقایسه)."""
    return datetime.now(TEHRAN_TZ).replace(tzinfo=None)


def gen_refcode():
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not db.get_user_by_refcode(code):
            return code


def is_member(user_id):
    try:
        member = bot.get_chat_member(CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        print(f"⚠️ خطا در بررسی عضویت کاربر {user_id}: {e}")
        return False


def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("🏆 جام جهانی"))
    kb.row(KeyboardButton("🏅 امتیاز من"), KeyboardButton("🏅 نفرات برتر"))
    kb.row(KeyboardButton("👥 دعوت دوستان"), KeyboardButton("📜 قوانین"))
    return kb


def phone_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("📱 ارسال شماره تماس", request_contact=True))
    return kb


def join_keyboard():
    kb = InlineKeyboardMarkup()
    ch = CHANNEL.lstrip("@")
    kb.add(InlineKeyboardButton("📢 عضویت در کانال", url=f"https://ble.ir/{ch}"))
    kb.add(InlineKeyboardButton("✅ عضو شدم", callback_data="check_join"))
    return kb


def parse_dt(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M")
    except Exception:
        return None


def get_state(user_id):
    user = db.get_user(user_id)
    return user["state"] if user else None


def matches_keyboard():
    """کیبورد لیست بازی‌های فعال."""
    matches = db.active_matches()
    if not matches:
        return None
    kb = InlineKeyboardMarkup()
    for m in matches:
        kb.add(InlineKeyboardButton(
            f"{m['team1']} ⚔️ {m['team2']}",
            callback_data=f"match_{m['id']}"))
    return kb


# ============== استارت ==============
@bot.message_handler(commands=["start"])
def cmd_start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    args = message.text.split()
    referred_by = None

    if len(args) > 1:
        ref = db.get_user_by_refcode(args[1].strip())
        if ref and ref["user_id"] != user_id:
            referred_by = ref["user_id"]

    user = db.get_user(user_id)
    if user is None:
        code = gen_refcode()
        db.create_user(user_id, code, referred_by)
        bot.send_message(chat_id,
            "👋 سلام و خوش آمدی!\n\n"
            "به ربات پیش‌بینی جام جهانی ۲۰۲۶ خوش آمدی.\n\n"
            "لطفاً برای شروع، نام و نام خانوادگی خود را بفرست:")
        db.update_user(user_id, state="ask_name")
    else:
        if user["state"] == "done":
            bot.send_message(chat_id, "خوش برگشتی! 👇", reply_markup=main_menu())
        else:
            resume_registration(user, chat_id)


def resume_registration(user, chat_id):
    if user["state"] == "ask_name":
        bot.send_message(chat_id, "لطفاً نام و نام خانوادگی خود را بفرست:")
    elif user["state"] == "ask_phone":
        bot.send_message(chat_id, "لطفاً شماره تماس خود را با دکمه زیر ارسال کن:",
                         reply_markup=phone_keyboard())
    elif user["state"] == "ask_join":
        bot.send_message(chat_id,
            f"برای استفاده از ربات باید در کانال ما عضو شوی:\n{CHANNEL}",
            reply_markup=join_keyboard())


# ============== راهنما ==============
@bot.message_handler(commands=["help"])
def cmd_help(message):
    bot.send_message(message.chat.id,
        "📌 راهنمای ربات:\n"
        "/start - شروع\n\n"
        "از دکمه‌های پایین صفحه استفاده کن:\n"
        "🏆 جام جهانی - دیدن بازی‌ها و پیش‌بینی\n"
        "🏅 امتیاز من - مشاهده امتیاز\n"
        "🏅 نفرات برتر - جدول ۱۰ نفر اول\n"
        "👥 دعوت دوستان - گرفتن لینک دعوت\n"
        "📜 قوانین - قوانین مسابقه")


# ============== دریافت نام ==============
@bot.message_handler(func=lambda m: get_state(m.from_user.id) == "ask_name",
                     content_types=["text"])
def get_name(message):
    name = message.text.strip()
    if len(name) < 3:
        bot.send_message(message.chat.id, "نام خیلی کوتاه است. لطفاً نام کامل را بفرست:")
        return
    db.update_user(message.from_user.id, full_name=name, state="ask_phone")
    bot.send_message(message.chat.id,
        f"ممنون {name} عزیز! ✅\n\n"
        "حالا لطفاً شماره تماس خود را با دکمه‌ی زیر ارسال کن:",
        reply_markup=phone_keyboard())


# ============== دریافت شماره ==============
@bot.message_handler(content_types=["contact"])
def get_contact(message):
    if get_state(message.from_user.id) != "ask_phone":
        return
    phone = message.contact.phone_number
    db.update_user(message.from_user.id, phone=phone, state="ask_join")
    bot.send_message(message.chat.id,
        "شماره‌ات ثبت شد ✅\n\n"
        f"آخرین مرحله: برای استفاده از ربات باید عضو کانال ما باشی:\n{CHANNEL}",
        reply_markup=join_keyboard())


# ============== چک عضویت ==============
@bot.callback_query_handler(func=lambda c: c.data == "check_join")
def cb_check_join(call):
    uid = call.from_user.id
    chat_id = call.message.chat.id
    if is_member(uid):
        user = db.get_user(uid)
        if user and user["referred_by"] and user["state"] != "done":
            db.add_points(user["referred_by"], config.POINTS_REFERRAL)
            try:
                bot.send_message(user["referred_by"],
                    "🎉 یک نفر با لینک دعوت تو عضو شد!\n"
                    f"{config.POINTS_REFERRAL} امتیاز به تو اضافه شد.")
            except Exception:
                pass

        db.update_user(uid, state="done")
        bot.answer_callback_query(call.id, "عضویت تایید شد ✅")
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        bot.send_message(chat_id,
            "🎉 ثبت‌نام تو کامل شد!\n\nاز منوی زیر استفاده کن 👇",
            reply_markup=main_menu())
    else:
        bot.answer_callback_query(call.id,
            "هنوز عضو کانال نشده‌ای! اول عضو شو بعد دکمه «عضو شدم» را بزن.",
            show_alert=True)


# ============== گارد عضویت ==============
def ensure_ready(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user = db.get_user(user_id)
    if user is None:
        bot.send_message(chat_id, "لطفاً ابتدا /start را بزن.")
        return False
    if user["state"] != "done":
        resume_registration(user, chat_id)
        return False
    if not is_member(user_id):
        db.update_user(user_id, state="ask_join")
        bot.send_message(chat_id,
            f"به نظر می‌رسد از کانال خارج شده‌ای. برای ادامه دوباره عضو شو:\n{CHANNEL}",
            reply_markup=join_keyboard())
        return False
    return True


# ============== دکمه: قوانین ==============
@bot.message_handler(func=lambda m: m.text == "📜 قوانین")
def show_rules(message):
    if not ensure_ready(message):
        return
    rules = db.get_setting("rules") or "قوانینی ثبت نشده است."
    bot.send_message(message.chat.id, rules)


# ============== دکمه: امتیاز من ==============
@bot.message_handler(func=lambda m: m.text == "🏅 امتیاز من")
def show_points(message):
    if not ensure_ready(message):
        return
    user = db.get_user(message.from_user.id)
    refs = db.count_referrals(message.from_user.id)
    bot.send_message(message.chat.id,
        f"🏅 امتیاز شما: {user['points']}\n"
        f"👥 تعداد دوستان دعوت‌شده: {refs}")


# ============== دکمه: نفرات برتر ==============
@bot.message_handler(func=lambda m: m.text == "🏅 نفرات برتر")
def show_top(message):
    if not ensure_ready(message):
        return
    tops = db.top_users(10)
    if not tops:
        bot.send_message(message.chat.id,
            "🏆 هنوز کسی امتیازی کسب نکرده است.\nاولین نفر باش! ⚽")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 جدول ۱۰ نفر برتر:\n"]
    for i, u in enumerate(tops):
        rank = medals[i] if i < 3 else f"{i + 1}."
        name = u["full_name"] or "بدون نام"
        lines.append(f"{rank} {name} — {u['points']} امتیاز")
    bot.send_message(message.chat.id, "\n".join(lines))


# ============== دکمه: دعوت دوستان ==============
@bot.message_handler(func=lambda m: m.text == "👥 دعوت دوستان")
def show_referral(message):
    if not ensure_ready(message):
        return
    user = db.get_user(message.from_user.id)
    link = f"https://ble.ir/{BOT_USERNAME}?start={user['referral_code']}"
    refs = db.count_referrals(message.from_user.id)
    bot.send_message(message.chat.id,
        "👥 دعوت دوستان\n\n"
        "این لینک اختصاصی توست. هر کسی با آن وارد ربات شود و عضو کانال شود، "
        f"{config.POINTS_REFERRAL} امتیاز به تو هدیه داده می‌شود!\n\n"
        f"🔗 لینک دعوت تو:\n{link}\n\n"
        f"تا الان {refs} نفر را دعوت کرده‌ای.")


# ============== دکمه: جام جهانی ==============
@bot.message_handler(func=lambda m: m.text == "🏆 جام جهانی")
def show_worldcup(message):
    if not ensure_ready(message):
        return

    intro = (
        "🏆 پیش‌بینی بازی‌های جام جهانی ۲۰۲۶\n\n"
        "روی هر بازی که می‌زنی، پیش‌بینی می‌کنی که تیمِ اول (تیمی که اول نوشته شده) "
        "برنده می‌شود یا می‌بازد.\n\n"
        "مثال: در بازی «ایران – اوکراین» یعنی پیش‌بینی کن ایران ببرد یا ببازد.\n"
        "هر پاسخ درست = ۱۰ امتیاز 🎯\n\n"
        "یکی از بازی‌های زیر را انتخاب کن:"
    )

    kb = matches_keyboard()
    if kb is None:
        bot.send_message(message.chat.id,
            intro + "\n\n⏳ در حال حاضر بازی فعالی وجود ندارد. بعداً سر بزن!")
        return
    bot.send_message(message.chat.id, intro, reply_markup=kb)


# ============== انتخاب یک بازی ==============
@bot.callback_query_handler(func=lambda c: c.data.startswith("match_"))
def cb_match(call):
    uid = call.from_user.id
    chat_id = call.message.chat.id
    match_id = int(call.data.split("_")[1])
    m = db.get_match(match_id)

    if not m or m["is_finished"]:
        bot.answer_callback_query(call.id, "این بازی دیگر در دسترس نیست.", show_alert=True)
        return

    now = tehran_now()
    start = parse_dt(m["start_time"])
    close = parse_dt(m["close_time"])

    pred = db.get_prediction(uid, match_id)
    already = ""
    if pred:
        a = "برد تیم اول" if pred["answer"] == "win" else "باخت تیم اول"
        already = f"\n\n✅ پاسخ فعلی تو: {a}\n(می‌توانی تا پایان مهلت تغییر دهی)"

    if start and now < start:
        bot.answer_callback_query(call.id,
            f"⏳ هنوز زمان پاسخ‌دهی نرسیده.\nشروع: {m['start_time']}",
            show_alert=True)
        return
    if close and now > close:
        bot.answer_callback_query(call.id,
            "⛔ مهلت پاسخ‌دهی این بازی تمام شده است.", show_alert=True)
        return

    text = (
        f"⚽ {m['team1']} ⚔️ {m['team2']}\n\n"
        f"به نظرت {m['team1']} در این بازی چه می‌کند؟\n"
        f"⏰ مهلت پاسخ تا: {m['close_time']}"
        f"{already}"
    )
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(f"✅ {m['team1']} برنده می‌شود", callback_data=f"ans_{match_id}_win"),
        InlineKeyboardButton(f"❌ {m['team1']} می‌بازد", callback_data=f"ans_{match_id}_lose"),
    )
    kb.add(InlineKeyboardButton("🔙 بازگشت به لیست بازی‌ها", callback_data="back_matches"))
    try:
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)
    bot.answer_callback_query(call.id)


# ============== بازگشت به لیست بازی‌ها ==============
@bot.callback_query_handler(func=lambda c: c.data == "back_matches")
def cb_back_matches(call):
    chat_id = call.message.chat.id
    intro = (
        "🏆 پیش‌بینی بازی‌های جام جهانی ۲۰۲۶\n\n"
        "یکی از بازی‌های زیر را انتخاب کن:"
    )
    kb = matches_keyboard()
    if kb is None:
        try:
            bot.edit_message_text(
                intro + "\n\n⏳ در حال حاضر بازی فعالی وجود ندارد.",
                chat_id, call.message.message_id)
        except Exception:
            pass
        bot.answer_callback_query(call.id)
        return
    try:
        bot.edit_message_text(intro, chat_id, call.message.message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, intro, reply_markup=kb)
    bot.answer_callback_query(call.id)


# ============== ثبت پاسخ ==============
@bot.callback_query_handler(func=lambda c: c.data.startswith("ans_"))
def cb_answer(call):
    uid = call.from_user.id
    chat_id = call.message.chat.id
    _, match_id, answer = call.data.split("_")
    match_id = int(match_id)
    m = db.get_match(match_id)

    if not m or m["is_finished"]:
        bot.answer_callback_query(call.id, "این بازی دیگر در دسترس نیست.", show_alert=True)
        return

    now = tehran_now()
    start = parse_dt(m["start_time"])
    close = parse_dt(m["close_time"])
    if start and now < start:
        bot.answer_callback_query(call.id, "هنوز زمان پاسخ‌دهی نرسیده.", show_alert=True)
        return
    if close and now > close:
        bot.answer_callback_query(call.id, "مهلت پاسخ‌دهی تمام شده.", show_alert=True)
        return

    db.save_prediction(uid, match_id, answer)
    a = "برد تیم اول" if answer == "win" else "باخت تیم اول"

    # پیام موفقیت به‌صورت پاپ‌آپ
    bot.answer_callback_query(call.id,
        f"✅ پاسخ تو ثبت شد: {a}", show_alert=True)

    # بازگشت خودکار به لیست بازی‌ها
    intro = (
        f"✅ پاسخت برای بازی «{m['team1']} ⚔️ {m['team2']}» ثبت شد: {a}\n\n"
        "🏆 می‌توانی بازی بعدی را هم پیش‌بینی کنی:"
    )
    kb = matches_keyboard()
    if kb is None:
        try:
            bot.edit_message_text(
                f"✅ پاسخت ثبت شد: {a}\n\nفعلاً بازی دیگری برای پیش‌بینی نیست.",
                chat_id, call.message.message_id)
        except Exception:
            pass
        return
    try:
        bot.edit_message_text(intro, chat_id, call.message.message_id, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, intro, reply_markup=kb)


# ============== پیام‌های متفرقه ==============
@bot.message_handler(func=lambda m: True, content_types=["text"])
def fallback(message):
    if message.chat.type != "private":
        return
    state = get_state(message.from_user.id)
    if state in (None, "new"):
        bot.send_message(message.chat.id, "لطفاً ابتدا /start را بزن.")
    elif state == "done":
        bot.send_message(message.chat.id, "لطفاً از منوی زیر استفاده کن 👇",
                         reply_markup=main_menu())
    else:
        resume_registration(db.get_user(message.from_user.id), message.chat.id)


# ============== اجرا ==============
if __name__ == "__main__":
    print("🤖 ربات در حال اجراست... (برای توقف Ctrl+C)")
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"⚠️ خطا در Polling: {e}")
            time.sleep(5)
