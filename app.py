import os
from datetime import datetime
import sqlite3
from pathlib import Path

from flask import Flask, g, render_template, request, redirect, url_for, flash

# ---------------------------------------------------
# Configuration
# ---------------------------------------------------
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / 'carbon_emission_collector.db'
TEMPLATES_DIR = BASE_DIR / 'templates'

# ---------------------------------------------------
# Flask app setup
# ---------------------------------------------------
app = Flask(__name__, template_folder=str(TEMPLATES_DIR))
# Secret key for flash messages (in a real app use a secure random key)
app.config['SECRET_KEY'] = 'dev-secret-key'

# ---------------------------------------------------
# Database helpers
# ---------------------------------------------------

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS emissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            amount_kg REAL NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    ''')
    conn.commit()
    conn.close()

# ---------------------------------------------------
# Routes
# ---------------------------------------------------

@app.route('/')
def index():
    db = get_db()
    users = db.execute('SELECT * FROM users ORDER BY name').fetchall()
    return render_template('index.html', users=users)

# ---- Add User -------------------------------------------------
@app.route('/user/add', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        if not name or not email:
            flash('Name and email are required.', 'danger')
        else:
            db = get_db()
            try:
                db.execute('INSERT INTO users (name, email) VALUES (?, ?)', (name, email))
                db.commit()
                flash('User added successfully.', 'success')
                return redirect(url_for('index'))
            except sqlite3.IntegrityError:
                flash('Email already exists.', 'danger')
    return render_template('add_user.html')

# ---- Add Emission ---------------------------------------------
@app.route('/emission/add', methods=['GET', 'POST'])
def add_emission():
    db = get_db()
    users = db.execute('SELECT * FROM users ORDER BY name').fetchall()
    if request.method == 'POST':
        email = request.form['email']
        source = request.form['source'].strip()
        amount = request.form['amount']
        date_str = request.form.get('date')
        # Find user id
        user = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if not user:
            flash('User not found. Please add the user first.', 'danger')
        else:
            try:
                amount_val = float(amount)
                # Parse date or fallback to now
                if date_str:
                    try:
                        dt = datetime.fromisoformat(date_str)
                    except ValueError:
                        flash('Invalid date format – using current time.', 'warning')
                        dt = datetime.now()
                else:
                    dt = datetime.now()
                db.execute(
                    'INSERT INTO emissions (user_id, source, amount_kg, date) VALUES (?, ?, ?, ?)',
                    (user['id'], source, amount_val, dt.isoformat())
                )
                db.commit()
                flash('Emission recorded.', 'success')
                return redirect(url_for('index'))
            except ValueError:
                flash('Amount must be a number.', 'danger')
    return render_template('add_emission.html', users=users)

# ---- Totals ----------------------------------------------------
@app.route('/totals')
def totals():
    db = get_db()
    total_all = db.execute('SELECT SUM(amount_kg) AS total FROM emissions').fetchone()['total'] or 0.0
    # Per‑user totals
    per_user = db.execute('''
        SELECT u.name, u.email, COALESCE(SUM(e.amount_kg),0) AS total
        FROM users u LEFT JOIN emissions e ON u.id = e.user_id
        GROUP BY u.id ORDER BY u.name
    ''').fetchall()
    return render_template('totals.html', total_all=total_all, per_user=per_user)

# ---- Report ----------------------------------------------------
@app.route('/report')
def report():
    db = get_db()
    rows = db.execute('''
        SELECT u.name, u.email, e.source, e.amount_kg, e.date
        FROM emissions e JOIN users u ON e.user_id = u.id
        ORDER BY u.name, e.date
    ''').fetchall()
    return render_template('report.html', rows=rows)

# ---------------------------------------------------
# Main entry point
# ---------------------------------------------------
if __name__ == '__main__':
    # Ensure DB exists before the first request
    if not DB_PATH.exists():
        init_db()
    # Run Flask dev server; set debug=False for production
    app.run(debug=True, host='127.0.0.1', port=5000)
