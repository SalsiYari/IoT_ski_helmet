# this file represent the bridge that connects Arduino to MQTT broker on VPS


import paho.mqtt.client as mqtt
import serial
import json
import time
import sys

# --- CONFIGURAZIONE ---
BROKER_ADDRESS = "31.14.140.180" 
PORT = 1883
USER = "skier"
PASSWORD = "IoTskier1" 

GATE_ID = "gate_A"
TOPIC_CMD = f"unimore_ski/turnstiles/{GATE_ID}/set"

# Porta Seriale (Verifica su Arduino IDE quale porta usa!)
SERIAL_PORT = 'COM3' 
BAUD_RATE = 9600

# --- SETUP SERIALE ---
try:
    # Aggiunti dtr=False e rts=False per stabilità su Windows
    arduino = serial.Serial()
    arduino.port = SERIAL_PORT
    arduino.baudrate = BAUD_RATE
    arduino.timeout = 1
    arduino.setDTR(False)
    arduino.setRTS(False)
    arduino.open()
    
    time.sleep(2) 
    print(f"[HW] Arduino connesso su {SERIAL_PORT}")
except Exception as e:
    print(f"[ERRORE] Arduino non trovato: {e}")
    sys.exit()

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[NET] Connesso! Ascolto su: {TOPIC_CMD}")
        client.subscribe(TOPIC_CMD)
    else:
        print(f"[NET] Errore connessione: {rc}")

def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode()
        print(f"\n[RX] JSON Ricevuto: {payload_str}")
        
        dati = json.loads(payload_str)
        
        # 1. Estrazione dati dal Twin
        traffic = dati.get("traffic_light", "RED") # RED, GREEN, YELLOW
        display = dati.get("display_msg", "Errore")
        flow = dati.get("flow_rate", 0) # 0, 2, 10...
        
        # 2. Conversione Logica (Flow -> Millisecondi Lampeggio)
        # Se flow è 0 -> LED spento (0 ms)
        # Se flow è basso (2) -> Lampeggio lento (500 ms)
        # Se flow è alto (10) -> Lampeggio veloce (100 ms)
        blue_speed = 0
        if flow == 0:
            blue_speed = 0
        elif flow < 5:
            blue_speed = 500 # Lento
        else:
            blue_speed = 100 # Veloce
            
        # 3. Costruzione Stringa Protocollo per Arduino
        # Formato: "COLORE|MESSAGGIO|VELOCITA_BLU\n"
        comando_seriale = f"{traffic}|{display}|{blue_speed}\n"
        
        # 4. Invio
        arduino.write(comando_seriale.encode())
        print(f"[TX ARDUINO] Inviato: {comando_seriale.strip()}")
            
    except Exception as e:
        print(f"[ERRORE] {e}")

# --- MAIN ---
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(USER, PASSWORD)
client.on_connect = on_connect
client.on_message = on_message

print("Avvio Bridge Tornello...")
client.connect(BROKER_ADDRESS, PORT, 60)
client.loop_forever()
