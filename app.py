from html import escape
import streamlit as st
from local_auth import AuthError
from presentation import STATUS_LABELS, ROLE_LABELS, status_label, role_label, team_label, history_rows
from ticket_store import (AccessDenied, TEAMS, init_db, authenticate, register_user,
                          session_user, change_password, list_tickets, get_ticket,
                          create_ticket, set_status, list_users, role_history, change_access)

st.set_page_config(page_title='Smart IT Ticket', page_icon='🎫', layout='wide')
st.markdown('''<style>
:root{--ink:#142536;--muted:#657789;--line:#e3eaf0;--blue:#1267a5}
.block-container{max-width:1180px;padding-top:2rem;padding-bottom:3rem}
[data-testid="stSidebar"]{background:#f4f8fb;border-right:1px solid #e3eaf0}
.hero{padding:24px 28px;border-radius:18px;background:linear-gradient(120deg,#102a43,#1267a5);color:white;margin:4px 0 22px}
.hero h1{color:white;margin:0 0 6px}.hero p{margin:0;color:#dbeaf5}
.card{border:1px solid #e3eaf0;border-radius:14px;padding:18px 20px;background:#fff;margin-bottom:12px}
.small{color:#657789;font-size:.92rem}.badge{display:inline-block;padding:4px 10px;border-radius:999px;background:#eaf4fb;color:#145c8a;font-size:.85rem;font-weight:600}
[data-testid="stMetric"]{background:white;border:1px solid #e3eaf0;padding:14px;border-radius:14px}
</style>''', unsafe_allow_html=True)


def classify(text):
    t=text.casefold()
    groups={
      'Network':['wifi','wi-fi','อินเทอร์เน็ต','internet','เน็ต','network','เครือข่าย','vpn','lan','dns','dhcp','router','สัญญาณ'],
      'Hardware':['เครื่องเปิดไม่ติด','เปิดไม่ติด','จอ','monitor','keyboard','คีย์บอร์ด','เมาส์','mouse','printer','ปริ้นเตอร์','hardware','ฮาร์ดแวร์','แบต','battery'],
      'Software':['ติดตั้ง','โปรแกรม','software','ซอฟต์แวร์','error','แอป','application','windows','excel','word','outlook','teams','ค้าง','crash']}
    scores={k:sum(1 for kw in words if kw in t) for k,words in groups.items()}
    best=max(scores,key=scores.get)
    if scores[best]==0: return 'General Support',65
    return best,min(98,74+scores[best]*8)

def priority(text):
    t=text.casefold()
    if any(x in t for x in ['ด่วน','ทั้งแผนก','ใช้งานไม่ได้เลย','ระบบล่ม','urgent','down']):return 'High'
    if any(x in t for x in ['ช้า','หลุด','ผิดพลาด','error','ไม่ได้']):return 'Medium'
    return 'Low'

def logout():
    st.session_state.pop('actor_id', None)
    st.rerun()

init_db()
if 'actor_id' not in st.session_state:
    st.markdown('<div class="hero"><h1>🎫 Smart IT Ticket</h1><p>ระบบ Ticket สำหรับผู้ใช้ภายใน</p></div>', unsafe_allow_html=True)
    login_tab, signup_tab = st.tabs(['เข้าสู่ระบบ', 'สมัครบัญชี'])
    with login_tab:
        with st.form('login'):
            login_name = st.text_input('Username หรือ Email')
            login_password = st.text_input('Password', type='password')
            login_clicked = st.form_submit_button('เข้าสู่ระบบ')
        if login_clicked:
            try:
                st.session_state.actor_id = authenticate(login_name, login_password)
                st.rerun()
            except AccessDenied:
                st.error('เข้าสู่ระบบไม่สำเร็จ กรุณาตรวจสอบข้อมูลหรือสถานะบัญชี')
    with signup_tab:
        with st.form('signup'):
            new_name = st.text_input('ชื่อที่แสดง')
            new_username = st.text_input('Username')
            new_email = st.text_input('Email')
            new_password = st.text_input('Password (อย่างน้อย 12 ตัวอักษร)', type='password')
            confirm_password = st.text_input('ยืนยัน Password', type='password')
            signup_clicked = st.form_submit_button('สมัครบัญชี')
        if signup_clicked:
            if new_password != confirm_password:
                st.error('Password ไม่ตรงกัน')
            else:
                try:
                    register_user(new_username, new_email, new_password, new_name)
                    st.success('รับคำขอสมัครบัญชีแล้ว กรุณารอ Admin อนุมัติ')
                except AuthError as exc:
                    st.error(str(exc))
    st.stop()

actor_id = st.session_state.actor_id
try:
    me = session_user(actor_id)
except AccessDenied:
    logout()
