import os
import sqlite3
import random
import time
import smtplib
from email.mime.text import MIMEText
from flask import Flask, render_template_string, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pytz

# --- СИСТЕМА ЛОГИРОВАНИЯ КОНСОЛИ ---
LIVE_LOGS = []

def c_log(level, message):
    tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(tz)
    date_str = now.strftime('%d.%m.%Y | %H:%M')
    
    colors = {
        'INFO': '\033[97m',
        'SUCCESS': '\033[92m',
        'WARNING': '\033[93m',
        'ERROR': '\033[91m',
        'SERVICE': '\033[90m',
        'RESET': '\033[0m'
    }
    
    prefixes = {
        'INFO': 'INFORMATION',
        'SUCCESS': 'SUCCES',
        'WARNING': 'WARNING',
        'ERROR': 'ERROR',
        'SERVICE': 'SCRIPT SERVICE'
    }
    
    prefix = prefixes.get(level, 'LOG')
    color = colors.get(level, colors['RESET'])
    reset = colors['RESET']
    
    log_line = f"[ {prefix} - {date_str} ] = {message}"
    print(f"{color}{log_line}{reset}")
    
    LIVE_LOGS.append({'text': log_line, 'level': level.lower()})
    if len(LIVE_LOGS) > 50:
        LIVE_LOGS.pop(0)

# Инициализация Flask
c_log('SERVICE', "Initializing Flask application...")
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-dev-secret-key-123')

# --- НАСТРОЙКИ ПОЧТЫ ---
SMTP_EMAIL = "" 
SMTP_PASSWORD = ""

def send_real_email(to_email, code):
    c_log('SERVICE', f"Preparing to send 2FA code to {to_email}...")
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        c_log('ERROR', "SMTP Email/Password not configured. Cannot send real email.")
        return False 
    
    msg = MIMEText(f"Hello!\n\nYour Global Script's Hub 2FA verification code is: {code}\n\nThis code is valid for 15 minutes.")
    msg['Subject'] = 'Your 2FA Verification Code'
    msg['From'] = f"Global Script's <{SMTP_EMAIL}>"
    msg['To'] = to_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        c_log('SUCCESS', f"Email successfully sent to {to_email}.")
        return True
    except Exception as e:
        c_log('ERROR', f"SMTP Error: {e}")
        return False

# --- БАЗА ДАННЫХ (SQLITE3) ---
DB_NAME = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    c_log('SERVICE', "Connecting to SQLite3 database...")
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            secret TEXT,
            source TEXT,
            reg_date TEXT,
            plan TEXT DEFAULT 'Free Tier',
            plan_days INTEGER DEFAULT 0,
            dev_approved TEXT DEFAULT 'No'
        )
    ''')
    
    cursor = conn.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'is_frozen' not in columns:
        c_log('SERVICE', "Updating database schema: Adding 'is_frozen' column...")
        conn.execute("ALTER TABLE users ADD COLUMN is_frozen TEXT DEFAULT 'No'")

    # Таблица настроек
    conn.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance', 'No')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('discord_link', 'https://discord.gg/')")
    
    cursor = conn.execute("SELECT * FROM users WHERE login = 'Rob4ikDev'")
    if not cursor.fetchone():
        c_log('WARNING', "Admin 'Rob4ikDev' not found. Creating primary admin account...")
        tz = pytz.timezone('Europe/Moscow')
        reg_date = datetime.now(tz).strftime('%d.%m.%Y')
        conn.execute('''
            INSERT INTO users (login, password_hash, email, secret, source, reg_date, plan, plan_days, dev_approved, is_frozen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('Rob4ikDev', generate_password_hash('baconsecret6666'), '', 'globalscript', 'creator', reg_date, 'Developer Tier', 999, 'Yes', 'No'))
        c_log('SUCCESS', "Admin account 'Rob4ikDev' created successfully.")
    
    conn.commit()
    conn.close()
    c_log('SUCCESS', "Database loaded successfully.")

init_db()

# --- ПОЛНЫЙ HTML ШАБЛОН ---
TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Global Script's Hub</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg-color: #000000;
  --text-primary: #ffffff;
  --text-secondary: #888888;
  --card-bg: linear-gradient(135deg, rgba(30, 30, 32, 0.6), rgba(20, 20, 22, 0.4));
  --card-border: rgba(255, 255, 255, 0.08);
  --input-bg: rgba(255, 255, 255, 0.05);
  --input-border: rgba(255, 255, 255, 0.12);
  --accent: #ffffff;
  --accent-text: #000000;
  --error: #ea1515;
  --success: #34c759;
  --shadow-drop: 0 12px 30px rgba(0, 0, 0, 0.6);
  --shadow-inner: inset 0 1px 1px rgba(255, 255, 255, 0.1);
  --blur: blur(28px) saturate(180%);
  --dot-color: rgba(255, 255, 255, 0.3);
  --wave-1: rgba(255, 255, 255, 0.03);
  --wave-2: rgba(255, 255, 255, 0.015);
  --wave-3: rgba(255, 255, 255, 0.005);
}

[data-theme="light"] {
  --bg-color: #f5f5f7;
  --text-primary: #1d1d1f;
  --text-secondary: #86868b;
  --card-bg: linear-gradient(135deg, rgba(255, 255, 255, 0.7), rgba(255, 255, 255, 0.4));
  --card-border: rgba(0, 0, 0, 0.05);
  --input-bg: rgba(255, 255, 255, 0.6);
  --input-border: rgba(0, 0, 0, 0.08);
  --accent: #1d1d1f;
  --accent-text: #ffffff;
  --error: #ea1515;
  --success: #34c759;
  --shadow-drop: 0 12px 30px rgba(0, 0, 0, 0.08);
  --shadow-inner: inset 0 1px 1px rgba(255, 255, 255, 0.8);
  --dot-color: rgba(0, 0, 0, 0.2);
  --wave-1: rgba(0, 0, 0, 0.03);
  --wave-2: rgba(0, 0, 0, 0.015);
  --wave-3: rgba(0, 0, 0, 0.005);
}

* { box-sizing: border-box; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }

html, body { height: 100%; min-height: 100vh; margin: 0; padding: 0; }
body { 
  font-family: 'Inter', sans-serif; background-color: var(--bg-color); color: var(--text-primary); 
  transition: background-color 0.6s cubic-bezier(0.4, 0, 0.2, 1), color 0.6s ease; 
  overflow-x: hidden; overflow-y: auto; background-attachment: fixed;
  animation: globalFocus 1.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes globalFocus { 0% { filter: blur(20px); transform: scale(1.05); } 100% { filter: blur(0px); transform: scale(1); } }

.ambient-bg {
  position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: -3;
  background: radial-gradient(circle at 15% 30%, rgba(40, 40, 45, 0.4) 0%, transparent 50%),
              radial-gradient(circle at 85% 80%, rgba(30, 30, 35, 0.4) 0%, transparent 50%);
  filter: blur(40px); opacity: 0; animation: ambientFade 3s ease-in-out 0.5s forwards; pointer-events: none;
}
[data-theme="light"] .ambient-bg {
  background: radial-gradient(circle at 15% 30%, rgba(200, 200, 220, 0.4) 0%, transparent 50%),
              radial-gradient(circle at 85% 80%, rgba(180, 180, 200, 0.4) 0%, transparent 50%);
}
@keyframes ambientFade { to { opacity: 1; } }

#bgCanvas { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: -2; opacity: 0; animation: fadeInCanvas 2s ease-in-out forwards; pointer-events: none; }
.ocean { height: 30vh; width: 100%; position: fixed; bottom: 0; left: 0; z-index: -1; overflow: hidden; opacity: 0; animation: fadeInCanvas 3s ease-in-out 1s forwards; pointer-events: none; }
.wave { background: var(--wave-1); width: 200vw; height: 200vw; position: absolute; bottom: 0; left: 50%; margin-left: -100vw; margin-bottom: -195vw; border-radius: 46%; animation: drift 25s infinite linear; }
.wave:nth-of-type(2) { background: var(--wave-2); margin-bottom: -194vw; animation: drift 30s infinite linear; border-radius: 45%; }
.wave:nth-of-type(3) { background: var(--wave-3); margin-bottom: -196vw; animation: drift 35s infinite linear; border-radius: 44%; }
@keyframes drift { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes fadeInCanvas { to { opacity: 1; } }

.app-content { opacity: 0; display: flex; flex-direction: column; align-items: center; width: 100%; min-height: 100vh; padding: 100px 20px 40px 20px; animation: liquidReveal 1s cubic-bezier(0.16, 1, 0.3, 1) 0.2s forwards; }
@keyframes liquidReveal { 0% { opacity: 0; transform: translateY(20px) scale(0.99); } 100% { opacity: 1; transform: translateY(0) scale(1); } }
@keyframes elasticBounce { 0% { transform: scale(0.97) translateY(10px); opacity: 0; } 50% { transform: scale(1.01) translateY(-2px); opacity: 1; } 100% { transform: scale(1) translateY(0); opacity: 1; } }
@keyframes errorShake { 0%, 100% { transform: translateX(0); } 20%, 60% { transform: translateX(-6px); } 40%, 80% { transform: translateX(6px); } }
.shake-error { animation: errorShake 0.4s cubic-bezier(0.36, 0.07, 0.19, 0.97) forwards; }

.top-bar { position: fixed; top: 0; left: 0; width: 100vw; display: flex; justify-content: space-between; align-items: center; padding: 20px 40px; z-index: 100; background: transparent; }
.top-bar-left, .top-bar-right { display: flex; align-items: center; gap: 12px; }
.ui-pill { background: var(--card-bg); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur); border: 1px solid var(--card-border); box-shadow: var(--shadow-drop), var(--shadow-inner); color: var(--text-primary); padding: 8px 16px; border-radius: 98px; font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 10px; transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), background 0.3s ease; cursor: pointer; position: relative;}
.ui-pill:hover { transform: scale(1.05) translateY(-1px); }

/* ЯЗЫКОВОЕ МЕНЮ */
.lang-dropdown-wrapper { position: relative; }
.lang-menu { position: absolute; top: 120%; left: 0; background: var(--card-bg); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur); border: 1px solid var(--card-border); border-radius: 16px; padding: 8px; display: flex; flex-direction: column; gap: 4px; opacity: 0; pointer-events: none; transform: translateY(-10px); transition: all 0.3s ease; box-shadow: var(--shadow-drop); min-width: 120px; z-index: 1000;}
.lang-menu.show { opacity: 1; pointer-events: auto; transform: translateY(0); }
.lang-option { padding: 10px 12px; font-size: 13px; font-weight: 600; cursor: pointer; border-radius: 10px; transition: background 0.2s ease; display: flex; align-items: center; gap: 8px;}
.lang-option:hover { background: var(--input-bg); }

.recording-dot { width: 8px; height: 8px; background-color: var(--error); border-radius: 50%; animation: liquidBlink 2.5s infinite ease-in-out; }
@keyframes liquidBlink { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.8); } }
.theme-toggle { cursor: pointer; }
.logout-btn { cursor: pointer; color: var(--error); }
.logout-btn:hover { background: var(--error); color: #fff; border-color: var(--error); }

.header { display: flex; flex-direction: column; align-items: center; gap: 12px; margin-bottom: 24px; margin-top: auto; }
.header img { width: 72px; height: 72px; border-radius: 20px; box-shadow: var(--shadow-drop), var(--shadow-inner); border: 1px solid var(--card-border); transition: transform 0.5s cubic-bezier(0.34, 1.56, 0.64, 1); }
.header img:hover { transform: scale(1.1) rotate(4deg); }
.header h1 { margin: 0; font-size: 32px; font-weight: 700; letter-spacing: -0.04em; }

.form-container { margin: auto; display: flex; flex-direction: column; align-items: center; gap: 10px; background: var(--card-bg); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur); padding: 24px; border: 1px solid var(--card-border); border-radius: 28px; box-shadow: var(--shadow-drop), var(--shadow-inner); width: 100%; max-width: 360px; transition: all 0.4s ease; }
.form-header-text { margin: 0 0 6px 0; font-size: 14px; color: var(--text-primary); font-weight: 600; text-align: center; }
.form-container input[type="text"], .form-container input[type="password"] { width: 100%; padding: 12px 16px; font-size: 13px; font-family: inherit; font-weight: 500; color: var(--text-primary); background: var(--input-bg); border: 1px solid var(--input-border); border-radius: 14px; outline: none; transition: all 0.3s cubic-bezier(0.25, 1, 0.5, 1); }
.form-container input::placeholder { color: var(--text-secondary); }
.form-container input:focus { border-color: var(--text-primary); transform: scale(1.02); background: rgba(255, 255, 255, 0.08); }
.email-input::placeholder { color: rgba(136, 136, 136, 0.5) !important; }

