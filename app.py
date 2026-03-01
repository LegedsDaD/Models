import streamlit as st
import sqlite3
import requests
import base64
import datetime
import hashlib
import streamlit.components.v1 as components

# ===============================
# CONFIG
# ===============================
st.set_page_config(
    page_title="threedimensions Hub",
    page_icon="🔥",
    layout="wide"
)

st.markdown("""
<style>
body {background: linear-gradient(135deg,#0f0f0f,#1a1a1a); color:white;}
.stButton>button {
    background:#ff4b2b;
    color:white;
    border-radius:10px;
}
</style>
""", unsafe_allow_html=True)

# ===============================
# DATABASE
# ===============================
conn = sqlite3.connect("database.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    email TEXT UNIQUE,
    password TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS models(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    title TEXT,
    prompt TEXT,
    description TEXT,
    filename TEXT,
    likes INTEGER DEFAULT 0,
    views INTEGER DEFAULT 0,
    created_at TEXT
)
""")

conn.commit()

# ===============================
# UTILITIES
# ===============================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def upload_to_github(file, filename):
    token = st.secrets["GITHUB_TOKEN"]
    repo = st.secrets["GITHUB_REPO"]

    content = base64.b64encode(file.getvalue()).decode()

    url = f"https://api.github.com/repos/{repo}/contents/models/{filename}"

    data = {
        "message": f"Upload model {filename}",
        "content": content
    }

    response = requests.put(
        url,
        headers={"Authorization": f"token {token}"},
        json=data
    )

    return response.status_code in [200, 201]

def trending_score(likes, views, created_at):
    age_hours = (
        datetime.datetime.now() -
        datetime.datetime.fromisoformat(created_at)
    ).total_seconds() / 3600
    return (likes * 3 + views) / (age_hours + 2)

def show_3d_model(url):
    components.html(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>body{{margin:0;overflow:hidden}}</style>
    </head>
    <body>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/three@0.128/examples/js/loaders/OBJLoader.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/three@0.128/examples/js/controls/OrbitControls.js"></script>
        <script>
            const scene = new THREE.Scene();
            const camera = new THREE.PerspectiveCamera(75, window.innerWidth/window.innerHeight, 0.1, 1000);
            const renderer = new THREE.WebGLRenderer({{antialias:true}});
            renderer.setSize(window.innerWidth, 500);
            document.body.appendChild(renderer.domElement);

            const controls = new THREE.OrbitControls(camera, renderer.domElement);

            const light = new THREE.DirectionalLight(0xffffff, 1);
            light.position.set(0, 1, 1).normalize();
            scene.add(light);

            const loader = new THREE.OBJLoader();
            loader.load("{url}", function(object) {{
                scene.add(object);
            }});

            camera.position.z = 5;

            function animate() {{
                requestAnimationFrame(animate);
                controls.update();
                renderer.render(scene, camera);
            }}
            animate();
        </script>
    </body>
    </html>
    """, height=500)

# ===============================
# SESSION
# ===============================
if "user" not in st.session_state:
    st.session_state.user = None

# ===============================
# AUTH
# ===============================
if not st.session_state.user:

    tab1, tab2 = st.tabs(["Login", "Register"])

    # LOGIN
    with tab1:
        st.subheader("Login")
        login_username = st.text_input("Username", key="login_username")
        login_password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login", key="login_button"):
            c.execute(
                "SELECT * FROM users WHERE username=? AND password=?",
                (login_username, hash_password(login_password))
            )
            user = c.fetchone()

            if user:
                st.session_state.user = login_username
                st.success("Logged in!")
                st.rerun()
            else:
                st.error("Invalid credentials")

    # REGISTER
    with tab2:
        st.subheader("Register")
        register_username = st.text_input("Username", key="register_username")
        register_email = st.text_input("Email", key="register_email")
        register_password = st.text_input("Password", type="password", key="register_password")

        if st.button("Register", key="register_button"):
            try:
                c.execute(
                    "INSERT INTO users(username,email,password) VALUES(?,?,?)",
                    (register_username, register_email, hash_password(register_password))
                )
                conn.commit()
                st.success("Account created! Login now.")
            except:
                st.error("Username or email already exists")

# ===============================
# MAIN APP
# ===============================
else:

    st.sidebar.title(f"👋 {st.session_state.user}")
    page = st.sidebar.radio("Navigation",
                            ["Explore", "Upload", "Leaderboard", "Logout"],
                            key="nav_radio")

    repo = st.secrets["GITHUB_REPO"]

    # ---------------- EXPLORE ----------------
    if page == "Explore":
        st.title("🔥 Trending Models")

        c.execute("SELECT * FROM models")
        models = c.fetchall()

        models = sorted(
            models,
            key=lambda x: trending_score(x[6], x[7], x[8]),
            reverse=True
        )

        for model in models:
            st.markdown("---")
            st.subheader(model[2])
            st.write(f"By: {model[1]}")
            st.write(model[4])

            model_url = f"https://raw.githubusercontent.com/{repo}/main/models/{model[5]}"
            show_3d_model(model_url)

            col1, col2 = st.columns(2)

            with col1:
                if st.button("❤️ Like", key=f"like_{model[0]}"):
                    c.execute("UPDATE models SET likes = likes + 1 WHERE id=?",
                              (model[0],))
                    conn.commit()
                    st.rerun()

            with col2:
                st.write(f"❤️ {model[6]}   👁 {model[7]}")

            c.execute("UPDATE models SET views = views + 1 WHERE id=?",
                      (model[0],))
            conn.commit()

    # ---------------- UPLOAD ----------------
    elif page == "Upload":
        st.title("🚀 Upload 3D Model (.obj only)")

        title = st.text_input("Model Title", key="upload_title")
        prompt = st.text_area("Prompt Used", key="upload_prompt")
        description = st.text_area("Description", key="upload_description")
        uploaded_file = st.file_uploader("Upload OBJ file", type=["obj"], key="upload_file")

        if st.button("Submit", key="upload_submit"):
            if uploaded_file:
                success = upload_to_github(uploaded_file, uploaded_file.name)

                if success:
                    c.execute("""
                    INSERT INTO models
                    (username,title,prompt,description,filename,created_at)
                    VALUES(?,?,?,?,?,?)
                    """,
                    (
                        st.session_state.user,
                        title,
                        prompt,
                        description,
                        uploaded_file.name,
                        datetime.datetime.now().isoformat()
                    ))
                    conn.commit()
                    st.success("Model uploaded successfully!")
                else:
                    st.error("GitHub upload failed")

    # ---------------- LEADERBOARD ----------------
    elif page == "Leaderboard":
        st.title("🏆 Top Creators")

        c.execute("""
        SELECT username, SUM(likes) as total_likes
        FROM models
        GROUP BY username
        ORDER BY total_likes DESC
        LIMIT 10
        """)

        leaders = c.fetchall()

        for i, leader in enumerate(leaders):
            st.write(f"{i+1}. {leader[0]} — ❤️ {leader[1] or 0}")

    # ---------------- LOGOUT ----------------
    elif page == "Logout":
        st.session_state.user = None
        st.rerun()
