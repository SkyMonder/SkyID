import sqlite3
import uuid
import hashlib
import os
from functools import wraps
from flask import Flask, request, render_template_string, redirect, session, url_for, flash, g

# --- КОНФИГУРАЦИЯ ---
app = Flask(__name__)
app.secret_key = 'skyid_very_secret_key_dev_only' # В продакшене используйте случайный токен
DB_NAME = 'skyid.db'

# --- HTML/CSS ШАБЛОНЫ (Внутри кода для однофайловости) ---

BASE_STYLES = """
<style>
    :root {
        --primary: #0077FF;
        --primary-hover: #005ECC;
        --bg: #F0F2F5;
        --card-bg: #FFFFFF;
        --text: #19191A;
        --text-sec: #65676B;
        --error: #E63946;
        --radius: 12px;
    }
    * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    body { background-color: var(--bg); color: var(--text); margin: 0; padding: 0; display: flex; flex-direction: column; min-height: 100vh; }
    
    .navbar { background: var(--card-bg); padding: 15px 40px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
    .brand { font-weight: 800; font-size: 24px; color: var(--primary); text-decoration: none; letter-spacing: -0.5px; }
    .nav-links a { margin-left: 20px; text-decoration: none; color: var(--text); font-weight: 500; font-size: 15px; }
    .nav-links a:hover { color: var(--primary); }
    
    .container { max-width: 460px; margin: 60px auto; padding: 0 20px; }
    .card { background: var(--card-bg); padding: 40px; border-radius: var(--radius); box-shadow: 0 4px 12px rgba(0,0,0,0.08); text-align: center; }
    .card h2 { margin-top: 0; margin-bottom: 25px; font-size: 22px; }
    
    .input-group { margin-bottom: 15px; text-align: left; }
    .input-group label { display: block; font-size: 13px; color: var(--text-sec); margin-bottom: 5px; font-weight: 600; }
    .input-group input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 15px; transition: 0.2s; }
    .input-group input:focus { border-color: var(--primary); outline: none; box-shadow: 0 0 0 3px rgba(0,119,255,0.1); }
    
    .btn { background: var(--primary); color: white; border: none; padding: 12px 20px; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; width: 100%; transition: 0.2s; text-decoration: none; display: inline-block; }
    .btn:hover { background: var(--primary-hover); }
    .btn-secondary { background: #E4E6EB; color: var(--text); }
    .btn-secondary:hover { background: #D8DADF; }
    
    .flash { background: #FFF4F4; color: var(--error); padding: 10px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; border: 1px solid rgba(230, 57, 70, 0.2); }
    
    .dev-dashboard { max-width: 900px; }
    .app-item { border: 1px solid #eee; padding: 15px; border-radius: 8px; margin-bottom: 10px; text-align: left; display: flex; justify-content: space-between; align-items: center; }
    .app-details { font-size: 13px; color: var(--text-sec); margin-top: 5px; }
    .code-box { background: #f8f9fa; padding: 8px; border-radius: 6px; font-family: monospace; color: #d63384; font-size: 12px; border: 1px solid #eee; display: inline-block; margin-top: 5px; }
    
    .oauth-scope { text-align: left; margin: 20px 0; background: #f7f9fa; padding: 15px; border-radius: 8px; }
    .scope-item { display: flex; align-items: center; margin-bottom: 8px; font-size: 14px; }
    .check-icon { color: var(--primary); margin-right: 10px; font-weight: bold; }
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
        <a href="/" class="brand">SkyID</a>
        <div class="nav-links">
            {% if session.get('user_id') %}
                <a href="/dashboard">Мой аккаунт</a>
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
        # Таблица пользователей
        db.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL
        )''')
        # Таблица приложений (для разработчиков)
        db.execute('''CREATE TABLE IF NOT EXISTS apps (
            client_id TEXT PRIMARY KEY,
            client_secret TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            app_name TEXT NOT NULL,
            redirect_uri TEXT NOT NULL
        )''')
        db.commit()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def hash_pass(password):
    # !!! ДОБАВЛЕНА СТРОКА ДЛЯ ОТЛАДКИ !!!
    hashed_result = hashlib.sha256(password.encode()).hexdigest()
    print(f"--- DEBUG: Hashing '{password[:2]}...' -> {hashed_result}") # Выводим хеш
    return hashed_result

# --- МАРШРУТЫ (ROUTES) ---

@app.route('/')
def index():
    return render_template_string(LAYOUT + """
    <div class="container" style="text-align: center; max-width: 800px;">
        <h1 style="font-size: 48px; margin-bottom: 20px; background: -webkit-linear-gradient(45deg, #0077FF, #00C6FF); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            Один аккаунт для всего.
        </h1>
        <p style="font-size: 20px; color: #65676B; margin-bottom: 40px; line-height: 1.5;">
            SkyID — это ваша цифровая экосистема. Безопасный вход, управление данными и интеграция с сотнями сервисов в один клик.
        </p>
        {% if not session.get('user_id') %}
            <a href="/register" class="btn" style="width: auto; padding: 15px 40px; font-size: 18px;">Создать SkyID</a>
        {% else %}
             <a href="/dashboard" class="btn" style="width: auto; padding: 15px 40px; font-size: 18px;">Перейти в кабинет</a>
        {% endif %}
        
        <div style="margin-top: 60px; display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
            <div class="card" style="text-align: left;">
                <h3>Для пользователей</h3>
                <p>Забудьте о десятках паролей. Входите на сайты быстро и безопасно.</p>
            </div>
            <div class="card" style="text-align: left;">
                <h3>Для разработчиков</h3>
                <p>Подключите OAuth за 5 минут. Получите доступ к аудитории SkyID.</p>
            </div>
        </div>
    </div>
    """)

@app.route('/register', methods=['GET', 'POST'])
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        
        db = get_db()
        try:
            # --- DEBUG: Пытаемся добавить пользователя ---
            print(f"--- DEBUG: Attempting to register user: {username}")
            
            db.execute('INSERT INTO users (username, password, name) VALUES (?, ?, ?)',
                       (username, hash_pass(password), name))
            
            # ГАРАНТИРОВАННАЯ ФИКСАЦИЯ ИЗМЕНЕНИЙ В БАЗЕ ДАННЫХ:
            db.commit() 
            print(f"--- DEBUG: SUCCESS! User {username} committed to DB.")

            flash('Аккаунт создан! Теперь войдите.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            print(f"--- DEBUG: FAILED! Username {username} already exists.")
            flash('Это имя пользователя уже занято.')
        except Exception as e:
            # Ловим любые другие ошибки при работе с БД
            print(f"--- DEBUG: CRITICAL DB ERROR during registration: {e}")
            flash('Произошла внутренняя ошибка при создании аккаунта.')
            
    return render_template_string(LAYOUT + """
    <div class="container">
        <div class="card">
            <h2>Регистрация SkyID</h2>
            {% with messages = get_flashed_messages() %}
                {% if messages %}<div class="flash">{{ messages[0] }}</div>{% endif %}
            {% endwith %}
            <form method="post">
                <div class="input-group">
                    <label>Имя (отображаемое)</label>
                    <input type="text" name="name" required placeholder="Иван Иванов">
                </div>
                <div class="input-group">
                    <label>Логин / Email</label>
                    <input type="text" name="username" required placeholder="example@sky.id">
                </div>
                <div class="input-group">
                    <label>Пароль</label>
                    <input type="password" name="password" required placeholder="••••••••">
                </div>
                <button type="submit" class="btn">Создать аккаунт</button>
            </form>
            <p style="margin-top: 20px; font-size: 14px;">Уже есть аккаунт? <a href="/login" style="color: var(--primary);">Войти</a></p>
        </div>
    </div>
    """)

@app.route('/login', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Проверка на наличие параметров OAuth (для редиректа после логина)
    next_url = request.args.get('next') or url_for('dashboard')
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        hashed_password = hash_pass(password) 

        db = get_db()
        
        # --- DEBUG: Пытаемся найти пользователя ---
        print(f"--- DEBUG: Attempting login for user: {username}")
        # Выполняем запрос
        user = db.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                          (username, hashed_password)).fetchone()
        
        if user:
            print(f"--- DEBUG: SUCCESS! User ID {user['id']} found. Redirecting to {next_url}")
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(next_url)
        else:
            # --- DEBUG: ВЫВОДИМ ОШИБКУ ---
            # Дополнительно проверим, существует ли логин вообще (без учета пароля)
            existing_user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            if existing_user:
                print("--- DEBUG: FAILURE! Username found, but password hash mismatch.")
            else:
                print("--- DEBUG: FAILURE! Username not found.")
            
            flash('Неверный логин или пароль')
            
    return render_template_string(LAYOUT + """
    <div class="container">
        <div class="card">
            <h2 style="color: var(--primary);">SkyID</h2>
            <h3 style="margin-top: -15px; color: var(--text-sec); font-weight: normal; font-size: 16px;">Вход в единый аккаунт</h3>
            
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
                <button type="submit" class="btn">Войти</button>
            </form>
            <p style="margin-top: 20px; font-size: 14px;">Нет аккаунта? <a href="/register" style="color: var(--primary);">Зарегистрироваться</a></p>
        </div>
    </div>
    """)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    db = get_db()
    
    # Создание нового приложения (для разработчиков)
    if request.method == 'POST':
        app_name = request.form['app_name']
        redirect_uri = request.form['redirect_uri']
        client_id = str(uuid.uuid4())[:18]
        client_secret = hashlib.sha256(os.urandom(32)).hexdigest()[:32]
        
        db.execute('INSERT INTO apps (client_id, client_secret, owner_id, app_name, redirect_uri) VALUES (?, ?, ?, ?, ?)',
                   (client_id, client_secret, session['user_id'], app_name, redirect_uri))
        db.commit()
        flash('Приложение создано!')
        return redirect(url_for('dashboard'))

    my_apps = db.execute('SELECT * FROM apps WHERE owner_id = ?', (session['user_id'],)).fetchall()
    
    return render_template_string(LAYOUT + """
    <div class="container dev-dashboard">
        <div class="card" style="margin-bottom: 20px; text-align: left;">
            <div style="display:flex; align-items:center;">
                <div style="width: 60px; height: 60px; background: var(--primary); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 24px; font-weight: bold; margin-right: 20px;">
                    {{ session['user_name'][0] }}
                </div>
                <div>
                    <h2>Привет, {{ session['user_name'] }}!</h2>
                    <p style="margin:0; color: var(--text-sec);">Ваш ID: {{ session['user_id'] }}</p>
                </div>
            </div>
        </div>

        <div class="card" style="text-align: left;">
            <h3 style="border-bottom: 1px solid #eee; padding-bottom: 10px;">🛠 SkyID для разработчиков</h3>
            <p>Создайте приложение, чтобы добавить кнопку "Войти через SkyID" на свой сайт.</p>
            
            <form method="post" style="background: #f7f9fa; padding: 20px; border-radius: 8px; margin-bottom: 30px;">
                <h4 style="margin-top:0;">Новое приложение</h4>
                <div class="input-group">
                    <label>Название приложения</label>
                    <input type="text" name="app_name" placeholder="Мой Супер Сайт" required>
                </div>
                <div class="input-group">
                    <label>Redirect URI (куда вернуть пользователя)</label>
                    <input type="text" name="redirect_uri" placeholder="https://mysite.com/callback" required>
                </div>
                <button type="submit" class="btn" style="width: auto;">Получить ключи API</button>
            </form>

            <h4>Мои приложения:</h4>
            {% if my_apps %}
                {% for app in my_apps %}
                <div class="app-item">
                    <div>
                        <strong>{{ app['app_name'] }}</strong>
                        <div class="app-details">URI: {{ app['redirect_uri'] }}</div>
                        <div class="app-details">
                            App ID: <span class="code-box">{{ app['client_id'] }}</span>
                        </div>
                         <div class="app-details">
                            Secret: <span class="code-box">{{ app['client_secret'] }}</span>
                        </div>
                    </div>
                    <a href="/oauth/authorize?client_id={{ app['client_id'] }}&response_type=code" target="_blank" class="btn btn-secondary" style="width: auto; padding: 8px 15px; font-size: 13px;">Тест входа</a>
                </div>
                {% endfor %}
            {% else %}
                <p style="color: var(--text-sec);">У вас пока нет созданных приложений.</p>
            {% endif %}
        </div>
    </div>
    """, my_apps=my_apps)

# --- OAUTH ЛОГИКА (АВТОРИЗАЦИЯ) ---

@app.route('/oauth/authorize', methods=['GET', 'POST'])
def oauth_authorize():
    # Это эндпоинт, на который перекидывает внешний сайт
    client_id = request.args.get('client_id')
    
    if not client_id:
        return "Ошибка: client_id не передан", 400

    db = get_db()
    app_info = db.execute('SELECT * FROM apps WHERE client_id = ?', (client_id,)).fetchone()
    
    if not app_info:
        return "Ошибка: Приложение не найдено", 404

    # Если пользователь не залогинен в SkyID, отправляем на логин, потом вернем сюда
    if 'user_id' not in session:
        return redirect(url_for('login', next=request.url))

    if request.method == 'POST':
        # Пользователь нажал "Разрешить"
        # В реальности здесь генерируется Authorization Code
        auth_code = hashlib.sha256(os.urandom(16)).hexdigest()[:16]
        
        # Редирект обратно на сайт разработчика с кодом
        redirect_to = f"{app_info['redirect_uri']}?code={auth_code}"
        return redirect(redirect_to)

    # Показываем экран согласия (Consent Screen)
    return render_template_string(LAYOUT + """
    <div class="container">
        <div class="card">
            <div style="margin-bottom: 20px;">
                <span style="font-size: 40px;">🔒 ➔ 🌍</span>
            </div>
            <h2>Вход через SkyID</h2>
            <p>Приложение <strong>{{ app_name }}</strong> запрашивает доступ к вашему аккаунту.</p>
            
            <div class="oauth-scope">
                <div class="scope-item"><span class="check-icon">✓</span> Доступ к имени и фото</div>
                <div class="scope-item"><span class="check-icon">✓</span> Доступ к ID профиля</div>
            </div>

            <div style="display: flex; gap: 10px;">
                <a href="/" class="btn btn-secondary">Отмена</a>
                <form method="post" style="width: 100%;">
                    <button type="submit" class="btn">Продолжить как {{ user_name }}</button>
                </form>
            </div>
            <p style="margin-top: 20px; font-size: 12px; color: var(--text-sec);">
                Нажимая «Продолжить», вы принимаете <a href="#">Политику конфиденциальности</a> SkyID.
            </p>
        </div>
    </div>
    """, app_name=app_info['app_name'], user_name=session['user_name'])

# --- ЗАПУСК ---

# --- ЗАПУСК ---

if __name__ == '__main__':
    # ВАЖНО: Вызываем init_db() каждый раз, чтобы убедиться, что структуры таблиц 
    # (CREATE TABLE IF NOT EXISTS) гарантированно присутствуют.
    # Если таблицы уже есть, SQLite их не пересоздаст.
    # Это более надежно, чем проверка db_exists.

    init_db() # Убрана проверка if not os.path.exists(DB_NAME)

    print(f"База данных {DB_NAME} инициализирована.")
    print("SkyID запущен на http://127.0.0.1:5000")
    
    # Временно устанавливаем `debug=False` или используем `flask run`, 
    # чтобы избежать проблемы с перезапуском, но для разработки оставим `True`.
    app.run(debug=True)