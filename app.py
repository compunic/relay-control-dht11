from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
DB = "relaydht.db"

# =========================
# GLOBAL CONFIG
# =========================
relay_status = 0
mode = "AUTO"
low_temp = 30
high_temp = 34


# =========================
# INIT DB
# =========================
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS sensor_data(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        temperature REAL,
        humidity REAL,
        relay INTEGER,
        sensor_status TEXT,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()


# =========================
# DASHBOARD
# =========================
@app.route("/")
def index():
    return render_template("index3.html")


# =========================
# ESP32 CONFIG ENDPOINT
# =========================
@app.route("/esp32")
def esp32():
    return jsonify({
        "relay": relay_status,
        "mode": mode,
        "low_temp": low_temp,
        "high_temp": high_temp
    })


# =========================
# UPDATE SENSOR DATA
# =========================
@app.route("/update", methods=["POST"])
def update():

    data = request.json

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    INSERT INTO sensor_data
    (temperature, humidity, relay, sensor_status, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (
        data.get("temperature"),
        data.get("humidity"),
        data.get("relay"),
        data.get("sensor_status"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# =========================
# HISTORY FILTER
# =========================
@app.route("/history")
def history():

    period = request.args.get("period", "24")
    start = request.args.get("start")
    end = request.args.get("end")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if start and end:

        c.execute("""
        SELECT * FROM sensor_data
        WHERE created_at BETWEEN ? AND ?
        ORDER BY id ASC
        """, (start.replace("T"," "), end.replace("T"," ")))

    else:

        hours = int(period)
        limit = datetime.now() - timedelta(hours=hours)

        c.execute("""
        SELECT * FROM sensor_data
        WHERE created_at >= ?
        ORDER BY id ASC
        """, (limit.strftime("%Y-%m-%d %H:%M:%S"),))

    rows = c.fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows])


# =========================
# DEVICE STATUS
# =========================
@app.route("/device_status")
def device_status():

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    SELECT created_at FROM sensor_data
    ORDER BY id DESC LIMIT 1
    """)

    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"status":"OFFLINE","last_update":"-"})

    last = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
    diff = (datetime.now() - last).total_seconds()

    return jsonify({
        "status": "ONLINE" if diff < 10 else "OFFLINE",
        "last_update": row[0]
    })


# =========================
# CONFIG FROM DASHBOARD
# =========================
@app.route("/config", methods=["POST"])
def config():

    global mode, low_temp, high_temp, relay_status

    data = request.json

    mode = data.get("mode", "AUTO")
    low_temp = float(data.get("low_temp", 30))
    high_temp = float(data.get("high_temp", 32))
    relay_status = int(data.get("relay", 0))

    return jsonify({"status":"ok"})


# =========================
# MANUAL RELAY
# =========================
@app.route("/relay/<int:state>")
def relay(state):

    global relay_status
    relay_status = state

    return jsonify({"relay": relay_status})


# =========================
# RUN SERVER
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5008, debug=True)