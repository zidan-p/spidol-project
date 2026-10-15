// #include <WiFi.h>

// // ====== KONFIGURASI ======
// const char* ssid     = "Pinang Merah LT-2";
// const char* password = "Pinangmerah36";

// // IP laptop yang menjalankan `python main.py --wifi-touch-port 8090`
// // (cek dengan ipconfig di Windows atau ifconfig di Mac/Linux -- harus
// // adapter Wi-Fi yang sebenarnya, satu jaringan dengan ESP32 ini).
// // Port 8080 sengaja dihindari -- di laptop ini sudah dipakai proses lain
// // (whatsapp-bridge.exe), jadi server kita tidak bisa listen di situ.
// const char* serverIP = "192.168.110.104";
// const int   serverPort = 8090;

// // ====== PIN TOMBOL ======
// // Microswitch (mouse-click style limit switch, e.g. Omron D2F) wired
// // between GPIO5 and GND -- no signal-conditioning module like the TTP223
// // has, so GPIO5 needs its internal pull-up enabled (INPUT_PULLUP) and the
// // logic is active-LOW: the pin reads HIGH when released (pulled up) and
// // LOW when pressed (switch closes the circuit to GND).
// //
// // Dipakai sebagai Touch Signal (marker sedang menyentuh papan), BUKAN AI
// // Trigger -- kirim "1" saat ditekan (mulai menggambar) dan "0" saat
// // dilepas (berhenti menggambar), ke server/hal/providers.py's
// // WifiTouchProvider, yang membaca status ini via is_touching(). Beda
// // dengan AI Trigger (GLOSSARY.md), yang merupakan aksi sekali-tekan
// // terpisah untuk memicu analisis gambar -- bukan tombol ini.
// #define TOUCH_PIN 5

// WiFiClient client;
// bool lastState = false;  // false = released, true = pressed

// void connectToServer();  // forward declaration -- defined below, but called from setup() above it

// void setup() {
//   Serial.begin(115200);
//   pinMode(TOUCH_PIN, INPUT_PULLUP);

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

//   // Baca microswitch -- active-LOW (lihat catatan INPUT_PULLUP di atas),
//   // jadi dibalik di sini supaya sisa kode tetap bekerja dengan "true =
//   // ditekan", bukan level sinyal mentahnya.
//   bool currentState = (digitalRead(TOUCH_PIN) == LOW);

//   // Kirim hanya saat status berubah (mencegah spam)
//   if (currentState != lastState) {
//     if (currentState) {
//       client.println("1");  // Ditekan -> mulai menggambar
//       Serial.println("DITEKAN -> MENGGAMBAR");
//     } else {
//       client.println("0");  // Dilepas -> berhenti menggambar
//       Serial.println("DILEPAS -> BERHENTI");
//     }
//     lastState = currentState;
//   }

//   delay(20); // Debounce kecil
// }
