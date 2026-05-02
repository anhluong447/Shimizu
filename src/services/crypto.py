import base64

def xor_cipher(data: str, key: str) -> str:
    """Thực hiện XOR giữa data và key (lặp lại key nếu cần)."""
    return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(data))

def encrypt_data(text: str, key: str) -> str:
    """Mã hóa text bằng XOR sau đó chuyển sang Base64 để lưu trữ an toàn."""
    xor_result = xor_cipher(text, key)
    return base64.b64encode(xor_result.encode('utf-8')).decode('utf-8')

def decrypt_data(encoded_text: str, key: str) -> str:
    """Giải mã Base64 sau đó thực hiện XOR để lấy lại dữ liệu gốc."""
    try:
        decoded_bytes = base64.b64decode(encoded_text)
        xor_input = decoded_bytes.decode('utf-8')
        return xor_cipher(xor_input, key)
    except Exception as e:
        return f"Error during decryption: {e}"
