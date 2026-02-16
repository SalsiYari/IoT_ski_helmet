# (mqtt-env) (base) yarisalsi@MacBook-Air-di-Yari IoT % cat helmet_simulaiton.py 
# THIS FILE IS RUN ON LOCAL MACHINE TO SIMULATE DIFFERENT USE-CASE SCENARIO
(mqtt-env) (base) yarisalsi@MacBook-Air-di-Yari IoT % cat helmet_simulaiton.py 
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
client.loop_start() 

# --- FUNZIONI GENERATRICI ---

def invia_telemetria(helmet_id, hum, lux, lat=44.18, lon=10.70, fall=False):
    """Crea e invia un pacchetto JSON identico a quello del casco reale"""
    payload = {
        "helmet_id": helmet_id,
        "timestamp": time.time(),
        "location": {"lat": lat, "lon": lon, "alt": 1500.0},
        "sensors": {
            "accel": [0.0, 0.0, 9.8],
            "gyro": [0.0, 0.0, 0.0],
            "temp": -2.5,
            "hum": hum,     
            "lux": lux,      
            "fall": fall    
        },
        "user_status": "OK"
    }
    topic = f"{ROOT_TOPIC}/helmets/{helmet_id}/telemetry"
    client.publish(topic, json.dumps(payload))
    print(f" -> Inviata telemetria per {helmet_id}: Umidità={hum}%, Luce={lux}lux, Fall={fall}")

def resetta_pista():
    """Spegne virtualmente i caschi 02 e 03 per evitare l'effetto fantasma nei test."""
    payload_off = {"user_status": "OFFLINE"}
    client.publish(f"{ROOT_TOPIC}/helmets/helmet_sim_02/telemetry", json.dumps(payload_off))
    client.publish(f"{ROOT_TOPIC}/helmets/helmet_sim_03/telemetry", json.dumps(payload_off))
    time.sleep(0.5) # Pausa breve per permettere al server di elaborare l'eliminazione


# --- MENU INTERATTIVO ---

def menu():
    while True:
        print("\n" + "="*50)
        print(" SIMULATORE CASCHI - UNIMORE SKI IoT")
        print("="*50)
        print("1) Condizioni PERFETTE (1 Casco) -> Tornello VERDE")
        print("2) Solo NEBBIA (1 Casco) -> Tornello GIALLO (Rallentare)")
        print("3) Solo AFFOLLAMENTO (3 Caschi) -> Tornello GIALLO (Attenzione)")
        print("4) NEBBIA + AFFOLLAMENTO (3 Caschi) -> Tornello ROSSO (Chiuso)")
        print("5) CADUTA SCIATORE -> Tornello ROSSO (Danger Environment)")
        print("6) RIPRISTINA CADUTA (Tutto ok) -> Tornello VERDE (1 Casco)")
        print("7) SPEGNI IMPIANTO -> Tornello OFF")
        print("0) Esci")
        
        scelta = input("Seleziona uno scenario: ")

        if scelta == "1":
            print("\n[Scenario] Pulizia pista e invio dati SERENO...")
            resetta_pista()
            invia_telemetria("helmet_sim_01", hum=40, lux=100) # Luce bassa = sereno (tua logica)
            time.sleep(1)

        elif scelta == "2":
            print("\n[Scenario] Pulizia pista e invio dati SOLO NEBBIA...")
            resetta_pista()
            invia_telemetria("helmet_sim_01", hum=95, lux=250) # Luce > 200 = nebbia
            time.sleep(1)

        elif scelta == "3":
            print("\n[Scenario] Invio dati SOLO AFFOLLAMENTO...")
            invia_telemetria("helmet_sim_01", hum=40, lux=100, lat=44.1801)
            invia_telemetria("helmet_sim_02", hum=40, lux=100, lat=44.1802)
            invia_telemetria("helmet_sim_03", hum=40, lux=100, lat=44.1803)
            time.sleep(1)

        elif scelta == "4":
            print("\n[Scenario] Invio dati NEBBIA + AFFOLLAMENTO...")
            invia_telemetria("helmet_sim_01", hum=95, lux=250, lat=44.1801)
            invia_telemetria("helmet_sim_02", hum=95, lux=250, lat=44.1802)
            invia_telemetria("helmet_sim_03", hum=95, lux=250, lat=44.1803)
            time.sleep(1)

        elif scelta == "5":
            print("\n[Scenario] Simulazione CADUTA in corso...")
            # Simuliamo che l'unico casco sia caduto
            resetta_pista()
            invia_telemetria("helmet_sim_01", hum=40, lux=100, fall=True)
            time.sleep(1)

        elif scelta == "6":
            print("\n[Scenario] Sciatore soccorso (Caduta finita)...")
            resetta_pista()
            invia_telemetria("helmet_sim_01", hum=40, lux=100, fall=False)
            time.sleep(1)

        elif scelta == "7":
            print("\n[Scenario] Chiusura Impianto a fine giornata...")
            payload_tornello = {
                "traffic_light": "OFF",
                "display_msg": "SISTEMA SPENTO",
                "flow_rate": 0
            }
            client.publish(f"{ROOT_TOPIC}/turnstiles/gate_A/set", json.dumps(payload_tornello), retain=True)
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
(mqtt-env) (base) yarisalsi@MacBook-Air-di-Yari IoT % 
