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
def c_log(level, message):
    tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(tz)
    date_str = now.strftime('%d.%m.%Y | %H:%M')
    
    # ANSI-коды для цветов
    colors = {
        'INFO': '\033[97m',      # Белый
        'SUCCESS': '\033[92m',   # Зеленый
        'WARNING': '\033[93m',   # Желтый
        'ERROR': '\033[91m',     # Красный
        'SERVICE': '\033[90m',   # Серый
        'RESET': '\033[0m'       # Сброс цвета
    }
    
    prefixes = {
        'INFO': 'INFORMATION',
        'SUCCESS': 'SUCCES',
        'WARNING': 'WARNING',
        'ERROR': 'ERROR',
        'SERVICE': 'SCRIPT SERVICE'
    }
    
    # Чтобы форматирование было ровным (с учетом разной длины префиксов)
    prefix = prefixes.get(level, 'LOG')
    color = colors.get(level, colors['RESET'])
    reset = colors['RESET']
    
    print(f"{color}[ {prefix} - {date_str} ] = {message}{reset}")

# Инициализация Flask
c_log('SERVICE', "Initializing Flask application...")
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-dev-secret-key-123')

# --- НАСТРОЙКИ ПОЧТЫ (ДЛЯ РЕАЛЬНОЙ ОТПРАВКИ) ---
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
    cursor = conn.execute("SELECT * FROM users WHERE login = 'rob4ikyay'")
    if not cursor.fetchone():
        c_log('WARNING', "Admin 'rob4ikyay' not found. Creating default admin account...")
        tz = pytz.timezone('Europe/Moscow')
        reg_date = datetime.now(tz).strftime('%d.%m.%Y')
        conn.execute('''
            INSERT INTO users (login, password_hash, email, secret, source, reg_date, plan, plan_days, dev_approved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('rob4ikyay', generate_password_hash('wowwow'), '', 'admin_secret', 'creator', reg_date, 'Developer Tier', 999, 'Yes'))
        c_log('SUCCESS', "Admin account created.")
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

body { margin: 0; padding: 0; min-height: 100vh; font-family: 'Inter', sans-serif; background-color: var(--bg-color); color: var(--text-primary); transition: background-color 0.6s cubic-bezier(0.4, 0, 0.2, 1), color 0.6s ease; overflow-x: hidden; }

#bgCanvas { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: -2; opacity: 0; animation: fadeInCanvas 2s ease-in-out forwards; pointer-events: none; }
.ocean { height: 30vh; width: 100%; position: fixed; bottom: 0; left: 0; z-index: -1; overflow: hidden; opacity: 0; animation: fadeInCanvas 3s ease-in-out 1s forwards; pointer-events: none; }
.wave { background: var(--wave-1); width: 200vw; height: 200vw; position: absolute; bottom: 0; left: 50%; margin-left: -100vw; margin-bottom: -195vw; border-radius: 46%; animation: drift 25s infinite linear; }
.wave:nth-of-type(2) { background: var(--wave-2); margin-bottom: -194vw; animation: drift 30s infinite linear; border-radius: 45%; }
.wave:nth-of-type(3) { background: var(--wave-3); margin-bottom: -196vw; animation: drift 35s infinite linear; border-radius: 44%; }
@keyframes drift { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes fadeInCanvas { to { opacity: 1; } }

.app-content { opacity: 0; display: flex; flex-direction: column; align-items: center; width: 100%; min-height: 100vh; padding: 100px 20px 40px 20px; animation: liquidReveal 1s cubic-bezier(0.16, 1, 0.3, 1) 0.2s forwards; }
@keyframes liquidReveal { 0% { opacity: 0; transform: translateY(20px) scale(0.99); } 100% { opacity: 1; transform: translateY(0) scale(1); } }
@keyframes elasticBounce { 0% { transform: scale(0.96) translateY(10px); opacity: 0; } 50% { transform: scale(1.01) translateY(-2px); opacity: 1; } 100% { transform: scale(1) translateY(0); opacity: 1; } }
@keyframes errorShake { 0%, 100% { transform: translateX(0); } 20%, 60% { transform: translateX(-6px); } 40%, 80% { transform: translateX(6px); } }
.shake-error { animation: errorShake 0.4s cubic-bezier(0.36, 0.07, 0.19, 0.97) forwards; }

.top-bar { position: fixed; top: 0; left: 0; width: 100vw; display: flex; justify-content: space-between; align-items: center; padding: 20px 40px; z-index: 100; background: transparent; }
.top-bar-left, .top-bar-right { display: flex; align-items: center; gap: 12px; }
.ui-pill { background: var(--card-bg); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur); border: 1px solid var(--card-border); box-shadow: var(--shadow-drop), var(--shadow-inner); color: var(--text-primary); padding: 8px 16px; border-radius: 98px; font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 10px; transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), background 0.3s ease; }
.ui-pill:hover { transform: scale(1.05) translateY(-1px); }
#userDisplay { cursor: pointer; }
.recording-dot { width: 8px; height: 8px; background-color: var(--error); border-radius: 50%; animation: liquidBlink 2.5s infinite ease-in-out; }
@keyframes liquidBlink { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.8); } }
.theme-toggle { cursor: pointer; }
.logout-btn { cursor: pointer; color: var(--error); }
.logout-btn:hover { background: var(--error); color: #fff; border-color: var(--error); }

.header { display: flex; flex-direction: column; align-items: center; gap: 12px; margin-bottom: 24px; margin-top: auto; }
.header img { width: 72px; height: 72px; border-radius: 20px; box-shadow: var(--shadow-drop), var(--shadow-inner); border: 1px solid var(--card-border); transition: transform 0.5s cubic-bezier(0.34, 1.56, 0.64, 1); }
.header img:hover { transform: scale(1.1) rotate(4deg); }
.header h1 { margin: 0; font-size: 32px; font-weight: 700; letter-spacing: -0.04em; }

.form-container { margin: auto; display: flex; flex-direction: column; align-items: center; gap: 12px; background: var(--card-bg); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur); padding: 32px; border: 1px solid var(--card-border); border-radius: 28px; box-shadow: var(--shadow-drop), var(--shadow-inner); width: 100%; max-width: 380px; transition: all 0.4s ease; }
.form-header-text { margin: 0 0 8px 0; font-size: 15px; color: var(--text-primary); font-weight: 600; text-align: center; }
.form-container input[type="text"], .form-container input[type="password"] { width: 100%; padding: 14px 16px; font-size: 14px; font-family: inherit; font-weight: 500; color: var(--text-primary); background: var(--input-bg); border: 1px solid var(--input-border); border-radius: 14px; outline: none; transition: all 0.3s cubic-bezier(0.25, 1, 0.5, 1); }
.form-container input::placeholder { color: var(--text-secondary); }
.form-container input:focus { border-color: var(--text-primary); transform: scale(1.02); background: rgba(255, 255, 255, 0.08); }
.email-input::placeholder { color: rgba(136, 136, 136, 0.5) !important; }

.form-container button { width: 100%; padding: 14px; font-size: 15px; font-family: inherit; font-weight: 700; color: var(--accent-text); background: var(--accent); border: none; border-radius: 16px; cursor: pointer; transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1); margin-top: 6px; text-transform: uppercase; letter-spacing: 1px; }
.form-container button:not(:disabled):hover { transform: translateY(-2px) scale(1.02); box-shadow: 0 6px 15px rgba(255, 255, 255, 0.15); }
.form-container button:not(:disabled):active { transform: scale(0.95); }
.form-container button:disabled { opacity: 0.5; cursor: not-allowed; }

.checkbox-container { display: flex; align-items: center; gap: 10px; font-size: 11px; color: var(--text-secondary); cursor: pointer; line-height: 1.4; margin-top: 4px; width: 100%; }
.checkbox-container input[type="checkbox"] { width: 18px; height: 18px; cursor: pointer; accent-color: var(--text-primary); margin: 0; flex-shrink: 0; }

.create-link-wrapper { max-height: 0; opacity: 0; overflow: hidden; transition: all 0.5s cubic-bezier(0.34, 1.56, 0.64, 1); width: 100%; text-align: center; }
.create-link-wrapper.show { max-height: 30px; opacity: 1; margin-top: 8px; }
.create-link, .back-link { color: var(--text-primary); opacity: 0.5; font-size: 13px; font-weight: 500; cursor: pointer; transition: opacity 0.3s ease; text-decoration: underline; }
.create-link:hover, .back-link:hover { opacity: 1; }
.back-link { display: block; text-align: center; margin-top: 8px; }

#message, #regMessage, #twoFaMessage { font-weight: 600; font-size: 13px; text-align: center; min-height: 18px; opacity: 0; transition: opacity 0.4s ease, color 0.3s ease; margin-top: 4px; }
#message.show, #regMessage.show, #twoFaMessage.show { opacity: 1; }
.success-msg { color: #34c759; }
.error-msg { color: var(--error); }

.loader-container { margin: auto; display: none; flex-direction: column; align-items: center; gap: 20px; }
.spinner { width: 46px; height: 46px; border: 3px solid var(--input-border); border-top: 3px solid var(--accent); border-radius: 50%; animation: spin 1s cubic-bezier(0.6, 0.2, 0.4, 0.8) infinite; }
.loader-text { font-size: 14px; font-weight: 600; color: var(--text-secondary); letter-spacing: 2px; animation: liquidBlink 2s infinite ease-in-out; }

.dashboard-layout { margin: auto; display: none; width: 100%; max-width: 1100px; gap: 20px; }
.sidebar { flex: 0 0 250px; background: var(--card-bg); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur); border: 1px solid var(--card-border); border-radius: 28px; padding: 20px; display: flex; flex-direction: column; box-shadow: var(--shadow-drop), var(--shadow-inner); }
.sidebar h2 { margin: 0 0 16px 0; font-size: 14px; text-transform: uppercase; color: var(--text-secondary); letter-spacing: 1px; }
.sidebar-nav { display: flex; flex-direction: column; gap: 8px; flex: 1; }
.sidebar-footer { display: flex; flex-direction: column; gap: 8px; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--card-border); }
.sidebar-btn { background: transparent; color: var(--text-primary); border: none; padding: 10px 14px; border-radius: 16px; font-family: inherit; cursor: pointer; text-align: left; transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); display: flex; flex-direction: column; gap: 2px; }
.sidebar-btn:hover { background: var(--input-border); transform: translateX(4px); }
.sidebar-btn.active { background: var(--text-primary); color: var(--bg-color); transform: scale(1.03); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
.sidebar-btn.active .btn-desc { color: var(--bg-color); opacity: 0.8; }
.sidebar-btn-footer { opacity: 0.5; }
.sidebar-btn-footer:hover { opacity: 1; }
.btn-title { font-weight: 600; font-size: 14px; text-transform: uppercase; }
.btn-desc { font-weight: 400; font-size: 11px; color: var(--text-secondary); line-height: 1.3; }

.main-content { flex: 1; display: flex; flex-direction: column; position: relative; }
.tab-content { display: none; flex-direction: column; gap: 20px; }
.tab-content.active { display: flex; animation: elasticBounce 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) forwards; }
.tab-content h2 { margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.02em; }

.dashboard-card { background: var(--card-bg); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur); border: 1px solid var(--card-border); border-radius: 28px; padding: 30px; box-shadow: var(--shadow-drop), var(--shadow-inner); color: var(--text-secondary); font-size: 15px; line-height: 1.6; }

.plans-switch { display: flex; gap: 8px; background: var(--input-bg); padding: 6px; border-radius: 20px; border: 1px solid var(--input-border); margin-bottom: 16px; }
.plan-sub-btn { flex: 1; background: transparent; color: var(--text-secondary); border: none; padding: 12px; border-radius: 14px; font-weight: 600; cursor: pointer; transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); }
.plan-sub-btn:hover { transform: scale(1.02); }
.plan-sub-btn.active { background: var(--card-border); color: var(--text-primary); box-shadow: var(--shadow-drop); transform: scale(1.03); }

.plan-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
.plan-card { background: var(--input-bg); border: 1px solid var(--input-border); padding: 20px; border-radius: 20px; display: flex; flex-direction: column; gap: 10px; transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); }
.plan-card:hover { transform: scale(1.03) translateY(-4px); }
.plan-card h4 { margin: 0; font-size: 18px; color: var(--text-primary); }
.plan-card .price { font-size: 13px; color: var(--accent); font-weight: 700; }
.plan-card p { font-size: 13px; margin: 0; flex: 1; }

.profile-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 16px; }
.profile-item { background: var(--input-bg); border: 1px solid var(--input-border); padding: 16px; border-radius: 16px; display: flex; flex-direction: column; gap: 4px; }
.profile-label { font-size: 11px; text-transform: uppercase; color: var(--text-secondary); letter-spacing: 1px; }
.profile-value { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.dev-approved-badge { color: var(--success); opacity: 0.5; font-weight: 700; }

.action-btn { background: var(--input-bg); color: var(--text-primary); border: 1px solid var(--input-border); padding: 14px 20px; border-radius: 16px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); }
.action-btn:hover { background: var(--card-border); transform: scale(1.03) translateY(-2px); box-shadow: 0 6px 15px rgba(0,0,0,0.2); }
.action-btn:active { transform: scale(0.97); }
.danger-btn { color: var(--error); }
.danger-btn:hover { background: rgba(234, 21, 21, 0.1); border-color: var(--error); }
.support-btn { opacity: 0.5; }
.support-btn:hover { opacity: 1; }

.script-card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 28px; overflow: hidden; display: flex; flex-direction: column; transition: transform 0.3s ease; }
.script-card:hover { transform: scale(1.01); }
.script-banner { width: 100%; height: 140px; background: url('https://static.wikia.nocookie.net/muscle-legends/images/5/50/Wiki-background/revision/latest/scale-to-width-down/670?cb=20210320061506') no-repeat center center, var(--input-bg); background-size: cover; position: relative; display: flex; justify-content: center; padding-top: 20px; }
.script-banner::after { content: ''; position: absolute; bottom: -1px; left: 0; width: 100%; height: 70px; background: linear-gradient(to bottom, transparent, var(--bg-color)); opacity: 0.85; }
.banner-title { position: relative; z-index: 2; color: #ffffff; font-size: 20px; font-weight: 800; letter-spacing: 4px; text-transform: uppercase; text-shadow: 0 4px 12px rgba(0,0,0,1); }
.script-content { padding: 0 24px 24px 24px; position: relative; z-index: 2; display: flex; flex-direction: column; gap: 10px; }
.script-header h3 { margin: 0; font-size: 20px; color: var(--text-primary); display: flex; align-items: center; gap: 10px; }
.game-tag { font-size: 13px; font-weight: 500; opacity: 0.5; }
.script-desc { margin: 0; font-size: 14px; color: var(--text-secondary); line-height: 1.5; }
.script-stats { display: flex; gap: 10px; margin-top: 2px; }
.stat-item { display: flex; align-items: center; gap: 4px; font-size: 13px; font-weight: 600; color: var(--text-secondary); background: var(--input-bg); padding: 6px 12px; border-radius: 12px; border: 1px solid var(--input-border); }
.copy-btn { background: var(--accent); color: var(--accent-text); border: none; padding: 14px; border-radius: 16px; font-weight: 700; font-family: 'Inter', monospace; cursor: pointer; text-transform: uppercase; font-size: 14px; transition: all 0.3s ease; }
.copy-btn:hover { transform: scale(1.02); }

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

  <canvas id="bgCanvas"></canvas>
  <div class="ocean"><div class="wave"></div><div class="wave"></div><div class="wave"></div></div>

  <div class="top-bar">
    <div class="top-bar-left">
      <div class="ui-pill" id="clockWrapper" style="{{ 'display:none;' if not current_user else 'display:flex;' }}"><div class="recording-dot"></div><span id="clock">00:00:00</span></div>
      <button class="ui-pill theme-toggle" id="themeBtn">Light Mode</button>
    </div>
    <div class="top-bar-right" id="userWrapper" style="{{ 'display:none;' if not current_user else 'display:flex;' }}">
      <div class="ui-pill" id="userDisplay" title="Click to open Profile">{{ current_user or '' }}</div>
      <button class="ui-pill logout-btn" id="logoutBtn">Logout</button>
    </div>
  </div>

  <div class="app-content">
    <div class="header" id="mainHeader">
      <img src="https://raw.githubusercontent.com/Rob4ik02/RobloxScripts/refs/heads/main/icon.png" alt="" />
      <h1>Global Script's</h1>
    </div>

    <div class="form-container" id="authForm" style="{{ 'display:none;' if current_user else 'display:flex;' }}">
      <input type="text" id="login" placeholder="Login" autocomplete="off" />
      <input type="password" id="password" placeholder="Password" />
      <button id="signUpBtn">Authorize</button>
      <div id="message"></div>
      
      <div class="create-link-wrapper" id="createAccountWrapper">
        <div class="create-link" id="createAccountLink">Dont have an account? Create it!</div>
      </div>
    </div>

    <div class="form-container" id="twoFaForm" style="display:none;">
      <p class="form-header-text">Bot Protection</p>
      <p style="font-size: 12px; color: var(--text-secondary); text-align: center; margin-top: 0;">We sent a 6-digit code to your email. Valid for 15 minutes.</p>
      <input type="text" id="twoFaCode" placeholder="Enter Code" autocomplete="off" />
      <button id="verifyBtn">Verify</button>
      <div id="twoFaMessage"></div>
      <div class="back-link" id="cancel2FaLink">Cancel</div>
    </div>

    <div class="form-container" id="regForm" style="display:none;">
      <p class="form-header-text">Describe yourself for the account.</p>
      <input type="text" id="regLogin" placeholder="Login" autocomplete="off" />
      <input type="password" id="regPassword" placeholder="Password" />
      <input type="text" id="regEmail" class="email-input" placeholder="Enter your email to protect against bots (Optional)" autocomplete="off" />
      <input type="text" id="regSecret" placeholder="Secret word if you forgot password" autocomplete="off" />
      <input type="text" id="regSource" placeholder="How did you hear about us?" autocomplete="off" />
      
      <label class="checkbox-container">
        <input type="checkbox" id="regAgree">
        I agree to the privacy cookies and am ready to create an account
      </label>

      <button id="regBtn" disabled>Create account</button>
      <div id="regMessage"></div>
      <div class="back-link" id="backToLoginLink">Back to Login</div>
    </div>

    <div class="loader-container" id="loaderScreen">
      <div class="spinner"></div>
      <div class="loader-text">Authenticating System...</div>
    </div>

    <div class="dashboard-layout" id="dashboardLayout">
      <div class="sidebar">
        <h2>Menu</h2>
        <div class="sidebar-nav">
          <button class="sidebar-btn active" data-target="tab-main"><div class="btn-title">Main</div><div class="btn-desc">Your main profile - it's you.</div></button>
          <button class="sidebar-btn" data-target="tab-keys"><div class="btn-title">Key System</div><div class="btn-desc">Get a key to unlock free access.</div></button>
          <button class="sidebar-btn" data-target="tab-scripts"><div class="btn-title">Scripts</div><div class="btn-desc">Current game scripts.</div></button>
          <button class="sidebar-btn" data-target="tab-plans"><div class="btn-title">Plans</div><div class="btn-desc">Buy plans to get more functional abilities!</div></button>
          <button class="sidebar-btn" data-target="tab-faq"><div class="btn-title">FAQ</div><div class="btn-desc">Got questions? We answer fast!</div></button>
        </div>
        <div class="sidebar-footer">
          <button class="sidebar-btn sidebar-btn-footer" data-target="tab-developers"><div class="btn-title">Developers</div><div class="btn-desc">Website and script creators.</div></button>
          <button class="sidebar-btn sidebar-btn-footer" data-target="tab-discord"><div class="btn-title">Discord</div><div class="btn-desc">We're also in chat!</div></button>
        </div>
      </div>
      
      <div class="main-content">
        <div class="tab-content active" id="tab-main">
          <h2>User Profile</h2>
          <div class="dashboard-card">
            <p style="color: var(--text-primary); font-weight: 600; font-size: 18px; margin-bottom: 4px;">Account Details</p>
            <p style="margin-top: 0; font-size: 14px;">Here is your personal overview registered in the system.</p>
            <div class="profile-grid">
              <div class="profile-item"><span class="profile-label">Login</span><span class="profile-value" id="profileLogin">--</span></div>
              <div class="profile-item"><span class="profile-label">Current Plan</span><span class="profile-value" id="profilePlan">--</span></div>
              <div class="profile-item"><span class="profile-label">Registration Date</span><span class="profile-value" id="profileRegDate">--</span></div>
              <div class="profile-item"><span class="profile-label">Developer Approved</span><span class="profile-value dev-approved-badge" id="profileDevApproved">--</span></div>
            </div>
          </div>
        </div>

        <div class="tab-content" id="tab-keys">
          <h2>Key Generator</h2>
          <div class="dashboard-card"><p style="color: var(--text-primary); font-weight: 600; font-size: 18px; margin-bottom: 8px;">Unlock Free Access</p><p>Create unique HWID keys for your Roblox scripts.</p><button class="action-btn" style="margin-top: 10px;">Generate New Key</button></div>
        </div>

        <div class="tab-content" id="tab-scripts">
          <h2>Scripts Library</h2>
          <div class="script-card">
            <div class="script-banner"><div class="banner-title">MUSCLE LEGENDS</div></div>
            <div class="script-content">
              <div class="script-header"><h3>Oxygen Hub Script <span class="game-tag">for game: Muscle Legends</span></h3></div>
              <p class="script-desc">Good script, works in beta version. There are some bugs or errors. They say it will be updated and will be the best script.</p>
              <div class="script-stats">
                <div class="stat-item">👍 0</div><div class="stat-item">👎 0</div><div class="stat-item">⭐ Unrated</div>
              </div>
              <button class="copy-btn" onclick="copyLuaScript(this)">Click to Copy Lua Script</button>
            </div>
          </div>
        </div>

        <div class="tab-content" id="tab-plans">
          <h2>Upgrade Plans</h2>
          <div class="plans-switch">
            <button class="plan-sub-btn active" id="btnBuyPlan" onclick="switchPlanSubTab('buy')">Buy Plan</button>
            <button class="plan-sub-btn" id="btnMyPlan" onclick="switchPlanSubTab('my')">My Current Plan</button>
          </div>
          
          <div id="planBuySection">
            <div class="plan-grid">
              <div class="plan-card"><h4>Starter Plan</h4><div class="price">7 Days</div><p>Little access, but works perfectly for beginners.</p><button class="action-btn">Purchase</button></div>
              <div class="plan-card"><h4>Professional Plan</h4><div class="price">30 Days</div><p>More access, developer contact, and advanced features.</p><button class="action-btn">Purchase</button></div>
              <div class="plan-card"><h4>Extreme Plan</h4><div class="price">90 Days</div><p>All access, 24/7 support. You have everything.</p><button class="action-btn">Purchase</button></div>
            </div>
          </div>

          <div id="planMySection" style="display: none;">
             <div class="dashboard-card" style="display: flex; flex-direction: column; gap: 12px;">
               <h3 id="planGreeting" style="margin: 0; color: var(--text-primary); font-size: 22px;">Hi!</h3>
               <p id="planCurrentStatus" style="margin:0; font-weight: 600; color: var(--accent);">Your current plan: --</p>
               <p id="planDesc" style="margin:0;">All basic features unlocked.</p>
               <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px;">
                  <button class="action-btn" onclick="restartPlan()">Restart Plan</button>
                  <button class="action-btn danger-btn" onclick="deleteAccount()">Delete Account</button>
                  <button class="action-btn support-btn" id="supportBtn" onclick="contactSupport()">Contact Support</button>
               </div>
             </div>
          </div>
        </div>
        
        <div class="tab-content" id="tab-faq"><h2>FAQ</h2><div class="dashboard-card"><p>Got questions? We answer fast!</p></div></div>
        <div class="tab-content" id="tab-developers"><h2>Developers</h2><div class="dashboard-card"><p>Meet the team behind Global Script's. We build the architecture, you enjoy the results.</p></div></div>
        <div class="tab-content" id="tab-discord"><h2>Community</h2><div class="dashboard-card"><p>Join our Discord server. Connect with other users, share scripts, and stay updated!</p></div></div>
      </div>
    </div>
  </div>

<script>
  function showMessage(elementId, text, isSuccess) {
    const el = document.getElementById(elementId);
    el.innerText = text;
    el.className = isSuccess ? 'success-msg show' : 'error-msg show';
  }
  function hideMessage(elementId) { document.getElementById(elementId).classList.remove('show'); }

  function contactSupport() {
    const btn = document.getElementById('supportBtn');
    const original = btn.innerText;
    btn.innerText = "This feature will be available soon!";
    btn.style.opacity = "1";
    setTimeout(() => { btn.innerText = original; btn.style.opacity = "0.5"; }, 3000);
  }

  function restartPlan() {
    fetch('/restart_plan', { method: 'POST' }).then(res => res.json()).then(data => {
      if(data.success) {
        document.getElementById('planCurrentStatus').innerText = "Your current plan: " + data.plan + " - " + data.days + " Days";
        alert("Plan restarted successfully!");
      }
    });
  }

  function deleteAccount() {
    if(confirm("Are you sure you want to completely delete your account? This action cannot be undone.")) {
      fetch('/delete_account', { method: 'POST' }).then(() => window.location.reload());
    }
  }

  function switchPlanSubTab(tab) {
    document.getElementById('btnBuyPlan').classList.remove('active');
    document.getElementById('btnMyPlan').classList.remove('active');
    document.getElementById('planBuySection').style.display = 'none';
    document.getElementById('planMySection').style.display = 'none';
    if(tab === 'buy') {
      document.getElementById('btnBuyPlan').classList.add('active');
      document.getElementById('planBuySection').style.display = 'block';
    } else {
      document.getElementById('btnMyPlan').classList.add('active');
      document.getElementById('planMySection').style.display = 'block';
    }
  }

  function copyLuaScript(btn) {
    const luaCode = 'loadstring(game:HttpGet("https://raw.githubusercontent.com/Rob4ik02/Muscle-Legends-Roblox/refs/heads/main/Muscle%20Legends/Sirius%20Library/Loader.lua"))()';
    navigator.clipboard.writeText(luaCode).then(() => {
      const originalText = btn.innerText;
      btn.innerText = 'Copied successfully!';
      btn.style.backgroundColor = 'var(--success)';
      btn.style.color = '#fff';
      setTimeout(() => { btn.innerText = originalText; btn.style.backgroundColor = ''; btn.style.color = ''; }, 2000);
    });
  }

  const canvas = document.getElementById('bgCanvas'); const ctx = canvas.getContext('2d');
  let width, height, particles = [], mouse = { x: -1000, y: -1000 }, currentDotColor = 'rgba(255, 255, 255, 0.3)', isErrorState = false, globalSpeedBoost = 0; 
  function updateCanvasColor() { currentDotColor = getComputedStyle(document.body).getPropertyValue('--dot-color').trim(); }
  function resize() { width = canvas.width = window.innerWidth; height = canvas.height = window.innerHeight; initParticles(); }
  window.addEventListener('resize', resize);
  
  class Particle {
    constructor() { this.x = Math.random() * width; this.y = Math.random() * height; this.size = Math.random() * 2 + 1; this.density = (Math.random() * 20) + 5; this.angle = Math.random() * 360; this.speed = Math.random() * 0.3 + 0.1; this.vx = 0; this.vy = 0; this.friction = 0.92; }
    update() {
      this.angle += 0.01; this.vy -= this.speed * 0.1; this.vx += Math.sin(this.angle) * 0.05; this.y -= globalSpeedBoost * (this.speed * 1.5);
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
  themeBtn.innerText = (localStorage.getItem('theme') || 'dark') === 'dark' ? 'Light Mode' : 'Dark Mode';
  updateCanvasColor();
  themeBtn.addEventListener('click', () => {
    const newTheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme); localStorage.setItem('theme', newTheme);
    themeBtn.innerText = newTheme === 'dark' ? 'Light Mode' : 'Dark Mode'; updateCanvasColor();
  });
  function updateClock() { fetch('/get_time').then(res => res.json()).then(data => { document.getElementById('clock').innerText = data.time; }); }
  setInterval(updateClock, 1000); updateClock();

  const sidebarBtns = document.querySelectorAll('.sidebar-btn');
  const tabContents = document.querySelectorAll('.tab-content');
  function switchTab(targetId) {
    globalSpeedBoost = 30; 
    sidebarBtns.forEach(b => b.classList.remove('active')); tabContents.forEach(t => t.classList.remove('active'));
    sidebarBtns.forEach(b => { if(b.getAttribute('data-target') === targetId) b.classList.add('active'); }); document.getElementById(targetId).classList.add('active');
  }
  sidebarBtns.forEach(btn => btn.addEventListener('click', () => switchTab(btn.getAttribute('data-target'))));
  document.getElementById('userDisplay').addEventListener('click', () => switchTab('tab-main'));

  document.addEventListener('DOMContentLoaded', () => {
    const authForm = document.getElementById('authForm');
    const regForm = document.getElementById('regForm');
    const twoFaForm = document.getElementById('twoFaForm');
    const createAccountWrapper = document.getElementById('createAccountWrapper');
    
    document.getElementById('createAccountLink').addEventListener('click', () => { authForm.style.display = 'none'; regForm.style.display = 'flex'; globalSpeedBoost = 15; });
    document.getElementById('backToLoginLink').addEventListener('click', () => { regForm.style.display = 'none'; authForm.style.display = 'flex'; globalSpeedBoost = 15; createAccountWrapper.classList.remove('show'); hideMessage('message'); });
    document.getElementById('cancel2FaLink').addEventListener('click', () => { twoFaForm.style.display = 'none'; authForm.style.display = 'flex'; });

    const regAgree = document.getElementById('regAgree');
    const regBtn = document.getElementById('regBtn');
    regAgree.addEventListener('change', (e) => { regBtn.disabled = !e.target.checked; });

    regBtn.addEventListener('click', () => {
      const login = document.getElementById('regLogin').value.trim();
      const password = document.getElementById('regPassword').value;
      const email = document.getElementById('regEmail').value.trim();
      const secret = document.getElementById('regSecret').value.trim();
      const source = document.getElementById('regSource').value.trim();

      if (!login || !password || !secret || !source) { showMessage('regMessage', 'Please fill all required fields.', false); return; }

      fetch('/register', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ login, password, email, secret, source })
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
                document.getElementById('userDisplay').innerText = data.login;
                document.getElementById('profileLogin').innerText = data.login;
                document.getElementById('profilePlan').innerText = data.plan;
                document.getElementById('profileRegDate').innerText = data.reg_date;
                document.getElementById('profileDevApproved').innerText = data.dev_approved;
                document.getElementById('planGreeting').innerText = data.greeting;
                document.getElementById('planCurrentStatus').innerText = "Your current plan: " + data.plan + " - " + data.plan_days + " Days";
            }
        });
    }

    function triggerErrorAnimation(formEl) {
      formEl.classList.remove('shake-error');
      setTimeout(() => formEl.classList.add('shake-error'), 10);
      setTimeout(() => formEl.classList.remove('shake-error'), 400);
      isErrorState = true; setTimeout(() => { isErrorState = false; }, 600);
    }

    document.getElementById('logoutBtn').addEventListener('click', () => fetch('/logout').then(() => window.location.reload()));

    document.getElementById('signUpBtn').addEventListener('click', () => {
      const login = document.getElementById('login').value.trim();
      const password = document.getElementById('password').value;
      if (!login || !password) { showMessage('message', 'Empty fields detected.', false); triggerErrorAnimation(authForm); createAccountWrapper.classList.add('show'); return; }

      fetch('/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ login, password })
      }).then(res => res.json()).then(data => {
        if (data.success) {
          if(data.require_2fa) {
             authForm.style.display = 'none';
             twoFaForm.style.display = 'flex';
          } else {
             hideMessage('message'); authForm.style.display = 'none'; document.getElementById('mainHeader').style.display = 'none'; document.getElementById('loaderScreen').style.display = 'flex';
             setTimeout(() => { document.getElementById('clockWrapper').style.display = 'flex'; document.getElementById('userWrapper').style.display = 'flex'; document.getElementById('loaderScreen').style.display = 'none'; loadDashboard(); }, 1500);
          }
        } else { showMessage('message', 'Invalid credentials.', false); triggerErrorAnimation(authForm); createAccountWrapper.classList.add('show'); }
      });
    });

    document.getElementById('verifyBtn').addEventListener('click', () => {
       const code = document.getElementById('twoFaCode').value.trim();
       fetch('/verify_2fa', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code })
       }).then(res => res.json()).then(data => {
          if(data.success) {
             twoFaForm.style.display = 'none'; document.getElementById('mainHeader').style.display = 'none'; document.getElementById('loaderScreen').style.display = 'flex';
             setTimeout(() => { document.getElementById('clockWrapper').style.display = 'flex'; document.getElementById('userWrapper').style.display = 'flex'; document.getElementById('loaderScreen').style.display = 'none'; loadDashboard(); }, 1500);
          } else { showMessage('twoFaMessage', data.message, false); triggerErrorAnimation(twoFaForm); }
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
    return render_template_string(TEMPLATE, current_user=session.get('user'))

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
        return jsonify({
            'success': True,
            'login': user['login'],
            'plan': user['plan'],
            'plan_days': user['plan_days'],
            'reg_date': user['reg_date'],
            'dev_approved': user['dev_approved'],
            'greeting': random.choice(greetings)
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
        if user['email'] and user['email'].strip() != '':
            code = str(random.randint(100000, 999999))
            session['pending_user'] = login_input
            session['2fa_code'] = code
            session['2fa_expiry'] = time.time() + 900
            
            c_log('WARNING', f"2FA Triggered for {login_input}. Generating code...")
            email_sent = send_real_email(user['email'], code)
            
            if email_sent:
                c_log('SUCCESS', f"2FA code successfully emailed to {user['email']}")
            else:
                c_log('ERROR', f"Failed to send 2FA email. Fallback - Code is: {code}")
                
            return jsonify({'success': True, 'require_2fa': True})
        else:
            session['user'] = login_input
            c_log('SUCCESS', f"User {login_input} logged in successfully.")
            return jsonify({'success': True, 'require_2fa': False})
    else:
        c_log('ERROR', f"Invalid credentials provided for {login_input}.")
        return jsonify({'success': False, 'message': 'Invalid credentials'})

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
        INSERT INTO users (login, password_hash, email, secret, source, reg_date, plan, plan_days, dev_approved)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (login_input, generate_password_hash(password_input), email_input, secret_input, source_input, reg_date, 'Free Tier', 0, 'No'))
    conn.commit()
    conn.close()
    
    c_log('SUCCESS', f"New account created successfully for {login_input}.")
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
    c_log('SERVICE', "Starting server on port 5000...")
    app.run(debug=True)
