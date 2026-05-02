import os
from dotenv import load_dotenv
from utils.crypto_utils import encrypt_data

def main():
    load_dotenv()
    key = os.getenv('SECRET_KEY')
    
    if not key:
        print("❌ Lỗi: Không tìm thấy SECRET_KEY trong file .env")
        return

    input_file = 'meng.txt'
    output_file = 'meng.ann'

    if not os.path.exists(input_file):
        print(f"❌ Lỗi: Không tìm thấy file {input_file}")
        return

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        encrypted_content = encrypt_data(content, key)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(encrypted_content)

        print(f"✅ Thành công: Đã mã hóa {input_file} thành {output_file}")
        print(f"💡 Bây giờ bạn có thể an tâm push {output_file} lên Git.")
    except Exception as e:
        print(f"❌ Lỗi: {e}")

if __name__ == "__main__":
    main()
