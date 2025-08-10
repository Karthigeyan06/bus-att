import streamlit as st
import pandas as pd
import sqlite3
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from datetime import datetime
import geocoder

# ---------- DATABASE SETUP ----------
conn = sqlite3.connect("attendance.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reg_number TEXT,
    year TEXT,
    department TEXT,
    bus_name TEXT,
    timestamp TEXT,
    latitude REAL,
    longitude REAL
)
""")
conn.commit()

# ---------- HELPER FUNCTIONS ----------
def parse_roll_number(roll):
    """Extracts year, department from the given roll number."""
    year_joined = roll[4:6]
    year_map = {
        "22": "1st Year", "21": "2nd Year", "20": "3rd Year", "19": "4th Year"
    }
    year = year_map.get(year_joined, "Unknown")

    dept_code = roll[6:8]
    dept_map = {
        "60": "CSE", "61": "ECE", "62": "EEE", "63": "MECH", "64": "CIVIL"
    }
    department = dept_map.get(dept_code, "Unknown")
    return year, department

def scan_qr():
    """Opens camera once, scans QR, returns the data."""
    cap = cv2.VideoCapture(0)
    qr_data = None
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        for code in decode(frame):
            qr_data = code.data.decode('utf-8')
            cap.release()
            cv2.destroyAllWindows()
            return qr_data
        cv2.imshow("Scan QR Code - Press 'q' to cancel", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()
    return qr_data

def save_attendance(reg_number, bus_name):
    year, department = parse_roll_number(reg_number)
    g = geocoder.ip('me')
    lat, lon = (g.latlng if g.latlng else (None, None))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO attendance (reg_number, year, department, bus_name, timestamp, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (reg_number, year, department, bus_name, timestamp, lat, lon))
    conn.commit()

# ---------- STREAMLIT UI ----------
st.title("🚌 Bus Attendance System with QR Scan")

# Select Bus
bus_name = st.selectbox("Select Bus", ["R15", "R16", "R17", "R18", "R19", "R20"])

# Scan Button
if st.button("📷 Scan QR Code"):
    qr = scan_qr()
    if qr:
        save_attendance(qr, bus_name)
        st.success(f"Attendance marked for {qr} in bus {bus_name}")
    else:
        st.warning("No QR code detected.")

st.markdown("---")

# ---------- FILTERS FOR RETRIEVAL ----------
st.header("📊 Attendance Summary & Export")

date_filter = st.date_input("Select Date", datetime.today())
year_filter = st.selectbox("Select Year", ["", "1st Year", "2nd Year", "3rd Year", "4th Year"])
dept_filter = st.selectbox("Select Department", ["", "CSE", "ECE", "EEE", "MECH", "CIVIL"])
bus_filter = st.selectbox("Select Bus", [""] + ["R15", "R16", "R17", "R18", "R19", "R20"])

# ---------- QUERY ----------
query = """
SELECT bus_name, COUNT(*) AS present_count
FROM attendance
WHERE DATE(timestamp) = DATE(?)
"""
params = [date_filter]

if year_filter:
    query += " AND year = ?"
    params.append(year_filter)
if dept_filter:
    query += " AND department = ?"
    params.append(dept_filter)
if bus_filter:
    query += " AND bus_name = ?"
    params.append(bus_filter)

query += " GROUP BY bus_name"

df = pd.read_sql_query(query, conn, params=params)

st.dataframe(df)

# ---------- DOWNLOAD ----------
if not df.empty:
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name=f"attendance_summary_{date_filter}.csv",
        mime="text/csv"
    )
else:
    st.info("No data available for the selected filters.")
