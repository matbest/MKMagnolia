import streamlit as st
import folium
from streamlit_folium import st_folium
import sqlite3
import base64
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from datetime import datetime
from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS
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


def _get_current_origin() -> str:
    """Build origin from request host to avoid localhost/cloud redirect mismatches."""
    try:
        headers = getattr(st.context, "headers", {})
        host = headers.get("host", "")
    except Exception:
        host = ""

    if not host:
        return ""

    if host.startswith("localhost") or host.startswith("127.0.0.1"):
        return f"http://{host}"
    return f"https://{host}"


def _extract_google_identity(token_dict: dict) -> str | None:
    """Return an email/sub from OAuth token payload or Google userinfo endpoint."""
    if not token_dict:
        return None

    id_token = token_dict.get("id_token")
    if id_token:
        try:
            payload = _decode_id_token(id_token)
            return payload.get("email") or payload.get("sub")
        except Exception:
            pass

    access_token = token_dict.get("access_token")
    if not access_token:
        return None

    try:
        req = Request(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        with urlopen(req, timeout=8) as resp:
            profile = json.loads(resp.read().decode("utf-8"))
            return profile.get("email") or profile.get("sub")
    except Exception:
        return None


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
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    img = Image.open(uploaded_file).convert("RGB")
    img.thumbnail((max_px, max_px), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=78)
    return buf.getvalue()


def _gps_to_decimal(coord, ref) -> float:
    """Convert EXIF GPS coordinate tuple to signed decimal degrees."""

    def _part_to_float(part):
        if isinstance(part, tuple) and len(part) == 2 and part[1] != 0:
            return float(part[0]) / float(part[1])
        if hasattr(part, "numerator") and hasattr(part, "denominator") and part.denominator != 0:
            return float(part.numerator) / float(part.denominator)
        return float(part)

    degrees = _part_to_float(coord[0])
    minutes = _part_to_float(coord[1])
    seconds = _part_to_float(coord[2])
    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    if ref in ["S", "W"]:
        decimal = -decimal
    return decimal


def get_exif_lat_lng(uploaded_file):
    """Return (lat, lng) from EXIF GPS if present, otherwise None."""
    if uploaded_file is None:
        return None
    try:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        img = Image.open(uploaded_file)
        exif_data = img.getexif()
        if not exif_data:
            return None

        gps_info = None
        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, tag_id)
            if tag_name == "GPSInfo":
                gps_info = value
                break

        if not gps_info:
            return None

        gps = {}
        for key in gps_info:
            name = GPSTAGS.get(key, key)
            gps[name] = gps_info[key]

        if all(k in gps for k in ["GPSLatitude", "GPSLatitudeRef", "GPSLongitude", "GPSLongitudeRef"]):
            lat = _gps_to_decimal(gps["GPSLatitude"], gps["GPSLatitudeRef"])
            lng = _gps_to_decimal(gps["GPSLongitude"], gps["GPSLongitudeRef"])
            return round(lat, 6), round(lng, 6)
    except Exception:
        return None
    finally:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)

    return None


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

# ── Custom CSS Theme ──────────────────────────────────────────────────────────

_CUSTOM_CSS = """
<style>
    :root {
        --magnolia-pink: #d8536d;
        --magnolia-light-pink: #f4d4de;
        --magnolia-green: #2d6a4f;
        --magnolia-light-green: #74c476;
        --magnolia-cream: #faf9f7;
    }

    * {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }

    .appViewContainer {
        background: linear-gradient(135deg, #faf9f7 0%, #f0e8e0 100%);
    }

    h1 {
        color: var(--magnolia-green) !important;
        font-weight: 700 !important;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.08) !important;
        letter-spacing: -0.5px !important;
    }

    h2, h3 {
        color: var(--magnolia-green) !important;
        font-weight: 600 !important;
    }

    .stCaption {
        color: #666 !important;
        font-size: 0.95rem !important;
    }

    .stButton > button {
        background: linear-gradient(135deg, var(--magnolia-green) 0%, #1f4d35 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.5rem !important;
        box-shadow: 0 4px 12px rgba(45, 106, 79, 0.2) !important;
        transition: all 0.3s ease !important;
    }

    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 16px rgba(45, 106, 79, 0.3) !important;
    }

    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div {
        border: 2px solid var(--magnolia-light-green) !important;
        border-radius: 8px !important;
        background-color: white !important;
        font-size: 0.95rem !important;
        padding: 0.7rem !important;
        transition: all 0.3s ease !important;
    }

    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--magnolia-pink) !important;
        box-shadow: 0 0 0 3px rgba(216, 83, 109, 0.1) !important;
    }

    .stTabs > [data-baseweb="tab-list"] {
        background-color: rgba(45, 106, 79, 0.05);
        border-radius: 12px;
        padding: 4px;
        gap: 4px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        font-weight: 500 !important;
        color: var(--magnolia-green) !important;
    }

    .stTabs [aria-selected="true"] {
        background-color: white !important;
        box-shadow: 0 2px 8px rgba(45, 106, 79, 0.15) !important;
    }

    .streamlit-expanderHeader {
        background-color: var(--magnolia-light-pink) !important;
        border-radius: 8px !important;
    }

    .streamlit-expanderHeader:hover {
        background-color: rgba(216, 83, 109, 0.15) !important;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(45, 106, 79, 0.03) 0%, rgba(216, 83, 109, 0.03) 100%);
    }

    form {
        background-color: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
    }

    .stCheckbox > label {
        font-weight: 500 !important;
        color: var(--magnolia-green) !important;
    }

    a {
        color: var(--magnolia-pink) !important;
        text-decoration: none !important;
        font-weight: 500 !important;
    }

    a:hover {
        text-decoration: underline !important;
    }
</style>
"""