.form-container button { width: 100%; padding: 12px; font-size: 14px; font-family: inherit; font-weight: 700; color: var(--accent-text); background: var(--accent); border: none; border-radius: 14px; cursor: pointer; transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1); margin-top: 4px; text-transform: uppercase; letter-spacing: 1px; }
.form-container button:not(:disabled):hover { transform: translateY(-2px) scale(1.02); box-shadow: 0 6px 15px rgba(255, 255, 255, 0.15); }
.form-container button:not(:disabled):active { transform: scale(0.95); }
.form-container button:disabled { opacity: 0.5; cursor: not-allowed; }

.checkbox-container { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--text-secondary); cursor: pointer; line-height: 1.4; margin-top: 4px; width: 100%; text-align: left; }
.checkbox-container input[type="checkbox"] { width: 16px; height: 16px; cursor: pointer; accent-color: var(--text-primary); margin: 0; flex-shrink: 0; }

.create-link-wrapper { max-height: 0; opacity: 0; overflow: hidden; transition: all 0.5s cubic-bezier(0.34, 1.56, 0.64, 1); width: 100%; text-align: center; }
.create-link-wrapper.show { max-height: 30px; opacity: 1; margin-top: 6px; }
.create-link, .back-link { color: var(--text-primary); opacity: 0.5; font-size: 12px; font-weight: 500; cursor: pointer; transition: opacity 0.3s ease; text-decoration: underline; }
.create-link:hover, .back-link:hover { opacity: 1; }
.back-link { display: block; text-align: center; margin-top: 8px; }

#message, #regMessage, #twoFaMessage, #secretMessage { font-weight: 600; font-size: 12px; text-align: center; min-height: 16px; opacity: 0; transition: opacity 0.4s ease, color 0.3s ease; margin-top: 4px; }
#message.show, #regMessage.show, #twoFaMessage.show, #secretMessage.show { opacity: 1; }
.success-msg { color: #34c759; }
.error-msg { color: var(--error); }

/* --- ЭКРАНЫ ЗАМОРОЗКИ И ВЫКЛЮЧЕННОГО САЙТА --- */
.fullscreen-overlay {
  position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 2000;
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  text-align: center; padding: 20px; overflow: hidden;
}
#freezeScreen {
  background: radial-gradient(circle at center, rgba(10, 191, 255, 0.1) 0%, var(--bg-color) 80%);
  backdrop-filter: blur(10px) contrast(1.1); -webkit-backdrop-filter: blur(10px) contrast(1.1);
}
#maintenanceScreen {
  background: radial-gradient(circle at center, rgba(255, 159, 10, 0.08) 0%, var(--bg-color) 80%),
              repeating-linear-gradient(45deg, rgba(255, 159, 10, 0.03), rgba(255, 159, 10, 0.03) 10px, transparent 10px, transparent 20px);
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
}
.bg-massive-icon {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  font-size: 280px; z-index: 1; user-select: none;
}
#freezeScreen .bg-massive-icon {
  opacity: 0.2; color: #0abfff; filter: drop-shadow(0 0 50px #0abfff); animation: spin 10s linear infinite;
}
#maintenanceScreen .bg-massive-icon {
  opacity: 0.15; color: #ff9f0a; filter: drop-shadow(0 0 40px #ff9f0a); animation: slowPulse 3s ease-in-out infinite; cursor: pointer;
}
.overlay-content-box {
  position: relative; z-index: 2; max-width: 650px; padding: 40px; border-radius: 36px;
  backdrop-filter: var(--blur); box-shadow: 0 20px 60px rgba(0,0,0,0.8);
}
.freeze-card {
  background: rgba(10, 191, 255, 0.05); border: 1px solid rgba(10, 191, 255, 0.3);
  box-shadow: inset 0 0 20px rgba(10, 191, 255, 0.1), 0 20px 60px rgba(0,0,0,0.8);
}
.maint-card {
  background: rgba(255, 159, 10, 0.05); border: 1px solid rgba(255, 159, 10, 0.4); border-top: 4px solid #ff9f0a;
  box-shadow: inset 0 0 20px rgba(255, 159, 10, 0.1), 0 20px 60px rgba(0,0,0,0.8);
}
.overlay-content-box h2 { margin: 0 0 16px 0; color: var(--text-primary); font-size: 28px; line-height: 1.3; font-weight: 700; letter-spacing: -0.02em; }
.overlay-content-box p { margin: 0; color: var(--text-secondary); font-size: 16px; line-height: 1.5; font-weight: 500; }
@keyframes slowPulse { 0%, 100% { transform: translate(-50%, -50%) scale(1); } 50% { transform: translate(-50%, -50%) scale(1.05); } }

/* ЛОАДЕР */
.loader-container { margin: auto; display: none; flex-direction: column; align-items: center; justify-content: center; gap: 16px; }
.infinity-loader { width: 80px; height: 40px; }
.infinity-path-bg { fill: none; stroke: rgba(255, 255, 255, 0.1); stroke-width: 3; stroke-linecap: round; }
.infinity-path-tail { fill: none; stroke: var(--accent); stroke-width: 3; stroke-linecap: round; stroke-dasharray: 20 80; stroke-dashoffset: 0; animation: dash 1s linear infinite; filter: drop-shadow(0 0 4px var(--accent)) drop-shadow(0 0 8px var(--accent)); }
[data-theme="light"] .infinity-path-bg { stroke: rgba(0, 0, 0, 0.1); }
@keyframes dash { to { stroke-dashoffset: -100; } }
.loader-text { font-size: 13px; font-weight: 600; color: var(--text-secondary); letter-spacing: 2px; }

/* КОМПАКТНЫЙ DASHBOARD */
.dashboard-layout { margin: auto; display: none; width: 100%; max-width: 1100px; gap: 20px; }
.sidebar { flex: 0 0 250px; background: var(--card-bg); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur); border: 1px solid var(--card-border); border-radius: 28px; padding: 20px; display: flex; flex-direction: column; box-shadow: var(--shadow-drop), var(--shadow-inner); }
.sidebar h2 { margin: 0 0 16px 0; font-size: 14px; text-transform: uppercase; color: var(--text-secondary); letter-spacing: 1px; }
.sidebar-nav { display: flex; flex-direction: column; gap: 6px; flex: 1; }
.sidebar-footer { display: flex; flex-direction: column; gap: 6px; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--card-border); }
.sidebar-btn { background: transparent; color: var(--text-primary); border: none; padding: 10px 14px; border-radius: 14px; font-family: inherit; cursor: pointer; text-align: left; transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); display: flex; flex-direction: column; gap: 2px; }
.sidebar-btn:hover { background: var(--input-border); transform: translateX(4px); }
.sidebar-btn.active { background: var(--text-primary); color: var(--bg-color); transform: scale(1.03); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
.sidebar-btn.active .btn-desc { color: var(--bg-color); opacity: 0.8; }
.sidebar-btn-footer { opacity: 0.5; }
.sidebar-btn-footer:hover { opacity: 1; }
.btn-title { font-weight: 600; font-size: 13px; text-transform: uppercase; }
.btn-desc { font-weight: 400; font-size: 11px; color: var(--text-secondary); line-height: 1.3; }

.main-content { flex: 1; display: flex; flex-direction: column; position: relative; }
.tab-content { display: none; flex-direction: column; gap: 16px; }
.tab-content.active { display: flex; animation: elasticBounce 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) forwards; }
.tab-content h2 { margin: 0; font-size: 26px; font-weight: 700; letter-spacing: -0.02em; }

.dashboard-card { background: var(--card-bg); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur); border: 1px solid var(--card-border); border-radius: 28px; padding: 26px; box-shadow: var(--shadow-drop), var(--shadow-inner); color: var(--text-secondary); font-size: 14px; line-height: 1.6; }

.plans-switch { display: flex; gap: 8px; background: var(--input-bg); padding: 6px; border-radius: 20px; border: 1px solid var(--input-border); margin-bottom: 10px; }
.plan-sub-btn { flex: 1; background: transparent; color: var(--text-secondary); border: none; padding: 12px; border-radius: 14px; font-weight: 600; cursor: pointer; transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); }
.plan-sub-btn:hover { transform: scale(1.02); }
.plan-sub-btn.active { background: var(--card-border); color: var(--text-primary); box-shadow: var(--shadow-drop); transform: scale(1.03); }

.plan-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
.plan-card { background: var(--input-bg); border: 1px solid var(--input-border); padding: 20px; border-radius: 20px; display: flex; flex-direction: column; gap: 10px; transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); }
.plan-card:hover { transform: scale(1.03) translateY(-4px); }
.plan-card h4 { margin: 0; font-size: 17px; color: var(--text-primary); }
.plan-card .price { font-size: 12px; color: var(--accent); font-weight: 700; }
.plan-card p { font-size: 12px; margin: 0; flex: 1; }

.profile-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 12px; }
.profile-item { background: var(--input-bg); border: 1px solid var(--input-border); padding: 14px; border-radius: 14px; display: flex; flex-direction: column; gap: 4px; }
.profile-label { font-size: 11px; text-transform: uppercase; color: var(--text-secondary); letter-spacing: 1px; }
.profile-value { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.dev-approved-badge { color: var(--success); opacity: 0.5; font-weight: 700; }

.action-btn { background: var(--input-bg); color: var(--text-primary); border: 1px solid var(--input-border); padding: 12px 18px; border-radius: 14px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); }
.action-btn:hover { background: var(--card-border); transform: scale(1.03) translateY(-2px); box-shadow: 0 6px 15px rgba(0,0,0,0.2); }
.action-btn:active { transform: scale(0.97); }
.danger-btn { color: var(--error); }
.danger-btn:hover { background: rgba(234, 21, 21, 0.1); border-color: var(--error); }
.support-btn { opacity: 0.5; }
.support-btn:hover { opacity: 1; }

