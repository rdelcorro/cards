import streamlit as st
import sqlite3
import random

# ────────────────────────────────────────
#  PAGE CONFIG
# ────────────────────────────────────────
st.set_page_config(
    page_title="Card Game",
    page_icon="🃏",
    layout="wide",
    initial_sidebar_state="collapsed",   # starts collapsed → hamburger always visible
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# Hide deploy button & Streamlit extras
hide_streamlit_style = """
 <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Hide Deploy button */
    button[kind="header"] {display: none !important;}

    /* Optional: tighten sidebar padding */
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 0 !important;
    }

    .card-box {
        background-color: white;
        color: black;  
        padding: 20px;
        border-radius: 16px;
        border: 2px solid #222;
        box-shadow: 4px 4px 0px rgba(0,0,0,0.15);
        min-height: 120px;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        font-size: 18px;
        font-weight: 500;
    }

    .card-container {
        margin-bottom: 20px;
    }

    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)



# ────────────────────────────────────────
#  SESSION STATE
# ────────────────────────────────────────
if "last_drawn" not in st.session_state:
    st.session_state.last_drawn = None
if "just_drawn" not in st.session_state:
    st.session_state.just_drawn = False

# ────────────────────────────────────────
#  DATABASE
# ────────────────────────────────────────
def init_db():
    conn = sqlite3.connect('data/game.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS cards 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS state 
                 (key TEXT PRIMARY KEY, value INTEGER)''')
    conn.commit()
    return conn

conn = init_db()

# ────────────────────────────────────────
#  SIDEBAR (hamburger always visible when collapsed)
# ────────────────────────────────────────
with st.sidebar:
    st.title("Card Game")
    page = st.radio(
        "Navigation",
        ["Manage Users", "Manage Cards", "Draw a Card"],
        index=2,
        key="nav_radio"
    )


# ────────────────────────────────────────
#  PAGE: MANAGE USERS
# ────────────────────────────────────────
if page == "Manage Users":
    st.title("Manage Users")

    c = conn.cursor()
    c.execute("SELECT id, name FROM users ORDER BY name")
    users = c.fetchall()

    # Add new user
    with st.form("add_user_form", clear_on_submit=True):
        new_user_name = st.text_input("New user name", key="new_user_input")
        submitted = st.form_submit_button("Add User")
        if submitted and new_user_name.strip():
            try:
                c.execute("INSERT INTO users (name) VALUES (?)", (new_user_name.strip(),))
                conn.commit()
                st.success(f"User **{new_user_name}** added!")
            except sqlite3.IntegrityError:
                st.error("That name already exists.")
            st.rerun()

    st.markdown("---")

    if users:
        st.subheader("Existing users")

        for user_id, name in users:
            col1, col2 = st.columns([5, 1])

            with col1:
                st.write(f"• {name}")

            with col2:
                if st.button("Delete", key=f"delete_user_{user_id}"):
                    # Delete user's cards first
                    c.execute("DELETE FROM cards WHERE user_id = ?", (user_id,))
                    
                    # Delete user
                    c.execute("DELETE FROM users WHERE id = ?", (user_id,))

                    # Clean up last_picked if needed
                    c.execute("SELECT value FROM state WHERE key = 'last_picked'")
                    res = c.fetchone()
                    if res and res[0] == user_id:
                        c.execute("DELETE FROM state WHERE key = 'last_picked'")

                    conn.commit()

                    # Clear last drawn if it belongs to deleted user
                    if (
                        st.session_state.last_drawn and 
                        st.session_state.last_drawn["user"] == name
                    ):
                        st.session_state.last_drawn = None

                    st.success(f"Deleted {name} and all their cards.")
                    st.rerun()

    else:
        st.info("No users yet.")

# ────────────────────────────────────────
#  PAGE: MANAGE CARDS
# ────────────────────────────────────────
elif page == "Manage Cards":
    st.title("Manage Cards")

    c = conn.cursor()
    c.execute("SELECT id, name FROM users ORDER BY name")
    users = c.fetchall()
    user_names = [u[1] for u in users]

    if not user_names:
        st.warning("No users yet. Go to Manage Users first.")
    else:
        selected_user_name = st.selectbox("Select user", user_names)

        if selected_user_name:
            c.execute("SELECT id FROM users WHERE name = ?", (selected_user_name,))
            user_id = c.fetchone()[0]

            st.subheader(f"Cards – {selected_user_name}")

            # List cards
            c.execute("SELECT id, text FROM cards WHERE user_id = ? ORDER BY id", (user_id,))
            cards = c.fetchall()

            if cards:
                for card_id, card_text in cards:
                    st.markdown('<div class="card-container">', unsafe_allow_html=True)

                    col1, col2 = st.columns([6, 1])

                    with col1:
                        st.markdown(
                            f'<div class="card-box">{card_text}</div>',
                            unsafe_allow_html=True
                        )

                    with col2:
                        if st.button("✏️", key=f"edit_{card_id}"):
                            st.session_state[f"editing_{card_id}"] = True

                        if st.button("🗑️", key=f"delete_{card_id}"):
                            c.execute("DELETE FROM cards WHERE id = ?", (card_id,))
                            conn.commit()
                            st.rerun()

                    # Inline edit mode
                    if st.session_state.get(f"editing_{card_id}", False):
                        new_text = st.text_input(
                            "Edit card",
                            value=card_text,
                            key=f"text_{card_id}"
                        )
                        if st.button("Save", key=f"save_{card_id}"):
                            c.execute(
                                "UPDATE cards SET text = ? WHERE id = ?",
                                (new_text, card_id)
                            )
                            conn.commit()
                            st.session_state[f"editing_{card_id}"] = False
                            st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("No cards yet for this user.")

            # Add new card
            with st.form(key="add_card_form", clear_on_submit=True):
                new_card_text = st.text_input("Card content")
                submitted = st.form_submit_button("Add Card")

                if submitted and new_card_text.strip():
                    c.execute(
                        "INSERT INTO cards (user_id, text) VALUES (?, ?)",
                        (user_id, new_card_text.strip())
                    )
                    conn.commit()
                    st.success("Card added!")
                    st.rerun()



# ────────────────────────────────────────
#  PAGE: DRAW A CARD
# ────────────────────────────────────────
elif page == "Draw a Card":
    st.title("Draw a Random Card")

    # Show last drawn (persists)
    if st.session_state.last_drawn:
        st.subheader("Last Drawn")

        st.markdown(
            f"""
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
            """,
            unsafe_allow_html=True
        )

        st.markdown("<br>", unsafe_allow_html=True)


    if st.button("Draw Now", type="primary", use_container_width=True):
        c = conn.cursor()

        c.execute("""
            SELECT DISTINCT u.id, u.name 
            FROM users u 
            INNER JOIN cards c ON u.id = c.user_id 
            ORDER BY u.id
        """)
        active_users = c.fetchall()

        if not active_users:
            st.warning("No cards left in the game.")
        else:
            active_ids = [u[0] for u in active_users]

            c.execute("SELECT value FROM state WHERE key = 'last_picked'")
            res = c.fetchone()
            last_picked = res[0] if res else None

            if last_picked in active_ids:
                idx = active_ids.index(last_picked)
                next_idx = (idx + 1) % len(active_ids)
            else:
                next_idx = 0

            next_user_id = active_ids[next_idx]
            next_user_name = active_users[next_idx][1]

            c.execute("SELECT id, text FROM cards WHERE user_id = ?", (next_user_id,))
            user_cards = c.fetchall()

            if user_cards:
                card_id, card_text = random.choice(user_cards)

                st.session_state.last_drawn = {
                    "user": next_user_name,
                    "text": card_text
                }
                st.session_state.just_drawn = True

                c.execute("DELETE FROM cards WHERE id = ?", (card_id,))
                c.execute("INSERT OR REPLACE INTO state (key, value) VALUES ('last_picked', ?)", (next_user_id,))
                conn.commit()

                st.rerun()
            else:
                st.error("Unexpected: no cards for selected user.")

    if st.session_state.just_drawn:
        st.balloons()
        st.success("Card drawn!")
        st.session_state.just_drawn = False

conn.close()