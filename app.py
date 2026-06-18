
from flask import Flask, render_template, request, jsonify
from flask import send_file
import sqlite3
import os
from datetime import datetime, timedelta

app = Flask(__name__)

DB = "relaydht.db"

# ==================================================
# DATABASE
# ==================================================

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = get_db()
    c = conn.cursor()

    # ==========================================
    # DATA SENSOR
    # ==========================================
    c.execute("""
    CREATE TABLE IF NOT EXISTS sensor_data(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        device_name TEXT,
        temperature REAL,
        humidity REAL,
        relay INTEGER,
        sensor_status TEXT,
        created_at TEXT
    )
    """)

    # ==========================================
    # DEVICE CONFIG
    # ==========================================
    c.execute("""
    CREATE TABLE IF NOT EXISTS devices(
        device_id TEXT PRIMARY KEY,
        device_name TEXT,
        relay INTEGER DEFAULT 0,
        mode TEXT DEFAULT 'AUTO',
        low_temp REAL DEFAULT 30,
        high_temp REAL DEFAULT 34,
        updated_at TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()

# ==================================================
# HELPER
# ==================================================

def create_device_if_not_exists(
        device_id,
        device_name="Unknown Device"):

    conn = get_db()
    c = conn.cursor()

    c.execute("""
    SELECT *
    FROM devices
    WHERE device_id=?
    """, (device_id,))

    row = c.fetchone()

    if not row:

        c.execute("""
        INSERT INTO devices
        (
            device_id,
            device_name,
            relay,
            mode,
            low_temp,
            high_temp,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            device_id,
            device_name,
            0,
            "AUTO",
            31,
            34,
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ))

    else:

        c.execute("""
        UPDATE devices
        SET device_name=?
        WHERE device_id=?
        """,
        (
            device_name,
            device_id
        ))

    conn.commit()
    conn.close()


# ==================================================
# DASHBOARD
# ==================================================

@app.route("/")
def index():
    return render_template("index_multi.html")


# ==================================================
# LIST DEVICE
# ==================================================

@app.route("/devices")
def devices():

    conn = get_db()

    rows = conn.execute("""
    SELECT *
    FROM devices
    ORDER BY device_name
    """).fetchall()

    conn.close()

    return jsonify([
        dict(r)
        for r in rows
    ])


# ==================================================
# ESP32 GET CONFIG
# ==================================================

@app.route("/esp32/<device_id>")
def esp32(device_id):

    create_device_if_not_exists(
        device_id
    )

    conn = get_db()

    row = conn.execute("""
    SELECT *
    FROM devices
    WHERE device_id=?
    """,
    (device_id,)
    ).fetchone()

    conn.close()

    return jsonify(dict(row))


# ==================================================
# UPDATE SENSOR
# ==================================================