/* АДМИН ПАНЕЛЬ */
.dev-header { color: var(--success); font-weight: 700; margin-bottom: 12px; font-size: 18px; }
.dev-table-wrapper { width: 100%; overflow-x: auto; margin-top: 12px; border-radius: 14px; border: 1px solid var(--card-border); }
.dev-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; color: var(--text-primary); background: rgba(20,20,20,0.4); }
.dev-table th, .dev-table td { padding: 10px 14px; border-bottom: 1px solid var(--card-border); }
.dev-table th { background: var(--input-bg); color: var(--text-secondary); text-transform: uppercase; font-size: 10px; letter-spacing: 1px; }
.dev-select { background: var(--bg-color); color: var(--text-primary); border: 1px solid var(--card-border); padding: 6px 10px; border-radius: 10px; outline: none; font-family: inherit; font-size: 12px; }
.dev-btn-sm { padding: 6px 10px; font-size: 11px; border-radius: 8px; background: var(--input-bg); color: var(--text-primary); border: 1px solid var(--card-border); cursor: pointer; transition: all 0.2s ease; }
.dev-btn-sm:hover { background: var(--text-primary); color: var(--bg-color); }
.dev-btn-danger { border-color: var(--error); color: var(--error); }
.dev-btn-danger:hover { background: var(--error); color: #fff; }
.dev-btn-freeze { border-color: #0abfff; color: #0abfff; }
.dev-btn-freeze:hover { background: #0abfff; color: #fff; }

.web-console { background: #050505; border: 1px solid #222; border-radius: 14px; padding: 14px; font-family: 'Courier New', monospace; font-size: 12px; max-height: 220px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; box-shadow: inset 0 0 10px rgba(0,0,0,0.8); }
.web-log-line { line-height: 1.4; white-space: pre-wrap; word-break: break-all; }
.web-log-info { color: #ffffff; }
.web-log-success { color: #34c759; }
.web-log-warning { color: #ff9f0a; }
.web-log-error { color: #ff453a; }
.web-log-service { color: #8e8e93; }

/* ОБНОВЛЕННАЯ ВКЛАДКА SCRIPTS */
.script-card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 24px; overflow: hidden; display: flex; flex-direction: column; transition: transform 0.3s ease; }
.script-card:hover { transform: scale(1.01); }
.script-banner { width: 100%; height: 120px; background: url('https://static.wikia.nocookie.net/muscle-legends/images/5/50/Wiki-background/revision/latest/scale-to-width-down/670?cb=20210320061506') no-repeat center center, var(--input-bg); background-size: cover; position: relative; display: flex; justify-content: center; padding-top: 15px; }
.script-banner::after { content: ''; position: absolute; bottom: -1px; left: 0; width: 100%; height: 60px; background: linear-gradient(to bottom, transparent, var(--bg-color)); opacity: 0.85; }
.banner-title { position: relative; z-index: 2; color: #ffffff; font-size: 18px; font-weight: 800; letter-spacing: 4px; text-transform: uppercase; text-shadow: 0 4px 12px rgba(0,0,0,1); }
.script-content { padding: 0 20px 20px 20px; position: relative; z-index: 2; display: flex; flex-direction: column; gap: 8px; }
.script-header h3 { margin: 0; font-size: 18px; color: var(--text-primary); display: flex; align-items: center; gap: 10px; }
.game-tag { font-size: 12px; font-weight: 500; opacity: 0.5; }
.script-desc { margin: 0; font-size: 13px; color: var(--text-secondary); line-height: 1.5; }
.script-stats { display: flex; gap: 8px; margin-top: 2px; }
.stat-item { display: flex; align-items: center; gap: 4px; font-size: 12px; font-weight: 600; color: var(--text-secondary); background: var(--input-bg); padding: 6px 10px; border-radius: 10px; border: 1px solid var(--input-border); }
.copy-btn { background: var(--accent); color: var(--accent-text); border: none; padding: 12px; border-radius: 14px; font-weight: 700; font-family: 'Inter', monospace; cursor: pointer; text-transform: uppercase; font-size: 13px; transition: all 0.3s ease; }
.copy-btn:hover { transform: scale(1.02); }

/* CUSTOM MODALS */
.modal-overlay { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0, 0, 0, 0.4); backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px); z-index: 10000; display: flex; justify-content: center; align-items: center; opacity: 0; pointer-events: none; transition: opacity 0.4s cubic-bezier(0.34, 1.56, 0.64, 1); }
.modal-overlay.active { opacity: 1; pointer-events: auto; }
.custom-modal { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 28px; padding: 28px; width: 90%; max-width: 360px; text-align: center; box-shadow: var(--shadow-drop), var(--shadow-inner); transform: scale(0.9) translateY(20px); transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1); }
.modal-overlay.active .custom-modal { transform: scale(1) translateY(0); }
.custom-modal h3 { margin: 0 0 10px 0; font-size: 20px; color: var(--text-primary); }
.custom-modal p { margin: 0 0 20px 0; font-size: 13px; color: var(--text-secondary); line-height: 1.5; }
.modal-btns { display: flex; gap: 10px; justify-content: center; }
.modal-btn { flex: 1; padding: 12px; border: none; border-radius: 14px; font-weight: 600; cursor: pointer; font-family: inherit; font-size: 13px; transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); }
.modal-btn-cancel { background: var(--input-bg); color: var(--text-primary); border: 1px solid var(--input-border); }
.modal-btn-cancel:hover { background: var(--card-border); }
.modal-btn-confirm { background: var(--accent); color: var(--accent-text); }
.modal-btn-confirm:hover { transform: scale(1.05); box-shadow: 0 8px 20px rgba(255,255,255,0.2); }
.modal-btn-danger { background: var(--error); color: #fff; }
.modal-btn-danger:hover { transform: scale(1.05); box-shadow: 0 8px 20px rgba(234, 21, 21, 0.3); }

/* DISCORD CARD STYLING */
.discord-card { display: flex; flex-direction: column; align-items: center; text-align: center; gap: 16px; padding: 40px; }
.discord-btn { width: 100%; max-width: 250px; padding: 14px; background: #5865F2; color: #fff; border: none; border-radius: 16px; font-size: 14px; font-weight: 700; cursor: pointer; text-transform: uppercase; letter-spacing: 1px; transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); text-decoration: none;}
.discord-btn:hover { transform: scale(1.05) translateY(-2px); box-shadow: 0 8px 20px rgba(88, 101, 242, 0.4); }

@media (max-width: 900px) {
  .top-bar { padding: 16px 20px; } .dashboard-layout { flex-direction: column; width: 100%; padding: 0; }
  .sidebar { flex: none; width: 100%; padding: 16px; border-radius: 24px; } .sidebar h2 { display: none; }
  .sidebar-nav, .sidebar-footer { flex-direction: row; overflow-x: auto; border-top: none; margin-top: 0; padding-top: 0; }
  .btn-desc { display: none; } .sidebar-btn { padding: 10px 16px; align-items: center; justify-content: center; white-space: nowrap;}
  .dashboard-card { padding: 24px; border-radius: 24px; } .profile-grid { grid-template-columns: 1fr; }
}
</style>
</head>
<body>

  <!-- Глубокий атмосферный фон -->
  <div class="ambient-bg"></div>

  <canvas id="bgCanvas"></canvas>
  <div class="ocean"><div class="wave"></div><div class="wave"></div><div class="wave"></div></div>

  <!-- Custom Confirm Modal -->
  <div class="modal-overlay" id="customModalOverlay">
    <div class="custom-modal">
      <h3 id="modalTitle">Title</h3>
      <p id="modalMessage">Message</p>
      <div class="modal-btns">
        <button class="modal-btn modal-btn-cancel" id="modalCancelBtn" data-i18n="m_cancel">Cancel</button>
        <button class="modal-btn modal-btn-confirm" id="modalConfirmBtn" data-i18n="m_confirm">Confirm</button>
      </div>
    </div>
  </div>

  <!-- ЭКРАН ЗАМОРОЗКИ -->
  <div class="fullscreen-overlay" id="freezeScreen" style="display:none;">
      <div class="bg-massive-icon">❄️</div>
      <div class="overlay-content-box freeze-card">
          <h2 data-i18n="fr_tit">Your account has been frozen by the Developer</h2>
          <p data-i18n="fr_desc">Contact the Developer to resolve the issue, or request an unban.</p>
      </div>
  </div>

  <!-- ЭКРАН ТЕХ. РАБОТ -->
  <div class="fullscreen-overlay" id="maintenanceScreen" style="display:none;">
      <div class="bg-massive-icon" id="maintenanceLockIcon">🔒</div>
      <div class="overlay-content-box maint-card">
          <h2 data-i18n="mn_tit">The site is temporarily closed for maintenance.</h2>
          <p data-i18n="mn_desc">Please try visiting this site at another time!</p>
      </div>
  </div>

  <div class="top-bar">
    <div class="top-bar-left">
      <!-- Выбор языка -->
      <div class="lang-dropdown-wrapper">
         <div class="ui-pill" id="langBtn" onclick="toggleLangMenu()"><span id="langBtnText">🌎 EN</span></div>
         <div class="lang-menu" id="langMenu">
            <div class="lang-option" onclick="setLang('en')">🇺🇸 EN (English)</div>
            <div class="lang-option" onclick="setLang('ru')">🇷🇺 RU (Русский)</div>
            <div class="lang-option" onclick="setLang('ja')">🇯🇵 JA (日本語)</div>
            <div class="lang-option" onclick="setLang('pt')">🇧🇷 PT (Português)</div>
         </div>
      </div>
      
      <div class="ui-pill" id="clockWrapper" style="{{ 'display:none;' if not current_user else 'display:flex;' }}"><div class="recording-dot"></div><span id="clock">00:00:00</span></div>
      <button class="ui-pill theme-toggle" id="themeBtn" data-i18n="theme_btn">Light Mode</button>
    </div>
    <div class="top-bar-right" id="userWrapper" style="{{ 'display:none;' if not current_user else 'display:flex;' }}">
      <div class="ui-pill" id="userDisplay" title="Click to open Profile">{{ current_user or '' }}</div>
      <button class="ui-pill logout-btn" id="logoutBtn" data-i18n="logout">Logout</button>
    </div>
  </div>

  <div class="app-content" id="appMainWrapper">
    <div class="header" id="mainHeader">
      <img src="https://raw.githubusercontent.com/Rob4ik02/RobloxScripts/refs/heads/main/icon.png" alt="" />
      <h1>Global Script's</h1>
    </div>

    <!-- Форма Логина -->
    <div class="form-container" id="authForm" style="{{ 'display:none;' if current_user else 'display:flex;' }}">
      <input type="text" id="login" data-i18n-ph="login_ph" placeholder="Login" autocomplete="off" />
      <input type="password" id="password" data-i18n-ph="pass_ph" placeholder="Password" />
      <button id="signUpBtn" data-i18n="auth_btn">AUTHORIZE</button>
      <div id="message"></div>
      <div class="create-link-wrapper" id="createAccountWrapper">
        <div class="create-link" id="createAccountLink" data-i18n="no_acc">Don't have an account? Create it!</div>
      </div>
    </div>

    <!-- Форма Секрета (Разработчик) -->
    <div class="form-container" id="secretForm" style="display:none;">
      <p class="form-header-text" data-i18n="dev_auth">Developer Authentication</p>
      <p style="font-size: 12px; color: var(--text-secondary); text-align: center; margin-top: 0;" data-i18n="dev_desc">Enter the secret codename to verify admin privileges.</p>
      <input type="password" id="devSecretCode" data-i18n-ph="secret_ph" placeholder="Secret Word" autocomplete="off" />
      <button id="verifySecretBtn" data-i18n="unlock_btn">UNLOCK MAINFRAME</button>
      <div id="secretMessage"></div>
      <div class="back-link" id="cancelSecretLink" data-i18n="cancel">Cancel</div>
    </div>

    <!-- Форма 2FA -->
    <div class="form-container" id="twoFaForm" style="display:none;">
      <p class="form-header-text" data-i18n="bot_prot">Bot Protection</p>
      <p style="font-size: 12px; color: var(--text-secondary); text-align: center; margin-top: 0;" data-i18n="bot_desc">We sent a 6-digit code to your email. Valid for 15 minutes.</p>
      <input type="text" id="twoFaCode" data-i18n-ph="code_ph" placeholder="Enter Code" autocomplete="off" />
      <button id="verifyBtn" data-i18n="verify_btn">VERIFY</button>
      <div id="twoFaMessage"></div>
      <div class="back-link" id="cancel2FaLink" data-i18n="cancel">Cancel</div>
    </div>

    <!-- Форма Регистрации -->
    <div class="form-container" id="regForm" style="display:none;">
      <p class="form-header-text" data-i18n="reg_desc">Describe yourself for the account.</p>
      <input type="text" id="regLogin" data-i18n-ph="login_ph" placeholder="Login" autocomplete="off" />
      <input type="password" id="regPassword" data-i18n-ph="pass_ph" placeholder="Password" />
      <input type="text" id="regEmail" class="email-input" data-i18n-ph="email_ph" placeholder="Enter your email to protect against bots (Optional)" autocomplete="off" />
      <input type="password" id="regSecret" data-i18n-ph="reg_sec_ph" placeholder="Secret word if you forgot password" autocomplete="off" />
      <input type="text" id="regSource" data-i18n-ph="reg_src_ph" placeholder="How did you hear about us?" autocomplete="off" />
      <label class="checkbox-container"><input type="checkbox" id="regAgree"><span data-i18n="agree">I agree to the privacy cookies and am ready to create an account</span></label>
      <button id="regBtn" disabled data-i18n="create_btn">CREATE ACCOUNT</button>
      <div id="regMessage"></div>
      <div class="back-link" id="backToLoginLink" data-i18n="back_login">Back to Login</div>
    </div>

    <div class="loader-container" id="loaderScreen">
      <svg class="infinity-loader" viewBox="0 0 100 50">
          <path class="infinity-path-bg" pathLength="100" d="M50,25 C30,5 10,5 10,25 C10,45 30,45 50,25 C70,5 90,5 90,25 C90,45 70,45 50,25 Z" />
          <path class="infinity-path-tail" pathLength="100" d="M50,25 C30,5 10,5 10,25 C10,45 30,45 50,25 C70,5 90,5 90,25 C90,45 70,45 50,25 Z" />
      </svg>
      <div class="loader-text" id="loaderDynamicText" data-i18n="loading">Authenticating System...</div>
    </div>

    <div class="dashboard-layout" id="dashboardLayout">
      <div class="sidebar">
        <h2 data-i18n="menu">MENU</h2>
        <div class="sidebar-nav">
          <button class="sidebar-btn active" data-target="tab-main"><div class="btn-title" data-i18n="m_main">MAIN</div><div class="btn-desc" data-i18n="m_main_d">Your main profile - it's you.</div></button>
          <button class="sidebar-btn" data-target="tab-keys"><div class="btn-title" data-i18n="m_key">KEY SYSTEM</div><div class="btn-desc" data-i18n="m_key_d">Get a key to unlock free access.</div></button>
          <button class="sidebar-btn" data-target="tab-scripts"><div class="btn-title" data-i18n="m_scr">SCRIPTS</div><div class="btn-desc" data-i18n="m_scr_d">Current game scripts.</div></button>
          <button class="sidebar-btn" data-target="tab-plans"><div class="btn-title" data-i18n="m_plan">PLANS</div><div class="btn-desc" data-i18n="m_plan_d">Buy plans to get more functional abilities!</div></button>
          <button class="sidebar-btn" data-target="tab-faq"><div class="btn-title" data-i18n="m_faq">FAQ</div><div class="btn-desc" data-i18n="m_faq_d">Got questions? We answer fast!</div></button>
        </div>
        <div class="sidebar-footer">
          <button class="sidebar-btn sidebar-btn-footer" data-target="tab-developers"><div class="btn-title" data-i18n="m_dev">DEVELOPERS</div><div class="btn-desc" data-i18n="m_dev_d">Website and script creators.</div></button>
          <button class="sidebar-btn sidebar-btn-footer" data-target="tab-discord"><div class="btn-title" data-i18n="m_disc">DISCORD</div><div class="btn-desc" data-i18n="m_disc_d">We're also in chat!</div></button>
        </div>
      </div>
      
      <div class="main-content">
        <div class="tab-content active" id="tab-main">
          <h2 data-i18n="u_prof">User Profile</h2>
          <div class="dashboard-card">
            <p style="color: var(--text-primary); font-weight: 600; font-size: 16px; margin-bottom: 4px;" data-i18n="acc_det">Account Details</p>
            <p style="margin-top: 0; font-size: 14px;" data-i18n="acc_det_d">Here is your personal overview registered in the system.</p>
            <div class="profile-grid">
              <div class="profile-item"><span class="profile-label" data-i18n="l_login">LOGIN</span><span class="profile-value" id="profileLogin">--</span></div>
              <div class="profile-item"><span class="profile-label" data-i18n="l_plan">CURRENT PLAN</span><span class="profile-value" id="profilePlan">--</span></div>
              <div class="profile-item"><span class="profile-label" data-i18n="l_reg">REGISTRATION DATE</span><span class="profile-value" id="profileRegDate">--</span></div>
              <div class="profile-item"><span class="profile-label" data-i18n="l_dev">DEVELOPER APPROVED</span><span class="profile-value dev-approved-badge" id="profileDevApproved">--</span></div>
            </div>
          </div>
        </div>

        <div class="tab-content" id="tab-keys">
          <h2 data-i18n="k_gen">Key Generator</h2>
          <div class="dashboard-card">
            <p style="color: var(--text-primary); font-weight: 600; font-size: 16px; margin-bottom: 8px;" data-i18n="k_unl">Unlock Free Access</p>
            <p data-i18n="k_desc">Create unique HWID keys for your Roblox scripts.</p>
            <button class="action-btn" style="margin-top: 10px;" data-i18n="k_btn">Generate New Key</button>
          </div>
        </div>

        <div class="tab-content" id="tab-scripts">
          <h2 data-i18n="s_lib">Scripts Library</h2>
          <div class="script-card">
            <div class="script-banner"><div class="banner-title">MUSCLE LEGENDS</div></div>
            <div class="script-content">
              <div class="script-header"><h3>Oxygen Hub Script <span class="game-tag">for game: Muscle Legends</span></h3></div>
              <p class="script-desc" data-i18n="s_good">Good script, works in beta version. There are some bugs or errors. They say it will be updated and will be the best script.</p>
              <div class="script-stats">
                <div class="stat-item">👍 0</div><div class="stat-item">👎 0</div><div class="stat-item">⭐ Unrated</div>
              </div>
              <button class="copy-btn" onclick="copyLuaScript(this)" data-i18n="s_copy">CLICK TO COPY LUA SCRIPT</button>
            </div>
          </div>
        </div>

        <div class="tab-content" id="tab-plans">
          <h2 data-i18n="p_upg">Upgrade Plans</h2>
          <div class="plans-switch">
            <button class="plan-sub-btn active" id="btnBuyPlan" onclick="switchPlanSubTab('buy')" data-i18n="p_buy">Buy Plan</button>
            <button class="plan-sub-btn" id="btnMyPlan" onclick="switchPlanSubTab('my')" data-i18n="p_my">My Current Plan</button>
          </div>
          <div id="planBuySection">
            <div class="plan-grid">
              <div class="plan-card"><h4 data-i18n="p_start">Starter Plan</h4><div class="price">7 Days</div><p data-i18n="p_start_d">Little access, but works perfectly for beginners.</p><button class="action-btn" data-i18n="p_purch">Purchase</button></div>
              <div class="plan-card"><h4 data-i18n="p_pro">Professional Plan</h4><div class="price">30 Days</div><p data-i18n="p_pro_d">More access, developer contact, and advanced features.</p><button class="action-btn" data-i18n="p_purch">Purchase</button></div>
              <div class="plan-card"><h4 data-i18n="p_ext">Extreme Plan</h4><div class="price">90 Days</div><p data-i18n="p_ext_d">All access, 24/7 support. You have everything.</p><button class="action-btn" data-i18n="p_purch">Purchase</button></div>
            </div>
          </div>
          <div id="planMySection" style="display: none;">
             <div class="dashboard-card" style="display: flex; flex-direction: column; gap: 12px;">
               <h3 id="planGreeting" style="margin: 0; color: var(--text-primary); font-size: 20px;">Hi!</h3>
               <p id="planCurrentStatus" style="margin:0; font-weight: 600; color: var(--accent);">Your current plan: --</p>
               <p id="planDesc" style="margin:0;" data-i18n="p_desc">All basic features unlocked.</p>
               <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px;">
                  <button class="action-btn" onclick="requestRestartPlan()" data-i18n="p_rest">Restart Plan</button>
                  <button class="action-btn danger-btn" onclick="requestDeleteAccount()" data-i18n="p_del">Delete Account</button>
                  <button class="action-btn support-btn" id="supportBtn" onclick="contactSupport()" data-i18n="p_sup">Contact Support</button>
               </div>
             </div>
          </div>
        </div>
        
        <div class="tab-content" id="tab-faq"><h2 data-i18n="f_tit">FAQ</h2><div class="dashboard-card"><p data-i18n="f_desc">Got questions? We answer fast!</p></div></div>
        
        <!-- Вкладка Developers -->
        <div class="tab-content" id="tab-developers">
          <h2 data-i18n="d_tit">Developers</h2>
          <div class="dashboard-card" id="devUserView">
            <p data-i18n="d_desc">Meet the team behind Global Script's. We build the architecture, you enjoy the results.</p>
          </div>
          
          <div id="devAdminView" style="display: none; flex-direction: column; gap: 20px;">
             <div class="dashboard-card">
                <h3 id="devGreeting" class="dev-header">Welcome, Developer!</h3>
                <p style="margin: 0;">Mainframe core management modules activated.</p>
             </div>
             <div class="dashboard-card">
                <h4 style="margin: 0 0 10px 0; color: var(--text-primary);">Account Management</h4>
                <div class="dev-table-wrapper">
                   <table class="dev-table">
                      <thead><tr><th>User</th><th>Current Plan</th><th>Days</th><th>Change Plan</th><th>Actions</th></tr></thead>
                      <tbody id="devUsersTableBody"></tbody>
                   </table>
                </div>
             </div>
             <div class="dashboard-card">
                <h4 style="margin: 0 0 10px 0; color: var(--text-primary);">Site Infrastructure</h4>
                <p style="margin-top:0; font-size: 13px;">Database and backend core controls.</p>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                   <button class="dev-btn-sm" id="btnToggleMaintenance" onclick="adminToggleMaintenance()"></button>
                   <button class="dev-btn-sm" onclick="showConfirm('Flush Cache', 'Are you sure you want to flush all system caches?', 'Flush', false, () => { showConfirm('Success', 'All caches purged successfully!', 'OK', false, null, true) })">Flush Cache</button>
                </div>
             </div>
             
             <!-- Интеграция Discord -->
             <div class="dashboard-card">
                <h4 style="margin: 0 0 10px 0; color: var(--text-primary);">Discord Integration</h4>
                <p style="margin-top:0; font-size: 13px; color: var(--text-secondary);">Update the active Discord server invite link.</p>
                <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                   <input type="text" id="devDiscordLink" value="{{ discord_link }}" class="dev-select" style="flex: 1; min-width: 200px; padding: 10px;" placeholder="https://discord.gg/..." />
                   <button class="dev-btn-sm" onclick="adminUpdateDiscordLink()">Save Link</button>
                </div>
             </div>

             <div class="dashboard-card">
                <h4 style="margin: 0 0 10px 0; color: var(--text-primary);">Live System Console</h4>
                <p style="margin-top:0; font-size: 13px; color: var(--text-secondary);">Real-time mainframe diagnostic event stream logs.</p>
                <div class="web-console" id="webConsoleBox"></div>
             </div>
          </div>
        </div>
        
        <!-- НОВАЯ ВКЛАДКА DISCORD -->
        <div class="tab-content" id="tab-discord">
          <h2 data-i18n="c_tit">Community</h2>
          <div class="dashboard-card discord-card">
            <svg width="64" height="64" viewBox="0 0 127.14 96.36" fill="#5865F2">
              <path d="M107.7,8.07A105.15,105.15,0,0,0,81.47,0a72.06,72.06,0,0,0-3.36,6.83A97.68,97.68,0,0,0,49,6.83,72.37,72.37,0,0,0,45.64,0,105.89,105.89,0,0,0,19.39,8.09C2.79,32.65-1.71,56.6.54,80.21h0A105.73,105.73,0,0,0,32.71,96.36,77.7,77.7,0,0,0,39.6,85.25a68.42,68.42,0,0,1-10.85-5.18c.91-.66,1.8-1.34,2.66-2a75.57,75.57,0,0,0,64.32,0c.87.71,1.76,1.39,2.66,2a68.68,68.68,0,0,1-10.87,5.19,77,77,0,0,0,6.89,11.1A105.25,105.25,0,0,0,126.6,80.22h0C129.24,52.84,122.09,29.11,107.7,8.07ZM42.45,65.69C36.18,65.69,31,60,31,53s5-12.74,11.43-12.74S54,46,53.89,53,48.84,65.69,42.45,65.69Zm42.24,0C78.41,65.69,73.31,60,73.31,53s5-12.74,11.43-12.74S96.2,46,96.09,53,91.08,65.69,84.69,65.69Z"/>
            </svg>
            <h3 style="margin: 0; font-size: 24px; color: var(--text-primary);" data-i18n="disc_club">Global Scripts Club</h3>
            <p style="margin: 0; font-size: 14px; line-height: 1.6; max-width: 400px; color: var(--text-secondary); opacity: 0.5;" data-i18n="disc_desc">Мы обсуждаем, мы создаем, мы рассчитываем. Вступи чтобы следить за обновлениями и общаться с другими людьми!</p>
            <a href="{{ discord_link }}" id="discordJoinBtn" target="_blank" class="discord-btn" data-i18n="disc_join">Зайти в клуб</a>
          </div>
        </div>
      </div>
    </div>
  </div>

<script>
  // --- ТРАНСЛЯЦИЯ ЯЗЫКОВ (i18n) ---
  const i18n = {
    en: {
      theme_btn: "Light Mode", logout: "Logout", auth_btn: "AUTHORIZE", no_acc: "Don't have an account? Create it!",
      dev_auth: "Developer Authentication", dev_desc: "Enter the secret codename to verify admin privileges.",
      unlock_btn: "UNLOCK MAINFRAME", cancel: "Cancel", bot_prot: "Bot Protection",
      bot_desc: "We sent a 6-digit code to your email. Valid for 15 minutes.", verify_btn: "VERIFY",
      reg_desc: "Describe yourself for the account.", agree: "I agree to the privacy cookies and am ready to create an account",
      create_btn: "CREATE ACCOUNT", back_login: "Back to Login", loading: "Authenticating System...",
      menu: "MENU", m_main: "MAIN", m_main_d: "Your main profile - it's you.",
      m_key: "KEY SYSTEM", m_key_d: "Get a key to unlock free access.", m_scr: "SCRIPTS", m_scr_d: "Current game scripts.",
      m_plan: "PLANS", m_plan_d: "Buy plans to get more functional abilities!", m_faq: "FAQ", m_faq_d: "Got questions? We answer fast!",
      m_dev: "DEVELOPERS", m_dev_d: "Website and script creators.", m_disc: "DISCORD", m_disc_d: "We're also in chat!",
      u_prof: "User Profile", acc_det: "Account Details", acc_det_d: "Here is your personal overview registered in the system.",
      l_login: "LOGIN", l_plan: "CURRENT PLAN", l_reg: "REGISTRATION DATE", l_dev: "DEVELOPER APPROVED",
      k_gen: "Key Generator", k_unl: "Unlock Free Access", k_desc: "Create unique HWID keys for your Roblox scripts.", k_btn: "Generate New Key",
      s_lib: "Scripts Library", s_good: "Good script, works in beta version. There are some bugs or errors. They say it will be updated.",
      s_copy: "CLICK TO COPY LUA SCRIPT", p_upg: "Upgrade Plans", p_buy: "Buy Plan", p_my: "My Current Plan",
      p_start: "Starter Plan", p_start_d: "Little access, but works perfectly for beginners.",
      p_pro: "Professional Plan", p_pro_d: "More access, developer contact, and advanced features.",
      p_ext: "Extreme Plan", p_ext_d: "All access, 24/7 support. You have everything.", p_purch: "Purchase",
      p_desc: "All basic features unlocked.", p_rest: "Restart Plan", p_del: "Delete Account", p_sup: "Contact Support",
      f_tit: "FAQ", f_desc: "Got questions? We answer fast!", d_tit: "Developers", d_desc: "Meet the team behind Global Script's. We build the architecture, you enjoy the results.",
      c_tit: "Community", c_desc: "Join our Discord server.",
      fr_tit: "Your account has been frozen by the Developer", fr_desc: "Contact the Developer to resolve the issue, or request an unban.",
      mn_tit: "The site is temporarily closed, or offline for maintenance.", mn_desc: "Please try visiting this site at another time!",
      login_ph: "Login", pass_ph: "Password", secret_ph: "Secret Word", code_ph: "Enter Code", email_ph: "Enter your email to protect against bots (Optional)",
      reg_sec_ph: "Secret word if you forgot password", reg_src_ph: "How did you hear about us?",
      m_cancel: "Cancel", m_confirm: "Confirm",
      disc_club: "Global Scripts Club", disc_desc: "We discuss, we create, we calculate. Join to follow updates and chat with other people!", disc_join: "Join the Club"
    },
    ru: {
      theme_btn: "Светлая тема", logout: "Выйти", auth_btn: "АВТОРИЗАЦИЯ", no_acc: "Нет аккаунта? Создайте!",
      dev_auth: "Проверка Разработчика", dev_desc: "Введите кодовое слово для доступа.",
      unlock_btn: "РАЗБЛОКИРОВАТЬ", cancel: "Отмена", bot_prot: "Защита от ботов",
      bot_desc: "Мы отправили 6-значный код на вашу почту. Действует 15 минут.", verify_btn: "ПОДТВЕРДИТЬ",
      reg_desc: "Опишите себя для создания аккаунта.", agree: "Я соглашаюсь с куки конфиденциальности и готов создать аккаунт",
      create_btn: "СОЗДАТЬ АККАУНТ", back_login: "Назад ко входу", loading: "Авторизация системы...",
      menu: "МЕНЮ", m_main: "ГЛАВНАЯ", m_main_d: "Ваш основной профиль - это вы.",
      m_key: "СИСТЕМА КЛЮЧЕЙ", m_key_d: "Получите ключ для бесплатного доступа.", m_scr: "СКРИПТЫ", m_scr_d: "Текущие игровые скрипты.",
      m_plan: "ПЛАНЫ", m_plan_d: "Купите планы для новых возможностей!", m_faq: "FAQ", m_faq_d: "Нашлись вопросы? Ответим быстро!",
      m_dev: "РАЗРАБОТЧИКИ", m_dev_d: "Создатели сайта и скриптов.", m_disc: "DISCORD", m_disc_d: "Мы также есть в чате!",
      u_prof: "Профиль", acc_det: "Детали Аккаунта", acc_det_d: "Ваша личная информация в системе.",
      l_login: "ЛОГИН", l_plan: "ТЕКУЩИЙ ПЛАН", l_reg: "ДАТА РЕГИСТРАЦИИ", l_dev: "ОДОБРЕН РАЗРАБОТЧИКОМ",
      k_gen: "Генератор Ключей", k_unl: "Разблокировать Доступ", k_desc: "Создайте уникальные HWID ключи для Roblox.", k_btn: "Сгенерировать Ключ",
      s_lib: "Библиотека Скриптов", s_good: "Хороший скрипт, работает в бета версии. Есть ошибки. Говорят, обновят и будет лучшим.",
      s_copy: "НАЖМИТЕ ДЛЯ КОПИРОВАНИЯ LUA", p_upg: "Планы Улучшений", p_buy: "Купить План", p_my: "Мой План",
      p_start: "Начальный План", p_start_d: "Мало доступа, но отлично работает для новичков.",
      p_pro: "Про-План", p_pro_d: "Больше доступа, связь с разработчиками.",
      p_ext: "Экстремальный", p_ext_d: "Все доступы, поддержка 24/7. У вас есть всё.", p_purch: "Купить",
      p_desc: "Базовые функции разблокированы.", p_rest: "Перезапустить План", p_del: "Удалить Аккаунт", p_sup: "Связь с поддержкой",
      f_tit: "FAQ", f_desc: "Нашлись вопросы? Ответим быстро!", d_tit: "Разработчики", d_desc: "Встречайте создателей Global Script's.",
      c_tit: "Комьюнити", c_desc: "Заходите на наш Discord сервер.",
      fr_tit: "Ваш аккаунт был заморожен Разработчиком", fr_desc: "Обратитесь к Разработчику чтобы решить проблему, или попросите разблокировку.",
      mn_tit: "Сайт временно закрыт, или выключен по тех.перерывам.", mn_desc: "Попробуйте посетить этот сайт в другое время!",
      login_ph: "Логин", pass_ph: "Пароль", secret_ph: "Секретное слово", code_ph: "Введите код", email_ph: "Введите почту для защиты от ботов (Не обяз.)",
      reg_sec_ph: "Секретное слово если забыли пароль", reg_src_ph: "Откуда вы узнали про нас?",
      m_cancel: "Отмена", m_confirm: "Подтвердить",
      disc_club: "Global Scripts Club", disc_desc: "Мы обсуждаем, мы создаем, мы рассчитываем. Вступи чтобы следить за обновлениями и общаться с другими людьми!", disc_join: "Зайти в клуб"
    },
    ja: {
      theme_btn: "ライトテーマ", logout: "ログアウト", auth_btn: "承認する", no_acc: "アカウントがありませんか？作成！",
      dev_auth: "開発者認証", dev_desc: "管理者の秘密コードを入力してください。",
      unlock_btn: "システムを解除", cancel: "キャンセル", bot_prot: "ボット保護",
      bot_desc: "メールに6桁のコードを送信しました。15分間有効です。", verify_btn: "確認",
      reg_desc: "アカウント情報を入力してください。", agree: "プライバシーポリシーに同意します",
      create_btn: "アカウント作成", back_login: "ログインに戻る", loading: "システム認証中...",
      menu: "メニュー", m_main: "メイン", m_main_d: "あなたのプロフィール。",
      m_key: "キーシステム", m_key_d: "無料アクセスキーを取得。", m_scr: "スクリプト", m_scr_d: "現在のスクリプト。",
      m_plan: "プラン", m_plan_d: "プランを購入して機能をアンロック！", m_faq: "FAQ", m_faq_d: "よくある質問。",
      m_dev: "開発者", m_dev_d: "クリエイター。", m_disc: "DISCORD", m_disc_d: "チャットにもいます！",
      u_prof: "プロフィール", acc_det: "アカウント詳細", acc_det_d: "あなたのシステム情報です。",
      l_login: "ログイン", l_plan: "現在のプラン", l_reg: "登録日", l_dev: "開発者承認",
      k_gen: "キー生成", k_unl: "無料アクセス", k_desc: "独自のHWIDキーを作成。", k_btn: "キーを生成",
      s_lib: "スクリプトライブラリ", s_good: "ベータ版で動作します。バグがあります。",
      s_copy: "LUAをコピー", p_upg: "プラン", p_buy: "プラン購入", p_my: "現在のプラン",
      p_start: "スターター", p_start_d: "初心者向けです。",
      p_pro: "プロ", p_pro_d: "多くの機能とサポート。",
      p_ext: "エクストリーム", p_ext_d: "すべてにアクセス可能。24/7サポート。", p_purch: "購入",
      p_desc: "基本機能がアンロックされました。", p_rest: "再起動", p_del: "アカウント削除", p_sup: "サポートに連絡",
      f_tit: "FAQ", f_desc: "よくある質問。", d_tit: "開発者", d_desc: "私たちが作成しました。",
      c_tit: "コミュニティ", c_desc: "Discordに参加してください。",
      fr_tit: "あなたのアカウントは凍結されました", fr_desc: "開発者に連絡して問題を解決してください。",
      mn_tit: "現在メンテナンス中です。", mn_desc: "後でもう一度お試しください！",
      login_ph: "ログイン", pass_ph: "パスワード", secret_ph: "秘密の言葉", code_ph: "コードを入力", email_ph: "メールアドレスを入力 (任意)",
      reg_sec_ph: "忘れた場合の秘密の言葉", reg_src_ph: "どこで知りましたか？",
      m_cancel: "キャンセル", m_confirm: "確認",
      disc_club: "Global Scripts Club", disc_desc: "私たちは議論し、作成し、計算します。参加して最新情報をチェックし、他の人とチャットしましょう！", disc_join: "クラブに参加する"
    },
    pt: {
      theme_btn: "Modo Claro", logout: "Sair", auth_btn: "AUTORIZAR", no_acc: "Não tem uma conta? Crie uma!",
      dev_auth: "Autenticação de Dev", dev_desc: "Insira a palavra secreta.",
      unlock_btn: "DESBLOQUEAR", cancel: "Cancelar", bot_prot: "Proteção contra Bots",
      bot_desc: "Código de 6 dígitos enviado ao email. Válido por 15 min.", verify_btn: "VERIFICAR",
      reg_desc: "Descreva-se para a conta.", agree: "Concordo com os cookies de privacidade.",
      create_btn: "CRIAR CONTA", back_login: "Voltar", loading: "Autenticando...",
      menu: "MENU", m_main: "PRINCIPAL", m_main_d: "Seu perfil.",
      m_key: "CHAVES", m_key_d: "Obtenha acesso.", m_scr: "SCRIPTS", m_scr_d: "Scripts atuais.",
      m_plan: "PLANOS", m_plan_d: "Compre planos funcionais!", m_faq: "FAQ", m_faq_d: "Tem perguntas?",
      m_dev: "DEVS", m_dev_d: "Criadores.", m_disc: "DISCORD", m_disc_d: "Junte-se ao chat!",
      u_prof: "Perfil", acc_det: "Detalhes da Conta", acc_det_d: "Sua visão geral.",
      l_login: "LOGIN", l_plan: "PLANO ATUAL", l_reg: "REGISTRO", l_dev: "APROVADO",
      k_gen: "Gerador", k_unl: "Desbloquear Acesso", k_desc: "Crie chaves HWID.", k_btn: "Gerar Chave",
      s_lib: "Biblioteca", s_good: "Bom script, funciona na versão beta. Contém bugs.",
      s_copy: "COPIAR LUA", p_upg: "Planos", p_buy: "Comprar Plano", p_my: "Meu Plano",
      p_start: "Inicial", p_start_d: "Bom para iniciantes.",
      p_pro: "Profissional", p_pro_d: "Mais recursos e suporte.",
      p_ext: "Extremo", p_ext_d: "Acesso total 24/7.", p_purch: "Comprar",
      p_desc: "Recursos básicos liberados.", p_rest: "Reiniciar", p_del: "Excluir Conta", p_sup: "Suporte",
      f_tit: "FAQ", f_desc: "Dúvidas?", d_tit: "Desenvolvedores", d_desc: "Nossa equipe.",
      c_tit: "Comunidade", c_desc: "Junte-se ao Discord.",
      fr_tit: "Sua conta foi congelada pelo Desenvolvedor", fr_desc: "Contate o desenvolvedor para resolver.",
      mn_tit: "O site está fechado para manutenção.", mn_desc: "Tente novamente mais tarde!",
      login_ph: "Login", pass_ph: "Senha", secret_ph: "Palavra Secreta", code_ph: "Insira o Código", email_ph: "Email (Opcional)",
      reg_sec_ph: "Palavra de recuperação", reg_src_ph: "Como nos conheceu?",
      m_cancel: "Cancelar", m_confirm: "Confirmar",
      disc_club: "Global Scripts Club", disc_desc: "Nós discutimos, criamos e calculamos. Junte-se para acompanhar as atualizações e conversar com outras pessoas!", disc_join: "Entrar no clube"
    }
  };

  function setLang(lang) {
    localStorage.setItem('lang', lang);
    const map = { en: "🌎 EN", ru: "🇷🇺 RU", ja: "🇯🇵 JA", pt: "🇧🇷 PT" };
    document.getElementById('langBtnText').innerText = map[lang];
    document.getElementById('langMenu').classList.remove('show');
    
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      if(i18n[lang][key]) el.innerText = i18n[lang][key];
    });
    
    document.querySelectorAll('[data-i18n-ph]').forEach(el => {
      const key = el.getAttribute('data-i18n-ph');
      if(i18n[lang][key]) el.placeholder = i18n[lang][key];
    });
  }

  function toggleLangMenu() {
    document.getElementById('langMenu').classList.toggle('show');
  }

  // --- КАСТОМНЫЕ МОДАЛЬНЫЕ ОКНА ---
  let confirmActionCallback = null;

  function showConfirm(title, message, confirmText, isDanger, callback, hideCancel = false) {
      document.getElementById('modalTitle').innerText = title;
      document.getElementById('modalMessage').innerText = message;
      
      const confirmBtn = document.getElementById('modalConfirmBtn');
      confirmBtn.innerText = confirmText;
      confirmBtn.className = isDanger ? 'modal-btn modal-btn-danger' : 'modal-btn modal-btn-confirm';
      
      document.getElementById('modalCancelBtn').style.display = hideCancel ? 'none' : 'block';
      
      confirmActionCallback = callback;
      document.getElementById('customModalOverlay').classList.add('active');
  }

  function closeConfirm() {
      document.getElementById('customModalOverlay').classList.remove('active');
      confirmActionCallback = null;
  }

  document.getElementById('modalCancelBtn').addEventListener('click', closeConfirm);
  document.getElementById('modalConfirmBtn').addEventListener('click', () => {
      if(confirmActionCallback) confirmActionCallback();
      closeConfirm();
  });

  function showMessage(elementId, text, isSuccess) {
    const el = document.getElementById(elementId); el.innerText = text; el.className = isSuccess ? 'success-msg show' : 'error-msg show';
  }
  function hideMessage(elementId) { document.getElementById(elementId).classList.remove('show'); }

  function contactSupport() {
    const btn = document.getElementById('supportBtn'); const original = btn.innerText;
    btn.innerText = "This feature will be available soon!"; btn.style.opacity = "1";
    setTimeout(() => { btn.innerText = original; btn.style.opacity = "0.5"; }, 3000);
  }

  function requestRestartPlan() {
    showConfirm('Restart Plan', 'Are you sure you want to restart your current plan?', 'Restart', false, () => {
        fetch('/restart_plan', { method: 'POST' }).then(res => res.json()).then(data => {
          if(data.success) { document.getElementById('planCurrentStatus').innerText = "Your current plan: " + data.plan + " - " + data.days + " Days"; showConfirm('Success', 'Plan restarted successfully!', 'OK', false, null, true); }
        });
    });
  }

  function requestDeleteAccount() {
    showConfirm('Delete Account', 'Are you sure you want to completely delete your account? This action cannot be undone.', 'Delete', true, () => {
        fetch('/delete_account', { method: 'POST' }).then(() => window.location.reload());
    });
  }

  function switchPlanSubTab(tab) {
    document.getElementById('btnBuyPlan').classList.remove('active'); document.getElementById('btnMyPlan').classList.remove('active');
    document.getElementById('planBuySection').style.display = 'none'; document.getElementById('planMySection').style.display = 'none';
    if(tab === 'buy') { document.getElementById('btnBuyPlan').classList.add('active'); document.getElementById('planBuySection').style.display = 'block'; }
    else { document.getElementById('btnMyPlan').classList.add('active'); document.getElementById('planMySection').style.display = 'block'; }
  }

  // АДМИН-ФУНКЦИИ
  let isSiteMaintenance = false;
  function loadAdminPanel(devApproved) {
     if (devApproved !== 'Yes') return;
     document.getElementById('devUserView').style.display = 'none'; document.getElementById('devAdminView').style.display = 'flex';
     refreshAdminData(); setInterval(refreshConsoleLogs, 3000);
  }
  function refreshAdminData() {
     fetch('/admin/get_users').then(res => res.json()).then(data => {
        if(data.success) {
           isSiteMaintenance = data.maintenance === 'Yes';
           document.getElementById('btnToggleMaintenance').innerText = isSiteMaintenance ? "Turn Site ON" : "Turn Site OFF (Maintenance)";
           document.getElementById('btnToggleMaintenance').className = isSiteMaintenance ? "dev-btn-sm dev-btn-danger" : "dev-btn-sm";

           const tbody = document.getElementById('devUsersTableBody'); tbody.innerHTML = '';
           data.users.forEach(u => {
              const freezeText = u.is_frozen === 'Yes' ? 'Unfreeze' : 'Freeze';
              const freezeClass = u.is_frozen === 'Yes' ? 'dev-btn-sm dev-btn-danger' : 'dev-btn-sm dev-btn-freeze';
              tbody.innerHTML += `<tr><td><b>${u.login}</b></td><td>${u.plan}</td><td>${u.plan_days} d</td><td><select class="dev-select" onchange="adminChangePlan('${u.login}', this.value)"><option value="" selected disabled>Select plan</option><option value="Starter Plan">Starter</option><option value="Professional Plan">Professional</option><option value="Extreme Plan">Extreme</option></select></td><td><div style="display:flex; gap:8px;"><button class="dev-btn-sm" onclick="adminAddDays('${u.login}')">+7 Days</button><button class="${freezeClass}" onclick="adminToggleFreeze('${u.login}')">${freezeText}</button><button class="dev-btn-sm dev-btn-danger" onclick="requestAdminDeleteUser('${u.login}')">Delete</button></div></td></tr>`;
           });
        }
     });
     refreshConsoleLogs();
  }
  function refreshConsoleLogs() {
     fetch('/admin/get_logs').then(res => res.json()).then(data => {
        if(data.success) {
           const box = document.getElementById('webConsoleBox'); box.innerHTML = '';
           data.logs.forEach(l => { box.innerHTML += `<div class="web-log-line web-log-${l.level}">${l.text}</div>`; }); box.scrollTop = box.scrollHeight;
        }
     });
  }
  function adminChangePlan(login, newPlan) { fetch('/admin/change_plan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ login, plan: newPlan }) }).then(res => res.json()).then(data => { if(data.success) refreshAdminData(); }); }
  function adminAddDays(login) { fetch('/admin/add_days', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ login }) }).then(res => res.json()).then(data => { if(data.success) refreshAdminData(); }); }
  function adminToggleFreeze(login) { fetch('/admin/toggle_freeze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ login }) }).then(res => res.json()).then(data => { if(data.success) refreshAdminData(); else showConfirm('Error', data.message, 'OK', false, null, true); }); }
  function adminToggleMaintenance() { fetch('/admin/toggle_maintenance', { method: 'POST' }).then(res => res.json()).then(data => { if(data.success) refreshAdminData(); }); }

  function requestAdminDeleteUser(login) { 
      showConfirm('Delete User', `Are you sure you want to permanently delete '${login}'?`, 'Delete', true, () => {
          fetch('/admin/delete_user', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ login }) }).then(res => res.json()).then(data => { if(data.success) refreshAdminData(); else showConfirm('Error', data.message, 'OK', false, null, true); }); 
      });
  }

  function adminUpdateDiscordLink() {
      const link = document.getElementById('devDiscordLink').value.trim();
      fetch('/admin/update_discord', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ link })
      }).then(res => res.json()).then(data => {
          if(data.success) {
              document.getElementById('discordJoinBtn').href = link;
              showConfirm('Success', 'Discord link updated successfully!', 'OK', false, null, true);
          }
      });
  }

  function copyLuaScript(btn) {
    const luaCode = 'loadstring(game:HttpGet("https://raw.githubusercontent.com/Rob4ik02/Muscle-Legends-Roblox/refs/heads/main/Muscle%20Legends/Sirius%20Library/Loader.lua"))()';
    navigator.clipboard.writeText(luaCode).then(() => {
      const originalText = btn.innerText; btn.innerText = 'Copied successfully!'; btn.style.backgroundColor = 'var(--success)'; btn.style.color = '#fff';
      setTimeout(() => { btn.innerText = originalText; btn.style.backgroundColor = ''; btn.style.color = ''; }, 2000);
    });
  }

  // LIQUID PHYSICS
  const canvas = document.getElementById('bgCanvas'); const ctx = canvas.getContext('2d');
  let width, height, particles = [], mouse = { x: -1000, y: -1000 }, currentDotColor = 'rgba(255, 255, 255, 0.3)', isErrorState = false, globalSpeedBoost = 0, isSystemLoading = false; 
  function updateCanvasColor() { currentDotColor = getComputedStyle(document.body).getPropertyValue('--dot-color').trim(); }
  function resize() { width = canvas.width = window.innerWidth; height = canvas.height = window.innerHeight; initParticles(); }
  window.addEventListener('resize', resize);
  
  class Particle {
    constructor() { this.x = Math.random() * width; this.y = Math.random() * height; this.size = Math.random() * 2 + 1; this.density = (Math.random() * 20) + 5; this.angle = Math.random() * 360; this.speed = Math.random() * 0.3 + 0.1; this.vx = 0; this.vy = 0; this.friction = 0.92; }
    update() {
      this.angle += 0.01;
      if (isSystemLoading) { this.vy -= 1.5; this.vx += (Math.random() - 0.5) * 0.2; } else { this.vy -= this.speed * 0.1; this.vx += Math.sin(this.angle) * 0.05; }
      this.y -= globalSpeedBoost * (this.speed * 1.5);
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
  function animate() { ctx.clearRect(0, 0, width, height); globalSpeedBoost *= 0.92; for (let i = 0; i < particles.length; i++) { particles[i].update(); particles[i].draw(); } requestAnimationFrame(animate); }
  updateCanvasColor(); resize(); animate();

  const themeBtn = document.getElementById('themeBtn');
  document.documentElement.setAttribute('data-theme', localStorage.getItem('theme') || 'dark');
  updateCanvasColor();
  themeBtn.addEventListener('click', () => {
    const newTheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme); localStorage.setItem('theme', newTheme);
    updateCanvasColor();
  });
  function updateClock() { fetch('/get_time').then(res => res.json()).then(data => { document.getElementById('clock').innerText = data.time; }); }
  setInterval(updateClock, 1000); updateClock();

  const sidebarBtns = document.querySelectorAll('.sidebar-btn');
  const tabContents = document.querySelectorAll('.tab-content');
  function switchTab(targetId) {
    globalSpeedBoost = 30; sidebarBtns.forEach(b => b.classList.remove('active')); tabContents.forEach(t => t.classList.remove('active'));
    sidebarBtns.forEach(b => { if(b.getAttribute('data-target') === targetId) b.classList.add('active'); }); document.getElementById(targetId).classList.add('active');
  }
  sidebarBtns.forEach(btn => btn.addEventListener('click', () => switchTab(btn.getAttribute('data-target'))));
  document.getElementById('userDisplay').addEventListener('click', () => switchTab('tab-main'));

  // ЛОГИКА ДИНАМИЧЕСКОГО ЛОАДЕРА
  const loadingTexts = ["Authenticating System...", "Decrypting Data...", "Connecting to Mainframe...", "Loading Modules...", "Unlocking Interface..."];
  let loadingInterval;
  function showLoadingScreen() {
      document.getElementById('loaderScreen').style.display = 'flex';
      isSystemLoading = true; let i = 0; document.getElementById('loaderDynamicText').innerText = loadingTexts[i];
      loadingInterval = setInterval(() => { i = (i + 1) % loadingTexts.length; document.getElementById('loaderDynamicText').innerText = loadingTexts[i]; }, 500);
  }
  function hideLoadingScreen() { document.getElementById('loaderScreen').style.display = 'none'; isSystemLoading = false; clearInterval(loadingInterval); }

  // --- ГЛОБАЛЬНЫЙ ИНИТ И ЛОГИКА ---
  document.addEventListener('DOMContentLoaded', () => {
    
    const savedLang = localStorage.getItem('lang') || 'en';
    setLang(savedLang);

    const appMainWrapper = document.getElementById('appMainWrapper');
    const authForm = document.getElementById('authForm');
    const secretForm = document.getElementById('secretForm');
    const regForm = document.getElementById('regForm');
    const twoFaForm = document.getElementById('twoFaForm');
    const createAccountWrapper = document.getElementById('createAccountWrapper');
    
    if ({{ show_freeze }}) {
        appMainWrapper.style.display = 'none';
        document.getElementById('freezeScreen').style.display = 'flex';
        return;
    }
    
    if ({{ show_maintenance }}) {
        appMainWrapper.style.display = 'none';
        document.getElementById('maintenanceScreen').style.display = 'flex';
        let lockClicks = 0;
        document.getElementById('maintenanceLockIcon').addEventListener('click', () => {
            lockClicks++;
            if (lockClicks >= 3) { document.getElementById('maintenanceScreen').style.display = 'none'; appMainWrapper.style.display = 'flex'; authForm.style.display = 'flex'; }
        });
        return;
    }

    document.getElementById('createAccountLink').addEventListener('click', () => { authForm.style.display = 'none'; regForm.style.display = 'flex'; globalSpeedBoost = 20; });
    document.getElementById('backToLoginLink').addEventListener('click', () => { regForm.style.display = 'none'; authForm.style.display = 'flex'; globalSpeedBoost = 20; createAccountWrapper.classList.remove('show'); hideMessage('message'); });
    document.getElementById('cancelSecretLink').addEventListener('click', () => { secretForm.style.display = 'none'; authForm.style.display = 'flex'; globalSpeedBoost = 20; });
    document.getElementById('cancel2FaLink').addEventListener('click', () => { twoFaForm.style.display = 'none'; authForm.style.display = 'flex'; });

    const regAgree = document.getElementById('regAgree');
    const regBtn = document.getElementById('regBtn');
    regAgree.addEventListener('change', (e) => { regBtn.disabled = !e.target.checked; });

    regBtn.addEventListener('click', () => {
      const login = document.getElementById('regLogin').value.trim(); const password = document.getElementById('regPassword').value;
      const email = document.getElementById('regEmail').value.trim(); const secret = document.getElementById('regSecret').value.trim();
      const source = document.getElementById('regSource').value.trim();

      if (!login || !password || !secret || !source) { showMessage('regMessage', 'Please fill all required fields.', false); return; }

      fetch('/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ login, password, email, secret, source })
      }).then(res => res.json()).then(data => {
        if (data.success) {
          showMessage('regMessage', 'Account created successfully!', true);
          setTimeout(() => { regForm.style.display = 'none'; authForm.style.display = 'flex'; document.getElementById('login').value = login; hideMessage('regMessage'); createAccountWrapper.classList.remove('show'); hideMessage('message'); }, 1500);
        } else { showMessage('regMessage', data.message, false); }
      });
    });

    const isLoggedIn = {{ 'true' if current_user else 'false' }};
    if (isLoggedIn) { loadDashboard(); }

    function loadDashboard() {
        document.getElementById('mainHeader').style.display = 'none';
        document.getElementById('dashboardLayout').style.display = 'flex';
        fetch('/get_user_info').then(res => res.json()).then(data => {
            if(data.success) {
                if(data.is_frozen === 'Yes') { window.location.reload(); }
                document.getElementById('userDisplay').innerText = data.login;
                document.getElementById('profileLogin').innerText = data.login;
                document.getElementById('profilePlan').innerText = data.plan;
                document.getElementById('profileRegDate').innerText = data.reg_date;
                document.getElementById('profileDevApproved').innerText = data.dev_approved;
                document.getElementById('planGreeting').innerText = data.greeting;
                document.getElementById('planCurrentStatus').innerText = "Your current plan: " + data.plan + " - " + data.plan_days + " Days";
                loadAdminPanel(data.dev_approved);
                if(data.dev_approved === 'Yes') { document.getElementById('devGreeting').innerText = data.dev_greeting; }
            }
        });
    }

    function triggerErrorAnimation(formEl) {
      formEl.classList.remove('shake-error'); setTimeout(() => formEl.classList.add('shake-error'), 10);
      setTimeout(() => formEl.classList.remove('shake-error'), 400); isErrorState = true; setTimeout(() => { isErrorState = false; }, 600);
    }

    document.getElementById('logoutBtn').addEventListener('click', () => { showConfirm('Sign Out', 'Are you sure you want to log out of your account?', 'Logout', true, () => { fetch('/logout').then(() => window.location.reload()); }); });

    document.getElementById('signUpBtn').addEventListener('click', () => {
      const login = document.getElementById('login').value.trim(); const password = document.getElementById('password').value;
      if (!login || !password) { showMessage('message', 'Empty fields detected.', false); triggerErrorAnimation(authForm); createAccountWrapper.classList.add('show'); return; }

      fetch('/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ login, password })
      }).then(res => res.json()).then(data => {
        if (data.success) {
          if(data.is_frozen) { window.location.reload(); } 
          else if(data.require_secret) { hideMessage('message'); authForm.style.display = 'none'; secretForm.style.display = 'flex'; globalSpeedBoost = 15; } 
          else if(data.require_2fa) { authForm.style.display = 'none'; twoFaForm.style.display = 'flex'; } 
          else { hideMessage('message'); authForm.style.display = 'none'; document.getElementById('mainHeader').style.display = 'none'; showLoadingScreen(); setTimeout(() => { document.getElementById('clockWrapper').style.display = 'flex'; document.getElementById('userWrapper').style.display = 'flex'; hideLoadingScreen(); loadDashboard(); }, 2500); }
        } else { showMessage('message', 'Invalid credentials.', false); triggerErrorAnimation(authForm); createAccountWrapper.classList.add('show'); }
      });
    });
    
    document.getElementById('verifySecretBtn').addEventListener('click', () => {
       const secret = document.getElementById('devSecretCode').value.trim(); if(!secret) return;
       fetch('/verify_secret', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ secret })
       }).then(res => res.json()).then(data => {
          if(data.success) {
             if(data.require_2fa) { secretForm.style.display = 'none'; twoFaForm.style.display = 'flex'; } 
             else { hideMessage('secretMessage'); secretForm.style.display = 'none'; document.getElementById('mainHeader').style.display = 'none'; showLoadingScreen(); setTimeout(() => { document.getElementById('clockWrapper').style.display = 'flex'; document.getElementById('userWrapper').style.display = 'flex'; hideLoadingScreen(); loadDashboard(); }, 2500); }
          } else { showMessage('secretMessage', data.message, false); triggerErrorAnimation(secretForm); }
       });
    });

    document.getElementById('verifyBtn').addEventListener('click', () => {
       const code = document.getElementById('twoFaCode').value.trim();
       fetch('/verify_2fa', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code })
       }).then(res => res.json()).then(data => {
          if(data.success) { twoFaForm.style.display = 'none'; document.getElementById('mainHeader').style.display = 'none'; showLoadingScreen(); setTimeout(() => { document.getElementById('clockWrapper').style.display = 'flex'; document.getElementById('userWrapper').style.display = 'flex'; hideLoadingScreen(); loadDashboard(); }, 2500); } 
          else { showMessage('twoFaMessage', data.message, false); triggerErrorAnimation(twoFaForm); }
       });
    });
    
    document.getElementById('password').addEventListener('keypress', function (e) { if (e.key === 'Enter') document.getElementById('signUpBtn').click(); });
    document.getElementById('devSecretCode').addEventListener('keypress', function (e) { if (e.key === 'Enter') document.getElementById('verifySecretBtn').click(); });
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
            if user_data['is_frozen'] == 'Yes':
                is_frozen = True
                session.pop('user', None) 
            dev_approved = user_data['dev_approved']
        else:
            session.pop('user', None)
            
    conn.close()
    
    show_maintenance = 'true' if (is_maintenance and dev_approved != 'Yes') else 'false'
    show_freeze = 'true' if is_frozen else 'false'
    
    return render_template_string(TEMPLATE, current_user=session.get('user'), show_maintenance=show_maintenance, show_freeze=show_freeze, discord_link=discord_link)

