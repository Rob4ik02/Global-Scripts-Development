import os
import sqlite3
import random
import string
import time
import smtplib
import json
import hashlib
from email.mime.text import MIMEText
from flask import Flask, render_template_string, request, jsonify, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import pytz

# --- НАСТРОЙКИ ANYPAY.IO ---
ANYPAY_MERCHANT_ID = "18042" 
ANYPAY_SECRET_KEY_1 = "WhBnybt73zKilvcgcjSVJCShtdi8xOZSHqUSaG7" 
ANYPAY_SECRET_KEY_2 = "WhBnybt73zKilvcgcjSVJCShtdi8xOZSHqUSaG7" 

# --- СИСТЕМА ЛОГИРОВАНИЯ КОНСОЛИ ---
LIVE_LOGS = []

def c_log(level, message):
    tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(tz)
    date_str = now.strftime('%d.%m.%Y | %H:%M:%S')
    
    colors = {'INFO': '\033[97m', 'SUCCESS': '\033[92m', 'WARNING': '\033[93m', 'ERROR': '\033[91m', 'SERVICE': '\033[90m', 'RESET': '\033[0m'}
    prefixes = {'INFO': 'INFORMATION', 'SUCCESS': 'SUCCES', 'WARNING': 'WARNING', 'ERROR': 'ERROR', 'SERVICE': 'SCRIPT SERVICE'}
    
    prefix = prefixes.get(level, 'LOG')
    color = colors.get(level, colors['RESET'])
    reset = colors['RESET']
    
    log_line = f"[ {prefix} - {date_str} ] = {message}"
    print(f"{color}{log_line}{reset}")
    
    LIVE_LOGS.append({'text': log_line, 'level': level.lower()})
    if len(LIVE_LOGS) > 50: LIVE_LOGS.pop(0)

c_log('SERVICE', "Initializing Flask application...")
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-dev-secret-key-123')

SMTP_EMAIL = "" 
SMTP_PASSWORD = ""

def send_real_email(to_email, code):
    if not SMTP_EMAIL or not SMTP_PASSWORD: return False 
    msg = MIMEText(f"Hello!\n\nYour Global Script's Hub 2FA verification code is: {code}\n\nThis code is valid for 15 minutes.")
    msg['Subject'] = 'Your 2FA Verification Code'
    msg['From'] = f"Global Script's <{SMTP_EMAIL}>"
    msg['To'] = to_email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        return True
    except: return False

DB_NAME = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    c_log('SERVICE', "Connecting to SQLite3 database...")
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, login TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
            email TEXT, secret TEXT, source TEXT, reg_date TEXT, plan TEXT DEFAULT 'Free Tier',
            plan_days INTEGER DEFAULT 0, dev_approved TEXT DEFAULT 'No', is_frozen TEXT DEFAULT 'No', pending_reward TEXT DEFAULT '')''')
    
    cursor = conn.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'is_frozen' not in columns: conn.execute("ALTER TABLE users ADD COLUMN is_frozen TEXT DEFAULT 'No'")
    if 'pending_reward' not in columns: conn.execute("ALTER TABLE users ADD COLUMN pending_reward TEXT DEFAULT ''")

    conn.execute('''CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT, key_code TEXT UNIQUE NOT NULL, user_login TEXT NOT NULL,
            plan TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, hwid TEXT DEFAULT '')''')

    conn.execute('''CREATE TABLE IF NOT EXISTS pending_payments (
            pay_id TEXT PRIMARY KEY, user_login TEXT NOT NULL, plan TEXT NOT NULL, amount INTEGER NOT NULL)''')

    conn.execute('''CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_login TEXT NOT NULL, plan TEXT NOT NULL,
            amount INTEGER NOT NULL, tx_id TEXT NOT NULL, date_str TEXT NOT NULL)''')

    conn.execute('''CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_login TEXT NOT NULL, reason TEXT NOT NULL,
            priority TEXT NOT NULL, status TEXT DEFAULT 'pending', created_at TEXT NOT NULL)''')
            
    conn.execute('''CREATE TABLE IF NOT EXISTS ticket_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER NOT NULL, sender TEXT NOT NULL,
            message TEXT NOT NULL, sent_at TEXT NOT NULL)''')

    conn.execute('''CREATE TABLE IF NOT EXISTS scripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, game TEXT NOT NULL,
            banner_url TEXT NOT NULL, release_date TEXT NOT NULL, script_code TEXT NOT NULL, 
            description TEXT NOT NULL, is_frozen TEXT DEFAULT 'No')''')

    conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance', 'No')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('discord_link', 'https://discord.gg/')")
    
    cursor = conn.execute("SELECT * FROM users WHERE login = 'Rob4ikDev'")
    if not cursor.fetchone():
        tz = pytz.timezone('Europe/Moscow')
        reg_date = datetime.now(tz).strftime('%d.%m.%Y')
        conn.execute('''INSERT INTO users (login, password_hash, email, secret, source, reg_date, plan, plan_days, dev_approved, is_frozen, pending_reward)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', ('Rob4ikDev', generate_password_hash('baconsecret6666'), '', 'globalscript', 'creator', reg_date, 'Developer Tier', 999, 'Yes', 'No', ''))
    
    s_cursor = conn.execute("SELECT * FROM scripts")
    if not s_cursor.fetchone():
        tz = pytz.timezone('Europe/Moscow')
        default_date = datetime.now(tz).strftime('%Y-%m-%dT%H:%M')
        conn.execute('''INSERT INTO scripts (title, game, banner_url, release_date, script_code, description, is_frozen)
            VALUES (?, ?, ?, ?, ?, ?, ?)''', 
            ('Oxygen Hub Script', 'Muscle Legends', 'https://static.wikia.nocookie.net/muscle-legends/images/5/50/Wiki-background/revision/latest/scale-to-width-down/670', 
            default_date, 'loadstring(game:HttpGet("https://raw.githubusercontent.com/Rob4ik02/Muscle-Legends-Roblox/refs/heads/main/Muscle%20Legends/Sirius%20Library/Loader.lua"))()', 
            'Good script, works in beta version. There are some bugs or errors. They say it will be updated.', 'No'))

    conn.commit(); conn.close()
    c_log('SUCCESS', "Database loaded successfully.")

init_db()

@app.route('/anypay-verification.txt')
@app.route('/7641a8b9610252ee169f2815a5c2.txt')
def anypay_txt_verify():
    return "7641a8b9610252ee169f2815a5c2", 200, {'Content-Type': 'text/plain'}

TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<meta name="anypay-verification" content="7641a8b9610252ee169f2815a5c2" />
<title>Global Script's Hub</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/lucide@latest/dist/umd/lucide.min.js"></script>
<style>
:root {
  --bg-color: #000000; --text-primary: #ffffff; --text-secondary: #888888;
  --card-bg: rgba(20, 20, 25, 0.4);
  --card-border: rgba(255, 255, 255, 0.08); --input-bg: rgba(255, 255, 255, 0.05);
  --input-border: rgba(255, 255, 255, 0.12); --accent: #ffffff; --accent-text: #000000;
  --error: #ea1515; --success: #34c759; 
  --shadow-drop: 0 15px 35px rgba(0,0,0,0.4);
  --shadow-inner: inset 0 1px 1px rgba(255, 255, 255, 0.1); 
  --blur: blur(20px) saturate(150%);
  --dot-color: rgba(255, 255, 255, 0.3); --wave-1: rgba(255, 255, 255, 0.03);
  --wave-2: rgba(255, 255, 255, 0.015); --wave-3: rgba(255, 255, 255, 0.005);
}

[data-theme="light"] {
  --bg-color: #f5f5f7; --text-primary: #1d1d1f; --text-secondary: #86868b;
  --card-bg: rgba(255, 255, 255, 0.5);
  --card-border: rgba(0, 0, 0, 0.05); --input-bg: rgba(255, 255, 255, 0.6);
  --input-border: rgba(0, 0, 0, 0.08); --accent: #1d1d1f; --accent-text: #ffffff;
  --shadow-drop: 0 12px 30px rgba(0, 0, 0, 0.08); --shadow-inner: inset 0 1px 1px rgba(255, 255, 255, 0.8);
  --dot-color: rgba(0, 0, 0, 0.2); --wave-1: rgba(0, 0, 0, 0.03); --wave-2: rgba(0, 0, 0, 0.015); --wave-3: rgba(0, 0, 0, 0.005);
}

/* Инверсия логотипа при белой теме */
[data-theme="light"] .header img {
  filter: invert(1);
}

* { box-sizing: border-box; -webkit-font-smoothing: antialiased; }
html, body { height: 100%; min-height: 100vh; margin: 0; padding: 0; }
body { font-family: 'Inter', sans-serif; background-color: var(--bg-color); color: var(--text-primary); transition: background-color 0.6s ease, color 0.6s ease; overflow-x: hidden; overflow-y: auto; background-attachment: fixed; perspective: 1000px; }

