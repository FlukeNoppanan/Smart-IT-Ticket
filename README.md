# Smart IT Ticket

ระบบ Ticket ภายในที่มีบัญชี local, การอนุมัติโดย Admin และสิทธิ์ User / IT Staff / Admin ใช้ SQLite ฐานข้อมูล `tickets.db` เดิมโดยไม่ลบ Ticket เก่า

## เริ่มใช้งาน

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python setup_admin.py --username admin --email YOUR_REAL_EMAIL --name "System Admin"
streamlit run app.py
```

แทน `YOUR_REAL_EMAIL` ด้วยอีเมลของคุณ และล็อกอินด้วย username ที่ระบุหลัง `--username` หรืออีเมลนั้น คำสั่ง `setup_admin.py` จะถาม Password ในเทอร์มินัล (ไม่ส่งผ่าน command line หรือเก็บใน source code) ใช้ Password อย่างน้อย 12 ตัวอักษร สร้าง Admin ได้เพียงครั้งเดียว และบังคับเปลี่ยน Password หลังล็อกอินครั้งแรก หากมี Admin ใช้งานอยู่แล้ว ให้ Admin นั้นจัดการผู้ใช้ผ่านหน้าแอป

ถ้าสร้าง Admin คนแรกไว้แล้วแต่จำ Password ไม่ได้ ให้รัน `python setup_admin.py --reset-password` **จากเครื่องที่เก็บ `tickets.db`** คำสั่งจะถาม Password ใหม่อย่างน้อย 12 ตัวอักษร รีเซ็ตได้เฉพาะบัญชี Admin ที่สร้างจาก bootstrap และบังคับเปลี่ยน Password หลังล็อกอินอีกครั้ง

ผู้ใช้สมัครด้วยชื่อ, username, email และ Password ในแท็บ **สมัครบัญชี** ระบบจะสร้างสถานะ `pending` และยังไม่อนุญาตให้ล็อกอิน Admin เปิด **จัดการผู้ใช้** แล้วเปลี่ยนสถานะเป็น `active`, เลือก Role และเลือกทีมเมื่อ Role เป็น `it_staff` ทีมที่รองรับคือ Network Engineer Team, Hardware Technician Team, Software Support Team และ Frontline Helpdesk Admin สามารถเปลี่ยน Role/ทีม, ตั้ง `disabled`, หรือเปลี่ยนกลับเป็น `pending` เพื่อเพิกถอนสิทธิ์ได้ การเปลี่ยนเหล่านี้บันทึกใน Audit Log โดยไม่เก็บ Password

ล็อกอินได้ด้วย username หรือ email Password ถูกเก็บเป็น salted `scrypt` hash; ไม่มีบัญชีเริ่มต้นหรือ Password ค้างใน source code Session อยู่ใน Streamlit session state และ logout จะล้าง session นี้ หากบัญชีถูกปิดระหว่างใช้งาน การอ่านหรือแก้ข้อมูลครั้งต่อไปจะถูกปฏิเสธ

User อ่านได้เฉพาะ Ticket ที่ตนสร้าง Staff อ่านและแก้ได้เฉพาะ Ticket ของทีม Admin จัดการ Ticket ได้ทุกทีม และ Admin เปลี่ยนสิทธิ์ของตนเองไม่ได้ Ticket เดิมยังอยู่ แต่ค่า `owner` เดิมจากบัญชีทดลองจะไม่ถูกโอนไปให้บัญชีใหม่โดยอัตโนมัติ บัญชี OIDC จากรุ่นก่อนที่ไม่มี Password local จะถูกตั้ง `disabled` หลัง migration

หากเผยแพร่ระบบ ควรให้บริการผ่าน HTTPS และจำกัดสิทธิ์ไฟล์ `tickets.db` โค้ดแยกการตรวจ Password ใน `local_auth.py` จึงสามารถเพิ่มผู้ให้บริการ OIDC ภายหลังได้โดยคงชั้นตรวจสิทธิ์ Ticket

## ทดสอบ

```bash
python -m py_compile app.py ticket_store.py local_auth.py setup_admin.py
python -m unittest discover -s tests -v
```

## เผยแพร่บน Streamlit Community Cloud

โค้ดอยู่ที่ `FlukeNoppanan/Smart-IT-Ticket`, branch `main`, ไฟล์เริ่มต้น `app.py` เมื่อเชื่อม GitHub กับบัญชี Streamlit Community Cloud แล้ว ให้เลือก **Create app → Yup, I have an app** และกรอกค่าทั้งสามรายการนี้ จากนั้นเลือกให้แอปเป็น Public

**ยังไม่ควรใช้ไฟล์ `tickets.db` ในแอป Cloud เป็นฐานข้อมูลจริง**: Streamlit Community Cloud ไม่รับประกันการเก็บไฟล์ที่แอปเขียนไว้ ข้อมูลบัญชี, password hash, สิทธิ์ และ Ticket อาจหายหลังแอปรีสตาร์ต อีกทั้งคำสั่ง `setup_admin.py` สำหรับสร้าง Admin คนแรกต้องรันในเครื่องที่เก็บฐานข้อมูลนั้น ก่อนเปิดให้ใช้งานจริงควรย้ายข้อมูลไปฐานข้อมูลภายนอกที่คงอยู่ และตั้งค่า Admin bootstrap โดยไม่ใส่ credential ลง GitHub