@app.route('/get_time')
def get_time():
    tz = pytz.timezone('Europe/Moscow')
    return jsonify({'time': datetime.now(tz).strftime('%H:%M:%S')})

@app.route('/get_user_info')
def get_user_info():
    current_user = session.get('user')
    if not current_user:
        c_log('WARNING', "Unauthorized attempt to fetch user info.")
        return jsonify({'success': False})
    
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE login = ?", (current_user,)).fetchone()
    conn.close()

    if user:
        greetings = [
            f"Hey {user['login']}, how is your day going?",
            f"Where do we start, {user['login']}?",
            f"Glad to see you, {user['login']}!"
        ]
        dev_greetings = [
            f"Welcome back, System Arch-Developer {user['login']}!",
            f"Mainframe core is fully synchronized. Greetings, {user['login']}!",
            f"Root privileges granted. Active session: Developer {user['login']}."
        ]
        return jsonify({
            'success': True,
            'login': user['login'],
            'plan': user['plan'],
            'plan_days': user['plan_days'],
            'reg_date': user['reg_date'],
            'dev_approved': user['dev_approved'],
            'is_frozen': user['is_frozen'],
            'greeting': random.choice(greetings),
            'dev_greeting': random.choice(dev_greetings)
        })
    c_log('ERROR', f"Failed to retrieve data for user: {current_user}")
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
        if user['is_frozen'] == 'Yes':
            c_log('WARNING', f"Frozen account {login_input} attempted login.")
            return jsonify({'success': True, 'is_frozen': True})
            
        session['pending_user'] = login_input
        
        if user['dev_approved'] == 'Yes':
            c_log('WARNING', f"Developer privileges detected for {login_input}. Requesting secret codename...")
            return jsonify({'success': True, 'require_secret': True, 'require_2fa': False, 'is_frozen': False})
            
        if user['email'] and user['email'].strip() != '':
            code = str(random.randint(100000, 999999))
            session['2fa_code'] = code
            session['2fa_expiry'] = time.time() + 900
            
            c_log('WARNING', f"2FA Triggered for {login_input}. Generating code...")
            email_sent = send_real_email(user['email'], code)
            if email_sent: c_log('SUCCESS', f"2FA code successfully emailed to {user['email']}")
            else: c_log('ERROR', f"Failed to send 2FA email. Fallback - Code is: {code}")
                
            return jsonify({'success': True, 'require_secret': False, 'require_2fa': True, 'is_frozen': False})
        else:
            session['user'] = login_input
            session.pop('pending_user', None)
            c_log('SUCCESS', f"User {login_input} logged in successfully.")
            return jsonify({'success': True, 'require_secret': False, 'require_2fa': False, 'is_frozen': False})
    else:
        c_log('ERROR', f"Invalid credentials provided for {login_input}.")
        return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/verify_secret', methods=['POST'])
