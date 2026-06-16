# راهنمای راه‌اندازی ربات جام جهانی ۲۰۲۶

## مرحله ۰ — پیش‌نیازها (یک‌بار انجام بده)

### الف) ساخت ربات و گرفتن توکن
۱. در بله وارد `@botfather` شو.
۲. دستور `/newbot` را بفرست و مراحل را طی کن.
۳. در پایان یک **توکن** می‌گیری (مثل `123456:ABC...`). آن را یادداشت کن.
۴. **یوزرنیم ربات** را هم یادداشت کن (مثلا `MyCupBot`).

### ب) ادمین کردن ربات در کانال (خیلی مهم!)
برای اینکه ربات بتواند عضویت را چک کند، **حتماً** ربات را
در کانال `@khabarelahzeii` به‌عنوان **ادمین** اضافه کن.
(تنظیمات کانال → مدیران → افزودن مدیر → ربات خودت را اضافه کن)
⚠️ اگر این کار را نکنی، چک عضویت کار نمی‌کند.

---

## مرحله ۱ — اتصال به سرور (VPS)

از طریق برنامه‌ای مثل **PuTTY** (ویندوز) یا ترمینال، با SSH به سرور وصل شو:
```
ssh root@آی‌پی-سرور
```

---

## مرحله ۲ — نصب پایتون و ابزارها

دستورات زیر را یکی‌یکی کپی و اجرا کن (برای اوبونتو):
```bash
apt update
apt install -y python3 python3-pip python3-venv git
```

---

## مرحله ۳ — انتقال فایل‌ها به سرور

یک پوشه بساز و همه‌ی فایل‌های پروژه را داخلش بگذار:
```bash
mkdir -p /root/worldcup_bot
cd /root/worldcup_bot
```
فایل‌ها را با برنامه‌ای مثل **WinSCP** (ویندوز) داخل این پوشه آپلود کن.
(ساختار باید مثل این باشد: config.py، bot.py، panel.py، database.py،
requirements.txt و پوشه‌ی templates با همه فایل‌های html)

---

## مرحله ۴ — نصب کتابخانه‌ها

```bash
cd /root/worldcup_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## مرحله ۵ — تنظیم config.py

فایل تنظیمات را باز کن:
```bash
nano config.py
```
این موارد را پر کن:
- `BOT_TOKEN` = توکنی که از botfather گرفتی
- `BOT_USERNAME` = یوزرنیم ربات بدون @
- `ADMIN_PASSWORD` = یک رمز قوی برای پنل
- `PANEL_SECRET_KEY` = یک رشته تصادفی طولانی

برای ذخیره: `Ctrl+O` بعد `Enter` بعد `Ctrl+X`

---

## مرحله ۶ — تست اولیه

ربات را تست کن:
```bash
python3 bot.py
```
اگر پیام «ربات در حال اجراست...» را دیدی، یعنی درست است.
حالا در بله به ربات `/start` بزن و تست کن.
برای توقف: `Ctrl+C`

پنل را تست کن:
```bash
python3 panel.py
```
در مرورگر برو به: `http://آی‌پی-سرور:8080`
با نام کاربری `admin` و رمزی که گذاشتی وارد شو.

---

## مرحله ۷ — اجرای دائمی (همیشه روشن بماند)

تا اینجا با بستن ترمینال، ربات هم خاموش می‌شود.
برای اینکه همیشه روشن بماند، از **systemd** استفاده می‌کنیم.

### سرویس ربات:
```bash
nano /etc/systemd/system/worldcup-bot.service
```
این متن را بگذار:
```ini
[Unit]
Description=World Cup Bale Bot
After=network.target

[Service]
WorkingDirectory=/root/worldcup_bot
ExecStart=/root/worldcup_bot/venv/bin/python3 bot.py
Restart=always
User=root

[Install]
WantedBy=multi-user.target
```

### سرویس پنل:
```bash
nano /etc/systemd/system/worldcup-panel.service
```
```ini
[Unit]
Description=World Cup Panel
After=network.target

[Service]
WorkingDirectory=/root/worldcup_bot
ExecStart=/root/worldcup_bot/venv/bin/python3 panel.py
Restart=always
User=root

[Install]
WantedBy=multi-user.target
```

### فعال‌سازی هر دو:
```bash
systemctl daemon-reload
systemctl enable worldcup-bot worldcup-panel
systemctl start worldcup-bot worldcup-panel
```

### بررسی وضعیت:
```bash
systemctl status worldcup-bot
systemctl status worldcup-panel
```
اگر سبز و `active (running)` بود، همه‌چیز درست است! 🎉

---

## دستورات روزمره

| کار | دستور |
|-----|-------|
| دیدن خطاهای ربات | `journalctl -u worldcup-bot -f` |
| ری‌استارت ربات | `systemctl restart worldcup-bot` |
| ری‌استارت پنل | `systemctl restart worldcup-panel` |
| بکاپ دیتابیس | `cp /root/worldcup_bot/worldcup.db ~/backup.db` |

---

## نکات مهم
- پورت پنل (8080) را در فایروال سرور باز کن.
- حتماً از فایل `worldcup.db` به‌صورت دوره‌ای بکاپ بگیر (همه‌ی امتیازها آنجاست).
- منابع سرور تو (۱ هسته، ۲ گیگ رم) برای این ربات کاملاً کافیست.