role = me['role']
if me['must_change_password']:
    st.warning('ต้องเปลี่ยน Password ก่อนใช้งาน')
    with st.form('change_password'):
        old_password = st.text_input('Password เดิม', type='password')
        new_password = st.text_input('Password ใหม่ (อย่างน้อย 12 ตัวอักษร)', type='password')
        confirm_new = st.text_input('ยืนยัน Password ใหม่', type='password')
        changed = st.form_submit_button('เปลี่ยน Password')
    if changed:
        if new_password != confirm_new:
            st.error('Password ไม่ตรงกัน')
        else:
            try:
                change_password(actor_id, old_password, new_password)
                st.success('เปลี่ยน Password แล้ว')
                st.rerun()
            except (AccessDenied, AuthError) as exc:
                st.error(str(exc) or 'เปลี่ยน Password ไม่สำเร็จ')
    st.button('ออกจากระบบ', on_click=logout)
    st.stop()
if role not in ('user', 'it_staff', 'admin') or (role == 'it_staff' and me['team'] not in TEAMS.values()):
    st.warning('บัญชีนี้ยังไม่ได้รับสิทธิ์หรือทีม กรุณาติดต่อ Admin')
    st.button('ออกจากระบบ', on_click=logout)
    st.stop()

with st.sidebar:
    st.markdown('### 🎫 Smart IT Ticket')
    st.caption(f"เข้าสู่ระบบ: **{me['name']}**")
    role_name = me['team'] if role == 'it_staff' else {'user':'ผู้แจ้งปัญหา','admin':'ผู้ดูแลระบบ'}[role]
    st.caption(role_name)
    menus = {'user':['แจ้งปัญหา','Ticket ของฉัน'],
             'it_staff':['งานของทีม'],
             'admin':['ภาพรวม','Ticket ทั้งหมด','จัดการผู้ใช้','ทดสอบ Classifier']}
    page = st.radio('เมนู', menus[role], label_visibility='collapsed')
    st.divider()
    st.button('ออกจากระบบ', on_click=logout, use_container_width=True)

try:
    tickets = list_tickets(actor_id)
except AccessDenied:
    st.error('ไม่มีสิทธิ์เข้าถึงข้อมูล')
    st.stop()


def header(title,sub):st.markdown(f'<div class="hero"><h1>{title}</h1><p>{sub}</p></div>',unsafe_allow_html=True)
def show_ticket(t,staff=False):
    try:
        t = get_ticket(actor_id, t['id'])
    except AccessDenied:
        st.error('ไม่มีสิทธิ์เข้าถึง Ticket')
        return
    safe = {key: escape(str(t[key])) for key in ('code','title','created_at','owner','body','category','priority','status','team','confidence')}
    st.markdown(f'''<div class="card"><b>{safe['code']} · {safe['title']}</b><br><span class="small">{safe['created_at']} · ผู้แจ้ง {safe['owner']}</span><hr><p>{safe['body']}</p><span class="badge">{safe['category']}</span>　<span class="badge">{safe['priority']}</span>　<span class="badge">{safe['status']}</span><p class="small">ส่งให้: {safe['team']} · NLP confidence: {safe['confidence']}%</p></div>''',unsafe_allow_html=True)
    if staff:
        options=['รอรับเรื่อง','กำลังดำเนินการ','เสร็จสิ้น']; current=options.index(t['status']) if t['status'] in options else 0
        c1,c2=st.columns([2,1]); choice=c1.selectbox(f"สถานะ {t['code']}",options,index=current,key=f"s{t['id']}")
        if c2.button('บันทึกสถานะ',key=f"b{t['id']}"):
            try:
                set_status(actor_id, t['id'], choice)
                st.success('บันทึกแล้ว')
                st.rerun()
            except AccessDenied:
                st.error('ไม่มีสิทธิ์แก้ไข Ticket')

if page=='แจ้งปัญหา' and role=='user':
    header('แจ้งปัญหา','พิมพ์อาการที่พบ ระบบจะจัดประเภทและส่งไปยังทีมที่เกี่ยวข้อง')
    with st.form('new_ticket',clear_on_submit=True):
        title=st.text_input('หัวข้อปัญหา',placeholder='เช่น Wi-Fi หลุดบ่อย')
        body=st.text_area('รายละเอียด',placeholder='อธิบายอาการและสิ่งที่ลองทำแล้ว',height=140)
        submitted=st.form_submit_button('วิเคราะห์และส่ง Ticket',type='primary')
    if submitted:
        if not title.strip() or not body.strip():st.warning('กรอกหัวข้อและรายละเอียดก่อนส่ง')
        else:
            code,cat,team,conf,p=create_ticket(actor_id,title.strip(),body.strip(),classify,priority)
            st.success(f'สร้าง {code} แล้ว · {cat} → {team}')
            st.info(f'Priority: {p} · Confidence: {conf}%')
            if conf<70:st.warning('ความมั่นใจต่ำ: ควรให้เจ้าหน้าที่ตรวจสอบหมวดหมู่')
elif page=='Ticket ของฉัน' and role=='user':
    header('Ticket ของฉัน','ติดตามสถานะคำขอที่คุณส่ง')
    mine=tickets
    if not mine:st.info('ยังไม่มี Ticket')
    for t in mine:show_ticket(t)
