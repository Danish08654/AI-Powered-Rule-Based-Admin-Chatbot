import html
import os
import re
import sqlite3

import streamlit as st

# Config

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")

DEFAULT_ADMIN_EMAIL = "admin@example.com"
try:
    ADMIN_EMAIL = st.secrets.get("ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL)
except Exception:
    ADMIN_EMAIL = DEFAULT_ADMIN_EMAIL

HELP_TEXT = (
    "**Here's what I can do:**\n"
    "- `add the user \"email\" phone number \"+123456789\"` (optionally add `city \"Lahore\"`)\n"
    "- `remove the user \"email\"` / `delete the user \"email\"`\n"
    "- `update \"email\" city to Lahore`\n"
    "- `update \"email\" phone to +123456789`\n"
    "- `update \"email\" email to new@example.com`\n"
    "- `search user \"email\"` / `find user \"email\"`\n"
    "- `count users` / `how many users`\n"
    "- `show all users` / `list users`\n"
    "- `remove all users` (asks for confirmation)\n"
    "- `help` - show this message again"
)


# Database helpers

@st.cache_resource
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            city  TEXT
        )
        """
    )
    conn.commit()

    cur = conn.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO users (email, phone, city) VALUES (?, NULL, NULL)",
            (ADMIN_EMAIL.strip().lower(),),
        )
        conn.commit()
    return conn


def find_user(conn, email):
    cur = conn.execute(
        "SELECT id, email, phone, city FROM users WHERE email = ?", (email,)
    )
    return cur.fetchone()


def all_users(conn):
    cur = conn.execute("SELECT email, phone, city FROM users ORDER BY email")
    return cur.fetchall()


def user_count(conn):
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


# Command parsing / handling

QUOTED = r'"([^"]+)"'


def extract_email(raw):
    m = re.search(QUOTED, raw)
    return m.group(1).strip().lower() if m else None


def extract_add_fields(raw):
    email = extract_email(raw)
    phone_match = re.search(
        r'phone(?:\s*number)?\s+"?(\+?[\d][\d\-\s]{4,20}\d)"?', raw, re.IGNORECASE
    )
    city_match = re.search(r'city\s+"?([A-Za-z\s]{2,40}?)"?(?:$|\s+phone)', raw, re.IGNORECASE)
    phone = phone_match.group(1).strip() if phone_match else None
    city = city_match.group(1).strip() if city_match else None
    return email, phone, city


def handle_command(conn, raw_text):
    msg = raw_text.lower().strip()

    if msg in ("help", "commands", "?"):
        return HELP_TEXT

    # ---- Add user ----
    if "add the user" in msg or "add user" in msg:
        email, phone, city = extract_add_fields(raw_text)
        if not email or not phone:
            return ('Please provide at least an email and phone number, e.g.\n'
                    '`add the user "name@example.com" phone number "+123456789"`')
        if find_user(conn, email):
            return f"User {email} already exists."
        conn.execute(
            "INSERT INTO users (email, phone, city) VALUES (?, ?, ?)",
            (email, phone, city),
        )
        conn.commit()
        extra = f", city {city}" if city else ""
        return f" User {email} added with phone {phone}{extra}."

    # ---- Remove user ----
    
    # Exact confirm phrase must be checked BEFORE the looser "remove all
    
    if msg == "confirm remove all users":
        if st.session_state.get("pending_action") == "remove_all":
            conn.execute("DELETE FROM users")
            conn.commit()
            st.session_state.pending_action = None
            return " All users have been removed."
        return "Nothing to confirm."

    if "remove all users" in msg:
        st.session_state.pending_action = "remove_all"
        return (" This will delete **all** users permanently. "
                "Type `confirm remove all users` to proceed.")

    if "remove the user" in msg or "delete the user" in msg:
        email = extract_email(raw_text)
        if not email:
            return 'Please provide the email in quotes, e.g. `remove the user "name@example.com"`'
        user = find_user(conn, email)
        if user:
            conn.execute("DELETE FROM users WHERE email = ?", (email,))
            conn.commit()
            return f" User {email} removed successfully."
        return f"User {email} not found."

    # ---- Update user ----
    if msg.startswith("update") or " update " in msg:
        m = re.search(r'update\s+"([^"]+)"\s+(\w+)\s+to\s+(.+)', raw_text, re.IGNORECASE)
        if not m:
            return ('Use format: `update "email" city to <City>`, '
                    '`update "email" phone to <Number>`, or '
                    '`update "email" email to <new_email>`')
        email = m.group(1).strip().lower()
        field = m.group(2).strip().lower()
        value = m.group(3).strip().strip('"')

        user = find_user(conn, email)
        if not user:
            return f"User {email} not found."

        if field == "city":
            conn.execute("UPDATE users SET city = ? WHERE email = ?", (value, email))
            conn.commit()
            return f" Updated {email}'s city to {value}."
        if field == "phone":
            conn.execute("UPDATE users SET phone = ? WHERE email = ?", (value, email))
            conn.commit()
            return f" Updated {email}'s phone to {value}."
        if field == "email":
            new_email = value.lower()
            if find_user(conn, new_email):
                return f"Cannot update: {new_email} is already in use."
            conn.execute("UPDATE users SET email = ? WHERE email = ?", (new_email, email))
            conn.commit()
            return f" Updated {email}'s email to {new_email}."
        return f"I can only update phone, city, or email, not '{field}'."

    # ---- Search 
    if "search user" in msg or "find user" in msg or "show user" in msg:
        email = extract_email(raw_text)
        if not email:
            return 'Please provide the email in quotes, e.g. `search user "name@example.com"`'
        user = find_user(conn, email)
        if not user:
            return f"User {email} not found."
        _, e, phone, city = user
        return (f" **{e}**\n"
                f"- Phone: {phone or 'N/A'}\n"
                f"- City: {city or 'N/A'}")

    # ---- Count users ----
    if "count users" in msg or "how many users" in msg:
        n = user_count(conn)
        return f"There {'is' if n == 1 else 'are'} {n} user(s) in the system."

    # ---- List all users ----
    if "show all users" in msg or "list users" in msg or "list all users" in msg:
        users = all_users(conn)
        if not users:
            return "No users found in the system."
        lines = [f"- {e}" + (f" ({phone})" if phone else "") for e, phone, _city in users]
        return "**Users in system:**\n" + "\n".join(lines)

    return "Sorry, I didn't understand that command. Type `help` to see available commands."


# Presentation helpers

def initials_of(email):
    local = (email or "?").split("@")[0]
    parts = re.split(r"[.\-_]+", local)
    parts = [p for p in parts if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return local[:2].upper() if len(local) >= 2 else local[:1].upper()


def md_lite_to_html(text):
    """Render the small markdown subset used by bot replies (bold, inline
    code, and '- ' bullet lists) as safe HTML."""
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    out, in_list = [], False
    for line in text.split("\n"):
        if line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{line[2:]}</li>")
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            if line.strip():
                out.append(f"<p>{line}</p>")
    if in_list:
        out.append("</ul>")
    return "".join(out)


def render_message(role, content, user_email=None):
    is_user = role == "user"
    if is_user:
        avatar = initials_of(user_email or "admin")
        avatar_class = "avatar avatar-user"
        bubble_class = "bubble bubble-user"
        body_html = html.escape(content)
        row = f"""
        <div class="msg-row msg-user">
          <div class="{bubble_class}"><p>{body_html}</p></div>
          <div class="{avatar_class}">{avatar}</div>
        </div>"""
    else:
        body_html = md_lite_to_html(content)
        row = f"""
        <div class="msg-row msg-bot">
          <div class="avatar avatar-bot">◆</div>
          <div class="bubble bubble-bot">{body_html}</div>
        </div>"""
    st.markdown(row, unsafe_allow_html=True)



# Global styling

st.set_page_config(page_title="Admin Console", page_icon="◆", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

    :root{
        --ink:#0F172A;
        --muted:#64748B;
        --bg:#EEF1F7;
        --surface:#FFFFFF;
        --border:#E2E8F0;
        --primary:#4338CA;
        --primary-2:#6366F1;
        --primary-soft:#EEF2FF;
        --success:#15803D;
        --danger:#DC2626;
    }

    html, body, [class*="css"]{
        font-family:'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color:var(--ink);
    }

    /* page chrome */
    .stApp{ background:var(--bg); }
    #MainMenu, footer, [data-testid="stToolbar"]{ visibility:hidden; height:0; }
    [data-testid="stHeader"]{ background:transparent; }
    [data-testid="stAppViewContainer"] > .main{ padding-top:0.5rem; }
    .block-container{ padding-top:1.2rem; max-width:900px; }

    /* sidebar */
    [data-testid="stSidebar"]{
        background:var(--ink);
        border-right:1px solid #1E293B;
    }
    [data-testid="stSidebar"] *{ color:#E2E8F0 !important; }
    [data-testid="stSidebar"] .stButton>button{
        background:#1E293B;
        border:1px solid #334155;
        color:#F1F5F9 !important;
        border-radius:10px;
        font-size:13.5px;
        font-weight:500;
        text-align:left;
        padding:8px 12px;
    }
    [data-testid="stSidebar"] .stButton>button:hover{
        border-color:var(--primary-2);
        background:#273449;
    }
    [data-testid="stSidebar"] [data-testid="stMetricValue"]{
        color:#FFFFFF !important;
        font-family:'Sora', sans-serif;
    }
    [data-testid="stSidebar"] [data-testid="stMetricLabel"]{ color:#94A3B8 !important; }
    [data-testid="stSidebar"] hr{ border-color:#1E293B; }

    .brand{
        display:flex; align-items:center; gap:10px;
        margin-bottom:4px;
    }
    .brand-mark{
        width:34px; height:34px; border-radius:9px; flex-shrink:0;
        background:linear-gradient(135deg, var(--primary-2), var(--primary));
        display:flex; align-items:center; justify-content:center;
        color:white; font-family:'Sora', sans-serif; font-weight:700; font-size:15px;
        box-shadow:0 4px 10px rgba(67,56,202,0.35);
    }
    .brand-name{ font-family:'Sora', sans-serif; font-weight:700; font-size:16.5px; color:#fff !important; }
    .brand-sub{ font-size:12px; color:#94A3B8 !important; margin-top:-2px; }

    .sidebar-section-label{
        font-size:11px; text-transform:uppercase; letter-spacing:.06em;
        color:#64748B !important; font-weight:600; margin:18px 0 8px 0;
    }

    /* main header */
    .console-header{
        display:flex; align-items:center; justify-content:space-between;
        margin-bottom:18px;
    }
    .console-title{ font-family:'Sora', sans-serif; font-weight:700; font-size:22px; color:var(--ink); }
    .console-sub{ font-size:13px; color:var(--muted); margin-top:2px; }
    .pill{
        background:var(--surface); border:1px solid var(--border);
        padding:6px 12px; border-radius:999px; font-size:12.5px; color:var(--muted);
        display:flex; align-items:center; gap:6px;
    }
    .pill-dot{ width:7px; height:7px; border-radius:50%; background:var(--success); display:inline-block; }

    /* chat card */
    .chat-card{
        background:var(--surface); border:1px solid var(--border);
        border-radius:16px; padding:20px 20px 6px 20px;
        box-shadow:0 1px 2px rgba(15,23,42,0.04);
        margin-bottom:14px;
    }

    /* message rows */
    .msg-row{ display:flex; align-items:flex-end; gap:10px; margin-bottom:14px; }
    .msg-user{ justify-content:flex-end; }
    .msg-bot{ justify-content:flex-start; }

    .avatar{
        width:30px; height:30px; border-radius:8px; flex-shrink:0;
        display:flex; align-items:center; justify-content:center;
        font-size:12px; font-weight:700; font-family:'Sora', sans-serif;
    }
    .avatar-bot{
        background:linear-gradient(135deg, var(--primary-2), var(--primary));
        color:white;
    }
    .avatar-user{
        background:var(--ink); color:white;
    }

    .bubble{
        max-width:72%; padding:11px 15px; border-radius:14px; font-size:14.5px; line-height:1.5;
    }
    .bubble p{ margin:0 0 4px 0; }
    .bubble p:last-child{ margin-bottom:0; }
    .bubble ul{ margin:2px 0 4px 18px; padding:0; }
    .bubble li{ margin-bottom:2px; }
    .bubble code{
        background:rgba(15,23,42,0.06); padding:1px 5px; border-radius:5px;
        font-family:'JetBrains Mono', monospace; font-size:12.8px;
    }

    .bubble-bot{
        background:#F8FAFC; border:1px solid var(--border); color:var(--ink);
        border-bottom-left-radius:4px;
    }
    .bubble-bot code{ background:var(--primary-soft); color:var(--primary); }
    .bubble-user{
        background:linear-gradient(135deg, var(--primary-2), var(--primary));
        color:white; border-bottom-right-radius:4px;
    }

    /* chat input */
    [data-testid="stChatInput"]{
        border-radius:14px; border:1px solid var(--border);
        background:var(--surface); box-shadow:0 1px 2px rgba(15,23,42,0.04);
    }
    
    [data-testid="stChatInput"] textarea{ font-size:14.5px; }

    /* login card */
    .login-wrap{ display:flex; justify-content:center; margin-top:6vh; }
    .login-card{
        background:var(--surface); border:1px solid var(--border);
        border-radius:18px; padding:36px 34px; width:100%; max-width:400px;
        box-shadow:0 10px 30px rgba(15,23,42,0.08);
        text-align:center;
    }
    
    .login-mark{
        width:52px; height:52px; border-radius:14px; margin:0 auto 16px auto;
        background:linear-gradient(135deg, var(--primary-2), var(--primary));
        display:flex; align-items:center; justify-content:center;
        color:white; font-family:'Sora', sans-serif; font-weight:700; font-size:22px;
        box-shadow:0 8px 20px rgba(67,56,202,0.3);
    }
    
    .login-title{ font-family:'Sora', sans-serif; font-weight:700; font-size:20px; color:var(--ink); margin-bottom:4px; }
    .login-sub{ font-size:13.5px; color:var(--muted); margin-bottom:22px; }
    .login-hint{
        font-size:12px; color:var(--muted); margin-top:16px;
        background:var(--primary-soft); border-radius:8px; padding:8px 10px;
    }
    
    .login-hint code{ font-family:'JetBrains Mono', monospace; color:var(--primary); }

    .stTextInput input{ border-radius:10px; border:1px solid var(--border); padding:10px 12px; }
    .stTextInput input:focus{ border-color:var(--primary-2); box-shadow:0 0 0 3px var(--primary-soft); }

    div[data-testid="stForm"] .stButton>button,
    .main .stButton>button{
        background:linear-gradient(135deg, var(--primary-2), var(--primary));
        color:white; border:none; border-radius:10px; font-weight:600;
        padding:10px 16px; box-shadow:0 4px 12px rgba(67,56,202,0.25);
    }
    
    .main .stButton>button:hover{ filter:brightness(1.05); }
    </style>
    """,
    unsafe_allow_html=True,
)

