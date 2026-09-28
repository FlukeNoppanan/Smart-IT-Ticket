import unittest
from presentation import history_rows, role_label, status_label

class PresentationTests(unittest.TestCase):
    def test_history_uses_readable_thai_labels(self):
        users = [{'id': 'admin', 'name': 'Admin', 'username': 'admin', 'email': 'admin@example.test'},
                 {'id': 'user', 'name': 'User', 'username': 'user', 'email': 'user@example.test'}]
        history = [{'actor_id': 'admin', 'target_id': 'user', 'old_role': None,
                    'old_team': None, 'new_role': 'it_staff',
                    'new_team': 'Network Engineer Team', 'old_status': 'pending',
                    'new_status': 'active', 'changed_at': '2026-09-28T09:00:00+00:00'}]
        row = history_rows(history, users)[0]
        self.assertEqual(row['ผู้ดำเนินการ'], 'Admin (admin)')
        self.assertEqual(row['บัญชีที่เปลี่ยน'], 'User (user)')
        self.assertEqual(row['สถานะเดิม'], 'รออนุมัติ')
        self.assertEqual(row['สถานะใหม่'], 'ใช้งานได้')
        self.assertEqual(row['สิทธิ์ใหม่'], 'เจ้าหน้าที่ไอที')
        self.assertEqual(row['วันที่และเวลา'], '28/09/2026 16:00')

if __name__ == '__main__': unittest.main()
