import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
from pyzbar import pyzbar
import av
import sqlite3
from datetime import datetime

# SQLite setup
def init_db():
    conn = sqlite3.connect("transport.db")
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reg_number TEXT,
        year INTEGER,
        department TEXT,
        bus_name TEXT,
        timestamp TEXT
    )
    """)
    conn.commit()
    return conn, c

class QRScanner(VideoTransformerBase):
    def __init__(self):
        self.last_qr = None

    def transform(self, frame):
        img = frame.to_ndarray(format="bgr24")
        decoded_objs = pyzbar.decode(img)
        for obj in decoded_objs:
            self.last_qr = obj.data.decode("utf-8")
        return av.VideoFrame.from_ndarray(img, format="bgr24")

st.title("📷 Bus Attendance QR Scanner")

bus_name = st.selectbox("Select Bus", ["Bus1", "Bus2", "Bus3"])

if "scanned_code" not in st.session_state:
    st.session_state.scanned_code = None

scanner = webrtc_streamer(
    key="qr-scanner",
    video_transformer_factory=QRScanner,
    media_stream_constraints={"video": True, "audio": False}
)

if scanner.video_transformer:
    code = scanner.video_transformer.last_qr
    if code and code != st.session_state.scanned_code:
        st.session_state.scanned_code = code

        # Extract year & dept from roll number
        roll = code.strip()
        year = 2000 + int(roll[4:6])  # "22" -> 2022
        dept_code = roll[6:8]
        dept_map = {
            "60": "CSE",
            "61": "ECE",
            "62": "EEE"
        }
        dept = dept_map.get(dept_code, "Unknown")

        # Save attendance
        conn, c = init_db()
        c.execute("INSERT INTO attendance (reg_number, year, department, bus_name, timestamp) VALUES (?, ?, ?, ?, ?)",
                  (roll, year, dept, bus_name, datetime.now().isoformat()))
        conn.commit()
        conn.close()

        st.success(f"✅ Scanned {roll} | Year: {year} | Dept: {dept}")

# Attendance summary for today
if st.button("📊 Show Today's Attendance Summary"):
    conn, c = init_db()
    df = pd.read_sql_query("""
        SELECT bus_name, year, department, COUNT(*) AS present_count
        FROM attendance
        WHERE DATE(timestamp) = DATE('now')
        GROUP BY bus_name, year, department
    """, conn)
    st.dataframe(df)
    conn.close()

# Download today's attendance
if st.button("⬇ Download Today's Attendance CSV"):
    conn, c = init_db()
    df = pd.read_sql_query("""
        SELECT * FROM attendance WHERE DATE(timestamp) = DATE('now')
    """, conn)
    st.download_button("Download CSV", df.to_csv(index=False), "attendance_today.csv", "text/csv")
    conn.close()