conn = get_conn()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_action" not in st.session_state:
    st.session_state.pending_action = None


def run_and_log(conn, cmd_text):
    st.session_state.messages.append({"role": "user", "content": cmd_text})
    try:
        reply = handle_command(conn, cmd_text)
    except Exception as exc:
        reply = f" Something went wrong processing that command: {exc}"
    st.session_state.messages.append({"role": "assistant", "content": reply})


# Views

def login_view():
    st.markdown('<div class="login-wrap"><div class="login-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="login-mark">◆</div>'
        '<div class="login-title">Admin Console</div>'
        unsafe_allow_html=True,
    )
    
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("Email", key="login_email", placeholder="you@example.com", label_visibility="collapsed")
        submitted = st.form_submit_button("Sign in", use_container_width=True)
    if submitted:
        email = (email or "").strip().lower()
        if not email:
            st.error("Please enter an email.")
        elif find_user(conn, email):
            st.session_state.logged_in = True
            st.session_state.user_email = email
            st.session_state.messages = []
            st.rerun()
        else:
            st.error("Email not found in system. Admin to add you first.")
    st.markdown(
        f'<div class="login-hint">First time here? <code>{html.escape(ADMIN_EMAIL)}</code> '
        f'you can sign in immediately.</div>',
        unsafe_allow_html=True,
    )
    
    st.markdown("</div></div>", unsafe_allow_html=True)


