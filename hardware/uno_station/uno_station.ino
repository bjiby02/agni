// AGNI station buzzer. On a 'D' byte over USB serial: LED on, 1 s tone, LED off.
// Wire a piezo buzzer to pin 8 and GND. The onboard LED (pin 13) shows the dispatch.
const int BUZZER = 8;
const int LED = LED_BUILTIN;

void setup() {
  pinMode(LED, OUTPUT);
  pinMode(BUZZER, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  if (Serial.available() > 0 && Serial.read() == 'D') {
    digitalWrite(LED, HIGH);
    tone(BUZZER, 880, 1000);
    delay(1000);
    digitalWrite(LED, LOW);
    Serial.println("OK");
  }
}
