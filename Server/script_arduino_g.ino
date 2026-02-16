#include <LiquidCrystal.h>

// --- CONFIGURAZIONE PIN ---
int rosso1  = 2;
int giallo1 = 3;
int verde1  = 4;
int blu1    = 5;

// LCD (RS, E, D4, D5, D6, D7)
LiquidCrystal lcd(12, 11, 6, 7, 8, 9);

// Variabili Gestione
String inputString = "";         
int bluStato = LOW;
unsigned long previousMillis = 0;
int intervalloBlu = 0;  // 0 = spento

void setup() {
  pinMode(rosso1, OUTPUT);
  pinMode(giallo1, OUTPUT);
  pinMode(verde1, OUTPUT);
  pinMode(blu1, OUTPUT);

  // Test iniziale luci
  digitalWrite(rosso1, HIGH); delay(200); digitalWrite(rosso1, LOW);
  digitalWrite(giallo1, HIGH); delay(200); digitalWrite(giallo1, LOW);
  digitalWrite(verde1, HIGH); delay(200); digitalWrite(verde1, LOW);

  lcd.begin(16, 2);
  lcd.print("STARTING SYSTEM...");
  lcd.setCursor(0, 1);
  lcd.print("WAITING DATAs...");

  Serial.begin(9600); 
  inputString.reserve(200);
}

void loop() {
  // 1. LETTURA SERIALE (Compatibile Arduino R4)
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    
    // Se arriva il comando di fine riga, eseguiamo
    if (inChar == '\n') {
      parseCommand(inputString);
      inputString = ""; // Reset stringa
    } else {
      inputString += inChar; // Accumula caratteri
    }
  }

  // 2. GESTIONE LAMPEGGIO BLU (Non bloccante)
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

// Funzione di Parsing: "COLORE|MESSAGGIO|VELOCITA_BLU"
void parseCommand(String data) {
  data.trim(); // Rimuove spazi vuoti
  
  int firstPipe = data.indexOf('|');
  int secondPipe = data.indexOf('|', firstPipe + 1);

  if (firstPipe > 0 && secondPipe > 0) {
    String colorCmd = data.substring(0, firstPipe);
    String lcdMsg = data.substring(firstPipe + 1, secondPipe);
    String speedStr = data.substring(secondPipe + 1);
    
    // --- AZIONI ---

    // A. Semaforo
    digitalWrite(rosso1, LOW);
    digitalWrite(giallo1, LOW);
    digitalWrite(verde1, LOW);

    if (colorCmd == "RED") digitalWrite(rosso1, HIGH);
    else if (colorCmd == "YELLOW") digitalWrite(giallo1, HIGH);
    else if (colorCmd == "GREEN") digitalWrite(verde1, HIGH);

    // B. LCD
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("STATO: " + colorCmd);
    lcd.setCursor(0, 1);
    // Tronca messaggio se troppo lungo per evitare errori grafici
    if(lcdMsg.length() > 16) lcdMsg = lcdMsg.substring(0, 16);
    lcd.print(lcdMsg);

    // C. Led Blu
    intervalloBlu = speedStr.toInt();
    
    // Debug verso PC
    Serial.println("ACK: OK"); 
  }
}