/* -------------------------------------
   DRAGON INTRO (Неоновая длинная сосиска)
-------------------------------------- */
#introOverlay { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: #000; z-index: 99999; display: flex; justify-content: center; align-items: center; overflow: hidden; transition: opacity 0.8s ease, visibility 0.8s; }
.dragon-container { display: flex; flex-direction: column; align-items: center; gap: 30px; width: 100%; }
.dragon-container h2 { color: #fff; font-weight: 800; letter-spacing: 10px; font-size: 32px; margin: 0; text-shadow: 0 0 20px rgba(255,255,255,0.5); }

.dragon-track { position: relative; width: 400px; height: 4px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; }
.white-dragon { position: absolute; top: 0; left: -250px; width: 200px; height: 100%; background: linear-gradient(90deg, transparent, #ffffff, #ffffff); box-shadow: 0 0 20px #ffffff, 0 0 40px #ffffff; border-radius: 4px; animation: dragonFlight 1.5s cubic-bezier(0.4, 0, 0.2, 1) forwards; }
@keyframes dragonFlight { 0% { left: -250px; } 100% { left: 400px; } }

/* -------------------------------------
   PARTICLE BURST (Nothing Style)
-------------------------------------- */
button { position: relative; overflow: hidden; }
.btn-particle {
    position: absolute;
    width: 6px; height: 6px;
    background: var(--text-primary);
    border-radius: 50%;
    pointer-events: none;
    transform: translate(-50%, -50%);
    animation: particleBurst 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    z-index: 10;
}
.login-to-start-btn .btn-particle, .action-btn:not(.modal-btn-cancel) .btn-particle, .copy-btn:not(:disabled) .btn-particle { background: var(--bg-color); }
@keyframes particleBurst {
    0% { transform: translate(-50%, -50%) scale(1); opacity: 1; }
    100% { transform: translate(calc(-50% + var(--tx)), calc(-50% + var(--ty))) scale(0); opacity: 0; }
}

/* -------------------------------------
   LANDING PREVIEW (Glassmorphism & Tilt)
-------------------------------------- */
#landingWrapper { display: none; flex-direction: column; align-items: center; width: 100%; min-height: 100vh; padding: 100px 20px 40px; animation: fadeInLanding 1s ease forwards; position: relative; z-index: 10; transition: opacity 0.6s ease; }
@keyframes fadeInLanding { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
.landing-hero { text-align: center; max-width: 800px; margin-top: 40px; margin-bottom: 50px; }
.landing-hero h1 { font-size: 64px; font-weight: 800; letter-spacing: -0.04em; margin-bottom: 20px; background: linear-gradient(135deg, #fff 30%, #888); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.landing-hero p { font-size: 20px; color: var(--text-secondary); line-height: 1.6; margin-bottom: 40px; }
.feature-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; width: 100%; max-width: 1100px; margin-bottom: 60px; perspective: 1200px; }

/* 3D Glassmorphism Cards - Фиксируем базовое состояние, чтобы не дергались */
.feature-box, .script-card, .plan-card, .dashboard-card {
    background: var(--card-bg);
    backdrop-filter: var(--blur);
    border: 1px solid var(--card-border);
    border-radius: 24px;
    box-shadow: var(--shadow-drop), var(--shadow-inner);
    padding: 26px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    text-align: left;
    transform: perspective(1200px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1);
    transition: transform 0.4s ease-out, box-shadow 0.4s ease;
    transform-style: preserve-3d; 
    will-change: transform;
}
.feature-box h3, .feature-box p, .script-header, .plan-card h4, .plan-card .price { transform: translateZ(20px); }
.feature-box i { transform: translateZ(30px); }

.login-to-start-btn { padding: 18px 54px; font-size: 16px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px; color: var(--accent-text); background: var(--accent); border: none; border-radius: 99px; cursor: pointer; box-shadow: 0 10px 30px rgba(255,255,255,0.2); transition: all 0.3s; transform-style: preserve-3d; }
.login-to-start-btn:hover { transform: translateY(-3px) scale(1.02); box-shadow: 0 15px 40px rgba(255,255,255,0.4); }

/* STANDARD APP UI */
.ambient-bg { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: -3; background: radial-gradient(circle at 15% 30%, rgba(40, 40, 45, 0.4) 0%, transparent 50%), radial-gradient(circle at 85% 80%, rgba(30, 30, 35, 0.4) 0%, transparent 50%); filter: blur(40px); opacity: 0; animation: ambientFade 3s ease-in-out 0.5s forwards; pointer-events: none; }
@keyframes ambientFade { to { opacity: 1; } }

#bgCanvas { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: -2; opacity: 0; animation: fadeInCanvas 2s ease-in-out forwards; pointer-events: none; }
.ocean { height: 30vh; width: 100%; position: fixed; bottom: 0; left: 0; z-index: -1; overflow: hidden; opacity: 0; animation: fadeInCanvas 3s forwards; pointer-events: none; }
.wave { background: var(--wave-1); width: 200vw; height: 200vw; position: absolute; bottom: 0; left: 50%; margin-left: -100vw; margin-bottom: -195vw; border-radius: 46%; animation: drift 25s infinite linear; }
.wave:nth-of-type(2) { background: var(--wave-2); margin-bottom: -194vw; animation: drift 30s infinite linear; border-radius: 45%; }
.wave:nth-of-type(3) { background: var(--wave-3); margin-bottom: -196vw; animation: drift 35s infinite linear; border-radius: 44%; }
@keyframes drift { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes fadeInCanvas { to { opacity: 1; } }

.app-content { display: none; flex-direction: column; align-items: center; width: 100%; min-height: 100vh; padding: 100px 20px 40px 20px; animation: liquidReveal 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
@keyframes liquidReveal { 0% { opacity: 0; transform: translateY(20px) scale(0.98); } 100% { opacity: 1; transform: translateY(0) scale(1); } }
@keyframes elasticBounce { 0% { transform: scale(0.97) translateY(10px); opacity: 0; } 50% { transform: scale(1.01) translateY(-2px); opacity: 1; } 100% { transform: scale(1) translateY(0); opacity: 1; } }
@keyframes errorShake { 0%, 100% { transform: translateX(0); } 20%, 60% { transform: translateX(-6px); } 40%, 80% { transform: translateX(6px); } }
.shake-error { animation: errorShake 0.4s forwards; }

.top-bar { position: fixed; top: 0; left: 0; width: 100vw; display: flex; justify-content: space-between; align-items: center; padding: 20px 40px; z-index: 100; background: transparent; }
.top-bar-left, .top-bar-right { display: flex; align-items: center; gap: 12px; }
.ui-pill { background: var(--card-bg); backdrop-filter: var(--blur); border: 1px solid var(--card-border); box-shadow: var(--shadow-drop), var(--shadow-inner); color: var(--text-primary); padding: 8px 16px; border-radius: 98px; font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 10px; transition: transform 0.3s, background 0.3s; cursor: pointer; position: relative;}
.ui-pill:hover { transform: scale(1.05) translateY(-1px); }

.lang-dropdown-wrapper { position: relative; }
.lang-menu { position: absolute; top: 120%; left: 0; background: var(--card-bg); backdrop-filter: var(--blur); border: 1px solid var(--card-border); border-radius: 16px; padding: 8px; display: flex; flex-direction: column; gap: 4px; opacity: 0; pointer-events: none; transform: translateY(-10px); transition: all 0.3s ease; box-shadow: var(--shadow-drop); min-width: 120px; z-index: 1000;}
.lang-menu.show { opacity: 1; pointer-events: auto; transform: translateY(0); }
.lang-option { padding: 10px 12px; font-size: 13px; font-weight: 600; cursor: pointer; border-radius: 10px; transition: background 0.2s; display: flex; align-items: center; gap: 8px;}
.lang-option:hover { background: var(--input-bg); }

.recording-dot { width: 8px; height: 8px; background-color: var(--error); border-radius: 50%; animation: liquidBlink 2.5s infinite ease-in-out; }
@keyframes liquidBlink { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.8); } }
.logout-btn { color: var(--error); } .logout-btn:hover { background: var(--error); color: #fff; }

.header { display: flex; flex-direction: column; align-items: center; gap: 12px; margin-bottom: 24px; margin-top: auto; }
.header img { width: 72px; height: 72px; border-radius: 20px; box-shadow: var(--shadow-drop); border: 1px solid var(--card-border); transition: transform 0.5s; }
.header img:hover { transform: scale(1.1) rotate(4deg); }
.header h1 { margin: 0; font-size: 32px; font-weight: 700; letter-spacing: -0.04em; }

.form-container { margin: auto; display: flex; flex-direction: column; align-items: center; gap: 10px; background: var(--card-bg); backdrop-filter: var(--blur); padding: 24px; border: 1px solid var(--card-border); border-radius: 28px; box-shadow: var(--shadow-drop); width: 100%; max-width: 360px; transition: all 0.4s; }
.form-header-text { margin: 0 0 6px 0; font-size: 14px; color: var(--text-primary); font-weight: 600; text-align: center; }
.form-container input, .form-container textarea { width: 100%; padding: 12px 16px; font-size: 13px; font-family: inherit; font-weight: 500; color: var(--text-primary); background: var(--input-bg); border: 1px solid var(--input-border); border-radius: 14px; outline: none; transition: all 0.3s; }
.form-container input::placeholder, .form-container textarea::placeholder { color: var(--text-secondary); }
.form-container input:focus, .form-container textarea:focus { border-color: var(--text-primary); transform: scale(1.02); }
.form-container button { width: 100%; padding: 12px; font-size: 14px; font-weight: 700; color: var(--accent-text); background: var(--accent); border: none; border-radius: 14px; cursor: pointer; transition: all 0.4s; margin-top: 4px; text-transform: uppercase; letter-spacing: 1px; }
.form-container button:not(:disabled):hover { transform: translateY(-2px) scale(1.02); }
.form-container button:disabled { opacity: 0.5; cursor: not-allowed; }
.checkbox-container { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--text-secondary); cursor: pointer; margin-top: 4px; width: 100%; text-align: left; }
.checkbox-container input[type="checkbox"] { width: 16px; height: 16px; cursor: pointer; accent-color: var(--text-primary); margin: 0; }
.create-link-wrapper { max-height: 0; opacity: 0; overflow: hidden; transition: all 0.5s; width: 100%; text-align: center; }
.create-link-wrapper.show { max-height: 30px; opacity: 1; margin-top: 6px; }
.create-link, .back-link { color: var(--text-primary); opacity: 0.5; font-size: 12px; font-weight: 500; cursor: pointer; text-decoration: underline; transition: opacity 0.3s;}
.create-link:hover, .back-link:hover { opacity: 1; }
.back-link { display: block; text-align: center; margin-top: 8px; }

#message, #regMessage, #twoFaMessage, #secretMessage, #keyMessage { font-weight: 600; font-size: 12px; text-align: center; min-height: 16px; opacity: 0; transition: opacity 0.4s; margin-top: 4px; }
.show { opacity: 1 !important; } .success-msg { color: #34c759; } .error-msg { color: var(--error); }

.fullscreen-overlay { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 2000; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 20px; overflow: hidden; background: rgba(0,0,0,0.6); backdrop-filter: blur(15px); }
#freezeScreen .bg-massive-icon { opacity: 0.2; color: #0abfff; filter: drop-shadow(0 0 50px #0abfff); animation: spin 10s linear infinite; }
#maintenanceScreen .bg-massive-icon { opacity: 0.15; color: #ff9f0a; filter: drop-shadow(0 0 40px #ff9f0a); animation: slowPulse 3s ease-in-out infinite; cursor: pointer; }
#rewardScreen .bg-massive-icon, #ticketSuccessOverlay .bg-massive-icon { opacity: 0.15; color: var(--success); filter: drop-shadow(0 0 50px var(--success)); animation: spin 15s linear infinite; }

.bg-massive-icon { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 280px; z-index: 1; user-select: none; }
.overlay-content-box { position: relative; z-index: 2; max-width: 650px; width: 100%; padding: 40px; border-radius: 36px; background: var(--card-bg); border: 1px solid var(--card-border); box-shadow: 0 20px 60px rgba(0,0,0,0.8); }
.freeze-card { border-top: 4px solid #0abfff; } .maint-card { border-top: 4px solid #ff9f0a; } .reward-card { border-top: 4px solid var(--success); }
.overlay-content-box h2 { margin: 0 0 16px 0; color: var(--text-primary); font-size: 28px; letter-spacing: -0.02em; }
.overlay-content-box p { margin: 0; color: var(--text-secondary); font-size: 16px; line-height: 1.5; font-weight: 500; }
@keyframes slowPulse { 0%, 100% { transform: translate(-50%, -50%) scale(1); } 50% { transform: translate(-50%, -50%) scale(1.05); } }
@keyframes spin { 100% { transform: translate(-50%, -50%) rotate(360deg); } }

.loader-container { margin: auto; display: none; flex-direction: column; align-items: center; gap: 16px; }
.infinity-loader { width: 80px; height: 40px; }
.infinity-path-bg { fill: none; stroke: rgba(255, 255, 255, 0.1); stroke-width: 3; stroke-linecap: round; }
.infinity-path-tail { fill: none; stroke: var(--accent); stroke-width: 3; stroke-linecap: round; stroke-dasharray: 20 80; stroke-dashoffset: 0; animation: dash 1s linear infinite; filter: drop-shadow(0 0 4px var(--accent)); }
@keyframes dash { to { stroke-dashoffset: -100; } }

.dashboard-layout { margin: auto; display: none; width: 100%; max-width: 1100px; gap: 20px; }
.sidebar { flex: 0 0 250px; background: var(--card-bg); backdrop-filter: var(--blur); border: 1px solid var(--card-border); border-radius: 28px; padding: 20px; display: flex; flex-direction: column; box-shadow: var(--shadow-drop); }
.sidebar h2 { margin: 0 0 16px 0; font-size: 14px; text-transform: uppercase; color: var(--text-secondary); letter-spacing: 1px; }
.sidebar-nav { display: flex; flex-direction: column; gap: 6px; flex: 1; }
.sidebar-footer { display: flex; flex-direction: column; gap: 6px; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--card-border); }
.sidebar-btn { background: transparent; color: var(--text-primary); border: none; padding: 10px 14px; border-radius: 14px; font-family: inherit; cursor: pointer; text-align: left; transition: all 0.3s; display: flex; gap: 12px; align-items: center; }
.sidebar-btn .lucide { width: 20px; height: 20px; color: var(--text-secondary); transition: color 0.3s; }
.sidebar-btn:hover { background: var(--input-border); transform: translateX(4px); }
.sidebar-btn.active { background: var(--text-primary); color: var(--bg-color); transform: scale(1.03); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
.sidebar-btn.active .lucide { color: var(--bg-color); }
.sidebar-btn.active .btn-desc { color: var(--bg-color); opacity: 0.8; }
.btn-text-content { display: flex; flex-direction: column; gap: 2px; }
.btn-title { font-weight: 600; font-size: 13px; text-transform: uppercase; }
.btn-desc { font-weight: 400; font-size: 11px; color: var(--text-secondary); line-height: 1.3; }

.main-content { flex: 1; display: flex; flex-direction: column; position: relative; height: 100%; }
.tab-content { display: none; flex-direction: column; gap: 16px; height: 100%; }
.tab-content.active { display: flex; animation: elasticBounce 0.6s forwards; }
.tab-content h2 { margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em; display: flex; align-items: center; gap: 10px;}

.plans-switch { display: flex; gap: 8px; background: var(--input-bg); padding: 6px; border-radius: 20px; border: 1px solid var(--input-border); margin-bottom: 10px; }
.plan-sub-btn { flex: 1; background: transparent; color: var(--text-secondary); border: none; padding: 12px; border-radius: 14px; font-weight: 600; cursor: pointer; transition: all 0.3s; }
.plan-sub-btn.active { background: var(--card-border); color: var(--text-primary); box-shadow: var(--shadow-drop); transform: scale(1.03); }

.plan-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
.plan-card { padding: 0; overflow: hidden; justify-content: space-between; }
.plan-card-content { padding: 24px; display: flex; flex-direction: column; gap: 12px; height: 100%; }
.plan-card h4 { margin: 0; font-size: 18px; color: var(--text-primary); }
.plan-card .price { font-size: 14px; color: var(--accent); font-weight: 700; }

.profile-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 12px; }
.profile-item { background: var(--input-bg); border: 1px solid var(--input-border); padding: 14px; border-radius: 14px; display: flex; flex-direction: column; gap: 4px; }
.profile-label { font-size: 11px; text-transform: uppercase; color: var(--text-secondary); letter-spacing: 1px; }
.profile-value { font-size: 15px; font-weight: 600; color: var(--text-primary); }

.action-btn { background: var(--input-bg); color: var(--text-primary); border: 1px solid var(--input-border); padding: 12px 18px; border-radius: 14px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.3s; display: flex; align-items: center; justify-content: center; gap: 8px;}
.action-btn:hover { background: var(--card-border); transform: translateZ(10px) scale(1.03); box-shadow: 0 6px 15px rgba(0,0,0,0.2); }
.danger-btn { color: var(--error); } .danger-btn:hover { background: rgba(234, 21, 21, 0.1); border-color: var(--error); }

.dev-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; color: var(--text-primary); background: rgba(20,20,20,0.4); border-radius: 14px; overflow: hidden; }
.dev-table th, .dev-table td { padding: 10px 14px; border-bottom: 1px solid var(--card-border); }
.dev-select { background: var(--bg-color); color: var(--text-primary); border: 1px solid var(--card-border); padding: 10px; border-radius: 10px; outline: none; font-family: inherit; font-size: 12px; width: 100%; }
.dev-btn-sm { padding: 6px 10px; font-size: 11px; border-radius: 8px; background: var(--input-bg); color: var(--text-primary); border: 1px solid var(--card-border); cursor: pointer; transition: all 0.2s ease; display: inline-flex; align-items: center; gap: 4px; justify-content: center;}
.dev-btn-sm:hover { background: var(--text-primary); color: var(--bg-color); }
.dev-btn-danger { border-color: var(--error); color: var(--error); } .dev-btn-danger:hover { background: var(--error); color: #fff; }

.web-console { background: #050505; border: 1px solid #222; border-radius: 14px; padding: 14px; font-family: monospace; font-size: 12px; max-height: 220px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; }
.web-log-info { color: #ffffff; } .web-log-success { color: #34c759; } .web-log-warning { color: #ff9f0a; } .web-log-error { color: #ff453a; } .web-log-service { color: #8e8e93; }

.scripts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; width: 100%; }
.script-card { padding: 0; }
.script-banner { width: 100%; height: 160px; background-size: cover; background-position: center; position: relative; }
.script-banner::after { content: ''; position: absolute; bottom: 0; left: 0; width: 100%; height: 80px; background: linear-gradient(to bottom, transparent, var(--card-bg)); opacity: 1; }
.script-content { padding: 20px; position: relative; z-index: 2; display: flex; flex-direction: column; gap: 10px; flex: 1; }
.script-header h3 { margin: 0; font-size: 20px; color: var(--text-primary); display: flex; flex-direction: column; gap: 4px; }
.game-tag { font-size: 11px; font-weight: 700; opacity: 0.6; text-transform: uppercase; letter-spacing: 1px;}
.script-desc { margin: 0; font-size: 13px; color: var(--text-secondary); line-height: 1.5; flex: 1; }
.copy-btn { background: var(--accent); color: var(--accent-text); border: none; padding: 14px; border-radius: 16px; font-weight: 800; font-family: 'Inter', monospace; cursor: pointer; text-transform: uppercase; font-size: 13px; transition: all 0.3s ease; display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: auto; transform: translateZ(30px); }
.copy-btn:not(:disabled):hover { transform: translateZ(40px) scale(1.05); }
.copy-btn:disabled { opacity: 0.5; cursor: not-allowed; background: var(--input-bg); color: var(--text-secondary); border: 1px solid var(--input-border); }

.modal-overlay { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0, 0, 0, 0.4); backdrop-filter: blur(15px); z-index: 10000; display: flex; justify-content: center; align-items: center; opacity: 0; pointer-events: none; transition: opacity 0.4s; }
.modal-overlay.active { opacity: 1; pointer-events: auto; }
.custom-modal { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 28px; padding: 28px; width: 90%; max-width: 400px; text-align: center; box-shadow: var(--shadow-drop); transform: scale(0.9) translateY(20px); transition: transform 0.4s; max-height: 80vh; overflow-y: auto;}
.modal-overlay.active .custom-modal { transform: scale(1) translateY(0); }
.modal-btn { flex: 1; padding: 12px; border: none; border-radius: 14px; font-weight: 600; cursor: pointer; font-size: 13px; }
.modal-btn-cancel { background: var(--input-bg); color: var(--text-primary); border: 1px solid var(--input-border); }
.modal-btn-confirm { background: var(--accent); color: var(--accent-text); }

.discord-btn { width: 100%; max-width: 250px; padding: 14px; background: #5865F2; color: #fff; border: none; border-radius: 16px; font-size: 14px; font-weight: 700; cursor: pointer; text-transform: uppercase; text-decoration: none;}
.key-box { background: var(--input-bg); border: 1px solid var(--input-border); padding: 16px; border-radius: 16px; font-family: monospace; font-size: 18px; font-weight: 700; text-align: center; color: var(--accent); margin: 12px 0; }
.captcha-box { background: rgba(0,0,0,0.3); border: 1px solid var(--input-border); border-radius: 14px; padding: 12px 16px; color: var(--text-primary); font-weight: bold; width: 45%; text-align: center; }

/* TICKET STYLES */
.ticket-item { background: var(--input-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 12px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; transition: 0.3s; opacity: 0.5; }
.ticket-item.closed { opacity: 0.3 !important; pointer-events: none; }
.ticket-item.active { opacity: 1 !important; border-color: var(--accent); }
.chat-box { background: rgba(0,0,0,0.5); border: 1px solid var(--card-border); border-radius: 12px; padding: 10px; flex-grow: 1; min-height: 200px; max-height: 300px; overflow-y: auto; margin-bottom: 10px; display: flex; flex-direction: column; gap: 8px;}
.chat-msg { padding: 8px 12px; border-radius: 12px; font-size: 13px; max-width: 80%; line-height: 1.4; word-wrap: break-word;}
.chat-msg.user { background: var(--input-border); align-self: flex-start; color: var(--text-primary);}
.chat-msg.dev { background: rgba(52, 199, 89, 0.2); border: 1px solid rgba(52, 199, 89, 0.4); align-self: flex-end; color: var(--success);}

@media (max-width: 900px) {
  .dashboard-layout { flex-direction: column; width: 100%; padding: 0; }
  .sidebar { width: 100%; padding: 16px; border-radius: 24px; } .sidebar h2 { display: none; }
  .sidebar-nav { flex-direction: row; overflow-x: auto; } .btn-desc { display: none; }
}
</style>
</head>
<body>

  <!-- INTRO TRAILER OVERLAY (Бесконечная прямая неоновая сосиска) -->
  <div id="introOverlay">
    <div class="dragon-container">
       <h2>GLOBAL SCRIPT'S</h2>
       <div class="dragon-track">
          <div class="white-dragon"></div>
       </div>
    </div>
  </div>

  <!-- LANDING PREVIEW (Презентация) -->
  <div id="landingWrapper">
    <div class="landing-hero">
      <h1>Dive in, ride with Global Scripts</h1>
      <p>Experience the next generation of script execution. Packed with power, built for stability, and designed for you. Join the elite community today.</p>
      <button class="login-to-start-btn" onclick="enterAppFromLanding()">LOGIN TO START</button>
    </div>
    <div class="feature-grid">
      <div class="feature-box">
        <h3><i data-lucide="zap" style="color:var(--success);"></i> Lightning Fast</h3>
        <p>Blazing fast script execution with virtually zero delay and optimized memory usage.</p>
      </div>
      <div class="feature-box">
        <h3><i data-lucide="shield-check" style="color:#0abfff;"></i> Crash Resistant</h3>
        <p>Tested interface and advanced stability protocols built by veteran developers.</p>
      </div>
      <div class="feature-box">
        <h3><i data-lucide="cloud" style="color:#ff9f0a;"></i> Cloud Hub</h3>
        <p>Instant access to a massive verified database of scripts for all popular games.</p>
      </div>
    </div>
  </div>

  <div class="ambient-bg"></div>
  <canvas id="bgCanvas"></canvas>
  <div class="ocean"><div class="wave"></div><div class="wave"></div><div class="wave"></div></div>

  <!-- MODALS -->
  <div class="modal-overlay" id="customModalOverlay">
    <div class="custom-modal">
      <h3 id="modalTitle">Title</h3>
      <p id="modalMessage">Message</p>
      <input type="text" id="modalInput" class="dev-select" style="display:none; margin-bottom: 16px;" autocomplete="off"/>
      <div style="display: flex; gap: 10px;">
        <button class="modal-btn modal-btn-cancel" id="modalCancelBtn" data-i18n="m_cancel">Cancel</button>
        <button class="modal-btn modal-btn-confirm" id="modalConfirmBtn" data-i18n="m_confirm">Confirm</button>
      </div>
    </div>
  </div>

  <div class="modal-overlay" id="receiptsModalOverlay">
    <div class="custom-modal" style="max-width: 500px;">
      <h3 data-i18n="r_hist">Receipts History</h3>
      <div id="receiptsContainer" style="text-align:left; font-size:13px; color:var(--text-secondary); max-height: 300px; overflow-y:auto; margin-bottom:15px; padding-right:5px; word-wrap: break-word;"></div>
      <button class="action-btn" style="width:100%;" onclick="document.getElementById('receiptsModalOverlay').classList.remove('active')" data-i18n="m_cancel">Close</button>
    </div>
  </div>

  <div class="fullscreen-overlay" id="freezeScreen" style="display:none;">
      <div class="bg-massive-icon">❄️</div>
      <div class="overlay-content-box freeze-card">
          <h2 data-i18n="fr_tit">Your account has been frozen</h2>
          <p data-i18n="fr_desc">Contact the Developer to resolve the issue.</p>
      </div>
  </div>

  <div class="fullscreen-overlay" id="maintenanceScreen" style="display:none;">
      <div class="bg-massive-icon" id="maintenanceLockIcon">🔒</div>
      <div class="overlay-content-box maint-card">
          <h2 data-i18n="mn_tit">Site is closed for maintenance.</h2>
          <p data-i18n="mn_desc">Please try visiting later!</p>
      </div>
  </div>

  <!-- TICKET SUCCESS MINI BG -->
  <div class="fullscreen-overlay" id="ticketSuccessOverlay" style="display:none; z-index: 2005;">
      <div class="bg-massive-icon">✉️</div>
      <div class="overlay-content-box" style="border-top: 4px solid var(--success);">
          <h2 data-i18n="t_suc_tit" style="color: var(--success);">Request Created!</h2>
          <p data-i18n="t_suc_desc">Your support ticket has been successfully submitted to developers.</p>
          <button class="action-btn" style="width: 100%; margin-top:20px;" onclick="document.getElementById('ticketSuccessOverlay').style.display='none'" data-i18n="r_btn">Okay</button>
      </div>
  </div>

  <div class="fullscreen-overlay" id="rewardScreen" style="display:none; z-index: 2001;">
      <div class="bg-massive-icon">🎉</div>
      <div class="overlay-content-box reward-card">
          <h2 data-i18n="r_tit" style="color: var(--success);">Congratulations!</h2>
          <p data-i18n="r_sub" style="margin-bottom: 6px; font-weight: 700; color: #fff;">You received from the developer:</p>
          <p id="rewardValue" style="opacity: 0.6; margin-bottom: 24px; font-size: 14px;">Value</p>
          <div style="background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 14px; margin-bottom: 24px; text-align: left;">
              <span data-i18n="r_dev" style="font-weight: 700; color: var(--success);">Developer: </span>
              <span id="rewardMessage" style="color: #fff; word-wrap: break-word;">Message</span>
          </div>
          <button class="action-btn" style="width: 100%; background: var(--success); color: #fff;" onclick="closeRewardScreen()" data-i18n="r_btn">Okay!</button>
      </div>
  </div>

  <div class="top-bar">
    <div class="top-bar-left">
      <div class="lang-dropdown-wrapper">
         <div class="ui-pill" id="langBtn" onclick="document.getElementById('langMenu').classList.toggle('show')"><span id="langBtnText">🌎 EN</span></div>
         <div class="lang-menu" id="langMenu">
            <div class="lang-option" onclick="setLang('en')">🇺🇸 EN (English)</div>
            <div class="lang-option" onclick="setLang('ru')">🇷🇺 RU (Русский)</div>
            <div class="lang-option" onclick="setLang('ja')">🇯🇵 JA (日本語)</div>
            <div class="lang-option" onclick="setLang('pt')">🇧🇷 PT (Português)</div>
         </div>
      </div>
      <div class="ui-pill" id="clockWrapper" style="{{ 'display:none;' if not current_user else 'display:flex;' }}"><div class="recording-dot"></div><span id="clock">00:00:00</span></div>
      <button class="ui-pill" id="themeBtn" data-i18n="theme_btn">Light Mode</button>
    </div>
    <div class="top-bar-right" id="userWrapper" style="{{ 'display:none;' if not current_user else 'display:flex;' }}">
      <div class="ui-pill" id="userDisplay"><i data-lucide="user" style="width:14px; height:14px;"></i> <span id="userLoginText">{{ current_user or '' }}</span></div>
      <button class="ui-pill logout-btn" id="logoutBtn" data-i18n="logout">Logout</button>
    </div>
  </div>

  <div class="app-content" id="appMainWrapper">
    <div class="header" id="mainHeader">
      <img src="https://raw.githubusercontent.com/Rob4ik02/RobloxScripts/refs/heads/main/icon.png" alt="" />
      <h1>Global Script's</h1>
    </div>

    <!-- ФОРМЫ АВТОРИЗАЦИИ -->
    <div class="form-container" id="authForm" style="{{ 'display:none;' if current_user else 'display:flex;' }}">
      <input type="text" id="login" data-i18n-ph="login_ph" placeholder="Login" autocomplete="off" />
      <input type="password" id="password" data-i18n-ph="pass_ph" placeholder="Password" />
      <button id="signUpBtn" data-i18n="auth_btn">AUTHORIZE</button>
      <div id="message"></div>
      <div class="create-link-wrapper show" id="createAccountWrapper">
        <div class="create-link" id="createAccountLink" data-i18n="no_acc">Don't have an account? Create it!</div>
      </div>
    </div>
    <div class="form-container" id="secretForm" style="display:none;">
      <p class="form-header-text" data-i18n="dev_auth">Developer Authentication</p>
      <input type="password" id="devSecretCode" data-i18n-ph="secret_ph" placeholder="Secret Word" autocomplete="off" />
      <button id="verifySecretBtn" data-i18n="unlock_btn">UNLOCK MAINFRAME</button>
      <div id="secretMessage"></div>
      <div class="back-link" id="cancelSecretLink" data-i18n="cancel">Cancel</div>
    </div>
    <div class="form-container" id="twoFaForm" style="display:none;">
      <p class="form-header-text" data-i18n="bot_prot">Bot Protection</p>
      <input type="text" id="twoFaCode" data-i18n-ph="code_ph" placeholder="Enter Code" autocomplete="off" />
      <button id="verifyBtn" data-i18n="verify_btn">VERIFY</button>
      <div id="twoFaMessage"></div>
      <div class="back-link" id="cancel2FaLink" data-i18n="cancel">Cancel</div>
    </div>
    <div class="form-container" id="regForm" style="display:none;">
      <p class="form-header-text" data-i18n="reg_desc">Describe yourself for the account.</p>
      <input type="text" id="regLogin" data-i18n-ph="login_ph" placeholder="Login" autocomplete="off" />
      <input type="password" id="regPassword" data-i18n-ph="pass_ph" placeholder="Password" />
      <input type="text" id="regEmail" class="email-input" data-i18n-ph="email_ph" placeholder="Enter your email" autocomplete="off" />
      <input type="password" id="regSecret" data-i18n-ph="reg_sec_ph" placeholder="Secret word" autocomplete="off" />
      <input type="text" id="regSource" data-i18n-ph="reg_src_ph" placeholder="How did you hear about us?" autocomplete="off" />
      <div style="display: flex; gap: 10px; width: 100%; margin-top: 4px;">
          <div id="captchaBox" class="captcha-box">? + ?</div>
          <input type="text" id="regCaptcha" data-i18n-ph="captcha_ph" placeholder="Answer" style="flex: 1;" autocomplete="off" />
      </div>
      <label class="checkbox-container"><input type="checkbox" id="regAgree"><span data-i18n="agree">I agree to the privacy cookies</span></label>
      <button id="regBtn" disabled data-i18n="create_btn">CREATE ACCOUNT</button>
      <div id="regMessage"></div>
      <div class="back-link" id="backToLoginLink" data-i18n="back_login">Back to Login</div>
    </div>

    <div class="loader-container" id="loaderScreen">
      <svg class="infinity-loader" viewBox="0 0 100 50"><path class="infinity-path-bg" pathLength="100" d="M50,25 C30,5 10,5 10,25 C10,45 30,45 50,25 C70,5 90,5 90,25 C90,45 70,45 50,25 Z" /><path class="infinity-path-tail" pathLength="100" d="M50,25 C30,5 10,5 10,25 C10,45 30,45 50,25 C70,5 90,5 90,25 C90,45 70,45 50,25 Z" /></svg>
      <div class="loader-text" id="loaderDynamicText" data-i18n="loading">Authenticating System...</div>
    </div>

    <!-- MAIN DASHBOARD -->
    <div class="dashboard-layout" id="dashboardLayout">
      <div class="sidebar">
        <h2 data-i18n="menu">MENU</h2>
        <div class="sidebar-nav">
          <button class="sidebar-btn active" data-target="tab-main"><i data-lucide="home"></i><div class="btn-text-content"><div class="btn-title" data-i18n="m_main">MAIN</div><div class="btn-desc" data-i18n="m_main_d">Your main profile</div></div></button>
          <button class="sidebar-btn" data-target="tab-keys"><i data-lucide="key"></i><div class="btn-text-content"><div class="btn-title" data-i18n="m_key">KEY SYSTEM</div><div class="btn-desc" data-i18n="m_key_d">Get a key</div></div></button>
          <button class="sidebar-btn" data-target="tab-scripts"><i data-lucide="file-code"></i><div class="btn-text-content"><div class="btn-title" data-i18n="m_scr">SCRIPTS</div><div class="btn-desc" data-i18n="m_scr_d">Game scripts</div></div></button>
          <button class="sidebar-btn" data-target="tab-plans"><i data-lucide="shopping-cart"></i><div class="btn-text-content"><div class="btn-title" data-i18n="m_plan">PLANS</div><div class="btn-desc" data-i18n="m_plan_d">Buy plans</div></div></button>
          <button class="sidebar-btn" data-target="tab-faq"><i data-lucide="help-circle"></i><div class="btn-text-content"><div class="btn-title" data-i18n="m_faq">FAQ</div><div class="btn-desc" data-i18n="m_faq_d">Got questions?</div></div></button>
        </div>
        <div class="sidebar-footer">
          <button class="sidebar-btn sidebar-btn-footer" data-target="tab-developers" id="navDevBtn" style="display:none;"><i data-lucide="server"></i><div class="btn-text-content"><div class="btn-title" data-i18n="m_dev">DEVELOPERS</div><div class="btn-desc" data-i18n="m_dev_d">Admin Panel</div></div></button>
          <button class="sidebar-btn sidebar-btn-footer" data-target="tab-discord"><i data-lucide="message-square"></i><div class="btn-text-content"><div class="btn-title" data-i18n="m_disc">DISCORD</div><div class="btn-desc" data-i18n="m_disc_d">Join us</div></div></button>
        </div>
      </div>
      
      <div class="main-content">
        <div class="tab-content active" id="tab-main">
          <h2 data-i18n="u_prof"><i data-lucide="user" style="width:28px; height:28px;"></i> User Profile</h2>
          <div class="dashboard-card">
            <p style="color: var(--text-primary); font-weight: 600; font-size: 16px; margin-bottom: 4px;" data-i18n="acc_det">Account Details</p>
            <div class="profile-grid">
              <div class="profile-item"><span class="profile-label" data-i18n="l_login">LOGIN</span><span class="profile-value" id="profileLogin">--</span></div>
              <div class="profile-item"><span class="profile-label" data-i18n="l_plan">CURRENT PLAN</span><span class="profile-value" id="profilePlan">--</span></div>
              <div class="profile-item"><span class="profile-label" data-i18n="l_reg">REGISTRATION</span><span class="profile-value" id="profileRegDate">--</span></div>
              <div class="profile-item"><span class="profile-label" data-i18n="l_dev">DEV APPROVED</span><span class="profile-value dev-approved-badge" id="profileDevApproved">--</span></div>
            </div>
          </div>
        </div>

        <div class="tab-content" id="tab-keys">
          <h2 data-i18n="k_gen"><i data-lucide="key" style="width:28px; height:28px;"></i> Key Generator</h2>
          <div class="dashboard-card">
            <p style="color: var(--text-primary); font-weight: 600; font-size: 16px; margin-bottom: 8px;" data-i18n="k_unl">Unlock Free Access</p>
            <p data-i18n="k_desc">Create unique HWID keys. Keys last 12 hours.</p>
            <div id="generatedKeyDisplay" class="key-box" style="display:none;"></div>
            <button class="action-btn" style="margin-top: 10px; width: 100%;" onclick="generateKey(false)" data-i18n="k_btn"><i data-lucide="zap" style="width:16px;height:16px;"></i> Generate New Key</button>
            <button class="action-btn danger-btn" id="devForceKeyBtn" style="display:none; margin-top: 10px; width: 100%;" onclick="generateKey(true)"><i data-lucide="zap-off" style="width:16px;height:16px;"></i> FORCE GENERATE (DEV)</button>
            <div id="keyMessage"></div>
          </div>
        </div>

        <div class="tab-content" id="tab-scripts">
          <h2 data-i18n="s_lib"><i data-lucide="file-code" style="width:28px; height:28px;"></i> Scripts Library</h2>
          <div class="scripts-grid" id="userScriptsContainer"></div>
        </div>

        <div class="tab-content" id="tab-plans">
          <h2 data-i18n="p_upg"><i data-lucide="shopping-cart" style="width:28px; height:28px;"></i> Upgrade Plans</h2>
          <div class="plans-switch">
            <button class="plan-sub-btn active" id="btnBuyPlan" onclick="switchPlanSubTab('buy')" data-i18n="p_buy">Buy Plan</button>
            <button class="plan-sub-btn" id="btnMyPlan" onclick="switchPlanSubTab('my')" data-i18n="p_my">My Current Plan</button>
          </div>
          <div id="planBuySection">
            <div class="plan-grid">
              <div class="plan-card">
                 <div class="plan-card-content">
                    <h4 data-i18n="p_start">Starter Plan</h4><div class="price">150 RUB / 7 Days</div><p data-i18n="p_start_d">Little access.</p>
                    <button class="action-btn" onclick="processPayment('Starter Plan')" data-i18n="p_purch">Purchase</button>
                 </div>
              </div>
              <div class="plan-card">
                 <div class="plan-card-content">
                    <h4 data-i18n="p_pro">Professional Plan</h4><div class="price">350 RUB / 30 Days</div><p data-i18n="p_pro_d">More access.</p>
                    <button class="action-btn" onclick="processPayment('Professional Plan')" data-i18n="p_purch">Purchase</button>
                 </div>
              </div>
              <div class="plan-card">
                 <div class="plan-card-content">
                    <h4 data-i18n="p_ext">Extreme Plan</h4><div class="price">700 RUB / 90 Days</div><p data-i18n="p_ext_d">All access.</p>
                    <button class="action-btn" onclick="processPayment('Extreme Plan')" data-i18n="p_purch">Purchase</button>
                 </div>
              </div>
            </div>
          </div>
          <div id="planMySection" style="display: none;">
             <div class="dashboard-card" style="display: flex; flex-direction: column; gap: 12px;">
               <h3 id="planGreeting" style="margin: 0; color: var(--text-primary); font-size: 20px;">Hi!</h3>
               <p id="planCurrentStatus" style="margin:0; font-weight: 600; color: var(--accent);">Your current plan: --</p>
               <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px;">
                  <button class="action-btn" onclick="requestRestartPlan()" data-i18n="p_rest"><i data-lucide="refresh-cw" style="width:16px;height:16px;"></i> Restart Plan</button>
                  <button class="action-btn" onclick="openReceipts()" data-i18n="r_hist_btn"><i data-lucide="receipt" style="width:16px;height:16px;"></i> Receipts</button>
                  <button class="action-btn danger-btn" onclick="requestDeleteAccount()" data-i18n="p_del"><i data-lucide="trash-2" style="width:16px;height:16px;"></i> Delete Account</button>
               </div>
             </div>
          </div>
        </div>
        
        <div class="tab-content" id="tab-faq">
          <h2 data-i18n="f_tit"><i data-lucide="help-circle" style="width:28px; height:28px;"></i> FAQ & Support</h2>
          <div class="dashboard-card" id="userTicketFormCard">
              <p data-i18n="f_desc" style="font-size: 16px; font-weight: bold;">Got questions? We answer fast!</p>
              <hr style="border-top: 1px solid var(--card-border); border-bottom: none; margin: 16px 0;">
              <input type="text" id="uTicketReason" class="dev-select" data-i18n-ph="t_reason_ph" placeholder="Reason for support..." style="margin-bottom: 12px; width: 100%;">
              <select id="uTicketPriority" class="dev-select" style="margin-bottom: 12px; width: 100%;">
                  <option value="Normal" data-i18n="t_norm">Normal Speed</option>
                  <option value="Fast" data-i18n="t_fast">Fast Response</option>
              </select>
              <button class="action-btn" style="width: 100%;" onclick="submitUserTicket()" data-i18n="t_send"><i data-lucide="send" style="width:16px;height:16px;"></i> Send Support Request</button>
          </div>
          <div class="dashboard-card" id="userTicketChatCard" style="display:none; padding: 20px; flex-direction: column;">
              <div style="display:flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                  <h4 style="margin:0; color: var(--text-primary);" id="uChatStatus">Support Chat</h4>
                  <span id="uChatBadge" style="font-size:12px; background:var(--input-border); padding:4px 8px; border-radius:8px;">Pending</span>
              </div>
              <div class="chat-box" id="uChatBox"></div>
              <div style="display:flex; gap:8px;" id="uChatInputs">
                  <input type="text" id="uChatInput" class="dev-select" data-i18n-ph="t_msg_ph" placeholder="Type a message..." style="flex:1;">
                  <button class="dev-btn-sm" onclick="sendTicketMessage('user')" data-i18n="t_reply"><i data-lucide="send" style="width:14px;height:14px;"></i></button>
              </div>
          </div>
        </div>
        
        <div class="tab-content" id="tab-developers">
          <h2 data-i18n="d_tit"><i data-lucide="server" style="width:28px; height:28px;"></i> Developers</h2>
          <div id="devAdminView" style="display: flex; flex-direction: column; gap: 20px;">
             <div class="dashboard-card">
                 <h4 style="margin: 0 0 10px 0; color: var(--text-primary); display:flex; align-items:center; gap:8px;"><i data-lucide="file-code" style="width:18px;height:18px;"></i> Script Management</h4>
                 <div style="display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px;">
                     <input type="hidden" id="devScriptId">
                     <div style="display:flex; gap:10px;">
                         <input type="text" id="devScriptTitle" class="dev-select" placeholder="Script Title" style="flex:1;">
                         <input type="text" id="devScriptGame" class="dev-select" placeholder="Game Name" style="flex:1;">
                     </div>
                     <input type="text" id="devScriptBanner" class="dev-select" placeholder="Banner Image URL">
                     <div style="display:flex; gap:10px; align-items:center;">
                         <span style="font-size:12px; color:var(--text-secondary); white-space:nowrap;">Release Date:</span>
                         <input type="datetime-local" id="devScriptDate" class="dev-select" style="flex:1;">
                     </div>
                     <input type="text" id="devScriptCode" class="dev-select" placeholder="Lua Code (loadstring...)">
                     <textarea id="devScriptDesc" class="dev-select" placeholder="Description..." rows="2"></textarea>
                     <div style="display:flex; gap:10px;">
                         <button class="action-btn" style="flex:1;" onclick="saveAdminScript()"><i data-lucide="plus" style="width:16px;height:16px;"></i> Add / Update</button>
                         <button class="action-btn danger-btn" onclick="clearScriptForm()"><i data-lucide="x" style="width:16px;height:16px;"></i> Clear</button>
                     </div>
                 </div>
                 <div class="dev-table-wrapper" style="max-height:200px; overflow-y:auto;">
                    <table class="dev-table">
                       <thead><tr><th>Title</th><th>Game</th><th>Release Date</th><th>Actions</th></tr></thead>
                       <tbody id="devScriptsTableBody"></tbody>
                    </table>
                 </div>
             </div>

             <div class="dashboard-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <h4 style="margin:0; color: var(--text-primary); display:flex; align-items:center; gap:8px;"><i data-lucide="inbox" style="width:18px;height:18px;"></i> Support Tickets</h4>
                    <button class="dev-btn-sm" id="btnShowAllTickets" style="display:none;" onclick="toggleAllTickets()" data-i18n="t_show_all">Show All</button>
                </div>
                <div id="adminTicketsContainer" style="display: flex; flex-direction: column; max-height: 400px; overflow-y: auto;"></div>
                <div id="adminChatView" style="display:none; margin-top: 15px; border-top: 1px solid var(--card-border); padding-top: 15px;">
                    <div style="display:flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <span id="adminChatTitle" style="color:var(--text-primary); font-weight:bold;">Chat with User</span>
                        <button class="dev-btn-sm dev-btn-danger" onclick="closeActiveTicket()" data-i18n="t_close"><i data-lucide="x-circle" style="width:14px;height:14px;"></i> Close</button>
                    </div>
                    <div class="chat-box" id="aChatBox"></div>
                    <div style="display:flex; gap:8px;">
                        <input type="text" id="aChatInput" class="dev-select" placeholder="Reply..." style="flex:1;">
                        <button class="dev-btn-sm" onclick="sendTicketMessage('admin')" data-i18n="t_reply"><i data-lucide="send" style="width:14px;height:14px;"></i></button>
                    </div>
                </div>
             </div>

             <div class="dashboard-card">
                <h4 style="margin: 0 0 10px 0; color: var(--text-primary); display:flex; align-items:center; gap:8px;"><i data-lucide="users" style="width:18px;height:18px;"></i> Account Management</h4>
                <div class="dev-table-wrapper">
                   <table class="dev-table">
                      <thead><tr><th>User</th><th>Current Plan</th><th>Days</th><th>Change Plan</th><th>Actions</th></tr></thead>
                      <tbody id="devUsersTableBody"></tbody>
                   </table>
                </div>
             </div>
             
             <div class="dashboard-card">
                <h4 style="margin: 0 0 10px 0; color: var(--text-primary); display:flex; align-items:center; gap:8px;"><i data-lucide="settings" style="width:18px;height:18px;"></i> Site Infrastructure</h4>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                   <button class="dev-btn-sm" id="btnToggleMaintenance" onclick="adminToggleMaintenance()"></button>
                   <button class="dev-btn-sm" onclick="showConfirm('Flush Cache', 'Are you sure you want to flush all system caches?', 'Flush', false, () => { showConfirm('Success', 'All caches purged successfully!', 'OK', false, null, true) })"><i data-lucide="trash" style="width:14px;height:14px;"></i> Flush Cache</button>
                </div>
                <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-top: 10px;">
                   <input type="text" id="devDiscordLink" value="{{ discord_link }}" class="dev-select" style="flex: 1; min-width: 200px; padding: 10px;" placeholder="Discord Link" />
                   <button class="dev-btn-sm" onclick="adminUpdateDiscordLink()"><i data-lucide="save" style="width:14px;height:14px;"></i> Save Link</button>
                </div>
             </div>

             <div class="dashboard-card">
                <h4 style="margin: 0 0 10px 0; color: var(--text-primary); display:flex; align-items:center; gap:8px;"><i data-lucide="terminal" style="width:18px;height:18px;"></i> Live System Console</h4>
                <div class="web-console" id="webConsoleBox"></div>
             </div>
          </div>
        </div>
        
        <div class="tab-content" id="tab-discord">
          <h2 data-i18n="c_tit"><i data-lucide="message-square" style="width:28px; height:28px;"></i> Community</h2>
          <div class="dashboard-card discord-card">
            <svg width="64" height="64" viewBox="0 0 127.14 96.36" fill="#5865F2"><path d="M107.7,8.07A105.15,105.15,0,0,0,81.47,0a72.06,72.06,0,0,0-3.36,6.83A97.68,97.68,0,0,0,49,6.83,72.37,72.37,0,0,0,45.64,0,105.89,105.89,0,0,0,19.39,8.09C2.79,32.65-1.71,56.6.54,80.21h0A105.73,105.73,0,0,0,32.71,96.36,77.7,77.7,0,0,0,39.6,85.25a68.42,68.42,0,0,1-10.85-5.18c.91-.66,1.8-1.34,2.66-2a75.57,75.57,0,0,0,64.32,0c.87.71,1.76,1.39,2.66,2a68.68,68.68,0,0,1-10.87,5.19,77,77,0,0,0,6.89,11.1A105.25,105.25,0,0,0,126.6,80.22h0C129.24,52.84,122.09,29.11,107.7,8.07ZM42.45,65.69C36.18,65.69,31,60,31,53s5-12.74,11.43-12.74S54,46,53.89,53,48.84,65.69,42.45,65.69Zm42.24,0C78.41,65.69,73.31,60,73.31,53s5-12.74,11.43-12.74S96.2,46,96.09,53,91.08,65.69,84.69,65.69Z"/></svg>
            <h3 style="margin: 0; font-size: 24px; color: var(--text-primary);" data-i18n="disc_club">Global Scripts Club</h3>
            <p style="margin: 0; font-size: 14px; max-width: 400px; color: var(--text-secondary); opacity: 0.5;" data-i18n="disc_desc">Join to follow updates!</p>
            <a href="{{ discord_link }}" id="discordJoinBtn" target="_blank" class="discord-btn" data-i18n="disc_join">Join the Club</a>
          </div>
        </div>
      </div>
    </div>
  </div>

<script>
  function updateIcons() {
      if (typeof lucide !== 'undefined') { lucide.createIcons(); }
  }
  
  document.addEventListener("DOMContentLoaded", function() {
      setTimeout(updateIcons, 100);
  });

  function initTiltEffect() {
      const cards = document.querySelectorAll('.feature-box:not(.tilt-applied), .script-card:not(.tilt-applied), .plan-card:not(.tilt-applied), .dashboard-card:not(.tilt-applied)');
      cards.forEach(card => {
          card.classList.add('tilt-applied');
          card.addEventListener('mousemove', e => {
              const rect = card.getBoundingClientRect();
              const x = e.clientX - rect.left;
              const y = e.clientY - rect.top;
              const centerX = rect.width / 2;
              const centerY = rect.height / 2;
              
              const isDashboard = card.closest('#dashboardLayout') !== null;
              const maxTilt = isDashboard ? 1.5 : 3; 

              const rotateX = ((y - centerY) / centerY) * -maxTilt;
              const rotateY = ((x - centerX) / centerX) * maxTilt;
              
              card.style.transform = `perspective(1200px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.01, 1.01, 1.01)`;
              card.style.transition = 'transform 0.2s ease-out';
              card.style.zIndex = '10';
          });
          card.addEventListener('mouseleave', () => {
              card.style.transform = `perspective(1200px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)`;
              card.style.transition = 'transform 0.6s ease';
              card.style.zIndex = '1';
          });
      });
  }

  document.addEventListener('mousedown', function(e) {
      const btn = e.target.closest('button');
      if (!btn) return;
      const rect = btn.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      for (let i = 0; i < 12; i++) {
          const particle = document.createElement('span');
          particle.className = 'btn-particle';
          const angle = Math.random() * Math.PI * 2;
          const velocity = 20 + Math.random() * 40; 
          const tx = Math.cos(angle) * velocity;
          const ty = Math.sin(angle) * velocity;

          particle.style.left = x + 'px';
          particle.style.top = y + 'px';
          particle.style.setProperty('--tx', tx + 'px');
          particle.style.setProperty('--ty', ty + 'px');

          btn.appendChild(particle);
          setTimeout(() => particle.remove(), 600);
      }
  });

  let globalWarpSpeedY = 0;

  window.addEventListener('DOMContentLoaded', () => {
      setTimeout(() => {
          const intro = document.getElementById('introOverlay');
          if(intro) {
              intro.style.opacity = '0';
              setTimeout(() => {
                  intro.style.display = 'none';
                  document.getElementById('landingWrapper').style.display = 'flex';
                  updateIcons();
                  initTiltEffect();
              }, 800);
          }
      }, 2000); 
  });

  function enterAppFromLanding() {
      const landing = document.getElementById('landingWrapper');
      landing.style.opacity = '0';
      
      setTimeout(() => {
          landing.style.display = 'none';
          
          globalWarpSpeedY = 25; 

          setTimeout(() => {
              const appContent = document.getElementById('appMainWrapper');
              appContent.style.display = 'flex';
              updateIcons();
              initTiltEffect();
          }, 600);
          
      }, 500);
  }

  window.userScriptsData = {};
  window.adminScriptsData = {};

  const i18n = {
    en: { theme_btn: "Light Mode", logout: "Logout", auth_btn: "AUTHORIZE", no_acc: "Don't have an account? Create it!", dev_auth: "Developer Authentication", dev_desc: "Enter secret codename.", unlock_btn: "UNLOCK MAINFRAME", cancel: "Cancel", bot_prot: "Bot Protection", bot_desc: "Check your email.", verify_btn: "VERIFY", reg_desc: "Describe yourself.", agree: "I agree to privacy cookies", create_btn: "CREATE ACCOUNT", back_login: "Back to Login", loading: "Authenticating System...", menu: "MENU", m_main: "MAIN", m_main_d: "Your main profile", m_key: "KEY SYSTEM", m_key_d: "Get a key", m_scr: "SCRIPTS", m_scr_d: "Game scripts", m_plan: "PLANS", m_plan_d: "Buy plans", m_faq: "FAQ", m_faq_d: "Got questions?", m_dev: "DEVELOPERS", m_dev_d: "Admin Panel", m_disc: "DISCORD", m_disc_d: "Join us", u_prof: "User Profile", acc_det: "Account Details", acc_det_d: "Your personal overview.", l_login: "LOGIN", l_plan: "CURRENT PLAN", l_reg: "REGISTRATION", l_dev: "DEV APPROVED", k_gen: "Key Generator", k_unl: "Unlock Free Access", k_desc: "Generate keys (12h). 1 per day.", k_btn: "Generate New Key", s_lib: "Scripts Library", s_good: "Good script in beta.", s_copy: "COPY LUA SCRIPT", p_upg: "Upgrade Plans", p_buy: "Buy Plan", p_my: "My Current Plan", p_start: "Starter Plan", p_start_d: "Little access.", p_pro: "Professional Plan", p_pro_d: "More access.", p_ext: "Extreme Plan", p_ext_d: "All access.", p_purch: "Purchase", p_desc: "Features unlocked.", p_rest: "Restart Plan", p_del: "Delete Account", p_sup: "Contact Support", f_tit: "FAQ & Support", f_desc: "Got questions? We answer fast!", d_tit: "Developers", d_desc: "Mainframe architecture.", c_tit: "Community", c_desc: "Join Discord.", fr_tit: "Account frozen", fr_desc: "Contact dev.", mn_tit: "Site Maintenance", mn_desc: "Try again later.", login_ph: "Login", pass_ph: "Password", secret_ph: "Secret Word", code_ph: "Code", email_ph: "Email", reg_sec_ph: "Secret recovery word", reg_src_ph: "How did you hear about us?", m_cancel: "Cancel", m_confirm: "Confirm", disc_club: "Global Scripts Club", disc_desc: "Join to follow updates and chat!", disc_join: "Join the Club", captcha_ph: "Answer", r_tit: "Congratulations!", r_sub: "You received:", r_dev: "Developer: ", r_btn: "Okay!", prompt_msg: "Message for user:", r_hist: "Receipts History", r_hist_btn: "Receipts", t_reason_ph: "Reason for support...", t_norm: "Normal Speed", t_fast: "Fast Response", t_send: "Send Support Request", t_suc_tit: "Request Created!", t_suc_desc: "Ticket submitted to developers.", t_msg_ph: "Type message...", t_reply: "Send", t_close: "Close Ticket", t_show_all: "Show All" },
    ru: { theme_btn: "Светлая тема", logout: "Выйти", auth_btn: "АВТОРИЗАЦИЯ", no_acc: "Нет аккаунта? Создайте!", dev_auth: "Проверка", dev_desc: "Секретный код.", unlock_btn: "РАЗБЛОКИРОВАТЬ", cancel: "Отмена", bot_prot: "Защита", bot_desc: "Код на почте.", verify_btn: "ПОДТВЕРДИТЬ", reg_desc: "Создание аккаунта.", agree: "Согласен с правилами", create_btn: "СОЗДАТЬ", back_login: "Назад", loading: "Загрузка...", menu: "МЕНЮ", m_main: "ГЛАВНАЯ", m_main_d: "Профиль", m_key: "КЛЮЧИ", m_key_d: "Получить доступ", m_scr: "СКРИПТЫ", m_scr_d: "Игровые скрипты", m_plan: "ПЛАНЫ", m_plan_d: "Купить", m_faq: "FAQ", m_faq_d: "Вопросы?", m_dev: "АДМИНКА", m_dev_d: "Управление", m_disc: "DISCORD", m_disc_d: "Чат", u_prof: "Профиль", acc_det: "Детали", acc_det_d: "Информация в системе.", l_login: "ЛОГИН", l_plan: "ПЛАН", l_reg: "ДАТА РЕГИСТРАЦИИ", l_dev: "АДМИН", k_gen: "Генератор", k_unl: "Доступ", k_desc: "Ключи на 12ч (раз в 24ч).", k_btn: "Сгенерировать", s_lib: "Скрипты", s_good: "Скрипт в бете.", s_copy: "КОПИРОВАТЬ LUA", p_upg: "Планы", p_buy: "Купить", p_my: "Мой План", p_start: "Начальный", p_start_d: "Для новичков.", p_pro: "Про-План", p_pro_d: "Больше функций.", p_ext: "Экстремальный", p_ext_d: "Всё включено.", p_purch: "Купить", p_desc: "Функции активны.", p_rest: "Перезапустить", p_del: "Удалить Аккаунт", p_sup: "Поддержка", f_tit: "FAQ и Поддержка", f_desc: "Есть вопросы? Ответим быстро!", d_tit: "Разработчики", d_desc: "Панель управления.", c_tit: "Комьюнити", c_desc: "Дискорд сервер.", fr_tit: "Аккаунт заморожен", fr_desc: "Пиши админу.", mn_tit: "Тех. работы", mn_desc: "Зайди позже.", login_ph: "Логин", pass_ph: "Пароль", secret_ph: "Секрет", code_ph: "Код", email_ph: "Почта", reg_sec_ph: "Секретное слово", reg_src_ph: "Откуда узнали?", m_cancel: "Отмена", m_confirm: "Подтвердить", disc_club: "Global Scripts Club", disc_desc: "Заходи, общайся, следи за апдейтами!", disc_join: "Зайти в клуб", captcha_ph: "Ответ", r_tit: "Поздравляем!", r_sub: "Вы получили от разработчика:", r_dev: "Разработчик: ", r_btn: "Хорошо!", prompt_msg: "Сообщение юзеру:", r_hist: "История Чеков", r_hist_btn: "Чеки", t_reason_ph: "Причина вызова поддержки...", t_norm: "Обычно", t_fast: "Быстро", t_send: "Отправить запрос", t_suc_tit: "Успешно!", t_suc_desc: "Запрос отправлен разработчикам.", t_msg_ph: "Сообщение...", t_reply: "Отправить", t_close: "Закрыть тикет", t_show_all: "Открыть все" },
    ja: { theme_btn: "ライト", logout: "ログアウト", auth_btn: "承認", no_acc: "作成する", dev_auth: "開発者認証", dev_desc: "秘密コード", unlock_btn: "解除", cancel: "キャンセル", bot_prot: "保護", bot_desc: "メール確認", verify_btn: "確認", reg_desc: "作成", agree: "同意する", create_btn: "作成", back_login: "戻る", loading: "ロード中...", menu: "メニュー", m_main: "メイン", m_main_d: "プロフィール", m_key: "キー", m_key_d: "アクセス", m_scr: "スクリプト", m_scr_d: "ゲーム", m_plan: "プラン", m_plan_d: "購入", m_faq: "FAQ", m_faq_d: "質問？", m_dev: "開発者", m_dev_d: "管理", m_disc: "DISCORD", m_disc_d: "参加", u_prof: "プロフィール", acc_det: "詳細", acc_det_d: "情報", l_login: "ログイン", l_plan: "プラン", l_reg: "登録", l_dev: "管理者", k_gen: "キー生成", k_unl: "アクセス", k_desc: "12時間有効", k_btn: "生成", s_lib: "ライブラリ", s_good: "ベータ版", s_copy: "コピー", p_upg: "プラン", p_buy: "購入", p_my: "マイスター", p_start: "スターター", p_start_d: "初心者", p_pro: "プロ", p_pro_d: "プロ向け", p_ext: "極", p_ext_d: "すべて", p_purch: "購入", p_desc: "アンロック", p_rest: "再起動", p_del: "削除", p_sup: "サポート", f_tit: "FAQ", f_desc: "質問？", d_tit: "開発者", d_desc: "管理", c_tit: "コミュニティ", c_desc: "参加", fr_tit: "凍結", fr_desc: "連絡して", mn_tit: "メンテ", mn_desc: "後で", login_ph: "ログイン", pass_ph: "パスワード", secret_ph: "秘密", code_ph: "コード", email_ph: "メール", reg_sec_ph: "秘密の言葉", reg_src_ph: "ソース", m_cancel: "キャンセル", m_confirm: "確認", disc_club: "クラブ", disc_desc: "チャットに参加！", disc_join: "参加", captcha_ph: "答え", r_tit: "おめでとう！", r_sub: "取得：", r_dev: "開発者：", r_btn: "OK", prompt_msg: "メッセージ：", r_hist: "レシート", r_hist_btn: "レシート", t_reason_ph: "理由...", t_norm: "通常", t_fast: "早い", t_send: "送信", t_suc_tit: "成功！", t_suc_desc: "送信しました。", t_msg_ph: "メッセージ...", t_reply: "送信", t_close: "閉じる", t_show_all: "すべて表示" },
    pt: { theme_btn: "Claro", logout: "Sair", auth_btn: "AUTORIZAR", no_acc: "Criar conta", dev_auth: "Dev Auth", dev_desc: "Código secreto.", unlock_btn: "DESBLOQUEAR", cancel: "Cancelar", bot_prot: "Proteção", bot_desc: "Cheque email.", verify_btn: "VERIFICAR", reg_desc: "Criar.", agree: "Concordo", create_btn: "CRIAR", back_login: "Voltar", loading: "Carregando...", menu: "MENU", m_main: "PRINCIPAL", m_main_d: "Perfil", m_key: "CHAVES", m_key_d: "Acesso", m_scr: "SCRIPTS", m_scr_d: "Scripts", m_plan: "PLANOS", m_plan_d: "Comprar", m_faq: "FAQ", m_faq_d: "Dúvidas?", m_dev: "DEVS", m_dev_d: "Admin", m_disc: "DISCORD", m_disc_d: "Junte-se", u_prof: "Perfil", acc_det: "Detalhes", acc_det_d: "Info.", l_login: "LOGIN", l_plan: "PLANO", l_reg: "DATA", l_dev: "ADMIN", k_gen: "Gerador", k_unl: "Acesso", k_desc: "12 horas.", k_btn: "Gerar", s_lib: "Biblioteca", s_good: "Bom.", s_copy: "COPIAR LUA", p_upg: "Planos", p_buy: "Comprar", p_my: "Meu Plano", p_start: "Inicial", p_start_d: "Básico.", p_pro: "Pro", p_pro_d: "Mais.", p_ext: "Extremo", p_ext_d: "Tudo.", p_purch: "Comprar", p_desc: "Ativo.", p_rest: "Reiniciar", p_del: "Excluir", p_sup: "Suporte", f_tit: "FAQ", f_desc: "Dúvidas?", d_tit: "Devs", d_desc: "Admin.", c_tit: "Comunidade", c_desc: "Discord.", fr_tit: "Congelado", fr_desc: "Contate.", mn_tit: "Manutenção", mn_desc: "Tente depois.", login_ph: "Login", pass_ph: "Senha", secret_ph: "Segredo", code_ph: "Código", email_ph: "Email", reg_sec_ph: "Recuperação", reg_src_ph: "Onde conheceu?", m_cancel: "Cancelar", m_confirm: "Confirmar", disc_club: "Clube", disc_desc: "Junte-se ao chat!", disc_join: "Entrar", captcha_ph: "Resposta", r_tit: "Parabéns!", r_sub: "Você recebeu:", r_dev: "Dev: ", r_btn: "OK", prompt_msg: "Mensagem:", r_hist: "Recibos", r_hist_btn: "Recibos", t_reason_ph: "Motivo...", t_norm: "Normal", t_fast: "Rápido", t_send: "Enviar Pedido", t_suc_tit: "Sucesso!", t_suc_desc: "Enviado.", t_msg_ph: "Mensagem...", t_reply: "Enviar", t_close: "Fechar", t_show_all: "Ver todos" }
  };

  let currentLang = 'en';

  function setLang(lang) {
    currentLang = lang; localStorage.setItem('lang', lang);
    const map = { en: "🌎 EN", ru: "🇷🇺 RU", ja: "🇯🇵 JA", pt: "🇧🇷 PT" };
    document.getElementById('langBtnText').innerText = map[lang];
    document.getElementById('langMenu').classList.remove('show');
    document.querySelectorAll('[data-i18n]').forEach(el => { if(i18n[lang][el.getAttribute('data-i18n')]) el.innerText = i18n[lang][el.getAttribute('data-i18n')]; });
    document.querySelectorAll('[data-i18n-ph]').forEach(el => { if(i18n[lang][el.getAttribute('data-i18n-ph')]) el.placeholder = i18n[lang][el.getAttribute('data-i18n-ph')]; });
  }

  let confirmActionCallback = null;
  function showConfirm(title, message, confirmText, isDanger, callback, hideCancel = false, isPrompt = false) {
      document.getElementById('modalTitle').innerText = title; document.getElementById('modalMessage').innerText = message;
      const confirmBtn = document.getElementById('modalConfirmBtn'); confirmBtn.innerText = confirmText; confirmBtn.className = isDanger ? 'modal-btn modal-btn-danger' : 'modal-btn modal-btn-confirm';
      document.getElementById('modalCancelBtn').style.display = hideCancel ? 'none' : 'block';
      const promptInput = document.getElementById('modalInput');
      if(isPrompt) { promptInput.style.display = 'block'; promptInput.value = ''; } else { promptInput.style.display = 'none'; }
      confirmActionCallback = callback; document.getElementById('customModalOverlay').classList.add('active');
  }
  function closeConfirm() { document.getElementById('customModalOverlay').classList.remove('active'); confirmActionCallback = null; }
  document.getElementById('modalCancelBtn').addEventListener('click', closeConfirm);
  document.getElementById('modalConfirmBtn').addEventListener('click', () => { const val = document.getElementById('modalInput').value.trim(); if(confirmActionCallback) confirmActionCallback(val); closeConfirm(); });

  function showMessage(elId, txt, succ) { const el=document.getElementById(elId); el.innerText=txt; el.className=succ?'success-msg show':'error-msg show'; }
  function hideMessage(elId) { document.getElementById(elId).classList.remove('show'); }

  function openReceipts() {
      fetch('/api/get_receipts').then(res => res.json()).then(data => {
          const cont = document.getElementById('receiptsContainer');
          cont.innerHTML = '';
          if(data.receipts.length === 0) { cont.innerHTML = '<p>No receipts found.</p>'; }
          else {
              data.receipts.forEach(r => {
                  cont.innerHTML += `<div style="background:var(--input-bg); border:1px solid var(--card-border); border-radius:12px; padding:10px; margin-bottom:8px;"><b>TxID:</b> ${r.tx_id}<br><b>Plan:</b> ${r.plan}<br><b>Amount:</b> ${r.amount} RUB<br><b>Date:</b> ${r.date_str}</div>`;
              });
          }
          document.getElementById('receiptsModalOverlay').classList.add('active');
      });
  }

  function processPayment(planName) {
      showConfirm('Purchase Plan', `Proceed to secure payment for ${planName}?`, 'Pay Now', false, () => {
          document.getElementById('loaderDynamicText').innerText = "Connecting to Payment Gateway...";
          document.getElementById('loaderScreen').style.display = 'flex';
          fetch('/create_payment', { 
              method: 'POST', 
              headers: { 'Content-Type': 'application/json' }, 
              body: JSON.stringify({ plan: planName }) 
          })
          .then(res => res.json())
          .then(data => {
              if(data.success) {
                  window.location.href = data.payment_url;
              } else {
                  document.getElementById('loaderScreen').style.display = 'none';
                  showConfirm('Payment Error', data.message || 'Could not connect to gateway', 'OK', false, null, true);
              }
          })
          .catch(err => {
              document.getElementById('loaderScreen').style.display = 'none';
              showConfirm('Network Error', 'Something went wrong.', 'OK', false, null, true);
          });
      });
  }

  function generateKey(forceOverride) {
      fetch('/generate_key', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ force: forceOverride }) }).then(res => res.json()).then(data => {
          if(data.success) { document.getElementById('generatedKeyDisplay').innerText = data.key; document.getElementById('generatedKeyDisplay').style.display = 'block'; showMessage('keyMessage', 'Key generated!', true); } 
          else { showConfirm('Cooldown Active', data.message, 'OK', false, null, true); }
      });
  }

  function switchPlanSubTab(tab) {
    document.getElementById('btnBuyPlan').classList.remove('active'); document.getElementById('btnMyPlan').classList.remove('active');
    document.getElementById('planBuySection').style.display = 'none'; document.getElementById('planMySection').style.display = 'none';
    if(tab === 'buy') { document.getElementById('btnBuyPlan').classList.add('active'); document.getElementById('planBuySection').style.display = 'block'; }
    else { document.getElementById('btnMyPlan').classList.add('active'); document.getElementById('planMySection').style.display = 'block'; }
    initTiltEffect();
  }

  let activeTicketId = null;
  let showAllTix = false;

  function loadAdminPanel(devApproved) {
     if (devApproved !== 'Yes') return;
     document.getElementById('devForceKeyBtn').style.display = 'block';
     document.getElementById('navDevBtn').style.display = 'flex';

     document.getElementById('devAdminView').style.display = 'flex';
     refreshAdminData(); setInterval(refreshConsoleLogs, 3000);
     setInterval(pollAdminTickets, 5000);
  }
  
  function refreshAdminData() {
     fetch('/admin/get_users').then(res => res.json()).then(data => {
        if(data.success) {
           document.getElementById('btnToggleMaintenance').innerHTML = data.maintenance === 'Yes' ? `<i data-lucide="power" style="width:14px;height:14px;"></i> Turn Site ON` : `<i data-lucide="power-off" style="width:14px;height:14px;"></i> Turn Site OFF (Maintenance)`;
           document.getElementById('btnToggleMaintenance').className = data.maintenance === 'Yes' ? "dev-btn-sm dev-btn-danger" : "dev-btn-sm";
           const tbody = document.getElementById('devUsersTableBody'); tbody.innerHTML = '';
           data.users.forEach(u => {
              const freezeText = u.is_frozen === 'Yes' ? 'Unfreeze' : 'Freeze';
              const freezeClass = u.is_frozen === 'Yes' ? 'dev-btn-sm dev-btn-danger' : 'dev-btn-sm dev-btn-freeze';
              tbody.innerHTML += `<tr><td><b>${u.login}</b></td><td>${u.plan}</td><td>${u.plan_days} d</td><td><select class="dev-select" onchange="promptAdminChangePlan('${u.login}', this.value)"><option value="" selected disabled>Select plan</option><option value="Starter Plan">Starter</option><option value="Professional Plan">Professional</option><option value="Extreme Plan">Extreme</option></select></td><td><div style="display:flex; gap:8px;"><button class="dev-btn-sm" onclick="promptAdminAddDays('${u.login}')">+7 Days</button><button class="${freezeClass}" onclick="adminToggleFreeze('${u.login}')">${freezeText}</button><button class="dev-btn-sm dev-btn-danger" onclick="requestAdminDeleteUser('${u.login}')">Delete</button></div></td></tr>`;
           });
           updateIcons();
        }
     }).catch(e => console.error(e));
     pollAdminTickets();
     loadAdminScripts(); 
  }

  function loadUserScripts() {
      fetch('/api/get_scripts').then(res=>res.json()).then(data=>{
          const container = document.getElementById('userScriptsContainer');
          container.innerHTML = '';
          if(data.scripts.length === 0) {
              container.innerHTML = '<p style="color:var(--text-secondary);">No scripts available at the moment.</p>';
              return;
          }
          
          let now = new Date().getTime();
          window.userScriptsData = {}; 
          
          data.scripts.forEach(s => {
              let releaseTime = new Date(s.release_date).getTime();
              let isLocked = releaseTime > now;
              
              window.userScriptsData[s.id] = s.script_code;
              
              let btnHtml = '';
              if (isLocked) {
                  let dateStr = new Date(s.release_date).toLocaleString();
                  btnHtml = `<button class="copy-btn" disabled><i data-lucide="lock" style="width:16px;height:16px;"></i> Unlocks: ${dateStr}</button>`;
              } else {
                  btnHtml = `<button class="copy-btn" onclick="copyDynamicScript(this, ${s.id})" data-i18n="s_copy"><i data-lucide="copy" style="width:16px;height:16px;"></i> COPY LUA SCRIPT</button>`;
              }
              
              container.innerHTML += `
              <div class="script-card">
                <div class="script-banner" style="background-image: url('${s.banner_url}');">
                </div>
                <div class="script-content">
                  <div class="script-header">
                      <h3>${s.title}</h3>
                      <span class="game-tag">for game: ${s.game}</span>
                  </div>
                  <p class="script-desc">${s.description}</p>
                  ${btnHtml}
                </div>
              </div>`;
          });
          updateIcons();
          initTiltEffect();
      });
  }

  function loadAdminScripts() {
      fetch('/api/get_scripts?admin=true').then(res=>res.json()).then(data=>{
          const tbody = document.getElementById('devScriptsTableBody');
          tbody.innerHTML = '';
          window.adminScriptsData = {}; 
          
          data.scripts.forEach(s => {
              window.adminScriptsData[s.id] = s;
              let f_icon = s.is_frozen === 'Yes' ? 'snowflake' : 'pause';
              let f_color = s.is_frozen === 'Yes' ? 'dev-btn-danger' : '';

              tbody.innerHTML += `
              <tr style="opacity: ${s.is_frozen === 'Yes' ? '0.5' : '1'}">
                  <td><b>${s.title}</b></td>
                  <td>${s.game}</td>
                  <td>${s.release_date}</td>
                  <td>
                      <div style="display:flex; gap:8px;">
                          <button class="dev-btn-sm" onclick="editAdminScript(${s.id})"><i data-lucide="edit-3" style="width:14px;height:14px;"></i></button>
                          <button class="dev-btn-sm ${f_color}" onclick="toggleFreezeScript(${s.id})"><i data-lucide="${f_icon}" style="width:14px;height:14px;"></i></button>
                          <button class="dev-btn-sm dev-btn-danger" onclick="deleteScript(${s.id})"><i data-lucide="trash-2" style="width:14px;height:14px;"></i></button>
                      </div>
                  </td>
              </tr>`;
          });
          updateIcons();
      });
  }

  function editAdminScript(id) {
      const s = window.adminScriptsData[id];
      if (!s) return;
      document.getElementById('devScriptId').value = s.id;
      document.getElementById('devScriptTitle').value = s.title;
      document.getElementById('devScriptGame').value = s.game;
      document.getElementById('devScriptBanner').value = s.banner_url;
      document.getElementById('devScriptDate').value = s.release_date;
      document.getElementById('devScriptCode').value = s.script_code;
      document.getElementById('devScriptDesc').value = s.description;
  }

  function copyDynamicScript(btn, id) {
    const finalCode = window.userScriptsData[id];
    if (!finalCode) return;
    navigator.clipboard.writeText(finalCode).then(() => {
      const originalHtml = btn.innerHTML; 
      btn.innerHTML = '<i data-lucide="check" style="width:16px;height:16px;"></i> Copied!'; 
      btn.style.backgroundColor = 'var(--success)'; btn.style.color = '#fff';
      updateIcons();
      setTimeout(() => { btn.innerHTML = originalHtml; btn.style.backgroundColor = ''; btn.style.color = ''; updateIcons(); }, 2000);
    });
  }

  function saveAdminScript() {
      const id = document.getElementById('devScriptId').value;
      const title = document.getElementById('devScriptTitle').value.trim();
      const game = document.getElementById('devScriptGame').value.trim();
      const banner = document.getElementById('devScriptBanner').value.trim();
      const date = document.getElementById('devScriptDate').value;
      const code = document.getElementById('devScriptCode').value.trim();
      const desc = document.getElementById('devScriptDesc').value.trim();
      
      if(!title || !game || !banner || !date || !code || !desc) {
          showConfirm('Error', 'Please fill all script fields!', 'OK', false, null, true);
          return;
      }
      
      fetch('/admin/save_script', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({id, title, game, banner_url: banner, release_date: date, script_code: code, description: desc})
      }).then(res=>res.json()).then(data=>{
          if(data.success) { clearScriptForm(); loadAdminScripts(); loadUserScripts(); }
      });
  }

  function clearScriptForm() {
      document.getElementById('devScriptId').value = '';
      document.getElementById('devScriptTitle').value = '';
      document.getElementById('devScriptGame').value = '';
      document.getElementById('devScriptBanner').value = '';
      document.getElementById('devScriptDate').value = '';
      document.getElementById('devScriptCode').value = '';
      document.getElementById('devScriptDesc').value = '';
  }

  function toggleFreezeScript(id) {
      fetch('/admin/freeze_script', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id}) })
      .then(res=>res.json()).then(data => { if(data.success){ loadAdminScripts(); loadUserScripts(); } });
  }

  function deleteScript(id) {
      showConfirm('Delete Script', 'Are you sure you want to permanently delete this script?', 'Delete', true, () => {
          fetch('/admin/delete_script', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id}) })
          .then(res=>res.json()).then(data => { if(data.success){ loadAdminScripts(); loadUserScripts(); } });
      });
  }

  function submitUserTicket() {
      const reason = document.getElementById('uTicketReason').value.trim();
      const prio = document.getElementById('uTicketPriority').value;
      if(!reason) return;
      fetch('/api/submit_ticket', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reason, priority: prio }) }).then(res=>res.json()).then(data=>{
          if(data.success) { document.getElementById('ticketSuccessOverlay').style.display='flex'; checkUserTicketState(); }
      });
  }

  function checkUserTicketState() {
      fetch('/api/get_user_ticket').then(res=>res.json()).then(data=>{
          if(data.ticket) {
              document.getElementById('userTicketFormCard').style.display = 'none';
              document.getElementById('userTicketChatCard').style.display = 'flex';
              document.getElementById('uChatBadge').innerText = data.ticket.status;
              activeTicketId = data.ticket.id;
              
              const box = document.getElementById('uChatBox');
              box.innerHTML = '';
              data.messages.forEach(m => {
                  const cl = m.sender === 'user' ? 'chat-msg user' : 'chat-msg dev';
                  box.innerHTML += `<div class="${cl}"><b>${m.sender}:</b> ${m.message}</div>`;
              });
              box.scrollTop = box.scrollHeight;
              
              if(data.ticket.status === 'closed') {
                  document.getElementById('uChatInputs').style.display = 'none';
                  document.getElementById('uChatBadge').innerText = "Closed ✔️";
              } else {
                  document.getElementById('uChatInputs').style.display = 'flex';
              }
          } else {
              document.getElementById('userTicketFormCard').style.display = 'block';
              document.getElementById('userTicketChatCard').style.display = 'none';
          }
      });
  }

  function pollAdminTickets() {
      fetch('/api/admin_get_tickets').then(res=>res.json()).then(data=>{
          if(!data.success) return;
          const cont = document.getElementById('adminTicketsContainer');
          cont.innerHTML = '';
          const tix = data.tickets;
          if(tix.length > 3) document.getElementById('btnShowAllTickets').style.display = 'block';
          else document.getElementById('btnShowAllTickets').style.display = 'none';
          
          let count = showAllTix ? tix.length : Math.min(3, tix.length);
          for(let i=0; i<count; i++) {
              let t = tix[i];
              let cl = t.status === 'closed' ? 'ticket-item closed' : (t.id === activeTicketId ? 'ticket-item active' : 'ticket-item');
              let mark = t.status === 'closed' ? '<i data-lucide="check-circle" style="color:var(--success);"></i>' : '<i data-lucide="alert-circle" style="color:#ff9f0a;"></i>';
              let btns = t.status === 'pending' ? `<button class="dev-btn-sm" style="background:var(--success); color:#fff; border:none;" onclick="actionTicket(${t.id}, 'accept')"><i data-lucide="check" style="width:14px;height:14px;"></i></button><button class="dev-btn-sm dev-btn-danger" onclick="actionTicket(${t.id}, 'reject')"><i data-lucide="x" style="width:14px;height:14px;"></i></button>` : `<button class="dev-btn-sm" onclick="openAdminChat(${t.id}, '${t.user_login}')"><i data-lucide="message-circle" style="width:14px;height:14px;"></i> Chat</button>`;
              
              if(t.status === 'closed') btns = `<span style="opacity:0.5;">Resolved</span>`;
              
              cont.innerHTML += `<div class="${cl}">
                  <div style="display:flex; align-items:center;">
                      <span class="ticket-icon" style="margin-right:10px;">${mark}</span>
                      <div><b>${t.user_login}</b> <span style="opacity:0.5; font-size:11px;">[${t.priority}]</span><br><span style="font-size:12px;">${t.reason}</span></div>
                  </div>
                  <div style="display:flex; gap:6px;">${btns}</div>
              </div>`;
          }
          updateIcons();
          if(activeTicketId) updateAdminChat(activeTicketId);
      });
  }

  function toggleAllTickets() { showAllTix = !showAllTix; document.getElementById('btnShowAllTickets').innerText = showAllTix ? "Show Less" : i18n[currentLang].t_show_all; pollAdminTickets(); }

  function actionTicket(id, action) {
      fetch('/api/ticket_action', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ id, action }) }).then(() => pollAdminTickets());
  }

  function openAdminChat(id, user) {
      activeTicketId = id;
      document.getElementById('adminChatView').style.display = 'block';
      document.getElementById('adminChatTitle').innerText = "Chat with " + user;
      updateAdminChat(id);
  }

  function closeActiveTicket() {
      if(!activeTicketId) return;
      actionTicket(activeTicketId, 'close');
      document.getElementById('adminChatView').style.display = 'none';
      activeTicketId = null;
  }

  function updateAdminChat(id) {
      fetch('/api/get_messages?id='+id).then(res=>res.json()).then(data=>{
          const box = document.getElementById('aChatBox');
          box.innerHTML = '';
          data.messages.forEach(m => {
              const cl = m.sender === 'dev' ? 'chat-msg dev' : 'chat-msg user';
              box.innerHTML += `<div class="${cl}"><b>${m.sender}:</b> ${m.message}</div>`;
          });
          box.scrollTop = box.scrollHeight;
      });
  }

  function sendTicketMessage(role) {
      const inputId = role === 'user' ? 'uChatInput' : 'aChatInput';
      const msg = document.getElementById(inputId).value.trim();
      if(!msg || !activeTicketId) return;
      
      fetch('/api/send_message', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ id: activeTicketId, message: msg, role }) }).then(() => {
          document.getElementById(inputId).value = '';
          if(role === 'user') checkUserTicketState(); else updateAdminChat(activeTicketId);
      });
  }

  function refreshConsoleLogs() {
     fetch('/admin/get_logs').then(res => res.json()).then(data => {
        if(data.success) {
           const box = document.getElementById('webConsoleBox'); box.innerHTML = '';
           data.logs.forEach(l => { box.innerHTML += `<div class="web-log-line web-log-${l.level}">${l.text}</div>`; }); box.scrollTop = box.scrollHeight;
        }
     });
  }

  function promptAdminChangePlan(login, newPlan) {
      if(!newPlan) return;
      showConfirm('Update Plan', i18n[currentLang].prompt_msg, 'Update', false, (msg) => {
          fetch('/admin/change_plan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ login: login, plan: newPlan, message: msg || 'Enjoy!' }) }).then(res => res.json()).then(data => { 
              if(data.success) refreshAdminData(); else showConfirm('Error', data.message, 'OK', false, null, true);
          });
      }, false, true);
  }
  function promptAdminAddDays(login) {
      showConfirm('Add +7 Days', i18n[currentLang].prompt_msg, 'Add', false, (msg) => {
          fetch('/admin/add_days', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ login: login, message: msg || 'Keep up the good work!' }) }).then(res => res.json()).then(data => { 
              if(data.success) refreshAdminData(); else showConfirm('Error', data.message, 'OK', false, null, true);
          });
      }, false, true);
  }

  function adminToggleFreeze(login) { fetch('/admin/toggle_freeze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ login }) }).then(res => res.json()).then(data => { if(data.success) refreshAdminData(); else showConfirm('Error', data.message, 'OK', false, null, true); }); }
  function adminToggleMaintenance() { fetch('/admin/toggle_maintenance', { method: 'POST' }).then(res => res.json()).then(data => { if(data.success) refreshAdminData(); }); }

  function requestAdminDeleteUser(login) { 
      showConfirm('Delete User', `Are you sure you want to permanently delete '${login}'?`, 'Delete', true, () => {
          fetch('/admin/delete_user', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ login }) }).then(res => res.json()).then(data => { if(data.success) refreshAdminData(); else showConfirm('Error', data.message, 'OK', false, null, true); }); 
      });
  }

  function adminUpdateDiscordLink() {
      const link = document.getElementById('devDiscordLink').value.trim();
      fetch('/admin/update_discord', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ link }) }).then(res => res.json()).then(data => {
          if(data.success) { document.getElementById('discordJoinBtn').href = link; showConfirm('Success', 'Discord link updated successfully!', 'OK', false, null, true); }
      });
  }

  function closeRewardScreen() {
      fetch('/api/clear_reward', { method: 'POST' }).then(() => { document.getElementById('rewardScreen').style.display = 'none'; });
  }

  function loadCaptcha() {
      fetch('/api/captcha').then(res => res.json()).then(data => { document.getElementById('captchaBox').innerText = data.text; document.getElementById('regCaptcha').value = ''; });
  }

  const canvas = document.getElementById('bgCanvas'); const ctx = canvas.getContext('2d');
  let width, height, particles = [], mouse = { x: -1000, y: -1000 }, currentDotColor = 'rgba(255, 255, 255, 0.3)', isErrorState = false, isSystemLoading = false; 
  function updateCanvasColor() { currentDotColor = getComputedStyle(document.body).getPropertyValue('--dot-color').trim(); }
  function resize() { width = canvas.width = window.innerWidth; height = canvas.height = window.innerHeight; initParticles(); }
  window.addEventListener('resize', resize);
  class Particle {
    constructor() { this.x = Math.random() * width; this.y = Math.random() * height; this.size = Math.random() * 2 + 1; this.density = (Math.random() * 20) + 5; this.angle = Math.random() * 360; this.speed = Math.random() * 0.3 + 0.1; this.vx = 0; this.vy = 0; this.friction = 0.92; }
    update() {
      this.angle += 0.01;
      
      if (globalWarpSpeedY > 0) {
          this.y -= globalWarpSpeedY * (this.speed * 2);
      } else {
          if (isSystemLoading) { this.vy -= 1.5; this.vx += (Math.random() - 0.5) * 0.2; } 
          else { this.vy -= this.speed * 0.1; this.vx += Math.sin(this.angle) * 0.05; }
      }

      let dx = mouse.x - this.x, dy = mouse.y - this.y, distance = Math.sqrt(dx * dx + dy * dy), maxDistance = 180;
      if (distance < maxDistance) { let force = (maxDistance - distance) / maxDistance; this.vx -= (dx / distance) * force * 1.5; this.vy -= (dy / distance) * force * 1.5; }
      this.vx *= this.friction; this.vy *= this.friction; this.x += this.vx; this.y += this.vy;
      if (this.y < -20) { this.y = height + 20; this.x = Math.random() * width; this.vx = 0; this.vy = 0;}
      if (this.y > height + 20) { this.y = -20; this.x = Math.random() * width; this.vx = 0; this.vy = 0;}
      if (this.x < -20) { this.x = width + 20; this.vx = 0; this.vy = 0;}
      if (this.x > width + 20) { this.x = -20; this.vx = 0; this.vy = 0;}
    }
    draw() { ctx.beginPath(); ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2); ctx.fillStyle = isErrorState ? '#ea1515' : currentDotColor; ctx.fill(); }
  }
  function initParticles() { particles = []; let numberOfParticles = (width * height) / 8000; for (let i = 0; i < numberOfParticles; i++) particles.push(new Particle()); }
  window.addEventListener('mousemove', (e) => { mouse.x = e.clientX; mouse.y = e.clientY; });
  window.addEventListener('mouseout', () => { mouse.x = -1000; mouse.y = -1000; });
  function animate() { 
      ctx.clearRect(0, 0, width, height); 
      if (globalWarpSpeedY > 0) { globalWarpSpeedY *= 0.94; if (globalWarpSpeedY < 0.1) globalWarpSpeedY = 0; }
      for (let i = 0; i < particles.length; i++) { particles[i].update(); particles[i].draw(); } 
      requestAnimationFrame(animate); 
  }
  updateCanvasColor(); resize(); animate();

  const themeBtn = document.getElementById('themeBtn');
  document.documentElement.setAttribute('data-theme', localStorage.getItem('theme') || 'dark');
  updateCanvasColor();
  themeBtn.addEventListener('click', () => {
    const newTheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme); localStorage.setItem('theme', newTheme); updateCanvasColor();
  });
  setInterval(() => { fetch('/get_time').then(res => res.json()).then(data => { document.getElementById('clock').innerText = data.time; }); }, 1000);

  const sidebarBtns = document.querySelectorAll('.sidebar-btn');
  const tabContents = document.querySelectorAll('.tab-content');
  function switchTab(targetId) {
    sidebarBtns.forEach(b => b.classList.remove('active')); tabContents.forEach(t => t.classList.remove('active'));
    sidebarBtns.forEach(b => { if(b.getAttribute('data-target') === targetId) b.classList.add('active'); }); document.getElementById(targetId).classList.add('active');
    if(targetId === 'tab-faq' && !document.getElementById('userTicketChatCard').style.display.includes('none')) { checkUserTicketState(); }
    if(targetId === 'tab-scripts') { loadUserScripts(); }
    initTiltEffect(); 
  }
  sidebarBtns.forEach(btn => btn.addEventListener('click', () => switchTab(btn.getAttribute('data-target'))));
  document.getElementById('userDisplay').addEventListener('click', () => switchTab('tab-main'));

  let loadingInterval;
  function showLoadingScreen() { document.getElementById('loaderScreen').style.display = 'flex'; isSystemLoading = true; let i = 0; const txts = ["Authenticating...", "Decrypting...", "Loading Modules..."]; document.getElementById('loaderDynamicText').innerText = txts[i]; loadingInterval = setInterval(() => { i = (i + 1) % txts.length; document.getElementById('loaderDynamicText').innerText = txts[i]; }, 500); }
  function hideLoadingScreen() { document.getElementById('loaderScreen').style.display = 'none'; isSystemLoading = false; clearInterval(loadingInterval); }

  document.addEventListener('DOMContentLoaded', () => {
    const savedLang = localStorage.getItem('lang') || 'en'; setLang(savedLang);
    const appMainWrapper = document.getElementById('appMainWrapper'); const authForm = document.getElementById('authForm'); const secretForm = document.getElementById('secretForm'); const regForm = document.getElementById('regForm'); const twoFaForm = document.getElementById('twoFaForm'); const createAccountWrapper = document.getElementById('createAccountWrapper');
    
    if ({{ show_freeze }}) { document.getElementById('introOverlay').style.display = 'none'; appMainWrapper.style.display = 'none'; document.getElementById('freezeScreen').style.display = 'flex'; return; }
    if ({{ show_maintenance }}) {
        document.getElementById('introOverlay').style.display = 'none';
        appMainWrapper.style.display = 'none'; document.getElementById('maintenanceScreen').style.display = 'flex';
        let lockClicks = 0; document.getElementById('maintenanceLockIcon').addEventListener('click', () => { lockClicks++; if (lockClicks >= 3) { document.getElementById('maintenanceScreen').style.display = 'none'; document.getElementById('landingWrapper').style.display = 'flex'; authForm.style.display = 'flex'; } });
        return;
    }

    document.getElementById('createAccountLink').addEventListener('click', () => { authForm.style.display = 'none'; regForm.style.display = 'flex'; loadCaptcha(); });
    document.getElementById('backToLoginLink').addEventListener('click', () => { regForm.style.display = 'none'; authForm.style.display = 'flex'; createAccountWrapper.classList.remove('show'); hideMessage('message'); });
    document.getElementById('cancelSecretLink').addEventListener('click', () => { secretForm.style.display = 'none'; authForm.style.display = 'flex'; });
    document.getElementById('cancel2FaLink').addEventListener('click', () => { twoFaForm.style.display = 'none'; authForm.style.display = 'flex'; });

    const regBtn = document.getElementById('regBtn');
    document.getElementById('regAgree').addEventListener('change', (e) => { regBtn.disabled = !e.target.checked; });

    regBtn.addEventListener('click', () => {
      const login = document.getElementById('regLogin').value.trim(); const password = document.getElementById('regPassword').value;
      const email = document.getElementById('regEmail').value.trim(); const secret = document.getElementById('regSecret').value.trim();
      const source = document.getElementById('regSource').value.trim(); const captcha = document.getElementById('regCaptcha').value.trim();
      if (!login || !password || !secret || !source || !captcha) { showMessage('regMessage', 'Please fill all required fields.', false); return; }
      fetch('/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ login, password, email, secret, source, captcha })
      }).then(res => res.json()).then(data => {
        if (data.success) { showMessage('regMessage', 'Account created successfully!', true); setTimeout(() => { regForm.style.display = 'none'; authForm.style.display = 'flex'; document.getElementById('login').value = login; hideMessage('regMessage'); createAccountWrapper.classList.remove('show'); hideMessage('message'); }, 1500); } 
        else { showMessage('regMessage', data.message, false); loadCaptcha(); triggerErrorAnimation(regForm); }
      });
    });

    if ({{ 'true' if current_user else 'false' }}) { 
        document.getElementById('introOverlay').style.display = 'none';
        document.getElementById('landingWrapper').style.display = 'none';
        appMainWrapper.style.display = 'flex';
        loadDashboard(); 
    }

    function loadDashboard() {
        document.getElementById('mainHeader').style.display = 'none'; document.getElementById('dashboardLayout').style.display = 'flex';
        fetch('/get_user_info').then(res => res.json()).then(data => {
            if(data.success) {
                if(data.is_frozen === 'Yes') { window.location.reload(); }
                if(data.pending_reward && data.pending_reward.type) {
                    const rType = data.pending_reward.type; const rVal = data.pending_reward.value; const rMsg = data.pending_reward.msg;
                    let valText = ""; if (rType === "plan") valText = "PLAN: " + rVal; if (rType === "days") valText = "+7 Days";
                    document.getElementById('rewardValue').innerText = valText; document.getElementById('rewardMessage').innerText = rMsg; document.getElementById('rewardScreen').style.display = 'flex';
                }
                if(data.active_key) { document.getElementById('generatedKeyDisplay').innerText = data.active_key; document.getElementById('generatedKeyDisplay').style.display = 'block'; }
                
                const greetings = ["Welcome back", "Glad to see you", "Hello", "Ready for action", "Good to have you"];
                const randGreet = greetings[Math.floor(Math.random() * greetings.length)];
                document.getElementById('planGreeting').innerText = `${randGreet}, ${data.login}!`;

                document.getElementById('userDisplay').innerHTML = `<i data-lucide="user" style="width:14px; height:14px;"></i> <span id="userLoginText">${data.login}</span>`;
                document.getElementById('profileLogin').innerText = data.login; document.getElementById('profilePlan').innerText = data.plan; document.getElementById('profileRegDate').innerText = data.reg_date; document.getElementById('profileDevApproved').innerText = data.dev_approved; document.getElementById('planCurrentStatus').innerText = "Your current plan: " + data.plan + " - " + data.plan_days + " Days";
                
                loadUserScripts(); 
                loadAdminPanel(data.dev_approved); setInterval(checkUserTicketState, 5000); checkUserTicketState();
                updateIcons();
            }
        });
    }

    function triggerErrorAnimation(formEl) { formEl.classList.remove('shake-error'); setTimeout(() => formEl.classList.add('shake-error'), 10); setTimeout(() => formEl.classList.remove('shake-error'), 400); isErrorState = true; setTimeout(() => { isErrorState = false; }, 600); }
    document.getElementById('logoutBtn').addEventListener('click', () => { showConfirm('Sign Out', 'Are you sure you want to log out?', 'Logout', true, () => { fetch('/logout').then(() => window.location.reload()); }); });

    document.getElementById('signUpBtn').addEventListener('click', () => {
      const login = document.getElementById('login').value.trim(); const password = document.getElementById('password').value;
      if (!login || !password) { showMessage('message', 'Empty fields detected.', false); triggerErrorAnimation(authForm); createAccountWrapper.classList.add('show'); return; }
      fetch('/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ login, password })
      }).then(res => res.json()).then(data => {
        if (data.success) {
          if(data.is_frozen) { window.location.reload(); } 
          else if(data.require_secret) { hideMessage('message'); authForm.style.display = 'none'; secretForm.style.display = 'flex'; } 
          else if(data.require_2fa) { authForm.style.display = 'none'; twoFaForm.style.display = 'flex'; } 
          else { hideMessage('message'); authForm.style.display = 'none'; document.getElementById('mainHeader').style.display = 'none'; showLoadingScreen(); setTimeout(() => { document.getElementById('clockWrapper').style.display = 'flex'; document.getElementById('userWrapper').style.display = 'flex'; hideLoadingScreen(); loadDashboard(); }, 2500); }
        } else { showMessage('message', 'Invalid credentials.', false); triggerErrorAnimation(authForm); createAccountWrapper.classList.add('show'); }
      });
    });
    
    document.getElementById('verifySecretBtn').addEventListener('click', () => {
       const secret = document.getElementById('devSecretCode').value.trim(); if(!secret) return;
       fetch('/verify_secret', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ secret }) }).then(res => res.json()).then(data => {
          if(data.success) { if(data.require_2fa) { secretForm.style.display = 'none'; twoFaForm.style.display = 'flex'; } else { hideMessage('secretMessage'); secretForm.style.display = 'none'; document.getElementById('mainHeader').style.display = 'none'; showLoadingScreen(); setTimeout(() => { document.getElementById('clockWrapper').style.display = 'flex'; document.getElementById('userWrapper').style.display = 'flex'; hideLoadingScreen(); loadDashboard(); }, 2500); }
          } else { showMessage('secretMessage', data.message, false); triggerErrorAnimation(secretForm); }
       });
    });

    document.getElementById('verifyBtn').addEventListener('click', () => {
       const code = document.getElementById('twoFaCode').value.trim();
       fetch('/verify_2fa', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code }) }).then(res => res.json()).then(data => {
          if(data.success) { twoFaForm.style.display = 'none'; document.getElementById('mainHeader').style.display = 'none'; showLoadingScreen(); setTimeout(() => { document.getElementById('clockWrapper').style.display = 'flex'; document.getElementById('userWrapper').style.display = 'flex'; hideLoadingScreen(); loadDashboard(); }, 2500); } 
          else { showMessage('twoFaMessage', data.message, false); triggerErrorAnimation(twoFaForm); }
       });
    });
  });
