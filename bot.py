import os, time, json, threading
from datetime import datetime, timedelta
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

MAIN_ADMIN = "5436530930"
MAX_ATTACK_TIME = 300     # 5 minutes
COOLDOWN_TIME = 1200      # 20 minutes
USERS_FILE = "users.json"

PLANS = {1: 100, 3: 150, 7: 300}

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
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(d):
    with open(USERS_FILE, "w") as f:
        json.dump(d, f, indent=2)

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

def remaining_days(uid):
    if uid == MAIN_ADMIN:
        return "Unlimited"
    u = users.get(uid)
    if not u:
        return "Expired"
    return max((datetime.fromisoformat(u["expires_at"]) - datetime.now()).days, 0)

# ================= UI =================
def get_menu(uid):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🚀 Attack", callback_data="attack"),
        InlineKeyboardButton("📞 Contact Admin", callback_data="contact"),
        InlineKeyboardButton("👤 User Panel", callback_data="panel"),
        InlineKeyboardButton("💳 Plans", callback_data="plans"),
    )
    if role(uid) == "main":
        kb.add(
            InlineKeyboardButton("➕ Add User", callback_data="adduser"),
            InlineKeyboardButton("➕ Add Admin", callback_data="addadmin"),
            InlineKeyboardButton("➖ Remove User", callback_data="remove"),
        )
    if uid in running:
        kb.add(InlineKeyboardButton("🛑 Stop Attack", callback_data="stop"))
    return kb

def end_chat_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("❌ End Admin Chat", callback_data="endchat"))
    return kb

# ================= HELPERS =================
def edit(chat_id, message_id, text, kb=None):
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=kb
    )

# ================= START =================
@bot.message_handler(commands=["start"])
def start(m):
    uid = str(m.chat.id)
    text = (
        "👑 <b>Main Admin Detected</b>\nFull control enabled."
        if uid == MAIN_ADMIN
        else "👋 <b>Welcome</b>\nChoose an option below"
    )
    bot.send_message(uid, text, reply_markup=get_menu(uid))

# ================= CALLBACKS =================
@bot.callback_query_handler(func=lambda c: True)
def callbacks(c):
    uid = str(c.message.chat.id)
    mid = c.message.message_id

    if c.data == "attack":
        if expired(uid):
            bot.answer_callback_query(c.id, "Plan expired. Contact admin.", show_alert=True)
            return
        awaiting.add(uid)
        edit(uid, mid,
             "📝 Enter:\n<code>IP PORT SECONDS</code>\nExample:\n<code>1.1.1.1 80 120</code>",
             get_menu(uid))

    elif c.data == "contact":
        admin_chat.add(uid)
        edit(uid, mid, "💬 <b>Admin chat enabled</b>\nType your message.", end_chat_kb())

    elif c.data == "endchat":
        admin_chat.discard(uid)
        edit(uid, mid, "✅ <b>Admin chat closed</b>", get_menu(uid))

    elif c.data == "panel":
        edit(
            uid, mid,
            f"👤 <b>User Panel</b>\n\nRole: <b>{role(uid)}</b>\nRemaining Days: <b>{remaining_days(uid)}</b>",
            get_menu(uid)
        )

    elif c.data == "plans":
        txt = "💳 <b>Available Plans</b>\n\n"
        for d, p in PLANS.items():
            txt += f"{d} Day(s) – ₹{p}\n"
        txt += "\nContact admin to purchase."
        edit(uid, mid, txt, get_menu(uid))

    elif c.data == "stop":
        stop_attack(uid)
        edit(uid, mid, "🛑 <b>Attack stopped</b>\n⏳ Cooldown started (20 min)", get_menu(uid))

    elif c.data in ("adduser", "addadmin", "remove") and uid == MAIN_ADMIN:
        help_map = {
            "adduser": "/adduser USERID DAYS",
            "addadmin": "/addadmin USERID DAYS",
            "remove": "/remove USERID"
        }
        edit(uid, mid, f"Usage:\n<code>{help_map[c.data]}</code>", get_menu(uid))

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
        bot.send_message(uid, "Plan expired.")
        return

    if uid != MAIN_ADMIN:
        last = cooldown.get(uid)
        if last and time.time() - last < COOLDOWN_TIME:
            bot.send_message(uid, "⏳ Next attack after 20 minutes.")
            return

    try:
        ip, port, sec = m.text.split()
        sec = int(sec)
        if sec > MAX_ATTACK_TIME:
            raise ValueError
    except:
        bot.send_message(uid, "❌ Invalid format. Use: IP PORT SECONDS")
        return

    end_time = time.time() + sec
    running[uid] = end_time

    msg = bot.send_message(uid, f"✅ <b>Attack started</b>\nTarget: {ip}\nTime: {sec}s",
                           reply_markup=get_menu(uid))

    def finish():
        while time.time() < end_time:
            time.sleep(1)
        if uid in running:
            running.pop(uid)
            cooldown[uid] = time.time()
            edit(uid, msg.message_id,
                 "✅ <b>Attack completed</b>\n⏳ Cooldown: 20 minutes",
                 get_menu(uid))

    threading.Thread(target=finish, daemon=True).start()

# ================= ADMIN COMMANDS =================
@bot.message_handler(commands=["adduser", "addadmin"])
def add_user(m):
    if str(m.chat.id) != MAIN_ADMIN:
        return
    try:
        _, uid, days = m.text.split()
        days = int(days)
        r = "admin" if m.text.startswith("/addadmin") else "user"
        exp = datetime.now() + timedelta(days=days)
        users[uid] = {"role": r, "expires_at": exp.isoformat()}
        save_users(users)
        bot.reply_to(m, f"✅ {r} {uid} added for {days} days")
    except:
        bot.reply_to(m, "Usage: /adduser <id> <days>")

@bot.message_handler(commands=["remove"])
def remove_user(m):
    if str(m.chat.id) != MAIN_ADMIN:
        return
    try:
        _, uid = m.text.split()
        users.pop(uid, None)
        save_users(users)
        bot.reply_to(m, f"Removed {uid}")
    except:
        bot.reply_to(m, "Usage: /remove <id>")

# ================= RUN =================
while True:
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(e)
        time.sleep(3)