def verify_secret():
    data = request.get_json()
    secret_input = data.get('secret', '').strip()
    
    if 'pending_user' not in session:
        c_log('ERROR', "Secret verification failed: Session expired.")
        return jsonify({'success': False, 'message': 'Session expired.'})
        
    target_user = session['pending_user']
    c_log('INFO', f"Verifying secret codename for developer: {target_user}")
    
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE login = ?", (target_user,)).fetchone()
    conn.close()
    
    if user and user['secret'] == secret_input:
        c_log('SUCCESS', f"Secret codename verified for {target_user}.")
        
        if user['email'] and user['email'].strip() != '':
            code = str(random.randint(100000, 999999))
            session['2fa_code'] = code
            session['2fa_expiry'] = time.time() + 900
            
            c_log('WARNING', f"2FA Triggered for {target_user}. Generating code...")
            send_real_email(user['email'], code)
            return jsonify({'success': True, 'require_2fa': True})
        else:
            session['user'] = target_user
            session.pop('pending_user', None)
            c_log('SUCCESS', f"Developer {target_user} logged in with full privileges.")
            return jsonify({'success': True, 'require_2fa': False})
    else:
        c_log('ERROR', f"Invalid secret codename entered by {target_user}.")
        return jsonify({'success': False, 'message': 'Invalid secret codename.'})

