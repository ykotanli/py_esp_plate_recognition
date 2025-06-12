#include <WiFi.h>
#include <HTTPClient.h>
#include "esp_camera.h"
#include <ESP32Servo.h>

// ====== Servo Ayarları ======
Servo myServo;
const int servoPin = 14; // Servo sinyal pini

// ====== WiFi Ayarları ======
const char *ssid = "ykiph";
const char *password = "osh4696256";

// ====== Flask Sunucu Ayarları ======
const char *host = "172.20.10.3"; // Flask sunucusunun IP'si
const int port = 5050;            // Flask sunucusunun portu

// ====== ESP32-CAM Kamera Pinleri ======
#define PWDN_GPIO_NUM 32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 0
#define SIOD_GPIO_NUM 26
#define SIOC_GPIO_NUM 27
#define Y9_GPIO_NUM 35
#define Y8_GPIO_NUM 34
#define Y7_GPIO_NUM 39
#define Y6_GPIO_NUM 36
#define Y5_GPIO_NUM 21
#define Y4_GPIO_NUM 19
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM 23
#define PCLK_GPIO_NUM 22

void setup()
{
    Serial.begin(115200);
    delay(1000);

    // Servo başlat
    myServo.setPeriodHertz(50);
    myServo.attach(servoPin, 500, 2400);
    myServo.write(0);

    // WiFi Bağlantısı
    Serial.println("WiFi'ye bağlanılıyor...");
    WiFi.begin(ssid, password);
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30)
    {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED)
    {
        Serial.println("\nWiFi bağlantısı başarılı!");
        Serial.print("IP Adresi: ");
        Serial.println(WiFi.localIP());
    }
    else
    {
        Serial.println("\nWiFi bağlantısı başarısız!");
        return;
    }

    // Kamera Ayarları
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sscb_sda = SIOD_GPIO_NUM;
    config.pin_sscb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;

    if (psramFound())
    {
        config.frame_size = FRAMESIZE_QVGA;
        config.jpeg_quality = 10;
        config.fb_count = 2;
    }
    else
    {
        config.frame_size = FRAMESIZE_QQVGA;
        config.jpeg_quality = 12;
        config.fb_count = 1;
    }

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK)
    {
        Serial.printf("Kamera başlatılamadı! Hata kodu: 0x%x\n", err);
        while (true)
            ;
    }

    Serial.println("Kamera başlatıldı.");
}

void loop()
{
    Serial.println("📷 Görüntü çekiliyor...");
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb)
    {
        Serial.println("🚫 Görüntü alınamadı!");
        return;
    }

    Serial.printf("✔ Görüntü alındı. Boyut: %zu bayt\n", fb->len);

    WiFiClient client;
    if (!client.connect(host, port))
    {
        Serial.println("🚫 Sunucuya bağlanılamadı!");
        esp_camera_fb_return(fb);
        return;
    }

    String boundary = "----ESP32FormBoundary";
    String head = "--" + boundary + "\r\n";
    head += "Content-Disposition: form-data; name=\"image\"; filename=\"esp.jpg\"\r\n";
    head += "Content-Type: image/jpeg\r\n\r\n";
    String tail = "\r\n--" + boundary + "--\r\n";

    int contentLength = head.length() + fb->len + tail.length();

    // HTTP POST Başlıkları
    client.println("POST /plaka-tanit HTTP/1.1");
    client.print("Host: ");
    client.println(host);
    client.println("User-Agent: ESP32-CAM");
    client.println("Connection: close");
    client.println("Content-Type: multipart/form-data; boundary=" + boundary);
    client.print("Content-Length: ");
    client.println(contentLength);
    client.println();

    // Veri gönderimi
    client.print(head);
    client.write(fb->buf, fb->len);
    client.print(tail);

    // Header'dan sonra gelen cevabı oku
    while (client.connected())
    {
        String line = client.readStringUntil('\n');
        if (line == "\r")
            break;
    }

    String response = client.readString();
    Serial.println("🖥 Sunucu yanıtı:");
    Serial.println(response);

    // JSON yanıtını manuel çözümleme
    String durum = "";
    int durumPos = response.indexOf("\"durum\":");
    if (durumPos != -1)
    {
        int startPos = response.indexOf(":", durumPos) + 2;
        int endPos = response.indexOf("\"", startPos);
        durum = response.substring(startPos, endPos);
    }

    // Durum kontrolü ve servo motoru hareket ettirme
    if (durum == "izinli")
    {
        Serial.println("✅ İzinli plaka tanındı! Servo çalışıyor.");
        myServo.write(90); // Servo açılacak
        delay(2000);       // 2 saniye bekle
        myServo.write(0);  // Servo kapanacak
        delay(1000);       // 1 saniye bekle
    }
    else
    {
        Serial.println("❌ İzinli plaka bulunamadı.");
    }

    client.stop();
    esp_camera_fb_return(fb);
}
