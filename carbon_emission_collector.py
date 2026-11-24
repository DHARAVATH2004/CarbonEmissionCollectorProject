import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).with_suffix('.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    # Create users table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE
        )
    ''')
    # Create emissions table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS emissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            amount_kg REAL NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

def add_user(name, email):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute('INSERT INTO users (name, email) VALUES (?, ?)', (name, email))
        conn.commit()
        print(f"User '{name}' added with email {email}.")
    except sqlite3.IntegrityError as e:
        print(f"Error adding user: {e}")
    finally:
        conn.close()

def add_emission(email, source, amount, date_str=None):
    conn = get_connection()
    cur = conn.cursor()
    # Find user id
    cur.execute('SELECT id FROM users WHERE email = ?', (email,))
    row = cur.fetchone()
    if not row:
        print(f"No user found with email {email}. Use 'add_user' first.")
        conn.close()
        return
    user_id = row['id']
    # Normalize date
    if date_str:
        try:
            dt = datetime.fromisoformat(date_str)
        except ValueError:
            print("Date must be ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS). Using current time.")
            dt = datetime.now()
    else:
        dt = datetime.now()
    cur.execute(
        'INSERT INTO emissions (user_id, source, amount_kg, date) VALUES (?, ?, ?, ?)',
        (user_id, source, amount, dt.isoformat())
    )
    conn.commit()
    conn.close()
    print(f"Recorded {amount} kg CO₂ from '{source}' for user {email}.")

def total_emissions(email=None):
    conn = get_connection()
    cur = conn.cursor()
    if email:
        cur.execute('SELECT id FROM users WHERE email = ?', (email,))
        row = cur.fetchone()
        if not row:
            print(f"No user found with email {email}.")
            conn.close()
            return
        user_id = row['id']
        cur.execute('SELECT SUM(amount_kg) as total FROM emissions WHERE user_id = ?', (user_id,))
    else:
        cur.execute('SELECT SUM(amount_kg) as total FROM emissions')
    result = cur.fetchone()
    total = result['total'] if result['total'] is not None else 0.0
    conn.close()
    if email:
        print(f"Total emissions for {email}: {total:.2f} kg CO₂")
    else:
        print(f"Total emissions for all users: {total:.2f} kg CO₂")

def generate_report(email=None):
    conn = get_connection()
    cur = conn.cursor()
    if email:
        cur.execute('SELECT id, name FROM users WHERE email = ?', (email,))
        user_row = cur.fetchone()
        if not user_row:
            print(f"No user found with email {email}.")
            conn.close()
            return
        user_id = user_row['id']
        user_name = user_row['name']
        cur.execute('SELECT source, amount_kg, date FROM emissions WHERE user_id = ? ORDER BY date', (user_id,))
        rows = cur.fetchall()
        print(f"=== Emission Report for {user_name} ({email}) ===")
        total = 0.0
        for r in rows:
            print(f"{r['date'][:10]} | {r['source']:15} | {r['amount_kg']:7.2f} kg")
            total += r['amount_kg']
        print('-' * 40)
        print(f"Total: {total:.2f} kg CO₂")
    else:
        # Report for all users aggregated by source
        cur.execute('SELECT u.name, u.email, e.source, e.amount_kg, e.date FROM emissions e JOIN users u ON e.user_id = u.id ORDER BY u.name, e.date')
        rows = cur.fetchall()
        if not rows:
            print("No emission records found.")
            conn.close()
            return
        print("=== Emission Report for All Users ===")
        current_user = None
        total_user = 0.0
        grand_total = 0.0
        for r in rows:
            if r['name'] != current_user:
                if current_user is not None:
                    print(f"  Sub‑total for {current_user}: {total_user:.2f} kg CO₂")
                    print()
                current_user = r['name']
                total_user = 0.0
                print(f"User: {current_user} ({r['email']})")
            print(f"  {r['date'][:10]} | {r['source']:15} | {r['amount_kg']:7.2f} kg")
            total_user += r['amount_kg']
            grand_total += r['amount_kg']
        print(f"\nGrand Total Emissions: {grand_total:.2f} kg CO₂")
    conn.close()

def main():
    parser = argparse.ArgumentParser(
        description='Carbon Emission Collector – record and analyse CO₂ emissions.'
    )
    subparsers = parser.add_subparsers(dest='command')

    # init
    subparsers.add_parser('init', help='Create/initialize the SQLite database.')

    # add_user
    pu = subparsers.add_parser('add_user', help='Add a new user.')
    pu.add_argument('name', help='Full name of the user')
    pu.add_argument('email', help='Email address (must be unique)')

    # add_emission
    pe = subparsers.add_parser('add_emission', help='Record an emission entry.')
    pe.add_argument('email', help='Email of the user owning this entry')
    pe.add_argument('source', help='Source of emission (e.g., "vehicle", "electricity")')
    pe.add_argument('amount', type=float, help='CO₂ amount in kilograms')
    pe.add_argument('--date', help='Date/time in ISO format (default: now)')

    # total
    pt = subparsers.add_parser('total', help='Show total emissions.')
    pt.add_argument('--email', help='Optional email to limit to a single user')

    # report
    pr = subparsers.add_parser('report', help='Generate a human‑readable report.')
    pr.add_argument('--email', help='Optional email for a per‑user report')

    args = parser.parse_args()
    if args.command == 'init':
        init_db()
    elif args.command == 'add_user':
        init_db()
        add_user(args.name, args.email)
    elif args.command == 'add_emission':
        init_db()
        add_emission(args.email, args.source, args.amount, args.date)
    elif args.command == 'total':
        init_db()
        total_emissions(args.email)
    elif args.command == 'report':
        init_db()
        generate_report(args.email)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    main()
