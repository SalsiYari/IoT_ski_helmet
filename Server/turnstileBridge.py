#include <LiquidCrystal.h>

// --- PIN SETTINGS ---
int red1  = 2;
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
  pinMode(red1, OUTPUT);
  pinMode(giallo1, OUTPUT);
  pinMode(verde1, OUTPUT);
  pinMode(blu1, OUTPUT);

  // Test iniziale luci
  digitalWrite(red1, HIGH); delay(200); digitalWrite(red1, LOW);
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
  
  while (Serial.available()) {                // is there any byte to be read?
    char inChar = (char)Serial.read();
    
    if (inChar == '\n') {                   //end of string command
      parseCommand(inputString);            //
      inputString = ""; // Reset stringa
    } else {
      inputString += inChar;                // adding chars
    }
  }

  // 2. managing blu lithning  (blinking without delay ---> not blocking)
  if (intervalloBlu > 0) {
    unsigned long currentMillis = millis();                         //millis starts from zero when i switch on the arduino
    if (currentMillis - previousMillis >= intervalloBlu) {          //is passed enought time from last time we changed led?
      previousMillis = currentMillis;
      bluStato = !bluStato;
      digitalWrite(blu1, bluStato);
    }
  } else {
    digitalWrite(blu1, LOW);                                        // switch off in interval is zero
  }
}

//  Parsing Function:  "COLOR|MESSAGE|BLU_VELOCITY"
void parseCommand(String data) {
  data.trim();          // remove white spaces
  
  int firstPipe = data.indexOf('|');
  int secondPipe = data.indexOf('|', firstPipe + 1);

  if (firstPipe > 0 && secondPipe > 0) {
    String colorCmd = data.substring(0, firstPipe);               //extract everything before fisrt pipe (color)
    String lcdMsg = data.substring(firstPipe + 1, secondPipe);    //extraction message
    String speedStr = data.substring(secondPipe + 1);             //velocity
    
    // --- AZIONI ---

    // A. Traffic Lighta
    digitalWrite(red1, LOW);
    digitalWrite(giallo1, LOW);
    digitalWrite(verde1, LOW);

    if (colorCmd == "RED") digitalWrite(red1, HIGH);
    else if (colorCmd == "YELLOW") digitalWrite(giallo1, HIGH);
    else if (colorCmd == "GREEN") digitalWrite(verde1, HIGH);

    // B. LCD
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("STATE: " + colorCmd);
    lcd.setCursor(0, 1);
    //i need to "cut " the message over 16 char to avoid grapghics error
    if(lcdMsg.length() > 16) lcdMsg = lcdMsg.substring(0, 16);
    lcd.print(lcdMsg);

    // C. Led Blu
    intervalloBlu = speedStr.toInt();
    
    // Debug verso PC
    Serial.println("ACK: OK"); 
  }
}
