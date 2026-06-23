# -*- coding: utf-8 -*-
"""
پنل مدیریت ربات جام جهانی.
از طریق مرورگر باز می‌شود: http://آدرس-سرور:8080
"""
from functools import wraps
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash,
)

import config
import database as db
import requests
import threading
import time

app = Flask(__name__)
app.secret_key = config.PANEL_SECRET_KEY

db.init_db()


# ---------- احراز هویت ----------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        if u == config.ADMIN_USERNAME and p == config.ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("matches"))
        flash("نام کاربری یا رمز اشتباه است.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- صفحه اصلی: لیست بازی‌ها ----------
@app.route("/")
@login_required
def matches():
    matches = db.all_matches()
    # افزودن وضعیت خوانا
    now = datetime.now()
    for m in matches:
        if m["is_finished"]:
            m["status"] = "تمام‌شده"
        else:
            try:
                start = datetime.strptime(m["start_time"], "%Y-%m-%d %H:%M")
                close = datetime.strptime(m["close_time"], "%Y-%m-%d %H:%M")
                if now < start:
                    m["status"] = "در انتظار شروع"
                elif now <= close:
                    m["status"] = "فعال (در حال پاسخ‌دهی)"
                else:
                    m["status"] = "مهلت تمام (منتظر نتیجه)"
            except Exception:
                m["status"] = "نامشخص"
    return render_template("matches.html", matches=matches)


# ---------- افزودن بازی ----------
@app.route("/match/add", methods=["GET", "POST"])
@login_required
def add_match():
    if request.method == "POST":
        team1 = request.form.get("team1", "").strip()
        team2 = request.form.get("team2", "").strip()
        start_time = request.form.get("start_time", "").strip().replace("T", " ")
        close_time = request.form.get("close_time", "").strip().replace("T", " ")
        if team1 and team2 and start_time and close_time:
            db.add_match(team1, team2, start_time, close_time)
            flash("بازی با موفقیت اضافه شد ✅", "ok")
            return redirect(url_for("matches"))
        flash("همه‌ی فیلدها را پر کن.", "error")
    return render_template("add_match.html")


# ---------- حذف بازی ----------
@app.route("/match/<int:match_id>/delete", methods=["POST"])
@login_required
def delete_match(match_id):
    db.delete_match(match_id)
    flash("بازی حذف شد.", "ok")
    return redirect(url_for("matches"))


# ---------- ثبت نتیجه و توزیع امتیاز ----------
@app.route("/match/<int:match_id>/result", methods=["GET", "POST"])
@login_required
def set_result(match_id):
    m = db.get_match(match_id)
    if not m:
        flash("بازی یافت نشد.", "error")
        return redirect(url_for("matches"))

    if request.method == "POST":
        result = request.form.get("result")  # win یا lose
        if result not in ("win", "lose"):
            flash("نتیجه نامعتبر است.", "error")
            return redirect(url_for("set_result", match_id=match_id))

        winners = db.award_match_points(match_id, result, config.POINTS_CORRECT_ANSWER)
        db.update_match(match_id, result=result, is_finished=1)
        flash(f"نتیجه ثبت شد. به {winners} نفر امتیاز داده شد ✅ "
              f"(این بازی دیگر در ربات نمایش داده نمی‌شود)", "ok")
        return redirect(url_for("matches"))

    return render_template("result.html", match=m)


# ---------- ویرایش زمان بازی ----------
@app.route("/match/<int:match_id>/edit", methods=["GET", "POST"])
@login_required
def edit_match(match_id):
    m = db.get_match(match_id)
    if not m:
        return redirect(url_for("matches"))
    if request.method == "POST":
        db.update_match(
            match_id,
            team1=request.form.get("team1", m["team1"]).strip(),
            team2=request.form.get("team2", m["team2"]).strip(),
            start_time=request.form.get("start_time", "").replace("T", " ").strip(),
            close_time=request.form.get("close_time", "").replace("T", " ").strip(),
        )
        flash("بازی ویرایش شد ✅", "ok")
        return redirect(url_for("matches"))
    return render_template("edit_match.html", match=m)


# ---------- لیست کاربران و رتبه‌بندی (برای قرعه‌کشی) ----------
@app.route("/users")
@login_required
def users():
    users = db.all_users()
    # افزودن تعداد رفرال
    for u in users:
        u["referrals"] = db.count_referrals(u["user_id"])
    return render_template("users.html", users=users)


# ---------- تنظیمات (قوانین) ----------
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        rules = request.form.get("rules", "")
        db.set_setting("rules", rules)
        flash("قوانین ذخیره شد ✅", "ok")
        return redirect(url_for("settings"))
    rules = db.get_setting("rules") or ""
    return render_template("settings.html", rules=rules)

# ---------- ارسال پیام همگانی ----------
def _send_broadcast(text):
    """در پس‌زمینه به همه کاربران پیام می‌فرستد."""
    url = f"https://tapi.bale.ai/bot{config.BOT_TOKEN}/sendMessage"
    user_ids = db.all_user_ids()
    sent, failed = 0, 0
    for uid in user_ids:
        try:
            r = requests.post(url, data={"chat_id": uid, "text": text}, timeout=10)
            if r.ok and r.json().get("ok"):
                sent += 1
            else:
                failed += 1
        except Exception:
            failed += 1
        time.sleep(0.05)  # جلوگیری از فشار به سرور بله
    print(f"📢 پیام همگانی: {sent} موفق، {failed} ناموفق")


@app.route("/broadcast", methods=["GET", "POST"])
@login_required
def broadcast():
    total_users = len(db.all_user_ids())
    if request.method == "POST":
        text = request.form.get("text", "").strip()
        if not text:
            flash("متن پیام خالی است.", "error")
            return redirect(url_for("broadcast"))
        # ارسال در پس‌زمینه تا صفحه قفل نشود
        threading.Thread(target=_send_broadcast, args=(text,), daemon=True).start()
        flash(f"📢 پیام در حال ارسال به {total_users} کاربر است... "
              "(چند لحظه طول می‌کشد)", "ok")
        return redirect(url_for("broadcast"))
    return render_template("broadcast.html", total_users=total_users)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PANEL_PORT)
