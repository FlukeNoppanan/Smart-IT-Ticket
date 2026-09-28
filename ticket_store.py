"""Persistence, local accounts, and ticket authorization."""
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from local_auth import AuthError, hash_password, verify_password, validate_username, validate_email

DB = Path(__file__).with_name('tickets.db')
TEAMS = {'Network': 'Network Engineer Team', 'Hardware': 'Hardware Technician Team',
         'Software': 'Software Support Team', 'General Support': 'Frontline Helpdesk'}
ROLES = ('user', 'it_staff', 'admin')
STATUSES = ('รอรับเรื่อง', 'กำลังดำเนินการ', 'เสร็จสิ้น')

class AccessDenied(Exception):
    pass

def conn():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def init_db():
    with conn() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, owner TEXT, title TEXT, body TEXT,
            category TEXT, team TEXT, confidence INTEGER, priority TEXT, status TEXT DEFAULT 'รอรับเรื่อง',
            created_at TEXT, updated_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT, role TEXT,
            team TEXT, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
            CHECK (role IS NULL OR role IN ('user','it_staff','admin')),
            CHECK ((role = 'it_staff' AND team IS NOT NULL) OR
                   (role IS NULL AND team IS NULL) OR
                   (role IN ('user','admin') AND team IS NULL)))''')
        columns = {r['name'] for r in c.execute('PRAGMA table_info(users)')}
        for name, definition in {'username': 'TEXT', 'password_hash': 'TEXT',
                                 'status': 'TEXT', 'created_at': 'TEXT',
                                 'must_change_password': 'INTEGER NOT NULL DEFAULT 0'}.items():
            if name not in columns:
                c.execute(f'ALTER TABLE users ADD COLUMN {name} {definition}')
        c.execute("UPDATE users SET status='disabled' WHERE status IS NULL AND password_hash IS NULL")
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS users_username_unique ON users(username COLLATE NOCASE) WHERE username IS NOT NULL')
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique ON users(email COLLATE NOCASE) WHERE email IS NOT NULL')
        c.execute('''CREATE TABLE IF NOT EXISTS role_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id TEXT NOT NULL,
            target_id TEXT NOT NULL, old_role TEXT, old_team TEXT,
            new_role TEXT, new_team TEXT, changed_at TEXT NOT NULL,
            old_status TEXT, new_status TEXT)''')
        audit_columns = {r['name'] for r in c.execute('PRAGMA table_info(role_audit)')}
        for col in ('old_status', 'new_status'):
            if col not in audit_columns:
                c.execute(f'ALTER TABLE role_audit ADD COLUMN {col} TEXT')
        c.execute('CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')

def register_user(username, email, password, name):
    username = validate_username(username)
    email = validate_email(email)
    name = name.strip()
    if not name or len(name) > 100:
        raise AuthError('กรุณากรอกชื่อ')
    password_hash = hash_password(password)
    user_id = str(uuid.uuid4())
    try:
        with conn() as c:
            c.execute('''INSERT INTO users(id,name,email,role,team,first_seen,last_seen,
                      username,password_hash,status,created_at,must_change_password)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,0)''',
                      (user_id, name, email, None, None, now(), now(), username,
                       password_hash, 'pending', now()))
    except sqlite3.IntegrityError:
        raise AuthError('ไม่สามารถสมัครบัญชีด้วยข้อมูลนี้ได้') from None
    return user_id

def bootstrap_admin(username, email, password, name):
    username = validate_username(username)
    email = validate_email(email)
    password_hash = hash_password(password)
    if not name.strip():
        raise AuthError('กรุณากรอกชื่อ')
    user_id = str(uuid.uuid4())
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute("SELECT 1 FROM app_settings WHERE key='bootstrap_done'").fetchone() or c.execute("SELECT 1 FROM users WHERE role='admin' AND status='active' AND password_hash IS NOT NULL").fetchone():
            raise AccessDenied()
        c.execute('''INSERT INTO users(id,name,email,role,team,first_seen,last_seen,
                  username,password_hash,status,created_at,must_change_password)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,1)''',
                  (user_id, name.strip(), email, 'admin', None, now(), now(), username,
                   password_hash, 'active', now()))
        c.execute("INSERT INTO app_settings(key,value) VALUES('bootstrap_done',?)", (user_id,))
        c.execute('INSERT INTO role_audit(actor_id,target_id,old_role,old_team,new_role,new_team,changed_at,old_status,new_status) VALUES(?,?,?,?,?,?,?,?,?)',
                  (user_id, user_id, None, None, 'admin', None, now(), None, 'active'))
    return user_id

def reset_bootstrap_password(password):
    """Offline recovery for the original bootstrap admin only."""
    password_hash = hash_password(password)
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('''SELECT u.id FROM users u
                           JOIN app_settings s ON s.key='bootstrap_done' AND s.value=u.id
                           WHERE u.role='admin' AND u.status='active' AND u.password_hash IS NOT NULL''').fetchone()
        if row is None:
            raise AccessDenied()
        c.execute('UPDATE users SET password_hash=?,must_change_password=1 WHERE id=?',
                  (password_hash, row['id']))

def authenticate(login, password):
    with conn() as c:
        row = c.execute('SELECT * FROM users WHERE username=? COLLATE NOCASE OR email=? COLLATE NOCASE',
                        (login.strip(), login.strip())).fetchone()
        if row is None or not row['password_hash'] or not verify_password(password, row['password_hash']) or row['status'] != 'active':
            raise AccessDenied()
        c.execute('UPDATE users SET last_seen=? WHERE id=?', (now(), row['id']))
        return row['id']

def session_user_in_connection(c, actor_id):
    row = c.execute('SELECT * FROM users WHERE id=?', (actor_id,)).fetchone()
    if row is None or row['status'] != 'active':
        raise AccessDenied()
    return row

def session_user(actor_id):
    with conn() as c:
        return session_user_in_connection(c, actor_id)

def change_password(actor_id, old_password, new_password):
    new_hash = hash_password(new_password)
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        row = session_user_in_connection(c, actor_id)
        if not verify_password(old_password, row['password_hash']):
            raise AccessDenied()
        if old_password == new_password:
            raise AuthError('Password ใหม่ต้องต่างจากเดิม')
        c.execute('UPDATE users SET password_hash=?,must_change_password=0 WHERE id=?',
                  (new_hash, actor_id))

def authorized(c, actor_id):
    row = session_user_in_connection(c, actor_id)
    if row['must_change_password'] or row['role'] not in ROLES:
        raise AccessDenied()
    if row['role'] == 'it_staff' and row['team'] not in TEAMS.values():
        raise AccessDenied()
    if row['role'] != 'it_staff' and row['team'] is not None:
        raise AccessDenied()
    return row

def require_admin(c, actor_id):
    actor = authorized(c, actor_id)
    if actor['role'] != 'admin':
        raise AccessDenied()
    return actor

def list_users(actor_id):
    with conn() as c:
        require_admin(c, actor_id)
        return c.execute('SELECT id,username,name,email,role,team,status,created_at FROM users ORDER BY name,id').fetchall()

def role_history(actor_id):
    with conn() as c:
        require_admin(c, actor_id)
        return c.execute('SELECT actor_id,target_id,old_role,old_team,new_role,new_team,old_status,new_status,changed_at FROM role_audit ORDER BY id DESC').fetchall()

def change_access(actor_id, target_id, role=None, team=None, status='active'):
    if status not in ('active', 'pending', 'disabled'):
        raise ValueError('Invalid status')
    if status == 'active':
        if role not in ROLES or (role == 'it_staff' and team not in TEAMS.values()) or (role != 'it_staff' and team is not None):
            raise ValueError('Invalid role or team')
    elif role is not None or team is not None:
        raise ValueError('Inactive accounts cannot hold roles')
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        require_admin(c, actor_id)
        if actor_id == target_id:
            raise AccessDenied()
        target = c.execute('SELECT role,team,status FROM users WHERE id=?', (target_id,)).fetchone()
        if target is None:
            raise AccessDenied()
        if (target['role'], target['team'], target['status']) == (role, team, status):
            return False
        c.execute('UPDATE users SET role=?,team=?,status=? WHERE id=?', (role, team, status, target_id))
        c.execute('''INSERT INTO role_audit(actor_id,target_id,old_role,old_team,new_role,new_team,changed_at,old_status,new_status)
                  VALUES(?,?,?,?,?,?,?,?,?)''',
                  (actor_id, target_id, target['role'], target['team'], role, team, now(), target['status'], status))
        return True

def list_tickets(actor_id):
    with conn() as c:
        actor = authorized(c, actor_id)
        if actor['role'] == 'admin':
            return c.execute('SELECT * FROM tickets ORDER BY id DESC').fetchall()
        if actor['role'] == 'it_staff':
            return c.execute('SELECT * FROM tickets WHERE team=? ORDER BY id DESC', (actor['team'],)).fetchall()
        return c.execute('SELECT * FROM tickets WHERE owner=? ORDER BY id DESC', (actor_id,)).fetchall()

def get_ticket(actor_id, ticket_id):
    with conn() as c:
        actor = authorized(c, actor_id)
        ticket = c.execute('SELECT * FROM tickets WHERE id=?', (ticket_id,)).fetchone()
        if ticket is None or not (actor['role'] == 'admin' or
            (actor['role'] == 'it_staff' and ticket['team'] == actor['team']) or
            (actor['role'] == 'user' and ticket['owner'] == actor_id)):
            raise AccessDenied()
        return ticket

def create_ticket(actor_id, title, body, classify, priority):
    with conn() as c:
        actor = authorized(c, actor_id)
        if actor['role'] != 'user':
            raise AccessDenied()
        if not title.strip() or not body.strip():
            raise ValueError('Title and body are required')
        category, confidence = classify(title + ' ' + body)
        team = TEAMS[category]
        p = priority(title + ' ' + body)
        timestamp = now()
        cur = c.execute('INSERT INTO tickets(owner,title,body,category,team,confidence,priority,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (actor_id, title, body, category, team, confidence, p, STATUSES[0], timestamp, timestamp))
        code = f'TK-{cur.lastrowid:04d}'
        c.execute('UPDATE tickets SET code=? WHERE id=?', (code, cur.lastrowid))
        return code, category, team, confidence, p

def set_status(actor_id, ticket_id, status):
    if status not in STATUSES:
        raise ValueError('Invalid status')
    with conn() as c:
        actor = authorized(c, actor_id)
        ticket = c.execute('SELECT team FROM tickets WHERE id=?', (ticket_id,)).fetchone()
        if ticket is None or not (actor['role'] == 'admin' or
            (actor['role'] == 'it_staff' and ticket['team'] == actor['team'])):
            raise AccessDenied()
        c.execute('UPDATE tickets SET status=?,updated_at=? WHERE id=?', (status, now(), ticket_id))
