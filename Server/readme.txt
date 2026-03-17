up to this point this reference is for dev-porpose:
https://www.notion.so/IoT-informazioni-x-Giulia-e-Leti-2f40cb40bdcb80219f92e041aac24a41?source=copy_link

---------------------------------------------------------
INFRASTRUCTURE SETUP & DEPLOYMENT COMMANDS (UBUNTU VPS)
---------------------------------------------------------

1. INSTALLAZIONE E CONFIGURAZIONE MOSQUITTO (MQTT BROKER)
---------------------------------------------------------
# Installazione pacchetti base
sudo apt update
sudo apt install mosquitto mosquitto-clients -y

# Creazione dell'utente MQTT protetto da password
sudo mosquitto_passwd -c /etc/mosquitto/passwd skier
# (Password inserita: IoTskier1)

# Configurazione del file mosquitto.conf
# È necessario assicurarsi che contenga le seguenti righe:
#   listener 1883
#   allow_anonymous false
#   password_file /etc/mosquitto/passwd

# Riavvio per applicare le modifiche
sudo systemctl restart mosquitto
sudo systemctl enable mosquitto

2. CONFIGURAZIONE DEL FIREWALL (UFW)
---------------------------------------------------------
# Apertura porta per la comunicazione MQTT dai caschi
sudo ufw allow 1883
# Apertura porta per la visualizzazione della Dashboard Web
sudo ufw allow 8080
sudo ufw reload

3. SETUP AMBIENTE PYTHON E LIBRERIE
---------------------------------------------------------
# Creazione ambiente virtuale isolato
sudo apt install python3-venv -y
python3 -m venv venvIot
source venvIot/bin/activate

# Installazione dipendenze
pip install paho-mqtt
pip install flask

4. ESECUZIONE COME SERVIZI IN BACKGROUND (SYSTEMD)
---------------------------------------------------------
# I file .service (salvati nella cartella infrastructure_setup)
# vanno copiati in /etc/systemd/system/
# Dopodiché si abilitano con:

sudo systemctl daemon-reload
sudo systemctl start digital-twin
sudo systemctl enable digital-twin

sudo systemctl start iot-web
sudo systemctl enable iot-web