</script>
</body>
</html>
'''

@app.route('/')
def index():
    c_log('INFO', f"Connection from {request.remote_addr} to homepage.")
    conn = get_db_connection()
    maintenance = conn.execute("SELECT value FROM settings WHERE key = 'maintenance'").fetchone()
    is_maintenance = True if (maintenance and maintenance['value'] == 'Yes') else False
    discord_row = conn.execute("SELECT value FROM settings WHERE key = 'discord_link'").fetchone()
    discord_link = discord_row['value'] if discord_row else "https://discord.gg/"
    
    current_user = session.get('user')
    is_frozen = False
    dev_approved = 'No'
    
    if current_user:
        user_data = conn.execute("SELECT is_frozen, dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
        if user_data:
            if user_data['is_frozen'] == 'Yes': is_frozen = True; session.pop('user', None) 
            dev_approved = user_data['dev_approved']
        else: session.pop('user', None)
            
    conn.close()
    show_maintenance = 'true' if (is_maintenance and dev_approved != 'Yes') else 'false'
    show_freeze = 'true' if is_frozen else 'false'
    return render_template_string(TEMPLATE, current_user=session.get('user'), show_maintenance=show_maintenance, show_freeze=show_freeze, discord_link=discord_link)

@app.route('/api/captcha')
def get_captcha():
    a = random.randint(1, 9); b = random.randint(1, 9)
    session['captcha_answer'] = str(a + b)
    return jsonify({"text": f"{a} + {b} = ?"})

@app.route('/api/clear_reward', methods=['POST'])
def clear_reward():
    current_user = session.get('user')
    if current_user:
        conn = get_db_connection()
        conn.execute("UPDATE users SET pending_reward = '' WHERE login = ?", (current_user,))
        conn.commit(); conn.close()
    return jsonify({"success": True})

@app.route('/get_time')
def get_time():
    tz = pytz.timezone('Europe/Moscow')
    return jsonify({'time': datetime.now(tz).strftime('%H:%M:%S')})

@app.route('/get_user_info')
def get_user_info():
    current_user = session.get('user')
    if not current_user: return jsonify({'success': False})
    
    tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(tz)
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE login = ?", (current_user,)).fetchone()
    
    active_key = None
    latest_key_row = conn.execute("SELECT key_code, expires_at FROM keys WHERE user_login = ? ORDER BY id DESC LIMIT 1", (current_user,)).fetchone()
    if latest_key_row:
        expires_time = datetime.strptime(latest_key_row['expires_at'], '%d.%m.%Y %H:%M:%S').replace(tzinfo=tz)
        if now <= expires_time: active_key = latest_key_row['key_code']
    conn.close()

    if user:
        pending_reward_data = {}
        if user['pending_reward']:
            try: pending_reward_data = json.loads(user['pending_reward'])
            except: pass
        return jsonify({'success': True, 'login': user['login'], 'plan': user['plan'], 'plan_days': user['plan_days'], 'reg_date': user['reg_date'], 'dev_approved': user['dev_approved'], 'is_frozen': user['is_frozen'], 'pending_reward': pending_reward_data, 'active_key': active_key})
    return jsonify({'success': False})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    login_input = data.get('login', '').strip()
    password_input = data.get('password', '')
    c_log('INFO', f"Login attempt for username: {login_input}")

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE login = ?", (login_input,)).fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password_input):
        if user['is_frozen'] == 'Yes': return jsonify({'success': True, 'is_frozen': True})
        session['pending_user'] = login_input
        if user['dev_approved'] == 'Yes': return jsonify({'success': True, 'require_secret': True, 'require_2fa': False, 'is_frozen': False})
        if user['email'] and user['email'].strip() != '':
            code = str(random.randint(100000, 999999))
            session['2fa_code'] = code; session['2fa_expiry'] = time.time() + 900
            send_real_email(user['email'], code)
            return jsonify({'success': True, 'require_secret': False, 'require_2fa': True, 'is_frozen': False})
        else:
            session['user'] = login_input; session.pop('pending_user', None)
            c_log('SUCCESS', f"User {login_input} logged in successfully.")
            return jsonify({'success': True, 'require_secret': False, 'require_2fa': False, 'is_frozen': False})
    else: return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/verify_secret', methods=['POST'])
def verify_secret():
    data = request.get_json()
    secret_input = data.get('secret', '').strip()
    if 'pending_user' not in session: return jsonify({'success': False, 'message': 'Session expired.'})
    target_user = session['pending_user']
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE login = ?", (target_user,)).fetchone()
    conn.close()
    
    if user and user['secret'] == secret_input:
        if user['email'] and user['email'].strip() != '':
            code = str(random.randint(100000, 999999))
            session['2fa_code'] = code; session['2fa_expiry'] = time.time() + 900
            send_real_email(user['email'], code)
            return jsonify({'success': True, 'require_2fa': True})
        else:
            session['user'] = target_user; session.pop('pending_user', None)
            return jsonify({'success': True, 'require_2fa': False})
    return jsonify({'success': False, 'message': 'Invalid secret codename.'})

@app.route('/verify_2fa', methods=['POST'])
def verify_2fa():
    data = request.get_json()
    code = data.get('code', '').strip()
    if 'pending_user' in session and '2fa_code' in session:
        target_user = session['pending_user']
        if time.time() > session.get('2fa_expiry', 0): return jsonify({'success': False, 'message': 'Code expired! Please login again.'})
        if code == session['2fa_code']:
            session['user'] = target_user; session.pop('pending_user', None); session.pop('2fa_code', None); session.pop('2fa_expiry', None)
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Incorrect code.'})
    return jsonify({'success': False, 'message': 'Session error.'})

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    login_input = data.get('login', '').strip()
    password_input = data.get('password', '')
    email_input = data.get('email', '').strip()
    secret_input = data.get('secret', '').strip()
    source_input = data.get('source', '').strip()
    captcha_input = data.get('captcha', '').strip()
    
    if session.get('captcha_answer') != captcha_input: return jsonify({'success': False, 'message': 'Invalid Captcha! Try again.'})

    conn = get_db_connection()
    if conn.execute("SELECT id FROM users WHERE login = ?", (login_input,)).fetchone():
        conn.close(); return jsonify({'success': False, 'message': 'Username is already taken.'})

    tz = pytz.timezone('Europe/Moscow')
    reg_date = datetime.now(tz).strftime('%d.%m.%Y')

    conn.execute('''INSERT INTO users (login, password_hash, email, secret, source, reg_date, plan, plan_days, dev_approved, is_frozen, pending_reward)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (login_input, generate_password_hash(password_input), email_input, secret_input, source_input, reg_date, 'Free Tier', 0, 'No', 'No', ''))
    conn.commit(); conn.close()
    session.pop('captcha_answer', None)
    c_log('SUCCESS', f"New account created successfully for {login_input}.")
    return jsonify({'success': True})

