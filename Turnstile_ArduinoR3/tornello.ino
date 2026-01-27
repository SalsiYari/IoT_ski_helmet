#include <LiquidCrystal.h>
#include <SoftwareSerial.h>

// LED
int rosso1  = 2;
int giallo1 = 3;
int verde1  = 4;
int blu1    = 5;

// Bluetooth
SoftwareSerial BT(A0, A1);

// LCD
LiquidCrystal lcd(12, 11, 6, 7, 8, 9);

// Variabili
int persone = -1;                 // valore iniziale (nessun LED)
unsigned long previousMillis = 0;
int bluStato = LOW;
int intervalloBlu = 1000;

void setup() {
  pinMode(rosso1, OUTPUT);
  pinMode(giallo1, OUTPUT);
  pinMode(verde1, OUTPUT);
  pinMode(blu1, OUTPUT);

  digitalWrite(rosso1, LOW);
  digitalWrite(giallo1, LOW);
  digitalWrite(verde1, LOW);
  digitalWrite(blu1, LOW);

  Serial.begin(9600);
  BT.begin(9600);

  Serial.setTimeout(10000);   // evita parse automatici

  Serial.println("Pronto: PC <-> Arduino <-> Bluetooth");
  Serial.println("Inserisci il numero di persone:");
}

void loop() {

  /* ----------- LETTURA NUMERO DA SERIAL ----------- */
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();

    if (input.length() > 0) {
      int nuovoValore = input.toInt();

      // aggiorna solo se il valore cambia
      if (nuovoValore != persone && nuovoValore >= 0) {
        persone = nuovoValore;

        // spegne LED principali
        digitalWrite(rosso1, LOW);
        digitalWrite(giallo1, LOW);
        digitalWrite(verde1, LOW);

        // pulisce LCD riga 2
        lcd.setCursor(0, 1);
        lcd.print("                ");
        lcd.setCursor(0, 1);

        // logica LED + LCD
        if (persone <= 5) {
          digitalWrite(verde1, HIGH);
          lcd.print("LIBERO");
          intervalloBlu = 250;
          Serial.println("VERDE - LIBERO");
        }
        else if (persone <= 10) {
          digitalWrite(giallo1, HIGH);
          lcd.print("QUASI PIENO");
          intervalloBlu = 500;
          Serial.println("GIALLO - QUASI PIENO");
        }
        else {
          digitalWrite(rosso1, HIGH);
          lcd.print("AL COMPLETO");
          intervalloBlu = 1000;
          Serial.println("ROSSO - AL COMPLETO");
        }
      }
    }
  }

  /* ----------- LAMPEGGIO LED BLU (NON BLOCCANTE) ----------- */
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= intervalloBlu) {
    previousMillis = currentMillis;
    bluStato = !bluStato;
    digitalWrite(blu1, bluStato);
  }

  /* ----------- PASSAGGIO DATI BLUETOOTH -> SERIAL ----------- */
  if (BT.available()) {
    char c = BT.read();
    Serial.write(c);
  }
}
