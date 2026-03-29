import streamlit as st
import folium
from streamlit_folium import st_folium
import sqlite3
import base64
import json
import os
from datetime import datetime
from PIL import Image
from io import BytesIO
from streamlit_oauth import OAuth2Component

DB_PATH = "trees.db"
MK_CENTER = [52.0406, -0.7594]


# ── Database helpers ───────────────────────────────────────────────────────────

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trees (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                latitude    REAL    NOT NULL,
                longitude   REAL    NOT NULL,
                image_data  BLOB,
                description TEXT,
                date_added  TEXT
            )
        """)
        conn.commit()


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _decode_id_token(id_token: str) -> dict:
    """Decode the payload of a Google JWT without signature verification."""
    payload_b64 = id_token.split(".")[1]
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += "=" * padding
    return json.loads(base64.urlsafe_b64decode(payload_b64))


def seed_sample_trees():
    """Populate a few example trees when the database is first created."""
    with sqlite3.connect(DB_PATH) as conn:
        if conn.execute("SELECT COUNT(*) FROM trees").fetchone()[0] == 0:
            samples = [
                ("Magnolia × soulangeana – Campbell Park",  52.0479, -0.7484, None, "Beautiful specimen near the canal",            "2026-03-29 10:00"),
                ("Star Magnolia – Willen Lake",              52.0618, -0.7317, None, "White star-shaped flowers in early spring",   "2026-03-29 10:00"),
                ("Magnolia stellata – Secklow Mound",        52.0398, -0.7562, None, "Large tree with fragrant blooms",             "2026-03-29 10:00"),
                ("Magnolia grandiflora – Bletchley Park",    51.9976, -0.7426, None, "Evergreen magnolia, year-round foliage",       "2026-03-29 10:00"),
                ("Magnolia 'Susan' – Wolverton Park",        52.0663, -0.8049, None, "Deep pink-purple flowers",                    "2026-03-29 10:00"),
            ]
            conn.executemany(
                "INSERT INTO trees (name, latitude, longitude, image_data, description, date_added) VALUES (?,?,?,?,?,?)",
                samples,
            )
            conn.commit()


def get_trees():
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            "SELECT id, name, latitude, longitude, image_data, description, date_added FROM trees ORDER BY id"
        ).fetchall()


def add_tree(name, lat, lng, image_bytes, description):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO trees (name, latitude, longitude, image_data, description, date_added) VALUES (?,?,?,?,?,?)",
            (name, lat, lng, image_bytes, description, datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        conn.commit()


def delete_tree(tree_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM trees WHERE id = ?", (tree_id,))
        conn.commit()


# ── Image helpers ─────────────────────────────────────────────────────────────

def compress_image(uploaded_file, max_px: int = 350) -> bytes:
    """Resize and JPEG-compress an uploaded image before storing in the DB."""
    img = Image.open(uploaded_file).convert("RGB")
    img.thumbnail((max_px, max_px), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=78)
    return buf.getvalue()


def b64_img_tag(image_data: bytes, width: int = 210) -> str:
    enc = base64.b64encode(image_data).decode()
    return (
        f'<img src="data:image/jpeg;base64,{enc}" '
        f'width="{width}" style="border-radius:6px; margin-top:5px; display:block;"/>'
    )


# ── Map builder ───────────────────────────────────────────────────────────────

def build_map(trees):
    m = folium.Map(location=MK_CENTER, zoom_start=13, tiles="CartoDB positron")

    for row in trees:
        tree_id, name, lat, lng, image_data, description, date_added = row

        img_html = (
            b64_img_tag(image_data)
            if image_data
            else "<span style='font-size:12px; color:#888; font-style:italic;'>No photo uploaded yet</span>"
        )

        card_html = f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif; width:230px; padding:4px 6px;">
          <div style="font-size:15px; font-weight:bold; color:#2d6a4f;">&#127800; {name}</div>
          <div style="margin:6px 0;">{img_html}</div>
          <div style="font-size:12px; color:#444; margin-top:4px;">{description or ''}</div>
          <div style="font-size:10px; color:#aaa; margin-top:6px;">Added: {date_added}</div>
        </div>"""

        folium.CircleMarker(
            location=[lat, lng],
            radius=10,
            color="#1a5c1a",
            weight=2,
            fill=True,
            fill_color="#74c476",
            fill_opacity=0.85,
            tooltip=folium.Tooltip(card_html, sticky=True, max_width=260),
            popup=folium.Popup(card_html, max_width=260),
        ).add_to(m)

    return m


# ── App layout ────────────────────────────────────────────────────────────────

st.set_page_config(page_title="MK Magnolia Map", page_icon="\U0001f338", layout="wide")
st.title("\U0001f338 Milton Keynes Magnolia Tree Map")
st.caption("Hover over a green dot to preview the tree. Click to pin the card.")

init_db()
seed_sample_trees()