@app.route('/generate_key', methods=['POST'])
def generate_key():
    current_user = session.get('user')
    if not current_user: return jsonify({'success': False, 'message': 'Unauthorized'})

    force_override = request.get_json().get('force', False)
    tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(tz)
    
    conn = get_db_connection()
    user = conn.execute("SELECT plan FROM users WHERE login = ?", (current_user,)).fetchone()
    
    if not force_override:
        last_key = conn.execute("SELECT created_at FROM keys WHERE user_login = ? ORDER BY id DESC LIMIT 1", (current_user,)).fetchone()
        if last_key:
            last_time = datetime.strptime(last_key['created_at'], '%d.%m.%Y %H:%M:%S').replace(tzinfo=tz)
            if now < last_time + timedelta(hours=24):
                time_left = (last_time + timedelta(hours=24)) - now
                hours, remainder = divmod(time_left.seconds, 3600); minutes, _ = divmod(remainder, 60)
                conn.close()
                return jsonify({'success': False, 'message': f'Please wait {hours}h {minutes}m before generating a new key.'})

    plan = user['plan']
    prefix = "FREE"
    if 'Starter' in plan: prefix = "STARTER"
    elif 'Professional' in plan: prefix = "PRO"
    elif 'Extreme' in plan: prefix = "EXTREME"
    elif 'Developer' in plan: prefix = "DEV"

    part1 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    part2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    part3 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    part4 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    key_code = f"{prefix}_GS-{part1}-{part2}-{part3}-{part4}"

    created_at = now.strftime('%d.%m.%Y %H:%M:%S')
    expires_at = (now + timedelta(hours=12) if 'Free' in plan else now + timedelta(days=90)).strftime('%d.%m.%Y %H:%M:%S')

    conn.execute('''INSERT INTO keys (key_code, user_login, plan, created_at, expires_at) VALUES (?, ?, ?, ?, ?)''', (key_code, current_user, plan, created_at, expires_at))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'key': key_code})

