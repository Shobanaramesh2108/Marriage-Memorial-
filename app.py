import os
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3

BASE_DIR = os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, 'matrimony.db')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-me-in-production'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB limit

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Simple User class for Flask-Login
class User(UserMixin):
    def __init__(self, id_, email, name):
        self.id = id_
        self.email = email
        self.name = name

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT,
        age INTEGER,
        religion TEXT,
        city TEXT,
        bio TEXT,
        photo TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, email, name FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return User(row['id'], row['email'], row['name'])
    return None

@app.route('/')
def index():
    conn = get_db()
    c = conn.cursor()
    q = request.args.get('q', '').strip()
    if q:
        c.execute("SELECT * FROM users WHERE name LIKE ? OR city LIKE ? OR religion LIKE ?",
                  (f'%{q}%', f'%{q}%', f'%{q}%'))
    else:
        c.execute("SELECT * FROM users")
    profiles = c.fetchall()
    conn.close()
    return render_template('index.html', profiles=profiles, q=q)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        name = request.form.get('name','').strip()
        if not email or not password:
            flash('Email and password required', 'danger')
            return redirect(url_for('register'))
        hashed = generate_password_hash(password)
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (email, password, name) VALUES (?, ?, ?)",
                      (email, hashed, name))
            conn.commit()
            flash('Registration successful. Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('Account with that email may already exist.', 'danger')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = c.fetchone()
        conn.close()
        if row and check_password_hash(row['password'], password):
            user = User(row['id'], row['email'], row['name'])
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (current_user.id,))
    profile = c.fetchone()
    conn.close()
    return render_template('dashboard.html', profile=profile)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/profile/<int:uid>')
def profile(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (uid,))
    p = c.fetchone()
    conn.close()
    if not p:
        flash('Profile not found.', 'warning')
        return redirect(url_for('index'))
    return render_template('profile.html', p=p)

@app.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    conn = get_db()
    c = conn.cursor()
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        age = request.form.get('age') or None
        religion = request.form.get('religion','').strip()
        city = request.form.get('city','').strip()
        bio = request.form.get('bio','').strip()
        photo = request.files.get('photo')
        photo_filename = None
        if photo and photo.filename:
            filename = secure_filename(photo.filename)
            photo_filename = f"{current_user.id}_{filename}"
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
        if age == '':
            age = None
        # build parameters
        params = [name, age, religion, city, bio]
        sql = "UPDATE users SET name=?, age=?, religion=?, city=?, bio=?"
        if photo_filename:
            sql += ", photo=?"
            params.append(photo_filename)
        sql += " WHERE id=?"
        params.append(current_user.id)
        c.execute(sql, tuple(params))
        conn.commit()
        flash('Profile updated.', 'success')
        conn.close()
        return redirect(url_for('dashboard'))
    else:
        c.execute("SELECT * FROM users WHERE id = ?", (current_user.id,))
        profile = c.fetchone()
        conn.close()
        return render_template('edit.html', profile=profile)

if __name__ == '__main__':
    app.run(debug=True)
