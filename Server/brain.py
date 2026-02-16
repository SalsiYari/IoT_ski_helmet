(venvIot) root@ysServer:~/iot_project# cat brain.py 
import sqlite3
import paho.mqtt.client as mqtt
import json
import time
import math  # per i calcoli trigonometrici GPS

# --- SETTINGS ---
BROKER = "localhost"
PORT = 1883
USER = "skier"          
PASSWORD = "IoTskier1"

# Topic Root
ROOT_TOPIC = "unimore_ski"

# --- DIGITAL TWIN STATE ---
digital_twin = {
    "helmets": {},
    "meteo_global": "SUNNY", 
    "tornelli": {
        "gate_A": "GREEN"
    }
}

# Parametri Soglia
SOGLIA_NEBBIA_UMIDITA = 80.0
SOGLIA_LUCE_BASSA = 300
SOGLIA_AFFOLLAMENTO = 3 

# --- DATABASE SETUP ---
DB_FILE = "ski_resort.db"

def init_db():
    """Initialize db if doesn't exist"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS helmet_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                device_id TEXT,
                hum REAL,
                temp REAL,
                lux INTEGER,
                speed_kmh REAL,  
                fall_detected INTEGER
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gate_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                status TEXT,
                reason TEXT
            )
        ''')
        conn.commit()
        conn.close()
        print("[DB] Database inizializzato correttamente.")
    except Exception as e:
        print(f"[DB ERROR] initialization failed: {e}")

def log_helmet_data(device_id, payload):
    """Save helmet data on DB"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        sensors = payload.get("sensors", {})
        speed = payload.get("calculated_speed_kmh", 0.0)
        
        # Legge lo switch "fall" direttamente dal sensore
        is_falling = sensors.get("fall", False)
        fall_status = 1 if is_falling else 0
        
        cursor.execute('''
            INSERT INTO helmet_logs (timestamp, device_id, hum, temp, lux, speed_kmh, fall_detected)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            time.time(),
            device_id,
            sensors.get("hum", 0),
            sensors.get("temp", 0),
            sensors.get("lux", 1000), 
            speed,  
            fall_status   
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] Scrittura fallita: {e}")

def log_gate_data(status, reason):
    """Salva i cambi di stato del tornello nel DB"""
    try:
        conn = sqlite3.connect(DB_FILE) 
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO gate_logs (timestamp, status, reason)
        VALUES (?, ?, ?)
        ''', (time.time(), status, reason))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] Scrittura tornello fallita: {e}")