@app.route('/api/mobile_verify', methods=['GET'])
def mobile_verify():
    key_input = request.args.get('key', '').strip()
    hwid_input = request.args.get('hwid', '').strip()
    if not key_input: return "ERROR|No key provided"

    conn = get_db_connection()
    key_row = conn.execute("SELECT * FROM keys WHERE key_code = ?", (key_input,)).fetchone()
    if not key_row: conn.close(); return "ERROR|Invalid key"

    tz = pytz.timezone('Europe/Moscow'); now = datetime.now(tz)
    expires_time = datetime.strptime(key_row['expires_at'], '%d.%m.%Y %H:%M:%S').replace(tzinfo=tz)
    if now > expires_time: conn.close(); return "ERROR|Key expired"

    user_row = conn.execute("SELECT is_frozen FROM users WHERE login = ?", (key_row['user_login'],)).fetchone()
    if user_row and user_row['is_frozen'] == 'Yes': conn.close(); return "ERROR|Account frozen"

    if key_row['hwid'] == '': conn.execute("UPDATE keys SET hwid = ? WHERE key_code = ?", (hwid_input, key_input)); conn.commit()
    elif hwid_input and key_row['hwid'] != hwid_input: conn.close(); return "ERROR|HWID Mismatch"
    conn.close()
    return f"SUCCESS|{key_row['user_login']}|{key_row['plan']}"

