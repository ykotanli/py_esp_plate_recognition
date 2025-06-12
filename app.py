import os
import re
import time
from flask import Flask, request, jsonify, render_template, send_from_directory
from ultralytics import YOLO
from PIL import Image
import cv2
import numpy as np
import pytesseract

app = Flask(__name__)

plate_model = YOLO("license_plate_detector.pt")

LOG_FILE = "plaka_log.txt"

# Static klasörünü oluşturun
os.makedirs("static/kayitlar", exist_ok=True)

# İzinli plakaları dosyadan okuma
def read_allowed_plates():
    if os.path.exists("izinli_plakalar.txt"):
        with open("izinli_plakalar.txt", "r") as file:
            return [line.strip() for line in file.readlines()]
    return []

# İzinli plakaları dosyaya yazma
def write_allowed_plates(plates):
    with open("izinli_plakalar.txt", "w") as file:
        for plate in plates:
            file.write(plate + "\n")

izinli_plakalar = read_allowed_plates()

def fix_turkish_plate_format(text):
    if not text:
        return None

    text = text.upper()
    text = re.sub(r'[^A-Z0-9]', '', text)

    text = re.sub(r'^(\d{2})(\d)', lambda m: m.group(1) + chr(ord('A') + int(m.group(2)) % 26), text)

    corrections = {
        'O': '0', 'Q': '0',
        'I': '1', 'L': '1',
        'Z': '2',
        'A': '4',
        'S': '5',
        'G': '9',
        'B': '8',
        'T': '7',
        'E': '3'
    }

    def fix_tail(tail):
        return ''.join([corrections.get(c, c) for c in tail])

    match = re.match(r'^(\d{2})([A-Z]{2,3})([A-Z0-9]{2,4})$', text)
    if not match:
        return None

    il_kodu, harfler, son = match.groups()
    son_fixed = fix_tail(son)

    return f"{il_kodu}{harfler}{son_fixed}"

def ocr_on_crop(crop):
    gray = cv2.cvtColor(np.array(crop), cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    config = '--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    text = pytesseract.image_to_string(thresh, config=config)
    return text.strip()

def log_entry(plate, image_path):
    action = "GİRİŞ"
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # Son satırdan başa doğru bak, aynı plakadan en son ne var bul
            for line in reversed(lines):
                if f"- {plate} -" in line:
                    if "GİRİŞ" in line:
                        action = "ÇIKIŞ"
                    else:
                        action = "GİRİŞ"
                    break
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        f.write(f"{timestamp} - {plate} - {action} - {image_path}\n")

@app.route('/')
def index():
    return render_template('index.html', izinli_plakalar=izinli_plakalar)

@app.route('/plaka-tanit', methods=['POST'])
def plaka_tanit():
    timestamp = int(time.time())
    img_path = f"static/kayitlar/goruntu_{timestamp}.jpg"  # Static dizininde kaydet
    image = request.files['image'].read()
    nparr = np.frombuffer(image, np.uint8)
    img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # Resmi kaydetme
    cv2.imwrite(img_path, img_np)
    print(f"[💾] Görüntü kaydedildi: {img_path}")

    results = plate_model(img_np)[0]

    if not results.boxes:
        print("[✖] Plaka bulunamadı.")
        return jsonify({'success': False, 'message': 'Plaka bulunamadı.'})

    for box in results.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        crop = Image.fromarray(img_np[y1:y2, x1:x2])

        raw_text = ocr_on_crop(crop)

        if raw_text and raw_text[0].isalpha():
            print(f"[ℹ] OCR sonucu harfle başlamış: {raw_text}. Baştaki harf kaldırılıyor.")
            raw_text = raw_text[1:]

        fixed_plate = fix_turkish_plate_format(raw_text)

        if not fixed_plate:
            print(f"[✖] OCR sonucu geçersiz: {raw_text}")
            return jsonify({'success': False, 'message': 'OCR sonucu geçersiz.', 'ocr': raw_text})

        print(f"[📸] Tanımlanan plaka: {fixed_plate}")

        # Sadece izinli plakalar için log kaydı
        if fixed_plate in izinli_plakalar:
            log_entry(fixed_plate, img_path)

        return jsonify({'success': True, 'plate': fixed_plate, 'durum': 'izinli' if fixed_plate in izinli_plakalar else 'izinsiz', 'image_path': f"/kayitlar/goruntu_{timestamp}.jpg"})
    
    return jsonify({'success': False, 'message': 'Plaka işlenemedi.'})

@app.route('/izinli-plaka-ekle', methods=['POST'])
def izinli_plaka_ekle():
    plaka = request.json.get('plaka')
    if plaka and plaka not in izinli_plakalar:
        izinli_plakalar.append(plaka)
        write_allowed_plates(izinli_plakalar)  # Plakayı dosyaya kaydet
        return jsonify({'success': True, 'izinli_plakalar': izinli_plakalar})
    return jsonify({'success': False, 'message': 'Plaka zaten var veya geçersiz.'})

@app.route('/izinli-plaka-sil', methods=['POST'])
def izinli_plaka_sil():
    plaka = request.json.get('plaka')
    if plaka in izinli_plakalar:
        izinli_plakalar.remove(plaka)
        write_allowed_plates(izinli_plakalar)  # Plakayı dosyadan sil
        return jsonify({'success': True, 'izinli_plakalar': izinli_plakalar})
    return jsonify({'success': False, 'message': 'Plaka bulunamadı.'})

@app.route('/izinli-plakalar', methods=['GET'])
def izinli_plakalar_api():
    return jsonify({'izinli_plakalar': izinli_plakalar})

# Resim dosyasını static klasöründen sunma
@app.route('/kayitlar/<filename>')
def serve_file(filename):
    return send_from_directory('static/kayitlar', filename)

# En son kaydedilen resmi döndüren route
@app.route('/son-resim', methods=['GET'])
def son_resim():
    # Kaydedilen son resmin yolunu döndürüyoruz
    latest_image = max([f"static/kayitlar/{f}" for f in os.listdir('static/kayitlar')], key=os.path.getctime)
    return jsonify({'last_image_url': f'/{latest_image}'})

# Logları arayüze göstermek için endpoint
@app.route('/plaka-log', methods=['GET'])
def plaka_log():
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f.readlines()[-20:]:  # Son 20 log
                logs.append(line.strip())
    return jsonify({'logs': logs})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050)
