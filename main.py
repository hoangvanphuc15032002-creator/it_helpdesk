import subprocess
import sys
import time
import socket

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

lan_ip = get_lan_ip()

print("🚀 ĐANG KHỞI ĐỘNG HỆ THỐNG IT HELPDESK...")

try:
    print("-> Đang bật Bot Telegram...")
    bot_process = subprocess.Popen([sys.executable, 'bot.py'])
    
    time.sleep(2)

    print("-> Đang bật trang Web Dashboard...")
    web_process = subprocess.Popen([sys.executable, 'app.py'])

    print("\n✅ HỆ THỐNG ĐÃ HOẠT ĐỘNG THÀNH CÔNG!")
    print("👉 Bot đã sẵn sàng nhận tin nhắn.")
    print("=" * 50)
    print(f"👉 http://{lan_ip}:8080")
    print("=" * 50)
    print("❌ (Để tắt toàn bộ hệ thống: Bấm tổ hợp phím Ctrl + C)\n")

    bot_process.wait()
    web_process.wait()

except KeyboardInterrupt:
    print("\n🛑 Đang dọn dẹp và tắt hệ thống...")
    bot_process.terminate()
    web_process.terminate()
    print("Đã tắt an toàn! Hẹn gặp lại.")