@app.route('/api/submit_ticket', methods=['POST'])
def submit_ticket():
    current_user = session.get('user')
    if not current_user: return jsonify({'success': False})
    data = request.get_json()
    reason = data.get('reason'); priority = data.get('priority')
    tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(tz).strftime('%d.%m.%Y %H:%M')
    conn = get_db_connection()
    conn.execute("INSERT INTO tickets (user_login, reason, priority, created_at) VALUES (?, ?, ?, ?)", (current_user, reason, priority, now))
    conn.commit(); conn.close()
    c_log('SUCCESS', f"User {current_user} created a new support ticket.")
    return jsonify({'success': True})

@app.route('/api/get_user_ticket', methods=['GET'])
def get_user_ticket():
    current_user = session.get('user')
    if not current_user: return jsonify({'ticket': None})
    conn = get_db_connection()
    ticket = conn.execute("SELECT * FROM tickets WHERE user_login = ? ORDER BY id DESC LIMIT 1", (current_user,)).fetchone()
    if ticket:
        messages = conn.execute("SELECT * FROM ticket_messages WHERE ticket_id = ?", (ticket['id'],)).fetchall()
        conn.close()
        return jsonify({'ticket': dict(ticket), 'messages': [dict(m) for m in messages]})
    conn.close()
    return jsonify({'ticket': None})

