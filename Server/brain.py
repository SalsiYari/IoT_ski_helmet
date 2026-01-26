import paho.mqtt.client as mqtt
import json
import time

# --- CONFIGURAZIONE ---
BROKER = "localhost"
PORT = 1883
USER = "skier"
PASSWORD = "IoTskier1$" # <--- ricontrolla la password

# Topic Root
ROOT_TOPIC = "unimore_ski"

# --- DIGITAL TWIN state ---
# here is stored the last telemetry known for each helmet
digital_twin = {
    "helmets": {},      # { "helmet_001": { "speed": 45, "hum": 85, "last_seen": 123456... } }
    "meteo_global": "SERENO", 
    "tornelli": {
        "gate_A": "GREEN" 
    }
}

# Treshold èarameters
SOGLIA_NEBBIA_UMIDITA = 80.0
SOGLIA_LUCE_BASSA = 300
SOGLIA_AFFOLLAMENTO = 3    #low number as test 

# --- MAIN LOGIC FUNCITONS ---

def calcola_meteo_e_sicurezza(client):
    """
    Analizza i dati aggregati di TUTTI i caschi e comanda i tornelli.
    """
    global digital_twin
    
    count_nebbia = 0
    totale_caschi_attivi = 0
    now = time.time()

    # Analisi Caschi (Pulizia vecchi dati > 60 secondi fa)
    caschi_ids = list(digital_twin["helmets"].keys())
    for helmet_id in caschi_ids:
        dati = digital_twin["helmets"][helmet_id]
        
        # Se il dato è vecchio di 1 minuto, ignoralo (sciatore andato via/spento)
        if now - dati.get("ts_ricezione", 0) > 60:
            continue
            
        totale_caschi_attivi += 1
        
        # Logica rilevamento nebbia del singolo casco
        env = dati.get("env", {})
        if env.get("hum", 0) > SOGLIA_NEBBIA_UMIDITA and env.get("lux", 1000) < SOGLIA_LUCE_BASSA:
            count_nebbia += 1

    # Decisione Meteo Globale
    if totale_caschi_attivi > 0 and (count_nebbia / totale_caschi_attivi) > 0.3:
        digital_twin["meteo_global"] = "NEBBIA"
    else:
        digital_twin["meteo_global"] = "SERENO"

    print(f"[LOGICA] Caschi Attivi: {totale_caschi_attivi} | Meteo: {digital_twin['meteo_global']}")

    # --- COMANDO TORNELLI ---
    # Logica: Nebbia O Troppa Gente -> Chiudi
    
    stato_richiesto = "GREEN"
    msg_display = "BENVENUTI - APERTO"
    flow = 10 # Frequenza alta
    
    if digital_twin["meteo_global"] == "NEBBIA":
        stato_richiesto = "RED"
        msg_display = "CHIUSO PER NEBBIA"
        flow = 0
    elif totale_caschi_attivi >= SOGLIA_AFFOLLAMENTO:
        stato_richiesto = "YELLOW"
        msg_display = "RALLENTARE - AFFOLLATO"
        flow = 2 # Frequenza bassa

    # Inviamo il comando SOLO se lo stato cambia (per non intasare la rete)
    if digital_twin["tornelli"]["gate_A"] != stato_richiesto:
        digital_twin["tornelli"]["gate_A"] = stato_richiesto
        
        payload_tornello = {
            "traffic_light": stato_richiesto, # RED, GREEN, YELLOW
            "display_msg": msg_display,
            "flow_rate": flow
        }
        
        topic_tornello = f"{ROOT_TOPIC}/turnstiles/gate_A/set"
        print(f"[CMD] Invio comando a {topic_tornello}: {payload_tornello}")
        client.publish(topic_tornello, json.dumps(payload_tornello), retain=True)


# --- CALLBACKS MQTT ---

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[SYSTEM] Connesso al Broker (Codice: {rc})")
    # Sottoscrizione con wildcard per ricevere dati da TUTTI i caschi
    # + indica "qualsiasi stringa a quel livello"
    # Riceviamo sia telemetry che event
    client.subscribe(f"{ROOT_TOPIC}/helmets/+/telemetry")
    client.subscribe(f"{ROOT_TOPIC}/helmets/+/event")

def on_message(client, userdata, msg):
    global digital_twin
    topic = msg.topic
    payload_str = msg.payload.decode()
    
    try:
        payload = json.loads(payload_str)
        
        # Parsing del topic per estrarre l'ID del casco
        # Topic atteso: unimore_ski/helmets/helmet_001/telemetry
        parts = topic.split("/")
        device_type = parts[2] # helmets
        device_id = parts[3]   # helmet_001
        msg_type = parts[4]    # telemetry O event

        if device_type == "helmets":
            # Aggiungiamo un timestamp di ricezione lato server
            payload["ts_ricezione"] = time.time()
            
            if msg_type == "telemetry":
                # Aggiorniamo lo stato del casco nel Digital Twin
                digital_twin["helmets"][device_id] = payload
                # Eseguiamo la logica globale (Nebbia, etc.)
                calcola_meteo_e_sicurezza(client)
                
            elif msg_type == "event":
                print(f"[ALARM] Evento critico da {device_id}: {payload}")
                # Qui potresti gestire la caduta (Type: FALL_DETECTED)
                if payload.get("type") == "FALL_DETECTED":
                    print("!!! ATTENZIONE: CADUTA RILEVATA !!!")
                    # Esempio: Invia comando SOS a tutti i caschi vicini
                    # client.publish(f"{ROOT_TOPIC}/helmets/all/cmd", json.dumps({"alert": "SOS NEARBY"}))

    except Exception as e:
        print(f"Errore elaborazione messaggio: {e}")

# --- MAIN ---
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

