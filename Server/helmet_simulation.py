# (mqtt-env) (base) yarisalsi@MacBook-Air-di-Yari IoT % cat helmet_simulaiton.py 
# THIS FILE IS RUN ON LOCAL MACHINE TO SIMULATE DIFFERENT USE-CASE SCENARIO

import paho.mqtt.client as mqtt
import json
import time

# --- CONFIGURAZIONE ---
BROKER_ADDRESS = "31.14.140.180" 
PORT = 1883
USER = "skier"
PASSWORD = "IoTskier1"
ROOT_TOPIC = "unimore_ski"

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(USER, PASSWORD)

print("Connessione al server VPS...")
client.connect(BROKER_ADDRESS, PORT, 60)
client.loop_start() # Usiamo start() invece di forever() per poter usare l'input utente

# --- FUNZIONI GENERATRICI ---

def invia_telemetria(helmet_id, hum, lux, lat=44.18, lon=10.70):
    """Crea e invia un pacchetto JSON identico a quello del casco reale"""
    payload = {
        "helmet_id": helmet_id,
        "timestamp": time.time(),
        "location": {"lat": lat, "lon": lon, "alt": 1500.0},
        "sensors": {
            "accel": [0.0, 0.0, 9.8],
            "gyro": [0.0, 0.0, 0.0],
            "temp": -2.5,
            "hum": hum,     # Importante per la nebbia
            "lux": lux      # Importante per la luce/nebbia
        },
        "user_status": "OK"
    }
    topic = f"{ROOT_TOPIC}/helmets/{helmet_id}/telemetry"
    client.publish(topic, json.dumps(payload))
    print(f" -> Inviata telemetria per {helmet_id}: Umidità={hum}%, Luce={lux}lux")

def invia_evento_caduta(helmet_id):
    """Simula un evento critico (caduta)"""
    payload = {
        "helmet_id": helmet_id,
        "timestamp": time.time(),
        "type": "FALL_DETECTED",
        "description": "Sensori inerziali rilevano un impatto e assenza di movimento."
    }
    topic = f"{ROOT_TOPIC}/helmets/{helmet_id}/event"
    client.publish(topic, json.dumps(payload))
    print(f" -> [ALLARME] Inviato evento CADUTA per {helmet_id}!")

# --- MENU INTERATTIVO ---

def menu():
    while True:
        print("\n" + "="*40)
        print(" SIMULATORE CASCHI - UNIMORE SKI IoT")
        print("="*40)
        print("1) Condizioni PERFETTE (Sereno, 1 Casco) -> Tornello VERDE")
        print("2) Rilevata NEBBIA (1 Casco) -> Tornello ROSSO")
        print("3) AFFOLLAMENTO PISTA (3 Caschi) -> Tornello GIALLO")
        print("4) CADUTA SCIATORE -> Allarme Log")
        print("0) Esci")
        
        scelta = input("Seleziona uno scenario: ")

        if scelta == "1":
            print("\n[Scenario] Invio dati SERENO...")
            invia_telemetria("helmet_sim_01", hum=40, lux=1000)
            time.sleep(1)

        elif scelta == "2":
            print("\n[Scenario] Invio dati NEBBIA...")
            # Umidità > 80 e Luce < 300 per far scattare la regola nel tuo brain.py
            invia_telemetria("helmet_sim_01", hum=95, lux=150)
            time.sleep(1)

        elif scelta == "3":
            print("\n[Scenario] Invio dati AFFOLLAMENTO...")
            # Invio dati fittizi da 3 caschi diversi contemporaneamente
            invia_telemetria("helmet_sim_01", hum=40, lux=1000, lat=44.1801)
            invia_telemetria("helmet_sim_02", hum=40, lux=1000, lat=44.1802)
            invia_telemetria("helmet_sim_03", hum=40, lux=1000, lat=44.1803)
            time.sleep(1)

        elif scelta == "4":
            print("\n[Scenario] Simulazione CADUTA...")
            invia_evento_caduta("helmet_sim_01")
            time.sleep(1)

        elif scelta == "0":
            print("Chiusura simulatore...")
            client.loop_stop()
            client.disconnect()
            break
        else:
            print("Scelta non valida.")

# Avvio
if __name__ == "__main__":
    try:
        menu()
    except KeyboardInterrupt:
        print("\nUscita forzata.")
        client.loop_stop()
        client.disconnect()
