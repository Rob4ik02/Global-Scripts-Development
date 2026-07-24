import os
from flask import Flask, render_template_string, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pytz

app = Flask(__name__)

# БЕЗОПАСНОСТЬ: Ключ берется из переменных окружения сервера. Если его нет - используется запасной.
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-dev-secret-key-123')

# Хранилище пользователей (ПАРОЛИ ТЕПЕРЬ ЗАХЕШИРОВАНЫ)
users = [
    {
        'login': 'Rob4ik', 
        'password_hash': generate_password_hash('secret'), 
        'reg_date': '14.05.2026', 
        'plan': 'Developer Tier', 
        'dev_approved': 'Yes'
    },
    {
        'login': 'PQruX', 
        'password_hash': generate_password_hash('pqrux'), 
        'reg_date': '25.07.2026', 
        'plan': 'Helper Tier', 
        'dev_approved': 'Yes'
    },
]

# HTML-шаблон
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
/* Тематические переменные (Liquid Glass: Apple + Nothing) */
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
  --shadow-drop: 0 16px 40px rgba(0, 0, 0, 0.6);
  --shadow-inner: inset 0 1px 1px rgba(255, 255, 255, 0.1);
  --blur: blur(28px) saturate(180%);
  --dot-color: rgba(255, 255, 255, 0.3);
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
  --shadow-drop: 0 16px 40px rgba(0, 0, 0, 0.08);
  --shadow-inner: inset 0 1px 1px rgba(255, 255, 255, 0.8);
  --dot-color: rgba(0, 0, 0, 0.2);
}

* {
  box-sizing: border-box;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  margin: 0;
  padding: 0;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background-color: var(--bg-color);
  color: var(--text-primary);
  transition: background-color 0.6s cubic-bezier(0.4, 0, 0.2, 1), color 0.6s ease;
  overflow-x: hidden;
}

#bgCanvas {
  position: fixed;
  top: 0; left: 0;
  width: 100vw; height: 100vh;
  z-index: -1;
  opacity: 0;
  animation: fadeInCanvas 2s ease-in-out forwards;
}
@keyframes fadeInCanvas { to { opacity: 1; } }

.app-content {
  opacity: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  padding-top: 80px;
  animation: liquidReveal 1.2s cubic-bezier(0.16, 1, 0.3, 1) 0.3s forwards;
}

@keyframes liquidReveal {
  0% { opacity: 0; transform: translateY(30px) scale(0.98); }
  100% { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes elasticBounce {
  0% { transform: scale(0.9) translateY(15px); opacity: 0; }
  45% { transform: scale(1.02) translateY(-4px); opacity: 1; }
  75% { transform: scale(0.99) translateY(2px); }
  100% { transform: scale(1) translateY(0); opacity: 1; }
}

@keyframes errorShake {
  0%, 100% { transform: translateX(0); }
  20%, 60% { transform: translateX(-8px) scale(0.99); }
  40%, 80% { transform: translateX(8px) scale(1.01); }
}
.shake-error {
  animation: errorShake 0.4s cubic-bezier(0.36, 0.07, 0.19, 0.97) forwards;
}

.top-bar {
  position: fixed;
  top: 0; left: 0;
  width: 100vw;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 40px;
  z-index: 100;
  background: transparent;
}

.top-bar-left, .top-bar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ui-pill {
  background: var(--card-bg);
  backdrop-filter: var(--blur);
  -webkit-backdrop-filter: var(--blur);
  border: 1px solid var(--card-border);
  box-shadow: var(--shadow-drop), var(--shadow-inner);
  color: var(--text-primary);
  padding: 10px 20px;
  border-radius: 98px;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 10px;
  transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1), background 0.3s ease;
}

.ui-pill:hover { transform: scale(1.05); }
#userDisplay { cursor: pointer; }
#userDisplay:hover { border-color: var(--text-primary); }

.recording-dot {
  width: 8px; height: 8px;
  background-color: var(--error);
  border-radius: 50%;
  animation: liquidBlink 2.5s infinite ease-in-out;
}

@keyframes liquidBlink {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.8); }
}