# --- FUNZIONI DI CALCOLO GEOGRAFICO ---

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calcola la distanza in METRI tra due coordinate GPS."""
    R = 6371000.0  
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0)**2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0)**2
    
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def calcola_velocita(device_id, current_payload):
    """Confronta la posizione attuale con la precedente e restituisce la velocità in km/h."""
    if device_id not in digital_twin["helmets"]:
        return 0.0

    prev_data = digital_twin["helmets"][device_id]
    
    curr_loc = current_payload.get("location", {})
    curr_lat = curr_loc.get("lat", 0.0)
    curr_lon = curr_loc.get("lon", 0.0)
    curr_ts = current_payload.get("timestamp", time.time()) 

    prev_loc = prev_data.get("location", {})
    prev_lat = prev_loc.get("lat", 0.0)
    prev_lon = prev_loc.get("lon", 0.0)
    prev_ts = prev_data.get("timestamp", 0)

    time_delta = curr_ts - prev_ts
    if time_delta <= 0: return 0.0

    dist_meters = haversine_distance(prev_lat, prev_lon, curr_lat, curr_lon)
    speed_ms = dist_meters / time_delta
    speed_kmh = speed_ms * 3.6
    
    if speed_kmh < 1.0: speed_kmh = 0.0
        
    return round(speed_kmh, 2)

# --- MAIN LOGIC FUNCTIONS ---

def calcola_meteo_e_sicurezza(client):
    global digital_twin
    
    count_nebbia = 0
    totale_caschi_attivi = 0
    totale_cadute = 0
    now = time.time()

    # Usiamo list() per poter eliminare chiavi durante l'iterazione
    caschi_ids = list(digital_twin["helmets"].keys())
    
    for helmet_id in caschi_ids:
        dati = digital_twin["helmets"][helmet_id]
        
        # Timeout Telemetria (Se non riceviamo dati da 60s, il casco è offline)
        if now - dati.get("ts_ricezione", 0) > 60:
            del digital_twin["helmets"][helmet_id]
            print(f"[CLEANUP] Casco {helmet_id} rimosso per inattività.")
            continue
            
        totale_caschi_attivi += 1
        
        sensors = dati.get("sensors", {})
        umidita = sensors.get("hum", 0)
        luce = sensors.get("lux", 1000) 
        
        # Lettura istantanea dello Switch Caduta inviato dal casco
        if sensors.get("fall") == True:
            totale_cadute += 1

        # --- LOGICA TEST: PRIORITÀ FOTORESISTENZA ---
        # Se il valore letto dal sensore di luminosità è maggiore di 200, dichiariamo nebbia.
        if luce > 200:
            count_nebbia += 1

    # Valutazione globale Meteo
    nuovo_meteo = "SERENO"
    if totale_caschi_attivi > 0 and (count_nebbia / totale_caschi_attivi) > 0.3:
        nuovo_meteo = "NEBBIA"
    
    digital_twin["meteo_global"] = nuovo_meteo

    print(f"[LOGICA] Caschi: {totale_caschi_attivi} | Cadute attive: {totale_cadute} | Meteo: {nuovo_meteo}")

    # --- LOGICA TORNELLI (SISTEMA A PRIORITÀ) ---
    stato_richiesto = "GREEN"
    msg_display = "WELCOME - OPEN"
    flow = 10 
    
    is_foggy = (nuovo_meteo == "NEBBIA")
    is_crowded = (totale_caschi_attivi >= SOGLIA_AFFOLLAMENTO)
    
    # Priorità 1: Caduta Rilevata
    if totale_cadute > 0:
        stato_richiesto = "RED"
        msg_display = "DANGER ENVIRONMENT"
        flow = 0
    # Priorità 2: Nebbia + Affollamento
    elif is_foggy and is_crowded:
        stato_richiesto = "RED"
        msg_display = "CLOSED: FOG+CROWD"
        flow = 0
    # Priorità 3: Solo Nebbia
    elif is_foggy:
        stato_richiesto = "YELLOW"
        msg_display = "SLOW DOWN: FOGGY"
        flow = 2
    # Priorità 4: Solo Affollamento
    elif is_crowded:
        stato_richiesto = "YELLOW"
        msg_display = "ALERT: CROWDED"
        flow = 2

    # Applicazione ed invio del comando solo se lo stato cambia
    if digital_twin["tornelli"]["gate_A"] != stato_richiesto:
        digital_twin["tornelli"]["gate_A"] = stato_richiesto
        payload_tornello = {
            "traffic_light": stato_richiesto,
            "display_msg": msg_display,
            "flow_rate": flow
        }
        topic_tornello = f"{ROOT_TOPIC}/turnstiles/gate_A/set"
        print(f"[CMD] Changing state -> {stato_richiesto}")
        client.publish(topic_tornello, json.dumps(payload_tornello), retain=True)
        log_gate_data(stato_richiesto, msg_display)

# --- CALLBACKS MQTT ---

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[SYSTEM] Connected to Broker (Code: {rc})")
    client.subscribe(f"{ROOT_TOPIC}/helmets/+/telemetry")
    client.subscribe(f"{ROOT_TOPIC}/helmets/+/event")

def on_message(client, userdata, msg):
    global digital_twin
    topic = msg.topic
    
    try:
        payload = json.loads(msg.payload.decode())
        
        parts = topic.split("/")
        if len(parts) < 4: return 

        device_type = parts[1] 
        device_id = parts[2]   
        msg_type = parts[3]    

        if device_type == "helmets":
            
            # --- NOVITÀ: GESTIONE SPEGNIMENTO CASCO ---
            if payload.get("user_status") == "OFFLINE":
                if device_id in digital_twin["helmets"]:
                    del digital_twin["helmets"][device_id]
                    print(f"[SYSTEM] Casco {device_id} spento manualmente.")
                    calcola_meteo_e_sicurezza(client)
                return # Esce, non c'è telemetria da elaborare

            # Altrimenti elabora normalmente
            payload["ts_ricezione"] = time.time()
            
            if msg_type == "telemetry":
                # CALCOLO VELOCITÀ
                speed_kmh = calcola_velocita(device_id, payload)
                payload["calculated_speed_kmh"] = speed_kmh
                
                # AGGIORNAMENTO STATO
                digital_twin["helmets"][device_id] = payload
                log_helmet_data(device_id, payload)
                calcola_meteo_e_sicurezza(client)
                
            elif msg_type == "event":
                print(f"[ALARM] Evento generico da {device_id}: {payload}")

    except Exception as e:
        print(f"Errore messaggio: {e}")

# --- MAIN ---
if __name__ == "__main__":
    init_db()
    
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(USER, PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    print("Avvio Server Digital Twin (Unimore Ski)...")
    try:
        client.connect(BROKER, PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("Spegnimento...")
(venvIot) root@ysServer:~/iot_project# 
