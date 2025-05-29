import os
import re
import time
from flask import Flask, request, jsonify
from ultralytics import YOLO
from PIL import Image
import cv2
import numpy as np
import pytesseract

app = Flask(__name__)

plate_model = YOLO("license_plate_detector.pt")

os.makedirs("kayitlar", exist_ok=True)

izinli_plakalar = ["27AJU998", '41AHB495', '26ADM842']

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

@app.route('/plaka-tanit', methods=['POST'])
def plaka_tanit():
    timestamp = int(time.time())
    img_path = f"kayitlar/goruntu_{timestamp}.jpg"
    image = request.files['image'].read()
    nparr = np.frombuffer(image, np.uint8)
    img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
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

        if fixed_plate in izinli_plakalar:
            print(f"[✅] Eşleşme: {fixed_plate} → İzinli")
            return jsonify({'success': True, 'plate': fixed_plate, 'durum': 'izinli'})
        else:
            print(f"[✖] Eşleşme yok: {fixed_plate} → İzinli değil")
            return jsonify({'success': True, 'plate': fixed_plate, 'durum': 'izinli değil'})

    return jsonify({'success': False, 'message': 'Plaka işlenemedi.'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050)