.theme-toggle { cursor: pointer; }
.logout-btn { cursor: pointer; color: var(--error); }
.logout-btn:hover { background: var(--error); color: #fff; border-color: var(--error); }

.header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  margin-bottom: 40px;
}

.header img {
  width: 84px; height: 84px;
  border-radius: 24px;
  box-shadow: var(--shadow-drop), var(--shadow-inner);
  border: 1px solid var(--card-border);
  transition: transform 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.header img:hover { transform: scale(1.1) rotate(4deg); }

.header h1 {
  margin: 0;
  font-size: 38px;
  font-weight: 700;
  letter-spacing: -0.04em;
}

.form-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  background: var(--card-bg);
  backdrop-filter: var(--blur);
  -webkit-backdrop-filter: var(--blur);
  padding: 44px;
  border: 1px solid var(--card-border);
  border-radius: 36px;
  box-shadow: var(--shadow-drop), var(--shadow-inner);
  width: 90%;
  max-width: 400px;
}

.form-container input {
  width: 100%;
  padding: 18px 20px;
  font-size: 16px;
  font-family: inherit;
  font-weight: 500;
  color: var(--text-primary);
  background: var(--input-bg);
  border: 1px solid var(--input-border);
  border-radius: 20px;
  outline: none;
  transition: all 0.3s cubic-bezier(0.25, 1, 0.5, 1);
}

.form-container input::placeholder { color: var(--text-secondary); }
.form-container input:focus { 
  border-color: var(--text-primary); 
  transform: scale(1.02);
  background: rgba(255, 255, 255, 0.1);
}

.form-container button {
  width: 100%;
  padding: 18px;
  font-size: 16px;
  font-family: inherit;
  font-weight: 700;
  color: var(--accent-text);
  background: var(--accent);
  border: none;
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  margin-top: 8px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.form-container button:hover { 
  transform: translateY(-2px) scale(1.02);
  box-shadow: 0 8px 20px rgba(255, 255, 255, 0.2);
}
.form-container button:active { transform: scale(0.95); }

#message {
  font-weight: 600;
  font-size: 14px;
  text-align: center;
  min-height: 20px;
  transition: color 0.3s ease;
}
.success-msg { color: #34c759; }
.error-msg { color: var(--error); }

.loader-container {
  display: none;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  margin-top: 60px;
}

.spinner {
  width: 54px; height: 54px;
  border: 4px solid var(--input-border);
  border-top: 4px solid var(--accent);
  border-radius: 50%;
  animation: spin 1s cubic-bezier(0.6, 0.2, 0.4, 0.8) infinite;
}

@keyframes spin { 
  0% { transform: rotate(0deg); } 
  100% { transform: rotate(360deg); } 
}

.loader-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-secondary);
  letter-spacing: 2px;
  animation: liquidBlink 2s infinite ease-in-out;
}

.dashboard-layout {
  display: none;
  width: 100%;
  max-width: 1200px;
  min-height: 65vh;
  gap: 24px;
  padding: 0 24px;
  padding-bottom: 40px;
}

.sidebar {
  flex: 0 0 300px;
  background: var(--card-bg);
  backdrop-filter: var(--blur);
  -webkit-backdrop-filter: var(--blur);
  border: 1px solid var(--card-border);
  border-radius: 36px;
  padding: 28px;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-drop), var(--shadow-inner);
}

.sidebar h2 {
  margin: 0 0 20px 0;
  font-size: 16px;
  text-transform: uppercase;
  color: var(--text-secondary);
  letter-spacing: 1.5px;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
}

.sidebar-footer {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--card-border);
}

.sidebar-btn {
  background: transparent;
  color: var(--text-primary);
  border: none;
  padding: 14px 18px;
  border-radius: 20px;
  font-family: inherit;
  cursor: pointer;
  text-align: left;
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sidebar-btn:hover { 
  background: var(--input-border); 
  transform: translateX(4px);
}
.sidebar-btn.active {
  background: var(--text-primary);
  color: var(--bg-color);
  transform: scale(1.05);
  box-shadow: 0 8px 20px rgba(0,0,0,0.2);
}

.sidebar-btn.active .btn-desc { color: var(--bg-color); opacity: 0.8; }
.sidebar-btn-footer { opacity: 0.5; }
.sidebar-btn-footer:hover { opacity: 1; }
.btn-title { font-weight: 600; font-size: 15px; text-transform: uppercase; }
.btn-desc { font-weight: 400; font-size: 12px; color: var(--text-secondary); line-height: 1.3; }

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
}

