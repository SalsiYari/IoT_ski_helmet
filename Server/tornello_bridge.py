import paho.mqtt.client as mqtt
import serial
import json
import time
import sys

# --- SETTINGS ---
# MQTT (VPS information)
BROKER_ADDRESS = "31.14.140.180" # here VPS IP or 'yarisalsi.com' if ports are open
PORT = 1883
USER = "skier"
PASSWORD = "IoTskier1"

# SERIAL (Arduino information)
SERIAL_PORT = "COM3"                    # <--- (on MAC could be /dev/ttyACM0 )
BAUD_RATE = 9600

# TOPIC TO LISTEN
TOPIC_CMD = "unimore_ski/turnstiles/gate_A/set"
TOPIC_STATUS = "unimore_ski/turnstiles/gate_A/status"

# --- CONNESSIONE SERIALE ---
try:
    arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)                                               # waiting arduino reboot
    print(f"[SERIAL] Connected to {SERIAL_PORT}\n")
except Exception as e:
    print(f"[ERROR] Impossible to Connect to Arduino on {SERIAL_PORT}\n")
    print(e)
    sys.exit(1)

# --- CALLBACKS MQTT ---
def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[MQTT] Connected to Broker (Code: {rc})\n")
    client.subscribe(TOPIC_CMD)                                     #client --subscribe-> topic
    print(f"[MQTT] Listening on : {TOPIC_CMD}\n")

def on_message(client, userdata, msg):
    """
    Recive JSON from server --and--> it Sends formatted String to Arduino
    """
    try:
        """ msg
        is the obj that represent the MQTT message recived on the callback
        it contains:
        msg.topic | msg.payload | msg.qos | msg.retain | msg.error
        """
        payload_str = msg.payload.decode()
        print(f"[RX] Recived: {payload_str}\n")
        
        data = json.loads(payload_str)      #json to python dict
        
        # Data Extraction:
        color = data.get("traffic_light", "GREEN")   # RED, YELLOW, GREEN
        text = data.get("display_msg", "MESSAGE ERROR")   # Msg LCD. NOTE: i have 16 char on LCD
        speed = data.get("flow_rate", 0)           # 0 means stop, ms per delay

        #Mapping flow_rate (0-10) in delay milliseconds for Arduino.
        # if speed 0 -> 0 (spento)
        # if speed higer (i.e. 10) -> shorter delay (i.e. 100ms) - fast pulse
        blink_delay = 0
        if speed > 0:
            if speed == 10: blink_delay = 100
            elif speed == 2: blink_delay = 500               # fi crowded
            else: blink_delay = 1000
        
        # --- Formatting Command for Arduino ---
        # Formato: COLOR|MSG|DELAY\n
        command = f"{color}|{text}|{blink_delay}\n"
        
        # sEND via USB
        arduino.write(command.encode())
        print(f"[TX Serial] Inviato: {command.strip()}")
        
        # Publish status confirmed
        client.publish(TOPIC_STATUS, json.dumps({"status": "OK", "current_color": color}))  #python to json

    except Exception as e:
        print(f"[ERROR] Parsing/Sending: {e}")


#ONLY FOR DEBUG!!!
def debug_mode():
    """
    Modalità di debug per testare Arduino e i componenti hardware.
    Permette di inviare comandi manuali via seriale simulando gli stati del tornello.
    """
    print("\n=== DEBUG MODE ATTIVO ===")
    print("Test hardware Arduino senza MQTT")
    print("Comandi disponibili:")
    print(" 1) RED")
    print(" 2) YELLOW")
    print(" 3) GREEN")
    print(" 4) CUSTOM MESSAGE")
    print(" 5) EXIT DEBUG\n")

    while True:
        choice = input("Seleziona un comando: ").strip()

        if choice == "1":
            color = "RED"
            text = "STOP"
            delay = 0

        elif choice == "2":
            color = "YELLOW"
            text = "WAIT"
            delay = 500

        elif choice == "3":
            color = "GREEN"
            text = "GO"
            delay = 100

        elif choice == "4":
            color = input("Colore (RED/YELLOW/GREEN): ").strip().upper()
            text = input("Messaggio LCD (max 16 char): ").strip()
            speed = int(input("Flow rate (0-10): ").strip())

            # mappatura identica al tuo codice
            if speed == 0:
                delay = 0
            elif speed == 10:
                delay = 100
            elif speed == 2:
                delay = 500
            else:
                delay = 1000

        elif choice == "5":
            print("Uscita dalla modalità debug...\n")
            break

        else:
            print("Scelta non valida\n")
            continue

        # Comando formattato come nel tuo bridge
        command = f"{color}|{text}|{delay}\n"
        arduino.write(command.encode())

        print(f"[DEBUG → Arduino] Inviato: {command.strip()}")
        time.sleep(0.3)




# --- MAIN ---

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(USER, PASSWORD)


##ONLY FOR DEBUG, REMOVE IT IN TESTING ##########
if len(sys.argv) > 1 and sys.argv[1] == "debug":
    debug_mode()
    sys.exit(0)
##################################################

client.on_connect = on_connect
client.on_message = on_message

print("[LOG]--STARTING TURNSTILE'S BRIDGE--\n")
try:
    client.connect(BROKER_ADDRESS, PORT, 60)
    client.loop_forever()
except KeyboardInterrupt:
    print("\n[LOS] Closing...\n")
    arduino.close()