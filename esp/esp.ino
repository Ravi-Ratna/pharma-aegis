/*
  ESP32 Sensors:
  MQ-135 (GPIO34 - Analog)
  Fire Sensor (GPIO27 - Digital)
  MPU6050 (I2C: SDA=21, SCL=22)

  Output (every 1 sec):
  {"air":120,"fire":0,"vibration":0.03}
*/

#include <Wire.h>
#include <math.h>

// Pins
const int MQ_PIN = 34;
const int FIRE_PIN = 27;
const uint8_t MPU_ADDR = 0x68;

// MPU Setup
void setupMPU() {
  Wire.begin(21, 22);  // SDA, SCL
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B); // Power register
  Wire.write(0);    // Wake up MPU6050
  Wire.endTransmission();
}

// Read accelerometer
void readAccel(float &ax, float &ay, float &az) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  Wire.endTransmission(false);

  Wire.requestFrom(MPU_ADDR, (uint8_t)6);

  if (Wire.available() >= 6) {
    int16_t raw_ax = (Wire.read() << 8) | Wire.read();
    int16_t raw_ay = (Wire.read() << 8) | Wire.read();
    int16_t raw_az = (Wire.read() << 8) | Wire.read();

    ax = raw_ax / 16384.0;
    ay = raw_ay / 16384.0;
    az = raw_az / 16384.0;
  } else {
    ax = ay = az = 0;
  }
}

void setup() {
  Serial.begin(115200);
  delay(5000);
  Serial.println("READY"); 
  Serial.println("ESP32 SENSOR SYSTEM STARTED");

  // ADC setup
  analogReadResolution(12);
  analogSetPinAttenuation(MQ_PIN, ADC_11db);

  pinMode(FIRE_PIN, INPUT);

  setupMPU();
}

void loop() {

  // 🔹 Read MQ-135
  int air = analogRead(MQ_PIN);

  // 🔹 Read Fire Sensor
  int fire_raw = digitalRead(FIRE_PIN);
  int fire = (fire_raw == HIGH) ? 1 : 0;

  // 🔹 Read MPU6050
  float ax, ay, az;
  readAccel(ax, ay, az);

  float vibration = sqrt(ax * ax + ay * ay + az * az);

  // 🔥 SEND CLEAN JSON (IMPORTANT)
  Serial.print("{\"air\":");
  Serial.print(air);
  Serial.print(",\"fire\":");
  Serial.print(fire);
  Serial.print(",\"vibration\":");
  Serial.print(vibration, 2);
  Serial.println("}");

  delay(1000);
}