.tab-content {
  display: none;
  flex-direction: column;
  gap: 24px;
}
.tab-content.active {
  display: flex;
  animation: elasticBounce 0.8s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}

.tab-content h2 {
  margin: 0;
  font-size: 34px;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.dashboard-card {
  background: var(--card-bg);
  backdrop-filter: var(--blur);
  -webkit-backdrop-filter: var(--blur);
  border: 1px solid var(--card-border);
  border-radius: 36px;
  padding: 44px;
  box-shadow: var(--shadow-drop), var(--shadow-inner);
  color: var(--text-secondary);
  font-size: 16px;
  line-height: 1.6;
}

/* Профиль */
.profile-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-top: 20px;
}
.profile-item {
  background: var(--input-bg);
  border: 1px solid var(--input-border);
  padding: 20px;
  border-radius: 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.profile-label {
  font-size: 12px;
  text-transform: uppercase;
  color: var(--text-secondary);
  letter-spacing: 1px;
}
.profile-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}
.dev-approved-badge {
  color: var(--success);
  opacity: 0.5;
  font-weight: 700;
}

/* --- СТИЛИ ДЛЯ КАРТОЧКИ СКРИПТА С НОВЫМ ИЗОБРАЖЕНИЕМ --- */
.script-card {
  background: var(--card-bg);
  backdrop-filter: var(--blur);
  -webkit-backdrop-filter: var(--blur);
  border: 1px solid var(--card-border);
  border-radius: 36px;
  overflow: hidden;
  box-shadow: var(--shadow-drop), var(--shadow-inner);
  display: flex;
  flex-direction: column;
  transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.script-card:hover { transform: scale(1.02); }

.script-banner {
  width: 100%;
  height: 180px;
  /* Изображение обновлено по твоей ссылке */
  background: url('https://static.wikia.nocookie.net/muscle-legends/images/5/50/Wiki-background/revision/latest/scale-to-width-down/670?cb=20210320061506') no-repeat center center, var(--input-bg);
  background-size: cover;
  position: relative;
  display: flex;
  justify-content: center;
  padding-top: 25px;
}

.script-banner::after {
  content: '';
  position: absolute;
  bottom: -1px; left: 0; width: 100%; height: 90px;
  background: linear-gradient(to bottom, transparent, var(--bg-color));
  opacity: 0.85;
}

.banner-title {
  position: relative;
  z-index: 2;
  color: #ffffff;
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 5px;
  text-transform: uppercase;
  text-shadow: 0 4px 16px rgba(0,0,0,1);
}

.script-content {
  padding: 0 36px 36px 36px;
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.script-header h3 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.game-tag {
  font-size: 15px;
  font-weight: 500;
  opacity: 0.5;
  text-transform: lowercase;
}

.script-desc {
  margin: 0;
  font-size: 15px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.script-stats {
  display: flex;
  gap: 12px;
  margin-top: 4px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--input-bg);
  padding: 8px 16px;
  border-radius: 16px;
  border: 1px solid var(--input-border);
}

.copy-btn {
  background: var(--accent);
  color: var(--accent-text);
  border: none;
  padding: 16px 24px;
  border-radius: 20px;
  font-weight: 700;
  font-family: 'Inter', monospace;
  cursor: pointer;
  margin-top: 8px;
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.copy-btn:hover { transform: scale(1.03); }
.copy-btn:active { transform: scale(0.97); }

.gen-btn {
  background: var(--accent);
  color: var(--accent-text);
  border: none;
  padding: 16px 24px;
  border-radius: 20px;
  font-weight: 700;
  font-family: inherit;
  cursor: pointer;
  margin-top: 20px;
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.gen-btn:hover { transform: scale(1.05); }
.gen-btn:active { transform: scale(0.95); }

/* Адаптивность */
@media (max-width: 900px) {
  .top-bar { padding: 16px 20px; }
  .dashboard-layout { flex-direction: column; padding: 0 16px; }
  .sidebar { flex: none; width: 100%; padding: 16px; border-radius: 28px; }
  .sidebar h2 { display: none; }
  .sidebar-nav, .sidebar-footer { flex-direction: row; overflow-x: auto; border-top: none; margin-top: 0; padding-top: 0; }
  .sidebar-footer { margin-left: 10px; }
  .btn-desc { display: none; }
  .sidebar-btn { padding: 12px 20px; align-items: center; justify-content: center; white-space: nowrap;}
  .dashboard-card { padding: 30px; border-radius: 28px; }
  .profile-grid { grid-template-columns: 1fr; }
  .script-content { padding: 0 24px 24px 24px; }
}
@media (max-width: 480px) {
  .top-bar { flex-direction: column; gap: 12px; padding: 12px; }
  .app-content { padding-top: 130px; }
  .header h1 { font-size: 32px; }
  .form-container { padding: 32px 24px; border-radius: 28px; }
  .script-stats { flex-wrap: wrap; }
}
</style>
</head>
<body>

  <canvas id="bgCanvas"></canvas>

  <div class="top-bar">
    <div class="top-bar-left">
      <div class="ui-pill" id="clockWrapper" style="{{ 'display:none;' if not current_user else 'display:flex;' }}">
        <div class="recording-dot"></div>
        <span id="clock">00:00:00</span>
      </div>
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
      <input type="text" id="login" placeholder="Username" autocomplete="off" />
      <input type="password" id="password" placeholder="Password" />
      <button id="signUpBtn">Authorize</button>
      <div id="message"></div>
    </div>

    <div class="loader-container" id="loaderScreen">
      <div class="spinner"></div>
      <div class="loader-text">Authenticating System...</div>
    </div>

    <div class="dashboard-layout" id="dashboardLayout">
      <div class="sidebar">
        <h2>Menu</h2>
        <div class="sidebar-nav">
          <button class="sidebar-btn active" data-target="tab-main">
            <div class="btn-title">Main</div>
            <div class="btn-desc">Your main profile - it's you.</div>
          </button>
          <button class="sidebar-btn" data-target="tab-keys">
            <div class="btn-title">Key System</div>
            <div class="btn-desc">Get a key to unlock free access.</div>
          </button>
          <button class="sidebar-btn" data-target="tab-scripts">
            <div class="btn-title">Scripts</div>
            <div class="btn-desc">Current game scripts.</div>
          </button>
          <button class="sidebar-btn" data-target="tab-plans">
            <div class="btn-title">Plans</div>
            <div class="btn-desc">Buy plans to get more functional abilities and level up faster!</div>
          </button>
          <button class="sidebar-btn" data-target="tab-faq">
            <div class="btn-title">FAQ</div>
            <div class="btn-desc">Got questions? We answer fast!</div>
          </button>
        </div>
        <div class="sidebar-footer">
          <button class="sidebar-btn sidebar-btn-footer" data-target="tab-developers">
            <div class="btn-title">Developers</div>
            <div class="btn-desc">Website and script creators.</div>
          </button>
          <button class="sidebar-btn sidebar-btn-footer" data-target="tab-discord">
            <div class="btn-title">Discord</div>
            <div class="btn-desc">We're not only on the site, but also in chat!</div>
          </button>
        </div>
      </div>
      
      <div class="main-content">
        <!-- Main -->
        <div class="tab-content active" id="tab-main">
          <h2>User Profile</h2>
          <div class="dashboard-card">
            <p style="color: var(--text-primary); font-weight: 600; font-size: 20px; margin-bottom: 4px;">Account Details</p>
            <p style="margin-top: 0;">Here is your personal overview registered in the system.</p>
            
            <div class="profile-grid">
              <div class="profile-item">
                <span class="profile-label">Login</span>
                <span class="profile-value" id="profileLogin">--</span>
              </div>
              <div class="profile-item">
                <span class="profile-label">Current Plan</span>
                <span class="profile-value" id="profilePlan">--</span>
              </div>
              <div class="profile-item">
                <span class="profile-label">Registration Date</span>
                <span class="profile-value" id="profileRegDate">--</span>
              </div>
              <div class="profile-item">
                <span class="profile-label">Developer Approved</span>
                <span class="profile-value dev-approved-badge" id="profileDevApproved">--</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Key System -->
        <div class="tab-content" id="tab-keys">
          <h2>Key Generator</h2>
          <div class="dashboard-card">
            <p style="color: var(--text-primary); font-weight: 600; font-size: 20px; margin-bottom: 12px;">Unlock Free Access</p>
            <p>Create unique HWID keys for your Roblox scripts. Use the generator below to authenticate.</p>
            <button class="gen-btn">Generate New Key</button>
          </div>
        </div>

        <!-- Scripts (НОВАЯ КАРТОЧКА С ИЗОБРАЖЕНИЕМ И КОДОМ) -->
        <div class="tab-content" id="tab-scripts">
          <h2>Scripts Library</h2>
          
          <div class="script-card">
            <div class="script-banner">
              <div class="banner-title">MUSCLE LEGENDS</div>
            </div>
            <div class="script-content">
              <div class="script-header">
                <h3>Oxygen Hub Script <span class="game-tag">for game: Muscle Legends</span></h3>
              </div>
              <p class="script-desc">Good script, works in beta version. There are some bugs or errors. They say it will be updated and will be the best script.</p>
              
              <div class="script-stats">
                <div class="stat-item">👍 0</div>
                <div class="stat-item">👎 0</div>
                <div class="stat-item">⭐ Unrated</div>
              </div>
              
              <button class="copy-btn" onclick="copyLuaScript(this)">Click to Copy Lua Script</button>
            </div>
          </div>
        </div>

        <!-- Plans -->
        <div class="tab-content" id="tab-plans">
          <h2>Upgrade Plans</h2>
          <div class="dashboard-card">
            <p>Buy premium plans to get more functional abilities, bypass limits, and level up faster than anyone else!</p>
          </div>
        </div>
        
        <!-- FAQ -->
        <div class="tab-content" id="tab-faq">
          <h2>FAQ</h2>
          <div class="dashboard-card">
            <p>Got questions? We answer fast! Check out the frequently asked questions or contact support.</p>
          </div>
        </div>

        <!-- Developers -->
        <div class="tab-content" id="tab-developers">
          <h2>Developers</h2>
          <div class="dashboard-card">
            <p>Meet the team behind Global Script's. We build the architecture, you enjoy the results.</p>
          </div>
        </div>

        <!-- Discord -->
        <div class="tab-content" id="tab-discord">
          <h2>Community</h2>
          <div class="dashboard-card">
            <p>Join our Discord server. Connect with other users, share scripts, and stay updated!</p>
          </div>
        </div>

      </div>
    </div>
  </div>

<script>
  // КОПИРОВАНИЕ СКРИПТА
  function copyLuaScript(btn) {
    const luaCode = 'loadstring(game:HttpGet("https://raw.githubusercontent.com/Rob4ik02/Muscle-Legends-Roblox/refs/heads/main/Muscle%20Legends/Sirius%20Library/Loader.lua"))()';
    navigator.clipboard.writeText(luaCode).then(() => {
      const originalText = btn.innerText;
      btn.innerText = 'Copied successfully!';
      btn.style.backgroundColor = 'var(--success)';
      btn.style.color = '#fff';
      
      setTimeout(() => {
        btn.innerText = originalText;
        btn.style.backgroundColor = '';
        btn.style.color = '';
      }, 2000);
    });
  }

  // LIQUID PHYSICS
  const canvas = document.getElementById('bgCanvas');
  const ctx = canvas.getContext('2d');
  let width, height;
  let particles = [];
  let mouse = { x: -1000, y: -1000 };
  let currentDotColor = 'rgba(255, 255, 255, 0.3)';
  let isErrorState = false;
  let globalSpeedBoost = 0; 

  function updateCanvasColor() {
    const computedStyle = getComputedStyle(document.body);
    currentDotColor = computedStyle.getPropertyValue('--dot-color').trim();
  }

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
    initParticles();
  }
  window.addEventListener('resize', resize);
  
  class Particle {
    constructor() {
      this.x = Math.random() * width;
      this.y = Math.random() * height;
      this.size = Math.random() * 2 + 1;
      this.density = (Math.random() * 20) + 5;
      this.angle = Math.random() * 360;
      this.speed = Math.random() * 0.3 + 0.1;
      this.vx = 0;
      this.vy = 0;
      this.friction = 0.92;
    }
    
    update() {
      this.angle += 0.01;
      this.vy -= this.speed * 0.1;
      this.vx += Math.sin(this.angle) * 0.05;
      this.y -= globalSpeedBoost * (this.speed * 1.5);

      let dx = mouse.x - this.x;
      let dy = mouse.y - this.y;
      let distance = Math.sqrt(dx * dx + dy * dy);
      let maxDistance = 180;

      if (distance < maxDistance) {
        let force = (maxDistance - distance) / maxDistance;
        this.vx -= (dx / distance) * force * 1.5;
        this.vy -= (dy / distance) * force * 1.5;
      }

      this.vx *= this.friction;
      this.vy *= this.friction;
      this.x += this.vx;
      this.y += this.vy;

      if (this.y < -20) { this.y = height + 20; this.x = Math.random() * width; this.vx = 0; this.vy = 0;}
      if (this.y > height + 20) { this.y = -20; this.x = Math.random() * width; this.vx = 0; this.vy = 0;}
      if (this.x < -20) { this.x = width + 20; this.vx = 0; this.vy = 0;}
      if (this.x > width + 20) { this.x = -20; this.vx = 0; this.vy = 0;}
    }
    
    draw() {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
      ctx.fillStyle = isErrorState ? '#ea1515' : currentDotColor;
      ctx.fill();
    }
  }

  function initParticles() {
    particles = [];
    let numberOfParticles = (width * height) / 8000;
    for (let i = 0; i < numberOfParticles; i++) {
      particles.push(new Particle());
    }
  }

  window.addEventListener('mousemove', (e) => { mouse.x = e.clientX; mouse.y = e.clientY; });
  window.addEventListener('mouseout', () => { mouse.x = -1000; mouse.y = -1000; });

  function animate() {
    ctx.clearRect(0, 0, width, height);
    globalSpeedBoost *= 0.92; 
    for (let i = 0; i < particles.length; i++) {
      particles[i].update();
      particles[i].draw();
    }
    requestAnimationFrame(animate);
  }

  updateCanvasColor();
  resize();
  animate();

  // ТЕМЫ
  const themeBtn = document.getElementById('themeBtn');
  const savedTheme = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
  themeBtn.innerText = savedTheme === 'dark' ? 'Light Mode' : 'Dark Mode';
  updateCanvasColor();

  themeBtn.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    themeBtn.innerText = newTheme === 'dark' ? 'Light Mode' : 'Dark Mode';
    updateCanvasColor();
  });

  function updateClock() {
    fetch('/get_time').then(res => res.json()).then(data => { document.getElementById('clock').innerText = data.time; });
  }
  setInterval(updateClock, 1000);
  updateClock();

  // ВКЛАДКИ
  const sidebarBtns = document.querySelectorAll('.sidebar-btn');
  const tabContents = document.querySelectorAll('.tab-content');
  const userDisplay = document.getElementById('userDisplay');

  function switchTab(targetId) {
    globalSpeedBoost = 30; 
    sidebarBtns.forEach(b => b.classList.remove('active'));
    tabContents.forEach(t => t.classList.remove('active'));
    sidebarBtns.forEach(b => { if(b.getAttribute('data-target') === targetId) b.classList.add('active'); });
    document.getElementById(targetId).classList.add('active');
  }

  sidebarBtns.forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.getAttribute('data-target')));
  });
  userDisplay.addEventListener('click', () => switchTab('tab-main'));

  // АВТОРИЗАЦИЯ
  document.addEventListener('DOMContentLoaded', () => {
    const signUpBtn = document.getElementById('signUpBtn');
    const loginInput = document.getElementById('login');
    const passwordInput = document.getElementById('password');
    const messageDiv = document.getElementById('message');
    const logoutBtn = document.getElementById('logoutBtn');
    const authForm = document.getElementById('authForm');
    
    const clockWrapper = document.getElementById('clockWrapper');
    const userWrapper = document.getElementById('userWrapper');
    const mainHeader = document.getElementById('mainHeader');
    const loaderScreen = document.getElementById('loaderScreen');
    const dashboardLayout = document.getElementById('dashboardLayout');

    const isLoggedIn = {{ 'true' if current_user else 'false' }};
    
    if (isLoggedIn) {
      mainHeader.style.display = 'none';
      dashboardLayout.style.display = 'flex';
      fetch('/get_user_info')
        .then(res => res.json())
        .then(data => {
          if(data.success) {
            userDisplay.innerText = data.login;
            document.getElementById('profileLogin').innerText = data.login;
            document.getElementById('profilePlan').innerText = data.plan;
            document.getElementById('profileRegDate').innerText = data.reg_date;
            document.getElementById('profileDevApproved').innerText = data.dev_approved;
          }
        });
    }

    function triggerErrorAnimation() {
      authForm.classList.remove('shake-error');
      setTimeout(() => authForm.classList.add('shake-error'), 10);
      setTimeout(() => authForm.classList.remove('shake-error'), 400);
      isErrorState = true;
      setTimeout(() => { isErrorState = false; }, 600);
    }

    logoutBtn.addEventListener('click', () => fetch('/logout').then(() => window.location.reload()));

    signUpBtn.addEventListener('click', () => {
      const login = loginInput.value.trim();
      const password = passwordInput.value;

      if (!login || !password) {
        messageDiv.innerText = 'Empty fields detected.';
        messageDiv.className = 'error-msg';
        triggerErrorAnimation();
        return;
      }

      fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ login: login, password: password })
      })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          messageDiv.innerText = '';
          authForm.style.display = 'none';
          mainHeader.style.display = 'none';
          loaderScreen.style.display = 'flex';

          setTimeout(() => {
            userDisplay.innerText = data.login;
            document.getElementById('profileLogin').innerText = data.login;
            document.getElementById('profilePlan').innerText = data.plan;
            document.getElementById('profileRegDate').innerText = data.reg_date;
            document.getElementById('profileDevApproved').innerText = data.dev_approved;

            clockWrapper.style.display = 'flex';
            userWrapper.style.display = 'flex';
            loaderScreen.style.display = 'none';
            dashboardLayout.style.display = 'flex';
          }, 1500);
        } else {
          messageDiv.innerText = 'Invalid credentials.';
          messageDiv.className = 'error-msg';
          triggerErrorAnimation(); 
        }
      });
    });
    
    passwordInput.addEventListener('keypress', function (e) { if (e.key === 'Enter') signUpBtn.click(); });
  });
