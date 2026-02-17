import sqlite3
import paho.mqtt.client as mqtt
import json
import time
import math

# --- SETTINGS ---
BROKER = "localhost"
PORT = 1883
USER = "skier"          
PASSWORD = "IoTskier1"
ROOT_TOPIC = "unimore_ski"

# --- DIGITAL TWIN STATE ---
digital_twin = {
    "helmets": {},
    # Stato indipendente per ogni gruppo di tornelli
    "tornelli": {
        "A1": "GREEN",
        "A2": "GREEN",
        "A3": "GREEN",
        "A4": "GREEN"
    }
}

# --- MAPPA DELLE DIPENDENZE (TOPOLOGIA PISTE -> IMPIANTI) ---
# Quali piste influenzano quali tornelli?
GATE_DEPENDENCIES = {
    "A1": ["P5", "P2", "P1"],
    "A2": ["P6", "P2", "P1"],
    "A3": ["P3", "P1"],
    "A4": ["P4", "P1"]
}

# Parametri Soglia
SOGLIA_AFFOLLAMENTO = 3 # Numero basso per simulazione

# --- DATABASE SETUP ---
DB_FILE = "ski_resort.db"

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # Aggiunta colonna 'piste'
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS helmet_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                device_id TEXT,
                piste TEXT,
                hum REAL,
                temp REAL,
                lux INTEGER,
                speed_kmh REAL,  
                fall_detected INTEGER
            )
        ''')
        # Aggiunta colonna 'gate_id'
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gate_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                gate_id TEXT,
                status TEXT,
                reason TEXT
            )
        ''')
        conn.commit()
        conn.close()
        print("[DB] Database inizializzato correttamente (Multi-Gate).")
    except Exception as e:
        print(f"[DB ERROR] Init fallita: {e}")

def log_helmet_data(device_id, payload):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        sensors = payload.get("sensors", {})
        speed = payload.get("calculated_speed_kmh", 0.0)
        piste = payload.get("piste", "UNKNOWN") # Estraiamo la pista
        
        fall_status = 1 if sensors.get("fall", False) else 0
        
        cursor.execute('''
            INSERT INTO helmet_logs (timestamp, device_id, piste, hum, temp, lux, speed_kmh, fall_detected)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            time.time(), device_id, piste,
            sensors.get("hum", 0), sensors.get("temp", 0), sensors.get("lux", 1000), 
            speed, fall_status   
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] Scrittura casco fallita: {e}")

def log_gate_data(gate_id, status, reason):
    try:
        conn = sqlite3.connect(DB_FILE) 
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO gate_logs (timestamp, gate_id, status, reason)
            VALUES (?, ?, ?, ?)
        ''', (time.time(), gate_id, status, reason))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] Scrittura tornello fallita: {e}")

# --- FUNZIONI GEOGRAFICHE ---
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000.0  
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    return R * (2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)))

def calcola_velocita(device_id, current_payload):
    if device_id not in digital_twin["helmets"]: return 0.0
    prev_data = digital_twin["helmets"][device_id]
    
    curr_loc = current_payload.get("location", {})
    prev_loc = prev_data.get("location", {})
    
    time_delta = current_payload.get("timestamp", time.time()) - prev_data.get("timestamp", 0)
    if time_delta <= 0: return 0.0

    dist = haversine_distance(prev_loc.get("lat", 0.0), prev_loc.get("lon", 0.0), curr_loc.get("lat", 0.0), curr_loc.get("lon", 0.0))
    speed_kmh = (dist / time_delta) * 3.6
    return round(speed_kmh, 2) if speed_kmh >= 1.0 else 0.0

# --- MAIN LOGIC FUNCTIONS ---