@app.route('/verify_2fa', methods=['POST'])
def verify_2fa():
    data = request.get_json()
    code = data.get('code', '').strip()
    
    if 'pending_user' in session and '2fa_code' in session:
        target_user = session['pending_user']
        c_log('INFO', f"2FA verification attempt for user: {target_user}")
        
        if time.time() > session.get('2fa_expiry', 0):
            c_log('ERROR', f"2FA code expired for {target_user}.")
            return jsonify({'success': False, 'message': 'Code expired! Please login again.'})
            
        if code == session['2fa_code']:
            session['user'] = target_user
            session.pop('pending_user', None)
            session.pop('2fa_code', None)
            session.pop('2fa_expiry', None)
            c_log('SUCCESS', f"User {target_user} passed 2FA and logged in.")
            return jsonify({'success': True})
        else:
            c_log('WARNING', f"Incorrect 2FA code entered by {target_user}.")
            return jsonify({'success': False, 'message': 'Incorrect code.'})
            
    c_log('ERROR', "2FA verification failed due to invalid session.")
    return jsonify({'success': False, 'message': 'Session error.'})

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    login_input = data.get('login', '').strip()
    password_input = data.get('password', '')
    email_input = data.get('email', '').strip()
    secret_input = data.get('secret', '').strip()
    source_input = data.get('source', '').strip()
    
    c_log('INFO', f"Registration attempt with username: {login_input}")

    conn = get_db_connection()
    if conn.execute("SELECT id FROM users WHERE login = ?", (login_input,)).fetchone():
        conn.close()
        c_log('WARNING', f"Registration failed. Username {login_input} is already taken.")
        return jsonify({'success': False, 'message': 'Username is already taken.'})

    tz = pytz.timezone('Europe/Moscow')
    reg_date = datetime.now(tz).strftime('%d.%m.%Y')

    conn.execute('''
        INSERT INTO users (login, password_hash, email, secret, source, reg_date, plan, plan_days, dev_approved, is_frozen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (login_input, generate_password_hash(password_input), email_input, secret_input, source_input, reg_date, 'Free Tier', 0, 'No', 'No'))
    conn.commit()
    conn.close()
    
    c_log('SUCCESS', f"New account created successfully for {login_input}.")
    return jsonify({'success': True})

# --- МАРШРУТЫ АДМИН-ПАНЕЛИ (ADMIN API) ---
@app.route('/admin/get_users')
def admin_get_users():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes':
        conn.close()
        return jsonify({'success': False}), 403
        
    db_users = conn.execute("SELECT login, plan, plan_days, is_frozen FROM users").fetchall()
    maintenance = conn.execute("SELECT value FROM settings WHERE key = 'maintenance'").fetchone()
    conn.close()
    
    users_list = [dict(u) for u in db_users]
    m_val = maintenance['value'] if maintenance else 'No'
    return jsonify({'success': True, 'users': users_list, 'maintenance': m_val})

@app.route('/admin/get_logs')
def admin_get_logs():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    conn.close()
    if not check or check['dev_approved'] != 'Yes':
        return jsonify({'success': False}), 403
        
    return jsonify({'success': True, 'logs': LIVE_LOGS})

@app.route('/admin/change_plan', methods=['POST'])
def admin_change_plan():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes':
        conn.close()
        return jsonify({'success': False}), 403
        
    data = request.get_json()
    target_user = data.get('login')
    new_plan = data.get('plan')
    
    days = 0
    if 'Starter' in new_plan: days = 7
    elif 'Professional' in new_plan: days = 30
    elif 'Extreme' in new_plan: days = 90
    
    conn.execute("UPDATE users SET plan = ?, plan_days = ? WHERE login = ?", (new_plan, days, target_user))
    conn.commit()
    conn.close()
    
    c_log('WARNING', f"Developer '{current_user}' updated '{target_user}' plan to '{new_plan}' ({days} days).")
    return jsonify({'success': True})

@app.route('/admin/add_days', methods=['POST'])
def admin_add_days():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes':
        conn.close()
        return jsonify({'success': False}), 403
        
    data = request.get_json()
    target_user = data.get('login')
    
    conn.execute("UPDATE users SET plan_days = plan_days + 7 WHERE login = ?", (target_user,))
    conn.commit()
    conn.close()
    
    c_log('WARNING', f"Developer '{current_user}' added +7 days to user '{target_user}'.")
    return jsonify({'success': True})

@app.route('/admin/toggle_freeze', methods=['POST'])
def admin_toggle_freeze():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes':
        conn.close()
        return jsonify({'success': False}), 403
        
    data = request.get_json()
    target_user = data.get('login')
    
    if target_user == current_user:
        conn.close()
        return jsonify({'success': False, 'message': 'You cannot freeze your own developer account!'})
        
    target_data = conn.execute("SELECT is_frozen FROM users WHERE login = ?", (target_user,)).fetchone()
    new_status = 'No' if target_data['is_frozen'] == 'Yes' else 'Yes'
    
    conn.execute("UPDATE users SET is_frozen = ? WHERE login = ?", (new_status, target_user))
    conn.commit()
    conn.close()
    
    c_log('WARNING', f"Developer '{current_user}' changed freeze status of '{target_user}' to {new_status}.")
    return jsonify({'success': True})

@app.route('/admin/toggle_maintenance', methods=['POST'])
def admin_toggle_maintenance():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes':
        conn.close()
        return jsonify({'success': False}), 403
        
    m_data = conn.execute("SELECT value FROM settings WHERE key = 'maintenance'").fetchone()
    new_val = 'No' if m_data and m_data['value'] == 'Yes' else 'Yes'
    
    conn.execute("UPDATE settings SET value = ? WHERE key = 'maintenance'", (new_val,))
    conn.commit()
    conn.close()
    
    c_log('WARNING', f"Developer '{current_user}' toggled Site Maintenance mode to: {new_val}.")
    return jsonify({'success': True})

@app.route('/admin/delete_user', methods=['POST'])
def admin_delete_user():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes':
        conn.close()
        return jsonify({'success': False}), 403
        
    data = request.get_json()
    target_user = data.get('login')
    
    if target_user == current_user:
        conn.close()
        return jsonify({'success': False, 'message': 'You cannot delete your own admin account!'})
        
    conn.execute("DELETE FROM users WHERE login = ?", (target_user,))
    conn.commit()
    conn.close()
    
    c_log('ERROR', f"Developer '{current_user}' permanently deleted account '{target_user}' from system database.")
    return jsonify({'success': True})

@app.route('/admin/update_discord', methods=['POST'])
def admin_update_discord():
    current_user = session.get('user')
    conn = get_db_connection()
    check = conn.execute("SELECT dev_approved FROM users WHERE login = ?", (current_user,)).fetchone()
    if not check or check['dev_approved'] != 'Yes':
        conn.close()
        return jsonify({'success': False}), 403
        
    new_link = request.get_json().get('link', '').strip()
    conn.execute("UPDATE settings SET value = ? WHERE key = 'discord_link'", (new_link,))
    conn.commit()
    conn.close()
    
    c_log('WARNING', f"Developer '{current_user}' updated Discord link to: {new_link}")
    return jsonify({'success': True})

@app.route('/restart_plan', methods=['POST'])
def restart_plan():
    current_user = session.get('user')
    if current_user:
        c_log('INFO', f"User {current_user} requested plan restart.")
        conn = get_db_connection()
        user = conn.execute("SELECT plan FROM users WHERE login = ?", (current_user,)).fetchone()
        if user:
            days = 0
            if 'Starter' in user['plan']: days = 7
            elif 'Professional' in user['plan']: days = 30
            elif 'Extreme' in user['plan']: days = 90
            elif 'Developer' in user['plan']: days = 999
            
            conn.execute("UPDATE users SET plan_days = ? WHERE login = ?", (days, current_user))
            conn.commit()
            conn.close()
            c_log('SUCCESS', f"Plan restarted for {current_user}. Days set to {days}.")
            return jsonify({'success': True, 'plan': user['plan'], 'days': days})
    c_log('ERROR', "Plan restart failed. User not authenticated.")
    return jsonify({'success': False})

@app.route('/delete_account', methods=['POST'])
def delete_account():
    current_user = session.get('user')
    if current_user:
        c_log('WARNING', f"User {current_user} is deleting their account.")
        conn = get_db_connection()
        conn.execute("DELETE FROM users WHERE login = ?", (current_user,))
        conn.commit()
        conn.close()
        session.pop('user', None)
        c_log('SUCCESS', f"Account for {current_user} has been permanently deleted.")
    return jsonify({'success': True})

@app.route('/logout')
def logout():
    user = session.get('user', 'Unknown')
    session.pop('user', None)
    c_log('INFO', f"User {user} logged out.")
    return ('', 204)

if __name__ == '__main__':
    c_log('SERVICE', "Starting production server on port 5000...")
    app.run(debug=True)
