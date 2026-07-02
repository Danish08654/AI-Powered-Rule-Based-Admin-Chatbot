from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import re

app = Flask(__name__)
app.secret_key = "supersecret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
db = SQLAlchemy(app)

# ----------------- Database Model -----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    city = db.Column(db.String(50))

with app.app_context():
    db.create_all()

# ----------------- Login -----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()
        if user:  # auto login if exists
            session["user"] = email
            return redirect(url_for("chat"))
        else:
            return render_template("login.html", error="Email not found in system.")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# ----------------- Chat Page -----------------
@app.route("/chat")
def chat():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("chat.html")

# ----------------- Chatbot Logic -----------------
@app.route("/chat", methods=["POST"])
def chat_post():
    data = request.get_json()
    msg = data.get("message", "").lower().strip()
    reply = "Sorry, I didn’t understand that command."

    # --- Add User ---
    if "add the user" in msg:
        match = re.search(r'\"(.+?)\".*phone number\s+\"?([\+\d]+)\"?', msg)
        if match:
            email = match.group(1)
            phone = match.group(2)
            if User.query.filter_by(email=email).first():
                reply = f"User {email} already exists."
            else:
                new_user = User(email=email, phone=phone)
                db.session.add(new_user)
                db.session.commit()
                reply = f"User {email} added with phone {phone}."
        else:
            reply = "Please provide email and phone number in quotes."

    # --- Remove User ---
    elif "remove the user" in msg or "delete the user" in msg:
        match = re.search(r'\"(.+?)\"', msg)
        if match:
            email = match.group(1)
            user = User.query.filter_by(email=email).first()
            if user:
                db.session.delete(user)
                db.session.commit()
                reply = f"User {email} removed successfully."
            else:
                reply = f"User {email} not found."
        else:
            reply = "Please provide the email in quotes."

    # --- Update User (city or phone) ---
    elif "update" in msg:
        match = re.search(r'update\s+\"(.+?)\"\s+(\w+)\s+to\s+([\w\+\d]+)', msg)
        if match:
            email = match.group(1)
            field = match.group(2).lower()
            value = match.group(3)

            user = User.query.filter_by(email=email).first()
            if user:
                if field == "city":
                    user.city = value
                    db.session.commit()
                    reply = f"Updated {email}'s city to {value}."
                elif field == "phone":
                    user.phone = value
                    db.session.commit()
                    reply = f"Updated {email}'s phone to {value}."
                else:
                    reply = f"I can only update phone or city, not '{field}'."
            else:
                reply = f"User {email} not found."
        else:
            reply = "Use format: update \"email\" city to <City> or update \"email\" phone to <Number>"

    # --- Show All Users ---
    elif "show all users" in msg or "list users" in msg:
        users = User.query.all()
        if users:
            # Only include users who have at least phone or city filled
            valid_users = [u for u in users if u.phone or u.city]

            if valid_users:
                reply_lines = [f"- {u.email}" for u in valid_users]
                reply = "Users in system:\n" + "\n".join(reply_lines)
            else:
                reply = "No users found in the system."
        else:
            reply = "No users found in the system."

    return jsonify({"reply": reply})

# ----------------- Run -----------------
if __name__ == "__main__":
    app.run(debug=True)
