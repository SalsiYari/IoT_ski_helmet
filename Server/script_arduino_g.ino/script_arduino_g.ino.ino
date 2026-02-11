#include <LiquidCrystal.h>

// NOTE: GIULIA Ho rimosso SoftwareSerial perché usiamo la USB nativa (Serial)

// LED
int rosso1  = 2;
int giallo1 = 3;
int verde1  = 4;
int blu1    = 5;

// LCD (Verifica che i pin siano corretti per il tuo setup)
LiquidCrystal lcd(12, 11, 6, 7, 8, 9);

// Variabili Gestione
String inputString = "";         // Stringa per contenere i dati in arrivo
bool stringComplete = false;     // Flag per stringa completata
int bluStato = LOW;
unsigned long previousMillis = 0;
int intervalloBlu = 1000;        // 0 = spento, >0 = millisecondi

void setup() {
  pinMode(rosso1, OUTPUT);
  pinMode(giallo1, OUTPUT);
  pinMode(verde1, OUTPUT);
  pinMode(blu1, OUTPUT);

  // Test iniziale LED
  digitalWrite(rosso1, HIGH); delay(200); digitalWrite(rosso1, LOW);
  digitalWrite(giallo1, HIGH); delay(200); digitalWrite(giallo1, LOW);
  digitalWrite(verde1, HIGH); delay(200); digitalWrite(verde1, LOW);

  lcd.begin(16, 2); // Inizializza LCD 16x2
  lcd.print("SISTEMA AVVIATO");

  Serial.begin(9600); // Comunicazione via USB con il PC
  inputString.reserve(200);
}

void loop() {
  // --- VECCHIO CODICE MANUALE (COMMENTATO) ---
  /*
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.length() > 0) {
       // ... TUA VECCHIA LOGICA CHE CALCOLAVA SOGLIE ...
       // COMMENTATA PERCHÉ ORA LA LOGICA È SUL SERVER
    }
  }
  */

  // --- NUOVA LOGICA: RICEZIONE COMANDI DA PYTHON ---
  // Protocollo atteso: "COLORE|MESSAGGIO_LCD|SPEED_BLU"
  // Esempio: "RED|CHIUSO NEBBIA|0" oppure "GREEN|BENVENUTI|200"
  
  if (stringComplete) {
    parseCommand(inputString);
    // Pulisci per il prossimo comando
    inputString = "";
    stringComplete = false;
  }

  // --- GESTIONE LAMPEGGIO BLU (NON BLOCCANTE) ---
  if (intervalloBlu > 0) {
    unsigned long currentMillis = millis();
    if (currentMillis - previousMillis >= intervalloBlu) {
      previousMillis = currentMillis;
      bluStato = !bluStato;
      digitalWrite(blu1, bluStato);
    }
  } else {
    digitalWrite(blu1, LOW); // Spegni se intervallo è 0
  }
}

// Funzione chiamata automaticamente quando arrivano dati seriali
void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    inputString += inChar;
    if (inChar == '\n') {
      stringComplete = true;
    }
  }
}

void parseCommand(String data) {
  data.trim(); // Rimuove spazi e newlines
  
  // Cerchiamo i separatori "|"
  int firstPipe = data.indexOf('|');
  int secondPipe = data.indexOf('|', firstPipe + 1);

  if (firstPipe > 0 && secondPipe > 0) {
    String colorCmd = data.substring(0, firstPipe);
    String lcdMsg = data.substring(firstPipe + 1, secondPipe);
    String speedStr = data.substring(secondPipe + 1);
    
    // 1. GESTIONE LED SEMAFORO

    digitalWrite(rosso1, LOW);
    digitalWrite(giallo1, LOW);
    digitalWrite(verde1, LOW);

    if (colorCmd == "RED") digitalWrite(rosso1, HIGH);
    else if (colorCmd == "YELLOW") digitalWrite(giallo1, HIGH);
    else if (colorCmd == "GREEN") digitalWrite(verde1, HIGH);

    // 2. GESTIONE LCD
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("STATO: " + colorCmd);
    lcd.setCursor(0, 1);
    // Tronchiamo il messaggio a 16 caratteri per sicurezza
    if(lcdMsg.length() > 16) lcdMsg = lcdMsg.substring(0, 16);
    lcd.print(lcdMsg);

    // 3. GESTIONE LED BLU
    intervalloBlu = speedStr.toInt();
    
    // Feedback verso il PC
    Serial.println("ACK: " + colorCmd); 
  }
}