# ── Google OAuth credentials (from .streamlit/secrets.toml or env vars) ──────

try:
    _CLIENT_ID     = st.secrets["GOOGLE_CLIENT_ID"]
    _CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
    _REDIRECT_URI  = st.secrets.get("REDIRECT_URI", "http://localhost:8501")
except (KeyError, FileNotFoundError):
    _CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
    _CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    _REDIRECT_URI  = os.environ.get("REDIRECT_URI", "http://localhost:8501")

# ── Sidebar: Google login / logout ───────────────────────────────────────────

if "username" not in st.session_state:
    st.session_state["username"] = None

with st.sidebar:
    st.header("\U0001f464 Account")

    if st.session_state["username"]:
        st.success(f"Signed in as **{st.session_state['username']}**")
        if st.button("Sign out", use_container_width=True):
            st.session_state["username"] = None
            st.rerun()
    else:
        if not _CLIENT_ID or not _CLIENT_SECRET:
            st.error(
                "Google OAuth is not configured.\n\n"
                "Create `.streamlit/secrets.toml` with:\n"
                "```\nGOOGLE_CLIENT_ID = \"...\""
                "\nGOOGLE_CLIENT_SECRET = \"...\"\n```"
            )
        else:
            oauth2 = OAuth2Component(
                _CLIENT_ID,
                _CLIENT_SECRET,
                "https://accounts.google.com/o/oauth2/v2/auth",
                "https://oauth2.googleapis.com/token",
                "https://oauth2.googleapis.com/token",
                "https://oauth2.googleapis.com/revoke",
            )
            result = oauth2.authorize_button(
                name="Sign in with Google",
                redirect_uri=_REDIRECT_URI,
                scope="openid email profile",
                key="google_login",
                use_container_width=True,
                icon="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg",
            )
            if result and "token" in result:
                id_token = result["token"].get("id_token")
                if id_token:
                    payload = _decode_id_token(id_token)
                    st.session_state["username"] = payload.get("email", payload.get("sub", "unknown"))
                    st.rerun()

tab_map, tab_add, tab_manage = st.tabs(["\U0001f5fa\ufe0f Map", "\u2795 Add Tree", "\U0001f4cb Manage Trees"])

# ── Tab: Map ──────────────────────────────────────────────────────────────────
with tab_map:
    trees = get_trees()
    st.info(f"{len(trees)} magnolia tree(s) recorded in Milton Keynes.", icon="\U0001f333")
    st_folium(build_map(trees), width="100%", height=620, returned_objects=[])

# ── Tab: Add Tree ─────────────────────────────────────────────────────────────
with tab_add:
    if not st.session_state["username"]:
        st.warning("\U0001f512 Please log in using the sidebar to add trees.")
        st.stop()
    st.subheader("Add a New Magnolia Tree")
    st.markdown(
        "Tip: find coordinates by right-clicking any location on "
        "[Google Maps](https://maps.google.com) and copying the lat/lng."
    )

    with st.form("add_tree_form", clear_on_submit=True):
        name = st.text_input("Tree name / variety *", placeholder="e.g. Magnolia × soulangeana")
        description = st.text_area(
            "Description",
            placeholder="e.g. Large pink blooms near the lake entrance",
            height=80,
        )
        col1, col2 = st.columns(2)
        with col1:
            lat = st.number_input("Latitude",  value=52.0406, format="%.6f", step=0.0001)
        with col2:
            lng = st.number_input("Longitude", value=-0.7594, format="%.6f", step=0.0001)
        photo = st.file_uploader("Upload a photo (optional)", type=["jpg", "jpeg", "png", "webp"])
        submitted = st.form_submit_button("Add Tree", type="primary")

    if submitted:
        if not name.strip():
            st.error("Please enter a tree name.")
        else:
            image_bytes = compress_image(photo) if photo else None
            add_tree(name.strip(), lat, lng, image_bytes, description.strip())
            st.success(f"\u2705 '{name}' added to the map!")
            st.rerun()

# ── Tab: Manage Trees ─────────────────────────────────────────────────────────
with tab_manage:
    if not st.session_state["username"]:
        st.warning("\U0001f512 Please log in using the sidebar to manage trees.")
        st.stop()
    st.subheader("All Recorded Trees")
    trees = get_trees()
    if not trees:
        st.info("No trees in the database yet.")
    else:
        for row in trees:
            tree_id, name, lat, lng, image_data, description, date_added = row
            with st.expander(f"\U0001f338 {name}  \u2014  ({lat:.5f}, {lng:.5f})"):
                if image_data:
                    st.image(BytesIO(image_data), width=220)
                else:
                    st.caption("No photo uploaded.")
                if description:
                    st.write(description)
                st.caption(f"Added: {date_added}")
                if st.button("\U0001f5d1\ufe0f Delete this tree", key=f"del_{tree_id}"):
                    delete_tree(tree_id)
                    st.rerun()

