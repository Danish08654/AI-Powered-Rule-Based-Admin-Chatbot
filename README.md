# Admin Chatbot 

A chat-style admin tool for managing users (add / remove / update / search /
count / list) via natural-language commands, backed by a local SQLite
database (`users.db`, created automatically on first run).

----

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

-----

Then open the URL Streamlit prints (usually `http://localhost:8501`).

On first run, the app seeds one admin account (`admin@example.com` by
default) so you always have a way to log in. Change this by setting an
`ADMIN_EMAIL` secret (see below).

-----

## Commands supported

- `add the user "email" phone number "+123456789"` (optionally `city "Lahore"`)
- `remove the user "email"` / `delete the user "email"`
- `update "email" city to Lahore`
- `update "email" phone to +123456789`
- `update "email" email to new@example.com`
- `search user "email"` / `find user "email"`
- `count users` / `how many users`
- `show all users` / `list users`
- `remove all users` (asks for a `confirm remove all users` before deleting)
- `help`

- ---

# Made by Danish Zulfiqar

----
