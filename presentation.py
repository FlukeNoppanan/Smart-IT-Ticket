"""Thai labels for account administration."""
from datetime import datetime
from zoneinfo import ZoneInfo

STATUS_LABELS = {'pending': 'รออนุมัติ', 'active': 'ใช้งานได้', 'disabled': 'ปิดใช้งาน'}
ROLE_LABELS = {'user': 'ผู้แจ้งปัญหา', 'it_staff': 'เจ้าหน้าที่ไอที', 'admin': 'ผู้ดูแลระบบ'}

def status_label(value):
    return STATUS_LABELS.get(value, 'ยังไม่กำหนด')

def role_label(value):
    return ROLE_LABELS.get(value, 'ยังไม่กำหนด')

def team_label(value):
    return value or 'ไม่ระบุทีม'

def history_rows(history, users):
    names = {user['id']: f"{user['name']} ({user['username'] or user['email'] or user['id']})" for user in users}
    rows = []
    for item in history:
        changed = datetime.fromisoformat(item['changed_at']).astimezone(ZoneInfo('Asia/Bangkok'))
        rows.append({
            'วันที่และเวลา': changed.strftime('%d/%m/%Y %H:%M'),
            'ผู้ดำเนินการ': names.get(item['actor_id'], item['actor_id']),
            'บัญชีที่เปลี่ยน': names.get(item['target_id'], item['target_id']),
            'สถานะเดิม': status_label(item['old_status']),
            'สถานะใหม่': status_label(item['new_status']),
            'สิทธิ์เดิม': role_label(item['old_role']),
            'สิทธิ์ใหม่': role_label(item['new_role']),
            'ทีมเดิม': team_label(item['old_team']),
            'ทีมใหม่': team_label(item['new_team']),
        })
    return rows