@app.route('/api/admin_get_tickets', methods=['GET'])
def admin_get_tickets():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes': conn.close(); return jsonify({'success': False}), 403
    tickets = conn.execute("SELECT * FROM tickets ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify({'success': True, 'tickets': [dict(t) for t in tickets]})

@app.route('/api/ticket_action', methods=['POST'])
def ticket_action():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes': conn.close(); return jsonify({'success': False}), 403
    data = request.get_json()
    t_id = data.get('id'); action = data.get('action')
    if action == 'accept': conn.execute("UPDATE tickets SET status = 'active' WHERE id = ?", (t_id,))
    elif action == 'reject' or action == 'close': conn.execute("UPDATE tickets SET status = 'closed' WHERE id = ?", (t_id,))
    conn.commit(); conn.close()
    return jsonify({'success': True})

@app.route('/api/send_message', methods=['POST'])
def send_message():
    data = request.get_json()
    t_id = data.get('id'); msg = data.get('message'); role = data.get('role')
    tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(tz).strftime('%H:%M')
    conn = get_db_connection()
    conn.execute("INSERT INTO ticket_messages (ticket_id, sender, message, sent_at) VALUES (?, ?, ?, ?)", (t_id, role, msg, now))
    conn.commit(); conn.close()
    return jsonify({'success': True})

@app.route('/api/get_messages', methods=['GET'])
def get_messages():
    t_id = request.args.get('id')
    conn = get_db_connection()
    messages = conn.execute("SELECT * FROM ticket_messages WHERE ticket_id = ?", (t_id,)).fetchall()
    conn.close()
    return jsonify({'messages': [dict(m) for m in messages]})

@app.route('/api/get_scripts', methods=['GET'])
def get_scripts():
    is_admin_request = request.args.get('admin') == 'true'
    current_user = session.get('user')
    conn = get_db_connection()
    if is_admin_request:
        check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
        if not check or check['dev_approved'] != 'Yes': 
            conn.close()
            return jsonify({'success': False}), 403
        scripts = conn.execute("SELECT * FROM scripts ORDER BY id DESC").fetchall()
    else:
        scripts = conn.execute("SELECT * FROM scripts WHERE is_frozen = 'No' ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify({'success': True, 'scripts': [dict(s) for s in scripts]})

@app.route('/admin/save_script', methods=['POST'])
def save_script():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes': 
        conn.close(); return jsonify({'success': False}), 403
    data = request.get_json()
    s_id = data.get('id'); title = data.get('title'); game = data.get('game')
    banner = data.get('banner_url'); r_date = data.get('release_date')
    code = data.get('script_code'); desc = data.get('description')
    if s_id:
        conn.execute('''UPDATE scripts SET title=?, game=?, banner_url=?, release_date=?, script_code=?, description=? WHERE id=?''',
                     (title, game, banner, r_date, code, desc, s_id))
    else:
        conn.execute('''INSERT INTO scripts (title, game, banner_url, release_date, script_code, description) VALUES (?, ?, ?, ?, ?, ?)''',
                     (title, game, banner, r_date, code, desc))
    conn.commit(); conn.close()
    return jsonify({'success': True})

@app.route('/admin/freeze_script', methods=['POST'])
def freeze_script():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes': conn.close(); return jsonify({'success': False}), 403
    s_id = request.get_json().get('id')
    target = conn.execute("SELECT is_frozen FROM scripts WHERE id = ?", (s_id,)).fetchone()
    new_status = 'No' if target['is_frozen'] == 'Yes' else 'Yes'
    conn.execute("UPDATE scripts SET is_frozen = ? WHERE id = ?", (new_status, s_id))
    conn.commit(); conn.close()
    return jsonify({'success': True})

@app.route('/admin/delete_script', methods=['POST'])
def delete_script():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes': conn.close(); return jsonify({'success': False}), 403
    s_id = request.get_json().get('id')
    conn.execute("DELETE FROM scripts WHERE id = ?", (s_id,))
    conn.commit(); conn.close()
    return jsonify({'success': True})

@app.route('/admin/get_users')
def admin_get_users():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes': conn.close(); return jsonify({'success': False}), 403
    db_users = conn.execute("SELECT login, plan, plan_days, is_frozen, dev_approved FROM users").fetchall()
    maintenance = conn.execute("SELECT value FROM settings WHERE key = 'maintenance'").fetchone()
    conn.close()
    return jsonify({'success': True, 'users': [dict(u) for u in db_users], 'maintenance': maintenance['value'] if maintenance else 'No'})

@app.route('/admin/get_logs')
def admin_get_logs():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    conn.close()
    if not check or check['dev_approved'] != 'Yes': return jsonify({'success': False}), 403
    return jsonify({'success': True, 'logs': LIVE_LOGS})

@app.route('/admin/change_plan', methods=['POST'])
def admin_change_plan():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes': conn.close(); return jsonify({'success': False}), 403
    data = request.get_json()
    target_user = data.get('login'); new_plan = data.get('plan'); dev_msg = data.get('message', '')
    target_data = conn.execute("SELECT plan, dev_approved FROM users WHERE login = ?", (target_user,)).fetchone()
    if target_data and (target_data['dev_approved'] == 'Yes' or 'Developer' in target_data['plan']):
        conn.close(); return jsonify({'success': False, 'message': 'Cannot modify a Developer account.'})
    days = 7 if 'Starter' in new_plan else (30 if 'Professional' in new_plan else 90)
    reward_data = json.dumps({"type": "plan", "value": new_plan, "msg": dev_msg})
    conn.execute("UPDATE users SET plan = ?, plan_days = ?, pending_reward = ? WHERE login = ?", (new_plan, days, reward_data, target_user))
    conn.execute("DELETE FROM keys WHERE user_login = ?", (target_user,))
    conn.commit(); conn.close()
    return jsonify({'success': True})

@app.route('/admin/add_days', methods=['POST'])
def admin_add_days():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes': conn.close(); return jsonify({'success': False}), 403
    data = request.get_json()
    target_user = data.get('login'); dev_msg = data.get('message', '')
    reward_data = json.dumps({"type": "days", "value": "+7 Days", "msg": dev_msg})
    conn.execute("UPDATE users SET plan_days = plan_days + 7, pending_reward = ? WHERE login = ?", (reward_data, target_user))
    conn.commit(); conn.close()
    return jsonify({'success': True})

@app.route('/admin/toggle_freeze', methods=['POST'])
def admin_toggle_freeze():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes': conn.close(); return jsonify({'success': False}), 403
    data = request.get_json(); target_user = data.get('login')
    target_data = conn.execute("SELECT is_frozen FROM users WHERE login = ?", (target_user,)).fetchone()
    new_status = 'No' if target_data['is_frozen'] == 'Yes' else 'Yes'
    conn.execute("UPDATE users SET is_frozen = ? WHERE login = ?", (new_status, target_user))
    conn.commit(); conn.close()
    return jsonify({'success': True})

@app.route('/admin/toggle_maintenance', methods=['POST'])
def admin_toggle_maintenance():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes': conn.close(); return jsonify({'success': False}), 403
    m_data = conn.execute("SELECT value FROM settings WHERE key = 'maintenance'").fetchone()
    new_val = 'No' if m_data and m_data['value'] == 'Yes' else 'Yes'
    conn.execute("UPDATE settings SET value = ? WHERE key = 'maintenance'", (new_val,))
    conn.commit(); conn.close()
    return jsonify({'success': True})

@app.route('/admin/delete_user', methods=['POST'])
def admin_delete_user():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes': conn.close(); return jsonify({'success': False}), 403
    data = request.get_json(); target_user = data.get('login')
    conn.execute("DELETE FROM users WHERE login = ?", (target_user,))
    conn.commit(); conn.close()
    return jsonify({'success': True})

@app.route('/admin/update_discord', methods=['POST'])
def admin_update_discord():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes': conn.close(); return jsonify({'success': False}), 403
    new_link = request.get_json().get('link', '').strip()
    conn.execute("UPDATE settings SET value = ? WHERE key = 'discord_link'", (new_link,))
    conn.commit(); conn.close()
    return jsonify({'success': True})

@app.route('/create_payment', methods=['POST'])
def create_payment():
    current_user = session.get('user')
    if not current_user: return jsonify({'success': False, 'message': 'Unauthorized'})
    data = request.get_json(); plan_name = data.get('plan')
    amount = 150 if 'Starter' in plan_name else (350 if 'Professional' in plan_name else 700)
    pay_id = f"{int(time.time())}{random.randint(10,99)}"
    desc = f"Payment for {plan_name}"
    currency = "RUB"
    conn = get_db_connection()
    conn.execute("INSERT INTO pending_payments (pay_id, user_login, plan, amount) VALUES (?, ?, ?, ?)", (pay_id, current_user, plan_name, amount))
    conn.commit(); conn.close()
    sign_string = f"{ANYPAY_MERCHANT_ID}:{amount}:{pay_id}:{currency}:{desc}:{ANYPAY_SECRET_KEY_1}"
    sign = hashlib.md5(sign_string.encode('utf-8')).hexdigest()
    payment_url = f"https://anypay.io/merchant?merchant_id={ANYPAY_MERCHANT_ID}&amount={amount}&pay_id={pay_id}&currency={currency}&desc={desc}&sign={sign}"
    return jsonify({'success': True, 'payment_url': payment_url})

@app.route('/api/anypay_ipn', methods=['POST', 'GET'])
def payment_webhook():
    data = request.form if request.form else request.get_json()
    if not data: return "No Data", 400
    merchant_id = data.get('merchant_id', '')
    amount = data.get('amount', '')
    pay_id = data.get('pay_id', '')
    status = data.get('status', '')
    if status == 'paid' or 'SIM_' in pay_id:
        conn = get_db_connection()
        pending = conn.execute("SELECT * FROM pending_payments WHERE pay_id = ?", (pay_id,)).fetchone()
        if pending:
            user_login = pending['user_login']; bought_plan = pending['plan']; amount_db = pending['amount']
            days = 7 if 'Starter' in bought_plan else (30 if 'Professional' in bought_plan else 90)
            tz = pytz.timezone('Europe/Moscow')
            date_str = datetime.now(tz).strftime('%d.%m.%Y %H:%M')
            reward_data = json.dumps({"type": "plan", "value": bought_plan, "msg": "Thank you for your purchase via AnyPay!"})
            conn.execute("UPDATE users SET plan = ?, plan_days = ?, pending_reward = ? WHERE login = ?", (bought_plan, days, reward_data, user_login))
            conn.execute("DELETE FROM keys WHERE user_login = ?", (user_login,))
            conn.execute("INSERT INTO receipts (user_login, plan, amount, tx_id, date_str) VALUES (?, ?, ?, ?, ?)", (user_login, bought_plan, amount_db, pay_id, date_str))
            conn.execute("DELETE FROM pending_payments WHERE pay_id = ?", (pay_id,))
        conn.commit(); conn.close()
    return "OK", 200

@app.route('/api/get_receipts', methods=['GET'])
def get_receipts():
    current_user = session.get('user')
    if not current_user: return jsonify({'receipts': []})
    conn = get_db_connection()
    receipts = conn.execute("SELECT * FROM receipts WHERE user_login = ? ORDER BY id DESC", (current_user,)).fetchall()
    conn.close()
    return jsonify({'receipts': [dict(r) for r in receipts]})

@app.route('/restart_plan', methods=['POST'])
def restart_plan():
    current_user = session.get('user')
    if current_user:
        conn = get_db_connection()
        user = conn.execute("SELECT plan FROM users WHERE login = ?", (current_user,)).fetchone()
        if user:
            days = 7 if 'Starter' in user['plan'] else (30 if 'Professional' in user['plan'] else (90 if 'Extreme' in user['plan'] else 999))
            conn.execute("UPDATE users SET plan_days = ? WHERE login = ?", (days, current_user))
            conn.commit(); conn.close()
            return jsonify({'success': True, 'plan': user['plan'], 'days': days})
    return jsonify({'success': False})

@app.route('/delete_account', methods=['POST'])
def delete_account():
    current_user = session.get('user')
    if current_user:
        conn = get_db_connection()
        conn.execute("DELETE FROM users WHERE login = ?", (current_user,))
        conn.commit(); conn.close()
        session.pop('user', None)
    return jsonify({'success': True})

@app.route('/logout')
def logout(): 
    session.pop('user', None)
    return ('', 204)

if __name__ == '__main__':
    c_log('SERVICE', "Starting production server on port 5000...")
    app.run(debug=True)
