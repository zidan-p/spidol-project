// // ============================================
// // ESP32 CAPACITIVE TOUCH WITH LED
// // Aluminium Foil sebagai sensor sentuh
// // GPIO 4 = Touch Sensor T0
// // GPIO 2 = LED Internal ESP32 DevKit
// // ============================================

// // Wajib di-include manual -- beda dengan file .ino, PlatformIO tidak
// // otomatis menyisipkan Arduino.h ke file .cpp. Tanpa ini, Serial/delay/
// // pinMode/touchRead/dll semuanya dianggap belum dideklarasikan.
// #include <Arduino.h>

// #define TOUCH_PIN 4
// #define LED_PIN   2

// // -------------------------
// // Pengaturan
// // -------------------------

// // Threshold akan dihitung otomatis saat kalibrasi
// int threshold;

// // Berapa kali pembacaan untuk menentukan rata-rata
// const int CALIBRATION_SAMPLES = 50;

// // Jeda pembacaan sensor (ms)
// const int READ_DELAY = 100;

// // ============================================
// // FUNGSI KALIBRASI
// // ============================================

// void calibrateSensor() {
//   Serial.println();
//   Serial.println("=================================");
//   Serial.println("KALIBRASI SENSOR");
//   Serial.println("Jangan sentuh aluminium foil!");
//   Serial.println("=================================");

//   delay(3000);

//   long total = 0;


//   for (int i = 0; i < CALIBRATION_SAMPLES; i++) {
//     int value = touchRead(TOUCH_PIN);
//     total += value;
//     Serial.print("."); 
//     Serial.println(value); 
//     delay(50);
//   }

//   float baseline = (float)total / CALIBRATION_SAMPLES;

//   // Threshold diatur 80% dari baseline
//   threshold = baseline - 10;

//   Serial.println();
//   Serial.println();
//   Serial.print("Baseline : ");
//   Serial.println(baseline);
//   Serial.print("Threshold: ");
//   Serial.println(threshold);
//   Serial.println();
//   Serial.println("Kalibrasi selesai.");
//   Serial.println("Sekarang silakan sentuh foil.");
//   Serial.println();
// }

// // ============================================
// // SETUP
// // ============================================

// void setup() {
//   Serial.begin(115200);
//   delay(1000);

//   // Atur pin LED sebagai OUTPUT
//   pinMode(LED_PIN, OUTPUT);
//   digitalWrite(LED_PIN, LOW); // Pastikan LED mati saat awal

//   Serial.println();
//   Serial.println("ESP32 Capacitive Touch Sensor");
//   Serial.println("GPIO 4 / T0");
  
//   calibrateSensor();
// }

// // ============================================
// // LOOP
// // ============================================

// void loop() {
//   // Baca sensor kapasitif
//   int touchValue = touchRead(TOUCH_PIN);

//   // Tentukan status sentuhan
//   bool touching = (touchValue < threshold);

//   // Kontrol LED dan Tampilan Serial
//   if (touching) {
//     digitalWrite(LED_PIN, HIGH); // Nyalakan LED
//     Serial.print("1  -> MENYENTUH | ");
//   } else {
//     digitalWrite(LED_PIN, LOW);  // Matikan LED
//     Serial.print("0  -> TIDAK MENYENTUH | ");
//   }

//   // Tampilkan nilai mentah sensor
//   Serial.print("Touch Value: ");
//   Serial.println(touchValue);

//   delay(READ_DELAY);
// }