def render_sidebar(conn):
    with st.sidebar:
        st.markdown(
            '<div class="brand">'
            '<div class="brand-mark">◆</div>'
            '<div><div class="brand-name">Admin Console</div>'
            '<div class="brand-sub">User directory</div></div>'
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        st.metric("Total users", user_count(conn))

        st.markdown('<div class="sidebar-section-label">Quick actions</div>', unsafe_allow_html=True)
        if st.button("  List all users", use_container_width=True, key="qa_list"):
            run_and_log(conn, "list users")
            st.rerun()
        if st.button("  Count users", use_container_width=True, key="qa_count"):
            run_and_log(conn, "count users")
            st.rerun()
        if st.button("  Show help", use_container_width=True, key="qa_help"):
            run_and_log(conn, "help")
            st.rerun()



        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("---")
        st.caption(f"Signed in as **{st.session_state.user_email}**")
        if st.button("Log out", use_container_width=True, key="logout_btn"):
            st.session_state.logged_in = False
            st.session_state.user_email = None
            st.session_state.pending_action = None
            st.rerun()


def chat_view():
    render_sidebar(conn)

    st.markdown(
        f"""
        <div class="console-header">
          <div>
            <div class="console-title">Conversations</div>
          </div>
          <div class="pill"><span class="pill-dot"></span>{user_count(conn)} users online in directory</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.messages:
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": " Hello! How can I help you? Type `help` for a list of commands.",
            }
        )

    st.markdown('<div class="chat-card">', unsafe_allow_html=True)
    for m in st.session_state.messages:
        render_message(m["role"], m["content"], st.session_state.user_email)
    st.markdown("</div>", unsafe_allow_html=True)

    prompt = st.chat_input(
        'Type a command, e.g. add the user "a@b.com" phone number "+123"...',
        key="chat_input_box",
    )
    if prompt:
        run_and_log(conn, prompt)
        st.rerun()


if st.session_state.logged_in:
    chat_view()
else:
    login_view()
