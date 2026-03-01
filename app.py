import streamlit as st
import sqlite3
import os
import bcrypt
from streamlit.components.v1 import html

# ---------------- CONFIG ----------------
st.set_page_config(page_title="ThreeDimensions Hub", layout="wide")
os.makedirs("models", exist_ok=True)

# ---------------- DATABASE ----------------
conn = sqlite3.connect("database.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password BLOB
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    prompt TEXT,
    file TEXT,
    user_id INTEGER,
    views INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS likes (
    user_id INTEGER,
    model_id INTEGER,
    UNIQUE(user_id, model_id)
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS ratings (
    user_id INTEGER,
    model_id INTEGER,
    rating INTEGER,
    UNIQUE(user_id, model_id)
)
""")

conn.commit()

# ---------------- STYLE ----------------
st.markdown("""
<style>
body { background-color: #0f172a; color: white; }
.stButton>button { background-color:#2563eb; color:white; }
</style>
""", unsafe_allow_html=True)

st.title("🚀 ThreeDimensions Hub")

# ---------------- SESSION ----------------
if "user" not in st.session_state:
    st.session_state.user = None

# ---------------- AUTH ----------------
if not st.session_state.user:

    mode = st.sidebar.selectbox("Account", ["Login", "Register"])
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if mode == "Register":
        if st.button("Create Account"):
            if username and password:
                hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
                try:
                    c.execute("INSERT INTO users (username,password) VALUES (?,?)",
                              (username, hashed))
                    conn.commit()
                    st.success("Account created.")
                except:
                    st.error("Username already exists.")

    if mode == "Login":
        if st.button("Login"):
            c.execute("SELECT id,password FROM users WHERE username=?",
                      (username,))
            user = c.fetchone()
            if user and bcrypt.checkpw(password.encode(), user[1]):
                st.session_state.user = {"id": user[0], "username": username}
                st.success("Logged in.")
                st.rerun()
            else:
                st.error("Invalid credentials.")

# ---------------- MAIN APP ----------------
else:

    st.sidebar.write("👤", st.session_state.user["username"])
    menu = st.sidebar.selectbox("Menu",
        ["Upload", "Explore", "Trending", "Logout"])

    # -------- LOGOUT --------
    if menu == "Logout":
        st.session_state.user = None
        st.rerun()

    # -------- UPLOAD --------
    if menu == "Upload":

        st.header("Upload Model")

        title = st.text_input("Title")
        prompt = st.text_area("Prompt Used")
        file = st.file_uploader("Upload .glb", type=["glb"])

        if st.button("Upload Model"):

            if not file:
                st.warning("Upload a file.")
                st.stop()

            if file.size > 10 * 1024 * 1024:
                st.error("File too large (Max 10MB).")
                st.stop()

            safe_name = file.name.replace("..", "").replace("/", "")
            path = f"models/{safe_name}"

            with open(path, "wb") as f:
                f.write(file.read())

            c.execute("INSERT INTO models (title,prompt,file,user_id) VALUES (?,?,?,?)",
                      (title, prompt, safe_name, st.session_state.user["id"]))
            conn.commit()

            st.success("Model uploaded.")

    # -------- EXPLORE --------
    if menu == "Explore":

        st.header("Explore Models")

        search = st.text_input("🔍 Search")

        if search:
            c.execute("SELECT * FROM models WHERE title LIKE ?",
                      (f"%{search}%",))
        else:
            c.execute("SELECT * FROM models")

        models = c.fetchall()

        for m in models:

            st.subheader(m[1])
            st.write("Prompt:", m[2])

            # Increase views
            c.execute("UPDATE models SET views=views+1 WHERE id=?", (m[0],))
            conn.commit()

            # Like count
            c.execute("SELECT COUNT(*) FROM likes WHERE model_id=?", (m[0],))
            like_count = c.fetchone()[0]

            # Avg rating
            c.execute("SELECT AVG(rating) FROM ratings WHERE model_id=?", (m[0],))
            avg_rating = c.fetchone()[0]

            st.write(f"👍 {like_count} Likes")
            if avg_rating:
                st.write(f"⭐ {round(avg_rating,1)} Average Rating")

            viewer = f"""
            <script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>
            <model-viewer src="models/{m[3]}" auto-rotate camera-controls style="width:100%; height:400px;"></model-viewer>
            """
            html(viewer, height=450)

            if st.button(f"Like {m[0]}"):
                try:
                    c.execute("INSERT INTO likes (user_id,model_id) VALUES (?,?)",
                              (st.session_state.user["id"], m[0]))
                    conn.commit()
                    st.success("Liked.")
                except:
                    st.warning("Already liked.")

            rating = st.slider(f"Rate {m[0]}", 1, 5)
            if st.button(f"Submit Rating {m[0]}"):
                try:
                    c.execute("INSERT INTO ratings (user_id,model_id,rating) VALUES (?,?,?)",
                              (st.session_state.user["id"], m[0], rating))
                    conn.commit()
                except:
                    c.execute("UPDATE ratings SET rating=? WHERE user_id=? AND model_id=?",
                              (rating, st.session_state.user["id"], m[0]))
                    conn.commit()

            st.markdown("---")

    # -------- TRENDING --------
    if menu == "Trending":

        st.header("🔥 Trending")

        c.execute("""
        SELECT models.*, COUNT(likes.user_id) as like_count
        FROM models
        LEFT JOIN likes ON models.id = likes.model_id
        GROUP BY models.id
        ORDER BY like_count DESC, views DESC
        LIMIT 10
        """)
        trending = c.fetchall()

        for m in trending:
            st.write("🔥", m[1])
