import paho.mqtt.client as mqtt
import serial
import json
import time
import sys

# --- SETTINGS ---
BROKER_ADDRESS = "31.14.140.180" 
PORT = 1883
USER = "skier"
PASSWORD = "IoTskier1" 

GATE_ID = "gate_A"
TOPIC_CMD = f"unimore_ski/turnstiles/{GATE_ID}/set"

# SERIAL PORT 
SERIAL_PORT = 'COM3' 
BAUD_RATE = 9600

# --- sERIAL SETUP ---
'''
when python opens a serial port on windows, the OS send 
automatically a signal on pin DTR and RTS. since DTR is automatically connected to RESET by tefault 
it restarts evry time i connect the bridge blocking communication for a while.
'''
try:
    arduino = serial.Serial()
    arduino.port = SERIAL_PORT
    arduino.baudrate = BAUD_RATE
    arduino.timeout = 1
    arduino.setDTR(False)                                   #win stability (don't send signal)
    arduino.setRTS(False)                                   #win stability
    arduino.open()
    
    time.sleep(2) 
    print(f"[HW] Arduino is CONNECTED on serial port: {SERIAL_PORT}")
except Exception as e:
    print(f"[ERROR] Arduino not find: {e}")
    sys.exit()


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[NET] Connected! listening on : {TOPIC_CMD}")
        client.subscribe(TOPIC_CMD)
    else:
        print(f"[NET] Errore connessione: {rc}")


def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode()                              #decoding bytes into mqtt string
        print(f"\n[RX] JSON recived: \n[RX]{payload_str}")
        
        dati = json.loads(payload_str)                                  #takes data into dictionary
        
        # 1. Extracting Data From Twin:
        traffic = dati.get("traffic_light", "RED")                      # RED, GREEN, YELLOW
        display = dati.get("display_msg", "Error")                      #default is needed  if keys is not found
        flow = dati.get("flow_rate", 0) # 0, 2, 10...
        
        # 2. logic Conversion (Flow -> Millisecondi Lampeggio)
        # if flow  0 -> LED spento (0 ms)
        # if flow low   (2) -> Lampeggio lento (10000 ms)
        # if flow hight (10) -> Lampeggio veloce (1000 ms)
        blue_speed = 0
        if flow == 0:
            blue_speed = 0
        elif flow < 5:
            blue_speed = 5000 # Lento                500
        else:
            blue_speed = 1000 # Veloce               100
            
        # 3. Making String for Arduino Protocol:
        # Format is : "COLOR|MESSAGE|VELOCITY_OF_BLUE\n"
        comando_seriale = f"{traffic}|{display}|{blue_speed}\n"
        
        # 4. SENDING
        arduino.write(comando_seriale.encode())
        
        print(f"\n[TX ARDUINO] Sending: \n[TX ARDUINO]{comando_seriale.strip()}")
            
    except Exception as e:
        print(f"[ERROR] {e}")

# --- MAIN ---
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(USER, PASSWORD)
client.on_connect = on_connect
client.on_message = on_message

print("--------------------------------\n")
print("Starting Turnstile Bridge...\n")
client.connect(BROKER_ADDRESS, PORT, 60)

# -- KEYBOARD INTERRUPT ---
try:
    client.loop_forever()                            # this stops the script to keep it in "listening mode"
except KeyboardInterrupt:
    print("--------------------------------\n")
    print("\n[SYSTEM] Closing The Bridge ....\n")    #ctrl+c
    
finally:
    print("[SYSTEM] Disconnecting from broker MQTT...\n")
    client.disconnect()
    print("-> Done. \n")
    
    if 'arduino' in locals() and arduino.is_open:
        print("[SYSTEM] Closing serial port...")
        arduino.close()
        print("-> Done. \n")
        
    print("[SYSTEM] Bridge Switched Off correctly.")
    print("\n")
    sys.exit(0)
