// #include <WiFi.h>

// // ====== KONFIGURASI ======
// const char* ssid     = "wifi testing";
// const char* password = "ini password wifi";

// // Ganti dengan IP laptop kamu (cek dengan ipconfig di Windows atau ifconfig di Mac/Linux)
// const char* serverIP = "10.178.81.149";
// const int   serverPort = 8080;

// // ====== PIN SENSOR ======
// #define TOUCH_PIN 5  // GPIO5 terhubung ke OUT modul TTP223

// WiFiClient client;
// bool lastState = LOW;

// void setup() {
//   Serial.begin(115200);
//   pinMode(TOUCH_PIN, INPUT);
  
//   // Sambung ke WiFi
//   Serial.print("Menghubungkan ke WiFi...");
//   WiFi.begin(ssid, password);
//   while (WiFi.status() != WL_CONNECTED) {
//     delay(500);
//     Serial.print(".");
//   }
//   Serial.println("\nWiFi terhubung!");
//   Serial.print("IP ESP32: ");
//   Serial.println(WiFi.localIP());
  
//   // Sambung ke server laptop
//   connectToServer();
// }

// void connectToServer() {
//   Serial.print("Menghubungkan ke server laptop...");
//   if (client.connect(serverIP, serverPort)) {
//     Serial.println("Terhubung!");
//   } else {
//     Serial.println("Gagal. Coba lagi nanti.");
//   }
// }

// void loop() {
//   // Jika koneksi terputus, coba sambung ulang
//   if (!client.connected()) {
//     connectToServer();
//     delay(1000);
//     return;
//   }
  
//   // Baca sensor sentuh
//   bool currentState = digitalRead(TOUCH_PIN);
  
//   // Kirim hanya saat status berubah (mencegah spam)
//   if (currentState != lastState) {
//     if (currentState == HIGH) {
//       client.println("1");  // Sentuh → mulai menggambar
//       Serial.println("SENTUH → MENGGAMBAR");
//     } else {
//       client.println("0");  // Lepas → berhenti menggambar
//       Serial.println("LEPAS → BERHENTI");
//     }
//     lastState = currentState;
//   }
  
//   delay(20); // Debounce kecil
// }