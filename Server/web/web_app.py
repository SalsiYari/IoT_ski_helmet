from flask import Flask, render_template, jsonify
import sqlite3
import time

app = Flask(__name__, template_folder='templates', static_folder='static')

DB_FILE = "/root/iot_project/ski_resort.db" 

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    
    # --- OTTIMIZZAZIONI LETTURA ---
    # Imposta la lettura non bloccante e aumenta la RAM dedicata alla cache (circa 64MB)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    conn.execute('PRAGMA cache_size=-64000;')
    
    conn.row_factory = sqlite3.Row
    return conn

def init_db_indexes():
    """ 
    Crea gli indici per velocizzare le letture del 99%.
    Viene eseguito una sola volta all'avvio dell'app.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        # Indice per le query dei tornelli
        conn.execute('CREATE INDEX IF NOT EXISTS idx_gate_id_time ON gate_logs(gate_id, timestamp DESC);')
        # Indici per le query sui caschi e sulle finestre temporali
        conn.execute('CREATE INDEX IF NOT EXISTS idx_helmet_time ON helmet_logs(timestamp DESC);')
        # Indice specifico per trovare istantaneamente le cadute
        conn.execute('CREATE INDEX IF NOT EXISTS idx_helmet_fall ON helmet_logs(fall_detected, timestamp DESC);')
        conn.commit()
        conn.close()
        print("[FLASK] Indici del Database ottimizzati con successo.")
    except Exception as e:
        print(f"[FLASK ERROR] Impossibile creare gli indici: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/dashboard')
def api_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    now = time.time()
    
    # 1. CURRENT TURNSTILES STATUS (A1, A2, A3, A4)
    gates_data = {}
    for gid in ["A1", "A2", "A3", "A4"]:
        # Ora questa query usa l'indice idx_gate_id_time ed è istantanea
        cursor.execute("SELECT status, reason, timestamp FROM gate_logs WHERE gate_id = ? ORDER BY timestamp DESC LIMIT 1", (gid,))
        gate_row = cursor.fetchone()
        gates_data[gid] = {
            "status": gate_row["status"] if gate_row else "UNKNOWN",
            "reason": gate_row["reason"] if gate_row else "WAITING DATA"
        }

    # 2. ACTIVE SKIERS & AVERAGE SPEEDS
    time_threshold = now - 60
    # Ora usa idx_helmet_time
    cursor.execute("SELECT COUNT(DISTINCT device_id) as active_count FROM helmet_logs WHERE timestamp >= ?", (time_threshold,))
    active_helmets = cursor.fetchone()["active_count"]
    
    cursor.execute('''
        SELECT device_id, AVG(speed_kmh) as avg_speed 
        FROM helmet_logs 
        WHERE timestamp >= ? 
        GROUP BY device_id
    ''', (time_threshold,))
    active_details = [{"id": r["device_id"], "speed": round(r["avg_speed"] or 0.0, 1)} for r in cursor.fetchall()]

    # 3. ALL EMERGENCIES (Falls history)
    # FIX: Aggiunto "LIMIT 50". Non vogliamo restituire 100.000 vecchie cadute via JSON intasando la rete!
    cursor.execute('''
        SELECT device_id, piste, timestamp 
        FROM helmet_logs 
        WHERE fall_detected = 1 
        ORDER BY timestamp DESC
        LIMIT 50
    ''')
    falls = [{"device": r["device_id"], "piste": r["piste"], "time": r["timestamp"]} for r in cursor.fetchall()]

    # 4. MANAGEMENT INSIGHTS (Last Hour)
    one_hour_ago = now - 3600
    cursor.execute('''
        SELECT AVG(speed_kmh) as avg_speed, MAX(speed_kmh) as max_speed, AVG(temp) as avg_temp
        FROM helmet_logs 
        WHERE timestamp >= ?
    ''', (one_hour_ago,))
    stats_row = cursor.fetchone()
    management_stats = {
        "avg_speed": round(stats_row["avg_speed"] or 0.0, 1),
        "max_speed": round(stats_row["max_speed"] or 0.0, 1),
        "avg_temp": round(stats_row["avg_temp"] or 0.0, 1)
    }

    # 5. CHART DATA (Live)
    cursor.execute('SELECT timestamp, hum, lux FROM helmet_logs ORDER BY timestamp DESC LIMIT 20')
    chart_rows = cursor.fetchall()[::-1] 
    
    chart_data = {
        "labels": [time.strftime('%H:%M:%S', time.localtime(r["timestamp"])) for r in chart_rows],
        "humidity": [r["hum"] for r in chart_rows],
        "light": [max(0, 1024 - r["lux"]) for r in chart_rows] 
    }

    conn.close()

    response = {
        "gates": gates_data,
        "active_helmets": active_helmets,
        "active_details": active_details,
        "falls": falls,
        "stats": management_stats,
        "chart": chart_data
    }
    
    return jsonify(response)

if __name__ == '__main__':
    init_db_indexes() # <--- Creazione indici automatica prima dell'avvio
    app.run(host='0.0.0.0', port=8080)
