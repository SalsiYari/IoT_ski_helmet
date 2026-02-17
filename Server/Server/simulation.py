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

def invia_telemetria(helmet_id, pista, hum, lux, lat=44.18, lon=10.70, fall=False):
    """Crea e invia un pacchetto JSON identico a quello del casco reale, includendo la pista"""
    payload = {
        "helmet_id": helmet_id,
        "piste": pista,            # <--- NUOVO: La pista su cui si trova il casco (es. "P1")
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
    print(f" -> Inviata telemetria {helmet_id} su [{pista}]: Lux={lux}, Fall={fall}")

def resetta_pista():
    """Spegne virtualmente i caschi per evitare l'effetto fantasma nei test."""
    payload_off = {"user_status": "OFFLINE"}
    # Spegniamo fino a 5 caschi per sicurezza, in base agli scenari
    for i in range(1, 6):
        client.publish(f"{ROOT_TOPIC}/helmets/helmet_sim_{i:02d}/telemetry", json.dumps(payload_off))
    time.sleep(0.5) 


# --- MENU INTERATTIVO ---

def menu():
    while True:
        print("\n" + "="*60)
        print(" SIMULATORE MULTI-PISTA - UNIMORE SKI IoT")
        print("="*60)
        print("1) Condizioni PERFETTE ovunque -> Tutti i Tornelli VERDI")
        print("2) NEBBIA su pista P5 -> A1 Rallenta (GIALLO), Altri VERDI")
        print("3) AFFOLLAMENTO su P2 -> A1 e A2 Rallentano (GIALLO), Altri VERDI")
        print("4) CADUTA su P4 -> A4 Bloccato (ROSSO), Altri VERDI")
        print("5) MAX EMERGENZA (Caduta su P1) -> TUTTI i tornelli Bloccati (ROSSI)")
        print("6) RIPRISTINA PISTE (Tutto ok su P1) -> Tutti i Tornelli VERDI")
        print("7) SPEGNI IMPIANTO -> Tutti i Tornelli OFF")
        print("0) Esci")
        
        scelta = input("Seleziona uno scenario: ")

        if scelta == "1":
            print("\n[Scenario] Pulizia piste e invio dati SERENO su varie piste...")
            resetta_pista()
            invia_telemetria("helmet_sim_01", "P1", hum=40, lux=100) 
            invia_telemetria("helmet_sim_02", "P3", hum=40, lux=100) 
            invia_telemetria("helmet_sim_03", "P4", hum=40, lux=100) 
            time.sleep(1)

        elif scelta == "2":
            print("\n[Scenario] NEBBIA solo su pista P5 (influenza solo A1)...")
            resetta_pista()
            # Mettiamo caschi sereni in giro per il resort
            invia_telemetria("helmet_sim_01", "P3", hum=40, lux=100)
            invia_telemetria("helmet_sim_02", "P4", hum=40, lux=100)
            # Mettiamo un casco nella nebbia su P5
            invia_telemetria("helmet_sim_03", "P5", hum=95, lux=250) 
            time.sleep(1)

        elif scelta == "3":
            print("\n[Scenario] AFFOLLAMENTO su P2 (influenza A1 e A2)...")
            resetta_pista()
            # Mettiamo 3 caschi su P2 per superare la SOGLIA_AFFOLLAMENTO
            invia_telemetria("helmet_sim_01", "P2", hum=40, lux=100, lat=44.1801)
            invia_telemetria("helmet_sim_02", "P2", hum=40, lux=100, lat=44.1802)
            invia_telemetria("helmet_sim_03", "P2", hum=40, lux=100, lat=44.1803)
            # Mettiamo 1 casco tranquillo su P4
            invia_telemetria("helmet_sim_04", "P4", hum=40, lux=100)
            time.sleep(1)

        elif scelta == "4":
            print("\n[Scenario] CADUTA su P4 (influenza solo A4)...")
            resetta_pista()
            # Casco sereno su P1
            invia_telemetria("helmet_sim_01", "P1", hum=40, lux=100)
            # Casco caduto su P4
            invia_telemetria("helmet_sim_02", "P4", hum=40, lux=100, fall=True)
            time.sleep(1)

        elif scelta == "5":
            print("\n[Scenario] CADUTA su P1 (Topologia Base: blocca tutto)...")
            resetta_pista()
            # P1 è la pista che porta a valle, se cade qualcuno lì, tutti gli impianti
            # che portano in quota (A1, A2, A3, A4) devono fermarsi come da tue regole.
            invia_telemetria("helmet_sim_01", "P1", hum=40, lux=100, fall=True)
            time.sleep(1)

        elif scelta == "6":
            print("\n[Scenario] Soccorso avvenuto. Ripristino sereno su P1...")
            resetta_pista()
            invia_telemetria("helmet_sim_01", "P1", hum=40, lux=100, fall=False)
            time.sleep(1)

        elif scelta == "7":
            print("\n[Scenario] Chiusura Impianto a fine giornata...")
            payload_tornello = {
                "traffic_light": "OFF",
                "display_msg": "SISTEMA SPENTO",
                "flow_rate": 0
            }
            # Spegniamo tutti e 4 gli impianti
            for gate in ["A1", "A2", "A3", "A4"]:
                client.publish(f"{ROOT_TOPIC}/turnstiles/{gate}/set", json.dumps(payload_tornello), retain=True)
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
