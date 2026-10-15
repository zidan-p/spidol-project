#include "BluetoothSerial.h"

// Cek apakah Bluetooth aktif di konfigurasi ESP32
#if !defined(CONFIG_BT_ENABLED) || !defined(CONFIG_BLUEDROID_ENABLED)
#error Bluetooth is not enabled! Please run make menuconfig to enable it
#endif

BluetoothSerial SerialBT;

// ====== KONFIGURASI HARDWARE ======
#define SWITCH_PIN 18  // Pin Microswitch (COM ke GND, NO ke GPIO 18)
#define LED_PIN    2   // LED Indikator Onboard

bool lastState = false; // Menyimpan status sakelar sebelumnya

void setup() {
  Serial.begin(115200);

  // 1. Inisialisasi Pin Microswitch & LED
  pinMode(SWITCH_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // 2. Inisialisasi Bluetooth dengan nama "SpidolPintar_BT"
  SerialBT.begin("SpidolPintar_BT"); 
  Serial.println("\nBluetooth Siap! Silakan pair dengan nama 'SpidolPintar_BT'.");
}

void loop() {
  // 1. Membaca status Microswitch (LOW saat tertekan/tersambung ke GND)
  int switchState = digitalRead(SWITCH_PIN);
  
  // Ubah logika: true saat sakelar ditekan ke tembok (LOW)
  bool currentState = (switchState == LOW);

  // 2. Kirim data via Bluetooth HANYA saat ada perubahan status (Edge Detection)
  if (currentState != lastState) {
    if (currentState) {
      digitalWrite(LED_PIN, HIGH);   // Nyalakan LED Indikator
      SerialBT.println("1");         // Kirim "1" via Bluetooth
      Serial.println("1 -> MENYENTUH TEMBOK (Kirim '1' via BT)");
    } else {
      digitalWrite(LED_PIN, LOW);    // Matikan LED Indikator
      SerialBT.println("0");         // Kirim "0" via Bluetooth
      Serial.println("0 -> DI UDARA (Kirim '0' via BT)");
    }
    lastState = currentState; // Simpan status terbaru
  }

  delay(20); // Delay debounce sederhana
}