st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)

st.title("\U0001f338 Milton Keynes Magnolia Tree Map")
st.caption("Hover over a green dot to preview the tree. Click to pin the card.")

init_db()
seed_sample_trees()

# ── Google OAuth credentials (from .streamlit/secrets.toml or env vars) ──────

try:
    _CLIENT_ID     = st.secrets["GOOGLE_CLIENT_ID"]
    _CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
    _REDIRECT_URI  = st.secrets.get("REDIRECT_URI", "")
    _LOCAL_REDIRECT_URI = st.secrets.get("LOCAL_REDIRECT_URI", "")
except (KeyError, FileNotFoundError):
    _CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
    _CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    _REDIRECT_URI  = os.environ.get("REDIRECT_URI", "")
    _LOCAL_REDIRECT_URI = os.environ.get("LOCAL_REDIRECT_URI", "")

_ORIGIN = _get_current_origin()
if _ORIGIN.startswith("http://"):
    # Localhost run: prefer explicit local redirect setting, else use current localhost origin.
    _EFFECTIVE_REDIRECT_URI = _LOCAL_REDIRECT_URI or f"{_ORIGIN}/"
elif _ORIGIN:
    # Cloud run: prefer explicit deploy redirect setting, else use current host origin.
    _EFFECTIVE_REDIRECT_URI = _REDIRECT_URI or f"{_ORIGIN}/"
else:
    _EFFECTIVE_REDIRECT_URI = _REDIRECT_URI or "http://localhost:8501/"

# ── Sidebar: Google login / logout ───────────────────────────────────────────

if "username" not in st.session_state:
    st.session_state["username"] = None
if "google_token" not in st.session_state:
    st.session_state["google_token"] = None

# Restore login from URL query params on page load/refresh
if "user" in st.query_params and not st.session_state["username"]:
    st.session_state["username"] = st.query_params["user"]

with st.sidebar:
    st.header("\U0001f464 Account")

    if st.session_state["username"]:
        st.success(f"Signed in as **{st.session_state['username']}**")
        if st.button("Sign out", use_container_width=True):
            st.session_state["username"] = None
            st.session_state["google_token"] = None
            st.query_params.clear()
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
                redirect_uri=_EFFECTIVE_REDIRECT_URI,
                scope="openid email profile",
                key="google_login",
                use_container_width=True,
                icon="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg",
            )
            if result and "token" in result:
                st.session_state["google_token"] = result["token"]
                identity = _extract_google_identity(result["token"])
                if identity:
                    st.session_state["username"] = identity
                    st.query_params["user"] = identity
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

    if "new_tree_lat" not in st.session_state:
        st.session_state["new_tree_lat"] = 52.0406
    if "new_tree_lng" not in st.session_state:
        st.session_state["new_tree_lng"] = -0.7594

    photo = st.file_uploader("Upload a photo (optional)", type=["jpg", "jpeg", "png", "webp"])
    exif_coords = get_exif_lat_lng(photo)
    if photo:
        info_col, button_col = st.columns([5, 2])
        with info_col:
            st.caption(f"Selected photo: {photo.name}")
        with button_col:
            extract_pressed = st.button(
                "Extract GPS",
                key="extract_gps_button",
                use_container_width=True,
                disabled=not bool(exif_coords),
            )

        if extract_pressed and exif_coords:
            st.session_state["new_tree_lat"] = exif_coords[0]
            st.session_state["new_tree_lng"] = exif_coords[1]
            st.rerun()

        if exif_coords:
            st.success(f"EXIF GPS found: {exif_coords[0]:.6f}, {exif_coords[1]:.6f}")
        else:
            st.info("No GPS EXIF metadata found in this image.")

    with st.form("add_tree_form", clear_on_submit=True):
        name = st.text_input("Tree name / variety", placeholder="e.g. Magnolia × soulangeana")
        description = st.text_area(
            "Description",
            placeholder="e.g. Large pink blooms near the lake entrance",
            height=80,
        )
        col1, col2 = st.columns(2)
        with col1:
            lat = st.number_input("Latitude", key="new_tree_lat", format="%.6f", step=0.0001)
        with col2:
            lng = st.number_input("Longitude", key="new_tree_lng", format="%.6f", step=0.0001)
        submitted = st.form_submit_button("Add Tree", type="primary")

    if submitted:
        final_name = name.strip()
        if not final_name and photo:
            final_name = Path(photo.name).stem.replace("_", " ").replace("-", " ").strip()

        if not final_name:
            st.error("Please enter a tree name, or upload a photo to auto-name it.")
        else:
            image_bytes = compress_image(photo) if photo else None
            add_tree(final_name, lat, lng, image_bytes, description.strip())
            st.success(f"\u2705 '{final_name}' added to the map!")
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

