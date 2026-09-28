import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import ticket_store as store

PASSWORD = 'long-test-password-123'
NEW_PASSWORD = 'changed-test-password-456'

class AccessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(store, 'DB', Path(self.tmp.name) / 'tickets.db')
        self.db_patch.start()
        store.init_db()
        self.admin = store.bootstrap_admin('admin', 'admin@example.test', PASSWORD, 'Admin')
        with self.assertRaises(store.AccessDenied): store.list_users(self.admin)
        store.change_password(self.admin, PASSWORD, NEW_PASSWORD)
        self.user = self.signup('user', 'user@example.test')
        self.other = self.signup('other', 'other@example.test')
        self.network = self.signup('network', 'network@example.test')
        self.hardware = self.signup('hardware', 'hardware@example.test')
        store.change_access(self.admin, self.user, 'user')
        store.change_access(self.admin, self.other, 'user')
        store.change_access(self.admin, self.network, 'it_staff', store.TEAMS['Network'])
        store.change_access(self.admin, self.hardware, 'it_staff', store.TEAMS['Hardware'])

    def tearDown(self):
        self.db_patch.stop()
        self.tmp.cleanup()

    def signup(self, username, email):
        return store.register_user(username, email, PASSWORD, username)

    def create(self, owner, category):
        code, *_ = store.create_ticket(owner, 'title', 'body', lambda _: (category, 90), lambda _: 'Low')
        return int(code.split('-')[1])

    def test_signup_pending_login_and_hash(self):
        pending = self.signup('pending', 'pending@example.test')
        with store.conn() as c:
            row = c.execute('SELECT * FROM users WHERE id=?', (pending,)).fetchone()
            self.assertEqual(row['status'], 'pending')
            self.assertIsNone(row['role'])
            self.assertIsNone(row['team'])
            self.assertNotIn(PASSWORD, row['password_hash'])
        for login in ('pending', 'pending@example.test'):
            with self.assertRaises(store.AccessDenied): store.authenticate(login, PASSWORD)
        with self.assertRaises(store.AccessDenied): store.list_tickets(pending)
        store.change_access(self.admin, pending, 'user')
        self.assertEqual(store.authenticate('PENDING@EXAMPLE.TEST', PASSWORD), pending)
        self.assertEqual(store.authenticate('PENDING', PASSWORD), pending)
        with self.assertRaises(store.AccessDenied): store.authenticate('PENDING', 'wrong-password')
        with self.assertRaises(store.AccessDenied): store.authenticate('missing', PASSWORD)
        with self.assertRaises(store.AuthError): self.signup('pending', 'new@example.test')

    def test_bootstrap_one_time_and_forced_password(self):
        with self.assertRaises(store.AccessDenied): store.bootstrap_admin('second', 'second@example.test', PASSWORD, 'Second')
        self.assertEqual(store.authenticate('admin', NEW_PASSWORD), self.admin)
        with self.assertRaises(store.AccessDenied): store.authenticate('admin', PASSWORD)
        store.reset_bootstrap_password(PASSWORD)
        self.assertEqual(store.authenticate('admin', PASSWORD), self.admin)
        with self.assertRaises(store.AccessDenied): store.list_tickets(self.admin)
        store.change_password(self.admin, PASSWORD, NEW_PASSWORD)

    def test_user_owner_only(self):
        mine = self.create(self.user, 'Network')
        other = self.create(self.other, 'Hardware')
        self.assertEqual([t['id'] for t in store.list_tickets(self.user)], [mine])
        with self.assertRaises(store.AccessDenied): store.get_ticket(self.user, other)
        with self.assertRaises(store.AccessDenied): store.set_status(self.user, mine, store.STATUSES[1])
        with self.assertRaises(store.AccessDenied): store.list_users(self.user)

    def test_staff_team_only(self):
        network = self.create(self.user, 'Network')
        hardware = self.create(self.other, 'Hardware')
        self.assertEqual([t['id'] for t in store.list_tickets(self.network)], [network])
        with self.assertRaises(store.AccessDenied): store.get_ticket(self.network, hardware)
        with self.assertRaises(store.AccessDenied): store.set_status(self.network, hardware, store.STATUSES[1])
        store.set_status(self.network, network, store.STATUSES[1])
        self.assertEqual(store.get_ticket(self.network, network)['status'], store.STATUSES[1])

    def test_admin_disable_and_audit(self):
        network = self.create(self.user, 'Network')
        hardware = self.create(self.other, 'Hardware')
        self.assertEqual({t['id'] for t in store.list_tickets(self.admin)}, {network, hardware})
        store.set_status(self.admin, hardware, store.STATUSES[2])
        self.assertEqual(len(store.list_users(self.admin)), 5)
        store.change_access(self.admin, self.network, status='disabled')
        with self.assertRaises(store.AccessDenied): store.authenticate('network', PASSWORD)
        with self.assertRaises(store.AccessDenied): store.list_tickets(self.network)
        with self.assertRaises(store.AccessDenied): store.set_status(self.network, network, store.STATUSES[1])
        history = store.role_history(self.admin)
        self.assertTrue(any(h['target_id'] == self.network and h['old_status'] == 'active' and h['new_status'] == 'disabled' for h in history))
        with self.assertRaises(store.AccessDenied): store.change_access(self.admin, self.admin, 'user')
        with self.assertRaises(store.AccessDenied): store.change_access(self.user, self.other, 'admin')

    def test_legacy_migration_preserves_ticket(self):
        legacy_db = Path(self.tmp.name) / 'legacy.db'
        with sqlite3.connect(legacy_db) as c:
            c.execute('CREATE TABLE tickets(id INTEGER PRIMARY KEY, owner TEXT, title TEXT, team TEXT)')
            c.execute('INSERT INTO tickets(owner,title,team) VALUES(?,?,?)', ('legacy', 'old', store.TEAMS['Network']))
            c.execute('CREATE TABLE users(id TEXT PRIMARY KEY,name TEXT NOT NULL,email TEXT,role TEXT,team TEXT,first_seen TEXT NOT NULL,last_seen TEXT NOT NULL)')
            c.execute("INSERT INTO users VALUES('oidc-admin','Old admin','old@example.test','admin',NULL,'now','now')")
            c.execute('CREATE TABLE role_audit(id INTEGER PRIMARY KEY,actor_id TEXT,target_id TEXT,old_role TEXT,old_team TEXT,new_role TEXT,new_team TEXT,changed_at TEXT NOT NULL)')
        with patch.object(store, 'DB', legacy_db):
            store.init_db()
            with store.conn() as c:
                self.assertEqual(c.execute('SELECT title FROM tickets').fetchone()['title'], 'old')
                self.assertEqual(c.execute("SELECT status FROM users WHERE id='oidc-admin'").fetchone()['status'], 'disabled')
            with self.assertRaises(store.AccessDenied): store.authenticate('old@example.test', PASSWORD)

if __name__ == '__main__': unittest.main()
