import telebot
from telebot import apihelper
import time
import logging
from config import BOT_TOKEN, CHANNEL_USERNAME

# تنظیم آدرس API برای بله
apihelper.API_URL = "https://tapi.bale.ai/bot{0}/{1}"

# راه‌اندازی ربات
bot = telebot.TeleBot(BOT_TOKEN)

# لاگ‌گیری ساده
logging.basicConfig(level=logging.INFO)

def is_member(user_id):
    """بررسی می‌کند که کاربر عضو کانال هست یا نه"""
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"⚠️ خطا در بررسی عضویت کاربر {user_id}: {e}")
        return False

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    try:
        if is_member(user_id):
            bot.send_message(
                user_id,
                "✅ به ربات خوش آمدید!\n"
                "شما عضو کانال هستید و می‌توانید از ربات استفاده کنید.\n"
                "برای راهنما /help را بزنید."
            )
        else:
            bot.send_message(
                user_id,
                f"❌ برای استفاده از ربات ابتدا در کانال {CHANNEL_USERNAME} عضو شوید.\n"
                "سپس دوباره /start را بزنید."
            )
    except Exception as e:
        print(f"⚠️ خطا در ارسال پیام شروع به {user_id}: {e}")

@bot.message_handler(commands=['help'])
def help(message):
    user_id = message.from_user.id
    try:
        bot.send_message(
            user_id,
            "📌 راهنمای ربات:\n"
            "/start - شروع و بررسی عضویت\n"
            "/help - نمایش این راهنما"
        )
    except Exception as e:
        print(f"⚠️ خطا در ارسال راهنما به {user_id}: {e}")

@bot.message_handler(func=lambda message: True)
def fallback(message):
    """
    این تابع برای هر پیام دیگری که دستور خاصی ندارد اجرا می‌شود.
    فقط به کاربرانی پاسخ می‌دهد که در چت خصوصی پیام داده‌اند.
    """
    # اگر پیام از گروه یا کانال باشد و فرستنده مشخص نباشد، نادیده بگیر
    if message.from_user is None:
        return

    # فقط پیام‌های خصوصی را پردازش کن
    if message.chat.type != 'private':
        return

    user_id = message.from_user.id
    try:
        bot.send_message(user_id, "لطفاً ابتدا /start را بزنید.")
    except Exception as e:
        # اگر کاربر ربات را بلاک کرده باشد یا دسترسی نباشد، فقط لاگ کن
        print(f"⚠️ خطا در ارسال پاسخ به {user_id}: {e}")

# اجرای ربات با Polling
if __name__ == "__main__":
    print("🤖 ربات در حال اجراست... (برای توقف Ctrl+C)")
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"⚠️ خطا در Polling: {e}")
            time.sleep(5)