</script>
</body>
</html>
'''

@app.route('/')
def index():
    current_user = session.get('user')
    return render_template_string(TEMPLATE, current_user=current_user)

@app.route('/get_time')
def get_time():
    tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(tz)
    time_str = now.strftime('%H:%M:%S')
    return jsonify({'time': time_str})

@app.route('/get_user_info')
def get_user_info():
    current_user = session.get('user')
    if not current_user:
        return jsonify({'success': False})
    
    user = next((u for u in users if u['login'] == current_user), None)
    if user:
        return jsonify({
            'success': True,
            'login': user['login'],
            'plan': user['plan'],
            'reg_date': user['reg_date'],
            'dev_approved': user['dev_approved']
        })
    return jsonify({'success': False})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    login_input = data.get('login', '').strip()
    password_input = data.get('password', '')

    user = next((u for u in users if u['login'] == login_input), None)
    # Проверка введенного пароля по его безопасному хешу
    if user and check_password_hash(user['password_hash'], password_input):
        session['user'] = login_input
        return jsonify({
            'success': True, 
            'login': user['login'],
            'plan': user['plan'],
            'reg_date': user['reg_date'],
            'dev_approved': user['dev_approved']
        })
    else:
        return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/logout')
def logout():
    session.pop('user', None)
    return ('', 204)

if __name__ == '__main__':
    app.run(debug=True)
