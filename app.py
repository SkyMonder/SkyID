import sqlite3
import uuid
import hashlib
import os
import secrets
from functools import wraps
from flask import Flask, request, render_template_string, redirect, session, url_for, flash, g, jsonify

# --- КОНФИГУРАЦИЯ ---
app = Flask(__name__)
app.secret_key = 'skyid_master_key_change_in_production'
DB_NAME = 'skyid.db'

# --- CSS И ДИЗАЙН (Без изменений) ---
BASE_STYLES = """
<style>
    :root {
        --primary: #0077FF;
        --primary-hover: #005ECC;
        --bg: #F0F2F5;
        --card-bg: #FFFFFF;
        --text: #19191A;
        --text-sec: #65676B;
        --radius: 12px;
        --shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    body { font-family: -apple-system, system-ui, Roboto, Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text); margin: 0; display: flex; flex-direction: column; min-height: 100vh; }
    
    .navbar { background: var(--card-bg); padding: 15px 40px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 2px rgba(0,0,0,0.1); z-index: 10; }
    .brand { font-weight: 800; font-size: 24px; color: var(--primary); text-decoration: none; display: flex; align-items: center; gap: 10px; }
    .nav-links a { margin-left: 20px; text-decoration: none; color: var(--text); font-weight: 500; font-size: 15px; transition: 0.2s; }
    .nav-links a:hover { color: var(--primary); }
    
    .container { max-width: 900px; margin: 40px auto; padding: 0 20px; width: 100%; }
    .container-small { max-width: 420px; }
    
    .card { background: var(--card-bg); padding: 30px; border-radius: var(--radius); box-shadow: var(--shadow); margin-bottom: 20px; }
    .card h2 { margin-top: 0; font-size: 22px; }
    .card h3 { margin-top: 0; font-size: 18px; color: var(--text-sec); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 15px; }

    .input-group { margin-bottom: 15px; }
    .input-group label { display: block; font-size: 13px; color: var(--text-sec); margin-bottom: 5px; font-weight: 600; }
    .input-group input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 15px; box-sizing: border-box; }
    .input-group input:focus { border-color: var(--primary); outline: none; box-shadow: 0 0 0 3px rgba(0,119,255,0.1); }
    
    .btn { background: var(--primary); color: white; border: none; padding: 12px 20px; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; display: inline-block; text-decoration: none; transition: 0.2s; text-align: center; }
    .btn:hover { background: var(--primary-hover); }
    .btn-block { display: block; width: 100%; }
    .btn-secondary { background: #E4E6EB; color: var(--text); }
    .btn-secondary:hover { background: #D8DADF; }

    .flash { background: #fee; color: #E63946; padding: 12px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #fcc; font-size: 14px; }
    
    /* Стили для виджета кнопки */
    .widget-preview { padding: 20px; background: #f8f9fa; border: 1px dashed #ccc; border-radius: 8px; text-align: center; margin: 15px 0; }
    .code-block { background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 6px; font-family: monospace; font-size: 12px; overflow-x: auto; position: relative; }
    
    .app-item { border-bottom: 1px solid #eee; padding: 20px 0; display: flex; justify-content: space-between; align-items: flex-start; }
    .app-item:last-child { border-bottom: none; }
    .key-display { font-family: monospace; background: #eee; padding: 4px 8px; border-radius: 4px; color: #333; font-size: 13px; word-break: break-all; }
    
    /* Стиль самой кнопки быстрого входа (для интеграции) */
    .skyid-widget-btn {
        background-color: #0077FF;
        color: white;
        font-family: -apple-system, sans-serif;
        font-weight: 600;
        padding: 10px 24px;
        border-radius: 8px;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        gap: 10px;
        transition: transform 0.1s;
        border: none;
        cursor: pointer;
    }
    .skyid-widget-btn:hover { background-color: #005ECC; }
    .skyid-widget-btn:active { transform: scale(0.98); }
    .skyid-logo-small { font-weight: 900; background: white; color: #0077FF; width: 20px; height: 20px; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 12px; }
</style>
"""