@app.route("/update", methods=["POST"])
def update():

    data = request.json

    device_id = data.get(
        "device_id",
        "unknown"
    )

    device_name = data.get(
        "device_name",
        "Unknown Device"
    )

    create_device_if_not_exists(
        device_id,
        device_name
    )

    conn = get_db()

    conn.execute("""
    INSERT INTO sensor_data
    (
        device_id,
        device_name,
        temperature,
        humidity,
        relay,
        sensor_status,
        created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
    (
        device_id,
        device_name,
        data.get("temperature"),
        data.get("humidity"),
        data.get("relay"),
        data.get("sensor_status", "OK"),
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "status": "ok",
        "device_id": device_id,
        "device_name": device_name
    })


# ==================================================
# HISTORY
# ==================================================

@app.route("/history")
def history():

    device_id = request.args.get("device")
    period = request.args.get("period", "24")

    start = request.args.get("start")
    end = request.args.get("end")

    conn = get_db()

    query = """
    SELECT *
    FROM sensor_data
    WHERE 1=1
    """

    params = []

    if device_id:

        query += """
        AND device_id=?
        """

        params.append(device_id)

    if start and end:

        query += """
        AND created_at
        BETWEEN ? AND ?
        """

        params.append(
            start.replace("T", " ")
        )

        params.append(
            end.replace("T", " ")
        )

    else:

        hours = int(period)

        limit = datetime.now() - timedelta(
            hours=hours
        )

        query += """
        AND created_at >= ?
        """

        params.append(
            limit.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

    query += " ORDER BY id ASC"

    rows = conn.execute(
        query,
        tuple(params)
    ).fetchall()

    conn.close()

    return jsonify([
        dict(r)
        for r in rows
    ])


# ==================================================
# DEVICE STATUS
# ==================================================

@app.route("/device_status/<device_id>")
def device_status(device_id):

    conn = get_db()

    row = conn.execute("""
    SELECT created_at
    FROM sensor_data
    WHERE device_id=?
    ORDER BY id DESC
    LIMIT 1
    """,
    (device_id,)
    ).fetchone()

    conn.close()

    if not row:

        return jsonify({
            "status": "OFFLINE",
            "last_update": "-"
        })

    last = datetime.strptime(
        row["created_at"],
        "%Y-%m-%d %H:%M:%S"
    )

    diff = (
        datetime.now() - last
    ).total_seconds()

    return jsonify({
        "status":
            "ONLINE"
            if diff < 10
            else "OFFLINE",
        "last_update":
            row["created_at"]
    })


# ==================================================
# CONFIG DEVICE
# ==================================================

@app.route(
    "/config/<device_id>",
    methods=["POST"]
)
def config(device_id):

    create_device_if_not_exists(
        device_id
    )

    data = request.json

    relay = int(
        data.get("relay", 0)
    )

    mode = data.get(
        "mode",
        "AUTO"
    )

    low_temp = float(
        data.get(
            "low_temp",
            30
        )
    )

    high_temp = float(
        data.get(
            "high_temp",
            34
        )
    )

    conn = get_db()

    conn.execute("""
    UPDATE devices
    SET
        relay=?,
        mode=?,
        low_temp=?,
        high_temp=?,
        updated_at=?
    WHERE device_id=?
    """,
    (
        relay,
        mode,
        low_temp,
        high_temp,
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        device_id
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "status": "ok",
        "device": device_id
    })


# ==================================================
# RELAY MANUAL
# ==================================================

@app.route(
    "/relay/<device_id>/<int:state>"
)
def relay(device_id, state):

    create_device_if_not_exists(
        device_id
    )

    conn = get_db()

    conn.execute("""
    UPDATE devices
    SET
        relay=?,
        updated_at=?
    WHERE device_id=?
    """,
    (
        state,
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        device_id
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "device": device_id,
        "relay": state
    })


# ==================================================
# LAST DATA
# ==================================================

@app.route("/last/<device_id>")
def last_data(device_id):

    conn = get_db()

    row = conn.execute("""
    SELECT *
    FROM sensor_data
    WHERE device_id=?
    ORDER BY id DESC
    LIMIT 1
    """,
    (device_id,)
    ).fetchone()

    conn.close()

    if not row:
        return jsonify({})

    return jsonify(
        dict(row)
    )


# ==================================================
# DELETE HISTORY DEVICE
# ==================================================

@app.route(
    "/delete_history/<device_id>",
    methods=["POST"]
)
def delete_history(device_id):

    conn = get_db()

    conn.execute("""
    DELETE FROM sensor_data
    WHERE device_id=?
    """,
    (device_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "status": "ok"
    })

# ==================================================
# MANAGEMENT DATA
# ==================================================
@app.route("/management")
def management():
    return render_template("management.html")



@app.route("/db_stats")
def db_stats():

    conn = get_db()

    total_device = conn.execute(
        "SELECT COUNT(*) FROM devices"
    ).fetchone()[0]

    total_record = conn.execute(
        "SELECT COUNT(*) FROM sensor_data"
    ).fetchone()[0]

    first_data = conn.execute(
        "SELECT MIN(created_at) FROM sensor_data"
    ).fetchone()[0]

    last_data = conn.execute(
        "SELECT MAX(created_at) FROM sensor_data"
    ).fetchone()[0]

    conn.close()

    db_size = round(os.path.getsize(DB) / (1024 * 1024), 2)

    return jsonify({
        "total_device": total_device,
        "total_record": total_record,
        "database_size": db_size,
        "first_data": first_data,
        "last_data": last_data
    })

# ==================================================
# HAPUS SEMUA
# ==================================================
@app.route("/delete_all", methods=["POST"])
def delete_all():

    conn = get_db()

    conn.execute("DELETE FROM sensor_data")

    conn.commit()

    conn.close()

    return jsonify({
        "status":"ok"
    })

# ==================================================
# HAPUS SEBELUMNYA
# ==================================================
@app.route("/delete_before", methods=["POST"])
def delete_before():

    date = request.json["date"]

    conn = get_db()

    conn.execute(
        "DELETE FROM sensor_data WHERE created_at < ?",
        (date,)
    )

    conn.commit()

    conn.close()

    return jsonify({
        "status":"ok"
    })
# ==================================================
# VACUUM
# ==================================================

@app.route("/vacuum", methods=["POST"])
def vacuum():

    conn = get_db()

    conn.execute("VACUUM")

    conn.close()

    return jsonify({
        "status":"ok"
    })

# ==================================================
# BACKUP DATABASE
# ==================================================

@app.route("/backup")
def backup():

    return send_file(
        DB,
        as_attachment=True
    )
# ==================================================
# SERVER
# ==================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5008,
        debug=True
    )

