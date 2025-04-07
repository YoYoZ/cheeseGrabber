import os
import cv2
from datetime import datetime
import json
from flask import Flask, jsonify
from moviepy import ImageSequenceClip
import threading
import logging


# Вимикаємо попередження від Flask
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

logging.basicConfig(level=logging.ERROR)
# Шлях для збереження налаштувань
settings_file = 'camera_settings.json'

# Глобальна змінна для зберігання шляху до поточної папки із зображеннями
current_capture_folder = None

# Функція для читання або створення налаштувань
def load_settings():
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as file:
            return json.load(file)
    else:
        return {}

# Функція для збереження налаштувань
def save_settings(username, password, url):
    settings = {
        'username': username,
        'password': password,
        'url': url
    }
    with open(settings_file, 'w') as file:
        json.dump(settings, file)

# Функція для підключення до камери
def get_camera_connection(username, password, url, use_auth):
    if use_auth:
        print(f"Використовую авторизацію з минулого запуску (якщо треба, видаліть файл camera_settings): {username}:{password}@{url[7:]}")
        return f"rtsp://{username}:{password}@{url[7:]}"  # Прибираємо 'rtsp://'
    print(f"Використовую підключення без логін\пароля: {url}")
    return url

# Ініціалізація Flask
app = Flask(__name__)

@app.route('/capture', methods=['GET'])
def capture_image():
    global current_capture_folder  # Використовуємо глобальну змінну

    try:
        if current_capture_folder is None:
            return "❌ Папка для знімків не була створена. Перевірте, чи працює запит /start у вашому g-code", 400

        # Загрузка настроек из файла
        settings = load_settings()
        username = settings.get('username', '')
        password = settings.get('password', '')
        url = settings.get('url', '')

        if not url:
            return "❌Камера не налаштована коректно. Будь-ласка, спробуйте наново", 500

        # Формуємо URL з авторизацією
        rtsp_url = get_camera_connection(username, password, url, True)

        # Відкриваємо RTSP потік
        print(f"Спроба підключення до RTSP потоку: {rtsp_url}")
        cap = cv2.VideoCapture(rtsp_url)

        if not cap.isOpened():
            return f"❌ Не вдалося підключитись до RTSP потоку: {rtsp_url}", 500

        ret, frame = cap.read()
        if ret:
            filename = f"{current_capture_folder}/capture_{datetime.now().strftime('%H%M%S')}.jpg"
            cv2.imwrite(filename, frame)
            cap.release()
            return f"✅ Знімок збережено як {filename}", 200
        else:
            cap.release()
            return "❌ Не вдалося зберегти файл.", 500

    except Exception as e:
        print(f"Ошибка: {e}")
        return "❌ Ой лишенько, трапилася дивна помилка!", 500

@app.route('/start', methods=['GET'])
def start_capture_folder():
    global current_capture_folder  # Використовуємо глобальну змінну

    try:
        # Завжди створюємо нову папку з унікальним ім'ям
        current_capture_folder = f'captures/capture_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        os.makedirs(current_capture_folder, exist_ok=True)

        return f"✅ Папку для таймлапсу створено: {current_capture_folder}", 200

    except Exception as e:
        print(f"Ошибка: {e}")
        return "❌ Не вдалося створити папку для таймлапсів", 500




@app.route('/stop', methods=['GET'])
def stop_capture():
    thread = threading.Thread(target=render_video)
    thread.start()
    thread.join()
    return f"✅ Рендер закінчився!: {current_capture_folder}.mp4", 200


def render_video():
    global current_capture_folder

    if current_capture_folder is None:
        return jsonify({"error": "Папку для знімків не створено."}), 400

    # Список усіх зображень у папці
    image_files = [f for f in os.listdir(current_capture_folder) if f.endswith('.jpg')]
    if not image_files:
        return jsonify({"error": "У папці нема жодного знімка."}), 400

    # Сортуємо зображення за ім'ям, щоб вони йшли в потрібному порядку
    image_files.sort()

    # Створення відеокліпу
    image_paths = [os.path.join(current_capture_folder, f) for f in image_files]
    video_filename = f"{current_capture_folder}.mp4"

    # Рендерим відео із зображень
    try:
        clip = ImageSequenceClip(image_paths, fps=30)  # Частота кадрів 30 на секунду
        clip.write_videofile(video_filename, codec="libx264")
    except Exception as e:
        print("Помилка при створенні відео: {str(e)}")
    return

# Головна функція для взаємодії з користувачем
def run_console_interface():
    # Читання налаштувань із файлу
    settings = load_settings()

    # Якщо налаштування вже існують, не запитуємо їх заново
    if settings.get('url'):
        print("Налаштування завантажено з файлу.")
        print("Ось ваші дані:")
        print(f"Логін: {settings['username']}, Пароль: {settings['password']}, URL: {settings['url']}")
    else:
        # Якщо налаштувань немає, запитуємо їх у користувача
        print("Оберіть тип підключення:")
        print("1: HTTP")
        print("2: RTSP (зазвичай)")
        choice = input("Оберіть 1 чи 2: ")

        if choice == '1':
            print("Ви обрали HTTP.")
        elif choice == '2':
            print("Ви обрали RTMP.")
        else:
            print("Некоректний вибір, пустунчик.")
            return

        # Запитуємо логін, пароль і URL
        username = input("Ваш логін (якщо нема, натисніть Enter): ") or settings.get('username', '')
        password = input("Ван пароль (якщо нема, натисніть Enter): ") or settings.get('password', '')
        url = input("Введіть лінк на камеру: ") or settings.get('url', '')

        # Зберігаємо налаштування для наступного запуску
        save_settings(username, password, url)
    
    print("Налаштування збережено. Сервер буде працювати з ними надалі")

    # Запуск Flask сервера
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    run_console_interface()
