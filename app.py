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
    "**Here's what I can do:**\n\n"
    "- `add the user \"email\" phone number \"+123456789\"` "
    "(optionally add `city \"Lahore\"`)\n"
    "- `remove the user \"email\"` / `delete the user \"email\"`\n"
    "- `update \"email\" city to Lahore`\n"
    "- `update \"email\" phone to +123456789`\n"
    "- `update \"email\" email to new@example.com`\n"
    "- `search user \"email\"` / `find user \"email\"` (show details)\n"
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

    # Seed a first admin account so the app is never impossible to log into.
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
    if "remove all users" in msg:
        st.session_state.pending_action = "remove_all"
        return ("This will delete **all** users permanently. "
                "Type `confirm remove all users` to proceed.")

    if msg == "confirm remove all users":
        if st.session_state.get("pending_action") == "remove_all":
            conn.execute("DELETE FROM users")
            conn.commit()
            st.session_state.pending_action = None
            return " All users have been removed."
        return "Nothing to confirm."

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

    # ---- Search / find single user ----
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
        n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        return f"There {'is' if n == 1 else 'are'} {n} user(s) in the system."

    # ---- List all users ----
    if "show all users" in msg or "list users" in msg or "list all users" in msg:
        users = all_users(conn)
        if not users:
            return "No users found in the system."
        lines = [f"- {e}" + (f" ({phone})" if phone else "") for e, phone, _city in users]
        return "**Users in system:**\n" + "\n".join(lines)

    return "Sorry, I didn't understand that command. Type `help` to see available commands."


# UI

st.set_page_config(page_title="Admin Chatbot", page_icon="👩‍💻", layout="centered")

st.markdown(
    """
    <style>
    .app-header {
        background: linear-gradient(135deg, #007bff, #6c63ff);
        color: white;
        padding: 16px 20px;
        border-radius: 12px;
        font-size: 20px;
        font-weight: 600;
        margin-bottom: 16px;
    }
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


def login_view():
    st.markdown("<div class='app-header'> Admin Chatbot Login</div>", unsafe_allow_html=True)
    st.caption(f"First time here? `{ADMIN_EMAIL}` is pre-seeded so you can log in immediately.")
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("Enter your email", key="login_email")
        submitted = st.form_submit_button("Login", use_container_width=True)
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
            st.error("Email not found in system. Ask an existing admin to add you first.")


def chat_view():
    header_col, logout_col = st.columns([4, 1])
    with header_col:
        st.markdown("<div class='app-header'> Admin Chatbot</div>", unsafe_allow_html=True)
    with logout_col:
        if st.button("Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_email = None
            st.session_state.pending_action = None
            st.rerun()

    if not st.session_state.messages:
        st.session_state.messages.append(
            {"role": "assistant", "content": "👋 Hello! How can I help you manage users today? Type `help` for a list of commands."}
        )

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    prompt = st.chat_input(
        "Type a command (e.g. add the user \"a@b.com\" phone number \"+123\")...",
        key="chat_input_box",
    )
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        try:
            reply = handle_command(conn, prompt)
        except Exception as exc:  # keep the chatbot alive even on unexpected errors
            reply = f" Something went wrong processing that command: {exc}"
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.rerun()


if st.session_state.logged_in:
    chat_view()
else:
    login_view()