elif page=='งานของทีม' and role=='it_staff':
    header('งานของทีม',f"Ticket ที่ Routing มายัง {me['team']}")
    assigned=tickets
    if not assigned:st.info('ยังไม่มี Ticket ที่ส่งมายังทีมนี้')
    for t in assigned:show_ticket(t,True)
elif page=='ภาพรวม' and role=='admin':
    header('ภาพรวมระบบ','สรุป Ticket ทุกทีมและสถานะการดำเนินงาน')
    c1,c2,c3,c4=st.columns(4); c1.metric('Ticket ทั้งหมด',len(tickets)); c2.metric('รอรับเรื่อง',sum(t['status']=='รอรับเรื่อง' for t in tickets)); c3.metric('กำลังดำเนินการ',sum(t['status']=='กำลังดำเนินการ' for t in tickets)); c4.metric('เสร็จสิ้น',sum(t['status']=='เสร็จสิ้น' for t in tickets))
    st.subheader('จำนวนตามประเภทและทีม')
    cats={k:sum(t['category']==k for t in tickets) for k in TEAMS}; st.bar_chart(cats)
    st.subheader('Ticket ล่าสุด')
    for t in tickets[:10]:show_ticket(t)
elif page=='Ticket ทั้งหมด' and role=='admin':
    header('Ticket ทั้งหมด','Admin สามารถดูและอัปเดตทุกทีม')
    for t in tickets:show_ticket(t,True)
elif page=='จัดการผู้ใช้' and role=='admin':
    header('จัดการผู้ใช้','อนุมัติ กำหนดสิทธิ์ หรือปิดบัญชี')
    try:
        users=list_users(actor_id)
        for user in users:
            summary = (f"{user['name']} ({user['username'] or user['email'] or user['id']}) · "
                       f"{status_label(user['status'])} · {role_label(user['role'])} · {team_label(user['team'])}")
            with st.expander(summary, expanded=False):
                st.caption(f"อีเมล: {user['email'] or 'ไม่ระบุ'}")
                if user['id'] == actor_id:
                    st.info('บัญชีของคุณ: ไม่สามารถเปลี่ยนสิทธิ์ของตัวเองได้')
                    continue
                with st.form(f"access_{user['id']}"):
                    statuses = ('pending', 'active', 'disabled')
                    roles = ('user', 'it_staff', 'admin')
                    teams = (None, *TEAMS.values())
                    status_choice = st.selectbox('สถานะบัญชี', statuses,
                        index=statuses.index(user['status']), format_func=status_label)
                    role_choice = st.selectbox('สิทธิ์เมื่ออนุมัติ', roles,
                        index=roles.index(user['role']) if user['role'] in roles else 0,
                        format_func=role_label)
                    team_choice = st.selectbox('ทีมของเจ้าหน้าที่ไอที', teams,
                        index=teams.index(user['team']) if user['team'] in teams else 0,
                        format_func=team_label)
                    if st.form_submit_button('บันทึกสิทธิ์'):
                        try:
                            selected_role = role_choice if status_choice == 'active' else None
                            selected_team = team_choice if selected_role == 'it_staff' else None
                            if selected_role == 'it_staff' and selected_team is None:
                                st.error('ต้องเลือกทีมสำหรับเจ้าหน้าที่ไอที')
                            elif change_access(actor_id, user['id'], selected_role, selected_team, status_choice):
                                st.success('บันทึกสิทธิ์แล้ว')
                                st.rerun()
                        except AccessDenied:
                            st.error('ไม่มีสิทธิ์จัดการผู้ใช้')
        st.subheader('ประวัติการเปลี่ยนสิทธิ์')
        history = history_rows(role_history(actor_id), users)
        if history:
            st.dataframe(history, use_container_width=True, hide_index=True)
        else:
            st.info('ยังไม่มีประวัติการเปลี่ยนสิทธิ์')
    except AccessDenied:
        st.error('ไม่มีสิทธิ์จัดการผู้ใช้')
elif page=='ทดสอบ Classifier' and role=='admin':
    header('ทดสอบ Classifier','ประเมินผลจากข้อความทดสอบและหมวดที่คาดหวัง')
    import pandas as pd
    st.caption('อัปโหลด CSV ที่มีคอลัมน์ text และ expected_category')
    f=st.file_uploader('CSV',type=['csv'])
    if f:
        try:
            df=pd.read_csv(f); needed={'text','expected_category'}
            if not needed.issubset(df.columns):st.error('ต้องมีคอลัมน์ text และ expected_category')
            else:
                df['predicted_category']=df['text'].astype(str).apply(lambda x:classify(x)[0]); df['correct']=df['predicted_category']==df['expected_category'].astype(str)
                st.metric('Accuracy',f"{df['correct'].mean()*100:.1f}%",f"{int(df['correct'].sum())}/{len(df)} ถูกต้อง")
                st.dataframe(df,use_container_width=True,hide_index=True)
        except Exception as e:st.error(f'อ่าน CSV ไม่สำเร็จ: {e}')

else:
    st.error('ไม่มีสิทธิ์เข้าถึงหน้านี้')
