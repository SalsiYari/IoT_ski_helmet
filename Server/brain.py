import sqlite3
import paho.mqtt.client as mqtt
import json
import time
import math  # <--- NUOVO: Serve per i calcoli trigonometrici GPS

# --- CONFIGURAZIONE ---
BROKER = "localhost"
PORT = 1883
USER = "skier"
PASSWORD = "IoTskier1"

# Topic Root
ROOT_TOPIC = "unimore_ski"

# --- DIGITAL TWIN STATE ---
digital_twin = {
    "helmets": {},      
    "meteo_global": "SERENO", 
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
    """Inizializza il database se non esiste"""
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
        print(f"[DB ERROR] Inizializzazione fallita: {e}")

def log_helmet_data(device_id, payload):
    """Salva i dati del casco nel DB"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        sensors = payload.get("sensors", {})
        
        # Recuperiamo la velocità che abbiamo calcolato noi nel main loop
        speed = payload.get("calculated_speed_kmh", 0.0)
        
        cursor.execute('''
            INSERT INTO helmet_logs (timestamp, device_id, hum, temp, lux, speed_kmh, fall_detected)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            time.time(),
            device_id,
            sensors.get("hum", 0),
            sensors.get("temp", 0),
            sensors.get("lux", 1000), 
            speed,  # <--- Salviamo la velocità calcolata
            0   
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] Scrittura fallita: {e}")

# --- FUNZIONI DI CALCOLO GEOGRAFICO (NUOVO) ---

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calcola la distanza in METRI tra due coordinate GPS.
    """
    R = 6371000.0  # Raggio della Terra in metri
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0)**2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0)**2
    
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    
    meters = R * c
    return meters

def calcola_velocita(device_id, current_payload):
    """
    Confronta la posizione attuale con quella precedente salvata nel Digital Twin
    e restituisce la velocità in km/h.

    Per farlo dobbiamo usare la Formula dell'Haversine, che calcola la distanza reale tra due punti su una sfera (la Terra).
    """
    # Se non abbiamo uno storico per questo casco, velocità è 0
    if device_id not in digital_twin["helmets"]:
        return 0.0

    prev_data = digital_twin["helmets"][device_id]
    
    # Estrazione dati attuali
    curr_loc = current_payload.get("location", {})
    curr_lat = curr_loc.get("lat", 0.0)
    curr_lon = curr_loc.get("lon", 0.0)
    curr_ts = current_payload.get("timestamp", time.time()) # Usa il timestamp del pacchetto!

    # Estrazione dati precedenti
    prev_loc = prev_data.get("location", {})
    prev_lat = prev_loc.get("lat", 0.0)
    prev_lon = prev_loc.get("lon", 0.0)
    prev_ts = prev_data.get("timestamp", 0)

    # Evitiamo calcoli se i dati sono identici o il tempo è 0 (pacchetti duplicati)
    time_delta = curr_ts - prev_ts
    if time_delta <= 0:
        return 0.0

    # Calcolo distanza
    dist_meters = haversine_distance(prev_lat, prev_lon, curr_lat, curr_lon)
    
    # Calcolo velocità (Metri al secondo)
    speed_ms = dist_meters / time_delta
    
    # Conversione in Km/h
    speed_kmh = speed_ms * 3.6
    
    # Filtro rumore GPS: se si muove meno di 1 km/h consideriamolo fermo
    if speed_kmh < 1.0:
        speed_kmh = 0.0
        
    return round(speed_kmh, 2)

# --- MAIN LOGIC FUNCTIONS ---

def calcola_meteo_e_sicurezza(client):
    global digital_twin
    
    count_nebbia = 0
    totale_caschi_attivi = 0
    now = time.time()

    caschi_ids = list(digital_twin["helmets"].keys())
    
    for helmet_id in caschi_ids:
        dati = digital_twin["helmets"][helmet_id]
        
        # Timeout
        if now - dati.get("ts_ricezione", 0) > 60:
            continue
            
        totale_caschi_attivi += 1
        
        sensors = dati.get("sensors", {})
        umidita = sensors.get("hum", 0)
        luce = sensors.get("lux", 1000) 

        if umidita > SOGLIA_NEBBIA_UMIDITA and luce < SOGLIA_LUCE_BASSA:
            count_nebbia += 1

    nuovo_meteo = "SERENO"
    if totale_caschi_attivi > 0 and (count_nebbia / totale_caschi_attivi) > 0.3:
        nuovo_meteo = "NEBBIA"
    
    digital_twin["meteo_global"] = nuovo_meteo

    print(f"[LOGICA] Caschi: {totale_caschi_attivi} | Meteo: {nuovo_meteo}")

    # --- LOGICA TORNELLI ---
    stato_richiesto = "GREEN"
    msg_display = "BENVENUTI - APERTO"
    flow = 10 
    
    if digital_twin["meteo_global"] == "NEBBIA":
        stato_richiesto = "RED"
        msg_display = "CHIUSO PER NEBBIA"
        flow = 0
    elif totale_caschi_attivi >= SOGLIA_AFFOLLAMENTO:
        stato_richiesto = "YELLOW"
        msg_display = "RALLENTARE - AFFOLLATO"
        flow = 2

    if digital_twin["tornelli"]["gate_A"] != stato_richiesto:
        digital_twin["tornelli"]["gate_A"] = stato_richiesto
        payload_tornello = {
            "traffic_light": stato_richiesto,
            "display_msg": msg_display,
            "flow_rate": flow
        }
        topic_tornello = f"{ROOT_TOPIC}/turnstiles/gate_A/set"
        print(f"[CMD] Cambio Stato -> {stato_richiesto}")
        client.publish(topic_tornello, json.dumps(payload_tornello), retain=True)

# --- CALLBACKS MQTT ---

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[SYSTEM] Connesso al Broker (Codice: {rc})")
    client.subscribe(f"{ROOT_TOPIC}/helmets/+/telemetry")
    client.subscribe(f"{ROOT_TOPIC}/helmets/+/event")

def on_message(client, userdata, msg):
    global digital_twin
    topic = msg.topic
    
    try:
        payload = json.loads(msg.payload.decode())
        
        # FIX: Parsing corretto del topic in 4 parti
        parts = topic.split("/")
        if len(parts) < 4: return 

        device_type = parts[1] # Indice 1 = helmets
        device_id = parts[2]   # Indice 2 = ID del casco
        msg_type = parts[3]    # Indice 3 = telemetry O event

        if device_type == "helmets":
            # Timestamp ricezione server
            payload["ts_ricezione"] = time.time()
            
            if msg_type == "telemetry":
                # --- 1. CALCOLO VELOCITÀ ---
                speed_kmh = calcola_velocita(device_id, payload)
                payload["calculated_speed_kmh"] = speed_kmh
                print(f"[INFO] {device_id} Speed: {speed_kmh} km/h")

                # --- 2. AGGIORNAMENTO STATO ---
                digital_twin["helmets"][device_id] = payload
                log_helmet_data(device_id, payload)
                calcola_meteo_e_sicurezza(client)
                
            elif msg_type == "event":
                print(f"[ALARM] Evento da {device_id}: {payload}")

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
