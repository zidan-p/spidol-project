// #include <NimBLEDevice.h>

// // ====== BLE GATT ======
// // Nama device dan UUID di bawah ini HARUS sama persis dengan
// // server/main.py's DEVICE_NAME / BLE_TOUCH_CHAR_UUID -- server mencari
// // device dengan nama ini, lalu subscribe ke characteristic ini lewat
// // BleTouchProvider.
// //
// // Board ini cuma punya satu microswitch (Touch Signal) -- belum ada
// // tombol fisik buat AI Trigger, jadi characteristic-nya sengaja tidak
// // dibuat di sini sama sekali. BleTouchProvider di server tetap aman
// // subscribe ke device ini walau characteristic AI Trigger-nya tidak ada
// // (lihat connect()-nya di server/hal/providers.py) -- Touch Signal tetap
// // jalan normal, cuma AI Trigger yang tidak pernah terpicu dari device ini.
// #define DEVICE_NAME           "SPIDOL_Stylus"
// #define SERVICE_UUID          "a1b2c3d4-0000-1000-8000-00805f9b34fb"
// #define TOUCH_CHAR_UUID       "a1b2c3d4-0001-1000-8000-00805f9b34fb"

// // ====== PIN TOMBOL ======
// // Microswitch (mouse-click style limit switch, e.g. Omron D2F) wired
// // between GPIO5 and GND -- tidak ada modul signal-conditioning, jadi
// // pull-up internal diaktifkan (INPUT_PULLUP) dan logikanya active-LOW:
// // pin bernilai HIGH saat dilepas (ditarik ke atas), LOW saat ditekan
// // (switch menyambung ke GND).
// //
// // Microswitch SPDT (3 kaki -- COM, NO, NC) dipakai dengan kombinasi
// // COM + NO saja (kaki NC dibiarkan tidak tersambung):
// //   - Kaki COM  -> GND
// //   - Kaki NO   -> GPIO5
// // Kenapa NO (Normally Open), bukan NC: saat tombol belum ditekan, NO
// // tidak tersambung ke COM, jadi GPIO5 tetap HIGH (ditarik oleh pull-up
// // internal). Saat tombol ditekan, tuas menyambungkan COM ke NO, sehingga
// // GPIO5 ditarik ke GND (LOW) -- persis logika active-LOW di atas.
// //
// // Dipakai sebagai Touch Signal (marker sedang menyentuh papan), BUKAN AI
// // Trigger -- notify 1 saat ditekan (mulai menggambar) dan 0 saat dilepas
// // (berhenti menggambar), ke server/hal/providers.py's BleTouchProvider,
// // yang membaca status ini via is_touching(). Beda dengan AI Trigger
// // (GLOSSARY.md), yang merupakan aksi sekali-tekan terpisah untuk memicu
// // analisis gambar -- belum ada tombol fisik terpasang untuk itu di board
// // ini, lihat catatan di setupBle() di bawah.
// #define TOUCH_PIN 5

// NimBLECharacteristic *touchChar = nullptr;

// bool lastState = false;  // false = dilepas, true = ditekan

// void setupBle() {
//   NimBLEDevice::init(DEVICE_NAME);

//   NimBLEServer *server = NimBLEDevice::createServer();
//   NimBLEService *service = server->createService(SERVICE_UUID);

//   touchChar = service->createCharacteristic(TOUCH_CHAR_UUID, NIMBLE_PROPERTY::NOTIFY);

//   // Nilai awal yang jelas (belum menyentuh), supaya central yang baca
//   // sebelum notify pertama tidak dapat nilai acak.
//   uint8_t initialTouch = 0;
//   touchChar->setValue(&initialTouch, 1);

//   service->start();

//   NimBLEAdvertising *advertising = NimBLEDevice::getAdvertising();
//   advertising->addServiceUUID(SERVICE_UUID);
//   advertising->start();

//   Serial.println("BLE aktif, menunggu koneksi dari server...");
//   Serial.print("MAC address (pakai ini untuk --ble-address): ");
//   Serial.println(NimBLEDevice::getAddress().toString().c_str());
// }

// void setup() {
//   Serial.begin(115200);
//   pinMode(TOUCH_PIN, INPUT_PULLUP);

//   setupBle();
// }

// void loop() {
//   // Dibalik di sini supaya sisa kode tetap bekerja dengan "true =
//   // ditekan", bukan level sinyal mentahnya (lihat catatan INPUT_PULLUP).
//   bool currentState = (digitalRead(TOUCH_PIN) == LOW);

//   // Notify hanya saat status berubah (mencegah spam) -- server yang
//   // mencetak status "ada sinyal/tidak" untuk tiap notifikasi yang
//   // diterima (lihat server/hal/providers.py).
//   if (currentState != lastState) {
//     lastState = currentState;

//     uint8_t value = currentState ? 1 : 0;
//     touchChar->setValue(&value, 1);
//     touchChar->notify();  // tidak error walau belum ada central yang subscribe
//   }

//   delay(20); // Debounce kecil
// }
