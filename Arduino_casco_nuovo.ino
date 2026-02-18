#include "DHT.h"
#include <Arduino_Modulino.h>
#include <ArduinoBLE.h>
#include <math.h>

ModulinoMovement movement;

/* ---------- SENSORI ---------- */
#define DHTPIN 2
#define DHTTYPE DHT11
#define LDR_PIN A0

DHT dht(DHTPIN, DHTTYPE);

/* ---------- ATTUATORI ---------- */
int buzzer = 9;
int led = 7;          // LED CADUTA
int sogliaLuce = 150;

/* ---------- BLE ---------- */
// UUID Standard (minuscoli per compatibilità)
BLEService infoService("180a");

// DEFINIZIONE PACCHETTO BINARIO (13 Bytes totali) per inviarli correttsmente al bridge
// __attribute__((packed)) dice al compilatore di non aggiungere spazi vuoti tra i byte
struct __attribute__((packed)) CompactPacket {
  int16_t accX;   // 2 bytes (valore * 100)
  int16_t accY;   // 2 bytes (valore * 100)
  int16_t accZ;   // 2 bytes (valore * 100)
  int16_t temp;   // 2 bytes (valore * 10)
  uint8_t hum;    // 1 byte  (intero)
  uint16_t lux;   // 2 bytes (intero)
  uint8_t fall;   // 1 byte  (bool: 1 o 0)
};

// Caratteristica dimensionata esattamente sulla struct
BLECharacteristic infoChar("2a57", BLERead | BLENotify, sizeof(CompactPacket));

bool isConnected = false;

/* ---------- MOVIMENTO ---------- */
float x, y, z;
bool inCaduta = false;

// Variabili per l'allarme prolungato (Non bloccante)
unsigned long fallTimer = 0;
bool allarmeAttivo = false;

/* soglie caduta (in g) */
#define FREE_FALL 0.6
#define IMPACT    1.2

// Timer per invio dati (senza bloccare il loop)
unsigned long previousMillis = 0;
const long interval = 200; // Invia dati ogni 200ms (5 volte al secondo)

void setup() {
  Serial.begin(9600);
  Serial.println("Avvio sensori...");

  dht.begin();
  Modulino.begin();
  movement.begin();

  pinMode(buzzer, OUTPUT);
  pinMode(led, OUTPUT);
  digitalWrite(led, LOW);

  /* ---------- BLE ---------- */
  if (!BLE.begin()) {
    Serial.println("Errore avvio BLE");
    while (1);
  }

  // Nome che l'app Flutter cercherà
  BLE.setLocalName("UNO_R4_BLE");
  
  BLE.setAdvertisedService(infoService);
  infoService.addCharacteristic(infoChar);
  BLE.addService(infoService);
  
  BLE.advertise();

  Serial.println("BLE pronto, in attesa di connessione...");
}

void loop() {
  // Mantiene vivo il BLE
  BLE.poll();

  /* ---------- LETTURA SENSORI ---------- */
  // Leggere il DHT è lento, se rallenta troppo il loop leggere meno spesso
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();
  int luce = analogRead(LDR_PIN);

  // Gestione errore sensore (mettiamo 0 per evitare crash nel pacchetto)
  if (isnan(humidity) || isnan(temperature)) {
    Serial.println("Errore DHT11");
    humidity = 0;
    temperature = 0;
  }

  /* ---------- MOVIMENTO ---------- */
  movement.update();
  x = movement.getX();
  y = movement.getY();
  z = movement.getZ();

  float accTot = sqrt(x*x + y*y + z*z);

  /* ---------- LOGICA LOCALE (NEBBIA/LUCE) ---------- */
  bool buio = (luce > sogliaLuce);

  if (buio && temperature < 10 && humidity > 85) {
     // Condizione Nebbia
     digitalWrite(led, HIGH);
  } else {
     // Condizione Normale (se non c'è allarme caduta in corso)
     if (!allarmeAttivo) digitalWrite(led, LOW);
  }

  /* ---------- RILEVAMENTO CADUTA ---------- */
  if (accTot < FREE_FALL) {
    inCaduta = true;
  }

  if (inCaduta && accTot > IMPACT) {
    Serial.println("🚨 CADUTA RILEVATA!");
    
    // Attiviamo lo stato di allarme senza bloccare il codice
    allarmeAttivo = true;
    fallTimer = millis(); 
    
    digitalWrite(led, HIGH);
    tone(buzzer, 1000);
    
    inCaduta = false; // Resettiamo la variabile di trigger meccanico
  }

  // Se l'allarme è attivo da più di 3 secondi, lo spegniamo
  if (allarmeAttivo && (millis() - fallTimer >= 3000)) {
    allarmeAttivo = false;
    digitalWrite(led, LOW);
    noTone(buzzer);
  }

  /* ---------- INVIO DATI BLE (Non-Bloccante) ---------- */
  BLEDevice central = BLE.central();
  
  if (central) {
    if (!isConnected) {
      isConnected = true;
      Serial.print("Connesso a: ");
      Serial.println(central.address());
    }

    // Usiamo millis() invece di delay() per gestire la frequenza di invio
    unsigned long currentMillis = millis();
    if (currentMillis - previousMillis >= interval) {
      previousMillis = currentMillis;

      // 1. Creiamo il pacchetto
      CompactPacket packet;

      // 2. Riempiamo i dati convertendo i float in int (Fixed Point)
      packet.accX = (int16_t)(x * 100); 
      packet.accY = (int16_t)(y * 100);
      packet.accZ = (int16_t)(z * 100);
      
      packet.temp = (int16_t)(temperature * 10);
      packet.hum  = (uint8_t)humidity;
      packet.lux  = (uint16_t)luce;
      
      // Convertiamo bool in uint8 (1 o 0). Usiamo allarmeAttivo per mantenere lo stato per 3 secondi.
      packet.fall = allarmeAttivo ? 1 : 0;

      // 3. Inviamo i byte grezzi
      infoChar.writeValue((void*)&packet, sizeof(packet));
    }

  } else {
    if (isConnected) {
      isConnected = false;
      Serial.println("Disconnesso");
    }
  }
}
