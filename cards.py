import streamlit as st
import sqlite3
import random
import hashlib
import os

# ────────────────────────────────────────
# PAGE CONFIG
# ────────────────────────────────────────
st.set_page_config(page_title="Card Game", page_icon="🃏", layout="wide")

# ────────────────────────────────────────
# STYLING
# ────────────────────────────────────────
st.markdown("""
<style>
.card-box {background-color: white;color: black;padding: 20px;border-radius: 16px;border: 2px solid #222;
box-shadow: 4px 4px 0px rgba(0,0,0,0.15);min-height: 120px;display: flex;align-items: center;
justify-content: center;text-align: center;font-size: 18px;font-weight: 500;}
.card-container {margin-bottom: 20px;}
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────
# SESSION STATE
# ────────────────────────────────────────
if "user_logged_in" not in st.session_state:
    st.session_state.user_logged_in = None
if "authenticated_users" not in st.session_state:
    st.session_state.authenticated_users = {}  # user_id: True if password entered
if "round_robin_index" not in st.session_state:
    st.session_state.round_robin_index = 0
if "last_drawn" not in st.session_state:
    st.session_state.last_drawn = None
if "just_drawn" not in st.session_state:
    st.session_state.just_drawn = False

# ────────────────────────────────────────
# DATABASE
# ────────────────────────────────────────
DB_PATH = 'data/game.db'
os.makedirs('data', exist_ok=True)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, password TEXT, is_admin INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS cards 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS state 
                 (key TEXT PRIMARY KEY, value INTEGER)''')
    conn.commit()

    # Create admin if not exists
    c.execute("SELECT * FROM users WHERE is_admin=1")
    if not c.fetchone():
        c.execute("INSERT INTO users (name, password, is_admin) VALUES (?, ?, 1)", 
                  ("admin", hash_pw("admin")))
        conn.commit()
    return conn

conn = init_db()
c = conn.cursor()

# ────────────────────────────────────────
# LOGIN
# ────────────────────────────────────────
if st.session_state.user_logged_in is None:
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        c.execute("SELECT id, name, is_admin FROM users WHERE name=? AND password=?", 
                  (username, hash_pw(password)))
        user = c.fetchone()
        if user:
            st.session_state.user_logged_in = {"id": user[0], "name": user[1], "is_admin": bool(user[2])}
            st.success(f"Logged in as {username}")
            st.stop()
        else:
            st.error("Invalid username or password")
    st.stop()

user_id = st.session_state.user_logged_in["id"]
user_name = st.session_state.user_logged_in["name"]
is_admin = st.session_state.user_logged_in["is_admin"]

# ────────────────────────────────────────
# SIDEBAR NAVIGATION
# ────────────────────────────────────────
with st.sidebar:
    st.title("Card Game")
    page = st.radio(
        "Navigation",
        ["Manage Users", "Manage Cards", "Draw a Card"] if is_admin else ["Manage Cards", "Draw a Card"],
        index=1 if not is_admin else 2
    )

# ────────────────────────────────────────
# MANAGE USERS (ADMIN)
# ────────────────────────────────────────
if page == "Manage Users":
    if not is_admin:
        st.warning("Only admin can manage users.")
        st.stop()

    st.title("Manage Users")
    c.execute("SELECT id, name FROM users ORDER BY name")
    users = c.fetchall()

    # Add user
    with st.form("add_user_form", clear_on_submit=True):
        new_user_name = st.text_input("New user name")
        new_user_pass = st.text_input("New user password", type="password")
        new_is_admin = st.checkbox("Admin?", value=False)
        if st.form_submit_button("Add User"):
            if new_user_name.strip() and new_user_pass.strip():
                try:
                    c.execute("INSERT INTO users (name, password, is_admin) VALUES (?, ?, ?)", 
                              (new_user_name.strip(), hash_pw(new_user_pass.strip()), int(new_is_admin)))
                    conn.commit()
                    st.success(f"User {new_user_name} added!")
                    st.stop()
                except sqlite3.IntegrityError:
                    st.error("Name exists.")

    st.markdown("---")
    st.subheader("Existing users")
    for u_id, uname in users:
        col1, col2 = st.columns([5,1])
        with col1:
            st.write(f"• {uname}")
        with col2:
            if st.button("Delete", key=f"delete_{u_id}"):
                if u_id == user_id:
                    st.error("Cannot delete yourself.")
                else:
                    c.execute("DELETE FROM cards WHERE user_id=?", (u_id,))
                    c.execute("DELETE FROM users WHERE id=?", (u_id,))
                    conn.commit()
                    st.success(f"Deleted {uname}")
                    st.stop()

# ────────────────────────────────────────
# MANAGE CARDS (CURRENT USER ONLY)
# ────────────────────────────────────────
elif page == "Manage Cards":
    st.title(f"{user_name}'s Cards")
    c.execute("SELECT id, text FROM cards WHERE user_id=? ORDER BY id", (user_id,))
    cards = c.fetchall()

    if cards:
        for card_id, card_text in cards:
            st.markdown('<div class="card-container">', unsafe_allow_html=True)
            col1, col2 = st.columns([6,1])
            with col1:
                st.markdown(f'<div class="card-box">{card_text}</div>', unsafe_allow_html=True)
            with col2:
                if st.button("✏️", key=f"edit_{card_id}"):
                    st.session_state[f"editing_{card_id}"] = True
                if st.button("🗑️", key=f"delete_{card_id}"):
                    c.execute("DELETE FROM cards WHERE id=?", (card_id,))
                    conn.commit()
                    st.stop()
            if st.session_state.get(f"editing_{card_id}", False):
                new_text = st.text_input("Edit card", value=card_text, key=f"text_{card_id}")
                if st.button("Save", key=f"save_{card_id}"):
                    c.execute("UPDATE cards SET text=? WHERE id=?", (new_text, card_id))
                    conn.commit()
                    st.session_state[f"editing_{card_id}"] = False
                    st.stop()
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("No cards yet.")

    # Add card
    with st.form("add_card_form", clear_on_submit=True):
        new_card_text = st.text_input("Card content")
        if st.form_submit_button("Add Card") and new_card_text.strip():
            c.execute("INSERT INTO cards (user_id, text) VALUES (?, ?)", (user_id, new_card_text.strip()))
            conn.commit()
            st.success("Card added!")
            st.stop()

# ────────────────────────────────────────
# DRAW CARD (ALL USERS AUTHENTICATE, ROUND-ROBIN)
# ────────────────────────────────────────
# --- DRAW CARD (ALL USERS AUTHENTICATE, ROUND-ROBIN) ---
elif page == "Draw a Card":
    st.title("Draw a Random Card (Round-Robin)")

    # Get all users who have cards
    c.execute("""
        SELECT u.id, u.name
        FROM users u
        INNER JOIN cards c ON u.id = c.user_id
        GROUP BY u.id
        ORDER BY u.id
    """)
    all_users = c.fetchall()
    if not all_users:
        st.warning("No cards available for drawing.")
        st.stop()

    # Initialize session state
    st.session_state.setdefault("authenticated_users", {})
    st.session_state.setdefault("round_robin_index", 0)
    st.session_state.setdefault("just_drawn", False)

    # Users who are not yet authenticated
    pending_users = [u for u in all_users if u[0] not in st.session_state.authenticated_users]

    # --- Authentication Form ---
    if pending_users:
        st.subheader("Authenticate all users for this round")

        with st.form("auth_all_users_form"):
            pw_inputs = {}
            for idx, (u_id, u_name) in enumerate(pending_users):
                widget_key = f"auth_pw_{u_id}"  # unique per user
                pw_inputs[u_id] = st.text_input(
                    f"Password for {u_name}",
                    type="password",
                    key=widget_key
                )

            submitted = st.form_submit_button("Authenticate All")
            if submitted:
                for u_id, u_name in pending_users:
                    pw = pw_inputs[u_id]
                    c.execute("SELECT id FROM users WHERE id=? AND password=?", (u_id, hash_pw(pw)))
                    if c.fetchone():
                        st.session_state.authenticated_users[u_id] = True
                        st.success(f"{u_name} authenticated!")
                    else:
                        st.error(f"Incorrect password for {u_name}")

        st.info(f"Authenticated {len(st.session_state.authenticated_users)}/{len(all_users)} users.")
        st.stop()  # Stop until all users authenticate

    # --- All users authenticated, draw cards ---
    st.success("All users authenticated! You can now draw cards.")

    # Round-robin user
    rr_index = st.session_state.round_robin_index % len(all_users)
    next_user_id, next_user_name = all_users[rr_index]

    if st.button(f"Draw card for {next_user_name}"):
        c.execute("SELECT id, text FROM cards WHERE user_id=?", (next_user_id,))
        user_cards = c.fetchall()
        if not user_cards:
            st.warning(f"No cards left for {next_user_name}. Skipping...")
            st.session_state.round_robin_index += 1
        else:
            # Pick random card
            card_id, card_text = random.choice(user_cards)
            st.session_state.last_drawn = {"user": next_user_name, "text": card_text}
            st.session_state.just_drawn = True

            # Delete card from DB
            c.execute("DELETE FROM cards WHERE id=?", (card_id,))
            conn.commit()

            # Move to next user
            st.session_state.round_robin_index += 1

    # --- Show last drawn card ---
    if st.session_state.get("last_drawn"):
        st.subheader("Last Drawn")
        st.markdown(f"""
        <div style="max-width:500px;margin:auto;">
            <div class="card-box">
                <div>
                    <div style="font-size:14px;opacity:0.6;margin-bottom:10px;">
                        From {st.session_state.last_drawn['user']}
                    </div>
                    <div style="font-size:22px;font-weight:600;">
                        {st.session_state.last_drawn['text']}
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.get("just_drawn"):
            st.balloons()
            st.success("Card drawn!")
            st.session_state.just_drawn = False


conn.close()