def calcola_meteo_e_sicurezza(client):
    global digital_twin
    now = time.time()

    # 1. Pulizia caschi inattivi (Timeout 60s)
    caschi_ids = list(digital_twin["helmets"].keys())
    for helmet_id in caschi_ids:
        if now - digital_twin["helmets"][helmet_id].get("ts_ricezione", 0) > 60:
            del digital_twin["helmets"][helmet_id]
            print(f"[CLEANUP] Casco {helmet_id} rimosso per inattività.")

    # 2. VALUTAZIONE INDIPENDENTE PER OGNI GRUPPO DI TORNELLI
    # Per ogni tornello (A1, A2, A3, A4), guardiamo solo le piste che lo influenzano
    for gate_id, dependent_pistes in GATE_DEPENDENCIES.items():
        
        totale_caschi = 0
        totale_cadute = 0
        count_nebbia = 0
        
        # Analizziamo solo i caschi che si trovano sulle piste dipendenti
        for hid, dati in digital_twin["helmets"].items():
            piste_casco = dati.get("piste", "UNKNOWN")
            
            if piste_casco in dependent_pistes:
                totale_caschi += 1
                sensors = dati.get("sensors", {})
                
                if sensors.get("fall") == True:
                    totale_cadute += 1
                
                # Priorità Fotoresistenza: > 200 = Nebbia
                if sensors.get("lux", 1000) > 200:
                    count_nebbia += 1

        # Calcolo Meteo Locale per questo gruppo
        is_foggy = False
        if totale_caschi > 0 and (count_nebbia / totale_caschi) > 0.3:
            is_foggy = True

        is_crowded = (totale_caschi >= SOGLIA_AFFOLLAMENTO)

        # Logica di Priorità specifica per QUESTO gate
        stato_richiesto = "GREEN"
        msg_display = "WELCOME - OPEN"
        flow = 10 
        
        if totale_cadute > 0:
            stato_richiesto = "RED"
            msg_display = "DANGER ENVIRONMENT"
            flow = 0
        elif is_foggy and is_crowded:
            stato_richiesto = "RED"
            msg_display = "CLOSED: FOG+CROWD"
            flow = 0
        elif is_foggy:
            stato_richiesto = "YELLOW"
            msg_display = "SLOW DOWN: FOGGY"
            flow = 2
        elif is_crowded:
            stato_richiesto = "YELLOW"
            msg_display = "ALERT: CROWDED"
            flow = 2

        # Applichiamo ed inviamo il comando SOLO se lo stato del singolo gate è cambiato
        if digital_twin["tornelli"][gate_id] != stato_richiesto:
            digital_twin["tornelli"][gate_id] = stato_richiesto
            
            payload_tornello = {
                "traffic_light": stato_richiesto,
                "display_msg": msg_display,
                "flow_rate": flow
            }
            topic_tornello = f"{ROOT_TOPIC}/turnstiles/{gate_id}/set"
            
            print(f"[CMD {gate_id}] Cambio stato -> {stato_richiesto} (Piste valutate: {dependent_pistes})")
            client.publish(topic_tornello, json.dumps(payload_tornello), retain=True)
            log_gate_data(gate_id, stato_richiesto, msg_display)

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

        device_type, device_id, msg_type = parts[1], parts[2], parts[3]

        if device_type == "helmets":
            # Gestione Spegnimento Volontario (LWT emulato)
            if payload.get("user_status") == "OFFLINE":
                if device_id in digital_twin["helmets"]:
                    del digital_twin["helmets"][device_id]
                    print(f"[SYSTEM] Casco {device_id} andato OFFLINE.")
                    calcola_meteo_e_sicurezza(client)
                return 

            payload["ts_ricezione"] = time.time()
            
            # Se la pista non è specificata dal casco, la forziamo a UNKNOWN
            if "piste" not in payload:
                payload["piste"] = "UNKNOWN"
            
            if msg_type == "telemetry":
                payload["calculated_speed_kmh"] = calcola_velocita(device_id, payload)
                digital_twin["helmets"][device_id] = payload
                log_helmet_data(device_id, payload)
                calcola_meteo_e_sicurezza(client)
                
            elif msg_type == "event":
                print(f"[ALARM] Evento da {device_id} su pista {payload['piste']}: {payload}")

    except Exception as e:
        print(f"Errore messaggio: {e}")

# --- MAIN ---
if __name__ == "__main__":
    init_db()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(USER, PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    print("Avvio Server Digital Twin Multi-Gate (Unimore Ski)...")
    try:
        client.connect(BROKER, PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("Spegnimento...")
root@ysServer:~/iot_project# 
