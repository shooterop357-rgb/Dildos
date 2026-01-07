import os, time, json, threading
from datetime import datetime, timedelta
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

MAIN_ADMIN = "5436530930"

MAX_ATTACK_TIME = 300        # 5 min
COOLDOWN_TIME = 1200         # 20 min
USERS_FILE = "users.json"

# ================= STATE =================
running = {}        # uid -> end_time
cooldown = {}       # uid -> last_end
awaiting = set()    # uid waiting for params
admin_chat = set()  # uid chatting with admin
lock = threading.Lock()

# ================= USERS =================
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    return json.load(open(USERS_FILE))

def save_users(d):
    json.dump(d, open(USERS_FILE, "w"), indent=2)

users = load_users()

def role(uid):
    if uid == MAIN_ADMIN:
        return "main"
    return users.get(uid, {}).get("role")

def expired(uid):
    if uid == MAIN_ADMIN:
        return False
    u = users.get(uid)
    if not u:
        return True
    return datetime.now() > datetime.fromisoformat(u["expires_at"])

# ================= UI =================
def menu(uid):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🚀 Attack", callback_data="attack"),
        InlineKeyboardButton("📞 Contact Admin", callback_data="contact"),
    )
    if uid in running:
        kb.add(InlineKeyboardButton("🛑 Stop Attack", callback_data="stop"))
    return kb

def end_chat_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("❌ End Admin Chat", callback_data="endchat"))
    return kb

# ================= CALLBACKS =================
@bot.callback_query_handler(func=lambda c: True)
def callbacks(c):
    uid = str(c.message.chat.id)

    if c.data == "attack":
        if expired(uid):
            bot.answer_callback_query(c.id, "Plan expired. Contact admin.", show_alert=True)
            return
        awaiting.add(uid)
        bot.edit_message_text(
            "Enter:\n<code>IP PORT SECONDS</code>\nExample:\n<code>1.1.1.1 80 120</code>",
            uid, c.message.message_id, reply_markup=menu(uid)
        )

    elif c.data == "contact":
        admin_chat.add(uid)
        bot.edit_message_text(
            "💬 <b>Admin chat enabled</b>\nType your message.",
            uid, c.message.message_id, reply_markup=end_chat_kb()
        )

    elif c.data == "endchat":
        admin_chat.discard(uid)
        bot.edit_message_text(
            "✅ <b>Admin chat closed</b>",
            uid, c.message.message_id, reply_markup=menu(uid)
        )

    elif c.data == "stop":
        stop_attack(uid)
        bot.edit_message_text(
            "🛑 <b>Attack stopped</b>\n⏳ Cooldown started (20 min)",
            uid, c.message.message_id, reply_markup=menu(uid)
        )

# ================= ADMIN CHAT =================
@bot.message_handler(func=lambda m: str(m.chat.id) in admin_chat and str(m.chat.id) != MAIN_ADMIN)
def user_to_admin(m):
    bot.send_message(MAIN_ADMIN, f"👤 User <code>{m.chat.id}</code>:\n{m.text}")

@bot.message_handler(func=lambda m: str(m.chat.id) == MAIN_ADMIN and m.reply_to_message)
def admin_to_user(m):
    try:
        uid = m.reply_to_message.text.split("<code>")[1].split("</code>")[0]
        bot.send_message(uid, m.text)
    except:
        pass

# ================= ATTACK (SIMULATED) =================
def stop_attack(uid):
    with lock:
        if uid in running:
            running.pop(uid)
            cooldown[uid] = time.time()

@bot.message_handler(func=lambda m: str(m.chat.id) in awaiting)
def receive_attack(m):
    uid = str(m.chat.id)

    if uid in admin_chat:
        return

    awaiting.discard(uid)

    if expired(uid):
        bot.send_message(uid, "Plan expired.", reply_markup=menu(uid))
        return

    if uid != MAIN_ADMIN:
        last = cooldown.get(uid)
        if last and time.time() - last < COOLDOWN_TIME:
            bot.send_message(uid, "Next attack after 20 minutes.", reply_markup=menu(uid))
            return

    try:
        ip, port, sec = m.text.split()
        sec = int(sec)
        if sec > MAX_ATTACK_TIME:
            raise ValueError
    except:
        bot.send_message(uid, "Invalid format.", reply_markup=menu(uid))
        return

    end_time = time.time() + sec
    with lock:
        running[uid] = end_time

    bot.send_message(
        uid,
        f"✅ <b>Attack started</b>\nTarget: {ip}\nTime: {sec}s",
        reply_markup=menu(uid)
    )

    def finish():
        while time.time() < end_time:
            time.sleep(1)
        with lock:
            if uid in running:
                running.pop(uid)
                cooldown[uid] = time.time()
        bot.send_message(
            uid,
            "✅ <b>Attack completed</b>\n⏳ Cooldown: 20 minutes",
            reply_markup=menu(uid)
        )

    threading.Thread(target=finish, daemon=True).start()

# ================= ADMIN COMMANDS =================
@bot.message_handler(commands=["adduser", "addadmin"])
def add_user(m):
    if str(m.chat.id) != MAIN_ADMIN:
        return
    try:
        _, uid, days = m.text.split()
        days = int(days)
        role = "admin" if m.text.startswith("/addadmin") else "user"
        exp = datetime.now() + timedelta(days=days)
        users[uid] = {"role": role, "expires_at": exp.isoformat()}
        save_users(users)
        bot.reply_to(m, f"✅ {role} added for {days} days")
    except:
        bot.reply_to(m, "Usage: /adduser <id> <days>")

# ================= START =================
@bot.message_handler(commands=["start"])
def start(m):
    uid = str(m.chat.id)
    bot.send_message(
        uid,
        "👋 <b>Welcome</b>\nChoose an option:",
        reply_markup=menu(uid)
    )

# ================= RUN =================
while True:
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(e)
        time.sleep(3)