LAYOUT = """
<!DOCTYPE html>
<html>
<head>
    <title>SkyID</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    """ + BASE_STYLES + """
</head>
<body>
    <nav class="navbar">
        <a href="/" class="brand">
            <span style="background:linear-gradient(45deg, #0077FF, #00C6FF); color:white; padding:5px 10px; border-radius:8px;">Sky</span> ID
        </a>
        <div class="nav-links">
            {% if session.get('user_id') %}
                <a href="/dashboard">Кабинет</a>
                <a href="/logout">Выйти</a>
            {% else %}
                <a href="/login">Войти</a>
                <a href="/register">Создать SkyID</a>
            {% endif %}
        </div>
    </nav>
    {% block content %}{% endblock %}
</body>
</html>
"""

# --- БАЗА ДАННЫХ ---

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_NAME)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        # ИЗМЕНЕНИЕ: Убран Email, только username (логин)
        db.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL, 
            password TEXT NOT NULL,
            name TEXT NOT NULL
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS apps (
            client_id TEXT PRIMARY KEY,
            api_key TEXT NOT NULL, 
            owner_id INTEGER NOT NULL,
            app_name TEXT NOT NULL,
            redirect_uri TEXT NOT NULL
        )''')
        db.commit()

# --- ЛОГИКА ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- МАРШРУТЫ ---

@app.route('/')
def index():
    return render_template_string(LAYOUT + """
    <div class="container" style="text-align: center;">
        <h1 style="font-size: 56px; margin: 40px 0 20px; letter-spacing: -1px;">
            Единый ключ ко всему.
        </h1>
        <p style="font-size: 20px; color: #65676B; max-width: 600px; margin: 0 auto 40px;">
            SkyID — это платформа идентификации. Один аккаунт для пользователей, мощный API для разработчиков.
        </p>
        {% if not session.get('user_id') %}
            <div style="display: flex; justify-content: center; gap: 15px;">
                <a href="/register" class="btn">Создать аккаунт</a>
                <a href="/login" class="btn btn-secondary">Войти</a>
            </div>
        {% else %}
             <a href="/dashboard" class="btn">Перейти в консоль разработчика</a>
        {% endif %}
    </div>
    """)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # ИЗМЕНЕНИЕ: Только username (логин) и password, name
        username = request.form['username'].strip() 
        password = request.form['password']
        name = request.form['name']
        
        db = get_db()
        try:
            db.execute('INSERT INTO users (username, password, name) VALUES (?, ?, ?)',
                       (username, hash_pass(password), name))
            db.commit()
            flash('Аккаунт успешно создан! Войдите.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash(f'Логин "{username}" уже занят.')

    return render_template_string(LAYOUT + """
    <div class="container container-small">
        <div class="card">
            <h2>Регистрация SkyID</h2>
            {% with messages = get_flashed_messages() %}
                {% if messages %}<div class="flash">{{ messages[0] }}</div>{% endif %}
            {% endwith %}
            <form method="post">
                <div class="input-group">
                    <label>Ваше Имя (отображаемое)</label>
                    <input type="text" name="name" required placeholder="Иван">
                </div>
                <div class="input-group">
                    <label>Логин (Никнейм)</label>
                    <input type="text" name="username" required placeholder="ivan_sky" pattern="[a-zA-Z0-9_]+" title="Только латинские буквы, цифры и подчеркивание.">
                </div>
                <div class="input-group">
                    <label>Пароль</label>
                    <input type="password" name="password" required>
                </div>
                <button type="submit" class="btn btn-block">Создать SkyID</button>
            </form>
            <p style="margin-top: 20px; font-size: 14px; text-align: center;">Есть аккаунт? <a href="/login">Войти</a></p>
        </div>
    </div>
    """)

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next') or url_for('dashboard')
    
    if request.method == 'POST':
        # ИЗМЕНЕНИЕ: Используем Логин (username)
        username = request.form['username'].strip()
        password = request.form['password']
        
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                          (username, hash_pass(password))).fetchone()
        
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(next_url)
        else:
            flash('Неверный логин или пароль')

    return render_template_string(LAYOUT + """
    <div class="container container-small">
        <div class="card">
            <h2>Вход</h2>
            {% with messages = get_flashed_messages() %}
                {% if messages %}<div class="flash">{{ messages[0] }}</div>{% endif %}
            {% endwith %}
            <form method="post">
                <div class="input-group">
                    <label>Логин</label>
                    <input type="text" name="username" required>
                </div>
                <div class="input-group">
                    <label>Пароль</label>
                    <input type="password" name="password" required>
                </div>
                <button type="submit" class="btn btn-block">Войти</button>
            </form>
            <p style="margin-top: 20px; font-size: 14px; text-align: center;">Нет аккаунта? <a href="/register">Создать</a></p>
        </div>
    </div>
    """)

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    db = get_db()
    host_url = request.host_url.rstrip('/')
    
    if request.method == 'POST':
        app_name = request.form['app_name']
        redirect_uri = request.form['redirect_uri']
        
        # Генерируем публичный App ID
        client_id = str(uuid.uuid4().int)[:10] 
        # Генерируем длинный секретный API ключ (64 символа)
        api_key = secrets.token_hex(32) 
        
        db.execute('INSERT INTO apps (client_id, api_key, owner_id, app_name, redirect_uri) VALUES (?, ?, ?, ?, ?)',
                   (client_id, api_key, session['user_id'], app_name, redirect_uri))
        db.commit()
        flash(f'Приложение "{app_name}" создано!')
        return redirect(url_for('dashboard'))

    my_apps = db.execute('SELECT * FROM apps WHERE owner_id = ?', (session['user_id'],)).fetchall()
    
    return render_template_string(LAYOUT + """
    <div class="container">
        <div class="card" style="display: flex; align-items: center; gap: 20px;">
            <div style="width: 60px; height: 60px; background: var(--primary); border-radius: 50%; color: white; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: bold;">
                {{ session['user_name'][0] }}
            </div>
            <div>
                <h2 style="margin: 0;">{{ session['user_name'] }}</h2>
                <span style="color: var(--text-sec);">User ID: {{ session['user_id'] }}</span>
            </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
            <div class="card">
                <h3>🚀 Новое приложение</h3>
                <form method="post">
                    <div class="input-group">
                        <label>Название сайта/приложения</label>
                        <input type="text" name="app_name" placeholder="Мой магазин" required>
                    </div>
                    <div class="input-group">
                        <label>Redirect URI (Callback)</label>
                        <input type="text" name="redirect_uri" placeholder="https://mysite.com/auth/callback" required>
                    </div>
                    <button type="submit" class="btn btn-block">Получить ключи</button>
                </form>
            </div>
            
            <div class="card" style="background: #EBF5FF;">
                <h3>📚 Быстрый старт</h3>
                <p style="font-size: 14px; line-height: 1.5;">
                    1. Создайте приложение слева.<br>
                    2. Скопируйте <b>App ID</b> и <b>API Key</b>.<br>
                    3. Используйте <b>Генератор кнопки</b> ниже.<br>
                    4. Меняйте полученный <code>code</code> на токен через наш API.
                </p>
            </div>
        </div>

        <div class="card">
            <h3>🔑 Мои приложения и API ключи</h3>
            {% if my_apps %}
                {% for app in my_apps %}
                <div class="app-item">
                    <div style="flex: 1;">
                        <h4 style="margin: 0 0 10px 0; color: var(--primary);">{{ app['app_name'] }}</h4>
                        
                        <div style="margin-bottom: 8px;">
                            <span style="font-weight: 600; font-size: 12px; color: #888;">APP ID (Публичный):</span><br>
                            <span class="key-display">{{ app['client_id'] }}</span>
                        </div>
                        
                        <div>
                            <span style="font-weight: 600; font-size: 12px; color: #E63946;">SECRET API KEY (Секретный):</span><br>
                            <span class="key-display">{{ app['api_key'] }}</span>
                        </div>
                    </div>
                    
                    <div style="flex: 1; margin-left: 20px;">
                         <span style="font-weight: 600; font-size: 12px; color: #888;">ГЕНЕРАТОР КНОПКИ:</span>
                         <div class="widget-preview">
                            <a href="{{ host_url }}/oauth/authorize?client_id={{ app['client_id'] }}&response_type=code" class="skyid-widget-btn" target="_blank">
                                <span class="skyid-logo-small">S</span> Войти через SkyID
                            </a>
                         </div>
                         <div class="code-block">
&lt;!-- Вставьте этот код на свой сайт --&gt;
&lt;a href="{{ host_url }}/oauth/authorize?client_id={{ app['client_id'] }}&response_type=code" 
   style="background:#0077FF; color:white; padding:10px 20px; text-decoration:none; border-radius:6px; font-family:sans-serif; font-weight:bold;"&gt;
   Войти через SkyID
&lt;/a&gt;
                         </div>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <p style="text-align: center; color: var(--text-sec);">У вас пока нет приложений.</p>
            {% endif %}
        </div>
    </div>
    """, host_url=host_url, my_apps=my_apps)

# --- OAUTH ЛОГИКА ---

@app.route('/oauth/authorize', methods=['GET', 'POST'])
def oauth_authorize():
    client_id = request.args.get('client_id')
    
    if not client_id:
        return "Ошибка: Не передан client_id", 400

    db = get_db()
    app_info = db.execute('SELECT * FROM apps WHERE client_id = ?', (client_id,)).fetchone()
    
    if not app_info:
        return "Ошибка: Приложение с таким ID не найдено", 404

    if 'user_id' not in session:
        return redirect(url_for('login', next=request.url))

    if request.method == 'POST':
        # Генерируем временный код авторизации
        auth_code = secrets.token_urlsafe(16)
        
        # В идеале нужно сохранить auth_code в БД и связать с client_id
        redirect_to = f"{app_info['redirect_uri']}?code={auth_code}"
        return redirect(redirect_to)

    return render_template_string(LAYOUT + """
    <div class="container container-small">
        <div class="card" style="text-align: center;">
            <div style="font-size: 48px; margin-bottom: 20px;">🔐</div>
            <h2>Разрешить доступ?</h2>
            <p>Приложение <strong style="color: var(--primary);">{{ app_name }}</strong> запрашивает доступ к вашему аккаунту SkyID.</p>
            
            <ul style="text-align: left; background: #f7f9fa; padding: 15px; border-radius: 8px; list-style: none; margin: 20px 0;">
                <li style="margin-bottom: 10px;">✅ Просмотр вашего имени</li>
                <li>✅ Просмотр вашего Логина (Никнейма)</li>
            </ul>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                <a href="/" class="btn btn-secondary" style="text-align: center;">Отмена</a>
                <form method="post" style="margin:0;">
                    <button type="submit" class="btn btn-block">Разрешить</button>
                </form>
            </div>
            <p style="margin-top: 20px; font-size: 12px; color: var(--text-sec);">
                Вы входите как <b>{{ user_name }}</b>
            </p>
        </div>
    </div>
    """, app_name=app_info['app_name'], user_name=session['user_name'])

@app.route('/oauth/token', methods=['POST'])
def oauth_token():
    grant_type = request.form.get('grant_type')
    client_id = request.form.get('client_id')
    api_key = request.form.get('client_secret') 
    code = request.form.get('code')
    
    if not all([grant_type, client_id, api_key, code]):
        return jsonify({'error': 'invalid_request', 'message': 'Missing parameters'}), 400
        
    db = get_db()
    app_info = db.execute('SELECT * FROM apps WHERE client_id = ? AND api_key = ?', 
                          (client_id, api_key)).fetchone()
    
    if not app_info:
        return jsonify({'error': 'invalid_client', 'message': 'Wrong Client ID or API Key'}), 401

    access_token = secrets.token_hex(20)
    
    return jsonify({
        'access_token': access_token,
        'token_type': 'Bearer',
        'expires_in': 3600,
        'user_id': app_info['owner_id'] 
    })

# --- ИНИЦИАЛИЗАЦИЯ И ЗАПУСК ---

# ГАРАНТИЯ: Таблицы БД создаются при запуске Gunicorn/Flask
with app.app_context():
    init_db()
    print("--- DEBUG: ГАРАНТИЯ: Таблицы БД созданы/проверены.")


if __name__ == '__main__':
    print("SkyID 3.0 запущен на http://127.0.0.1:5000 (Локально)")
    app.run(debug=True)
