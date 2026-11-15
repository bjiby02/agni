/*
  AGNI station light for SanD Hacks demo.
  Listens on USB serial 9600 for lines like D42\\n then buzzes + lights the LED.
*/

const int LED_PIN = 13;
const int BUZZER_PIN = 8;

String buffer;

void setup() {
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  Serial.begin(9600);
}

void pulseStation() {
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_PIN, HIGH);
    tone(BUZZER_PIN, 880, 120);
    delay(160);
    digitalWrite(LED_PIN, LOW);
    delay(80);
  }
  noTone(BUZZER_PIN);
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (buffer.length() >= 2 && buffer.charAt(0) == 'D') {
        pulseStation();
        Serial.println("OK");
      }
      buffer = "";
    } else if (buffer.length() < 16) {
      buffer += c;
    }
  }
}
