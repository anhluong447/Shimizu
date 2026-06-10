import os
import logging
from groq import AsyncGroq
from src.core.config import GROQ_API_KEYS, GROQ_ROTATION_LOG

# Setup dedicated logger for Groq rotation
groq_logger = logging.getLogger("GroqRotation")
groq_logger.setLevel(logging.INFO)

# Ensure logs directory exists
os.makedirs(os.path.dirname(GROQ_ROTATION_LOG), exist_ok=True)

# File handler
if not groq_logger.handlers:
    file_handler = logging.FileHandler(GROQ_ROTATION_LOG, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s'))
    groq_logger.addHandler(file_handler)
    
class GroqExhaustedError(Exception):
    """Raised when all Groq API keys and models are exhausted."""
    pass

class GroqRotator:
    def __init__(self):
        self.keys = GROQ_API_KEYS
        if not self.keys:
            groq_logger.error("CRITICAL: Không tìm thấy GROQ_API_KEYS trong file .env")
            raise ValueError("GROQ_API_KEYS không được cấu hình.")

        # Cleaned model list for high-quality chat interaction
        self.models = [
            "llama-3.3-70b-versatile",
            "mixtral-8x7b-32768",
            "llama-3.1-8b-instant"
        ]
        
        self.current_key_idx = 0
        self.current_model_idx = 0
        groq_logger.info(f"Khởi tạo GroqRotator với {len(self.keys)} keys và {len(self.models)} models.")

    async def generate_content_async(self, messages: list, system_instruction: str = None, temperature: float = 0.7, max_tokens: int = 4096) -> str:
        """Thử gọi API, xoay key ngay sau mỗi 1 request, chỉ xoay model nếu tất cả các key của model hiện tại thất bại."""
        # Merge system_instruction into messages if provided
        final_messages = messages.copy()
        if system_instruction:
            if not any(m.get("role") == "system" for m in final_messages):
                final_messages.insert(0, {"role": "system", "content": system_instruction})
        
        num_models = len(self.models)
        num_keys = len(self.keys)
        
        for model_attempt in range(num_models):
            model_idx = (self.current_model_idx + model_attempt) % num_models
            model_name = self.models[model_idx]
            
            # For this model, try all keys starting from current_key_idx
            for key_attempt in range(num_keys):
                key_idx = (self.current_key_idx + key_attempt) % num_keys
                key = self.keys[key_idx]
                
                try:
                    masked_key = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else key
                    groq_logger.info(f"Đang gọi Groq model '{model_name}' với Key [{key_idx}]: {masked_key}")
                    client = AsyncGroq(api_key=key)
                    
                    chat_completion = await client.chat.completions.create(
                        messages=final_messages,
                        model=model_name,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    
                    groq_logger.info(f"✅ Gọi Groq model '{model_name}' (Key {key_idx}) THÀNH CÔNG.")
                    
                    # Advance to next key for the next request to ensure per-request rotation
                    self.current_key_idx = (key_idx + 1) % num_keys
                    # Set the active model as the current model
                    self.current_model_idx = model_idx
                    
                    return chat_completion.choices[0].message.content
                    
                except Exception as e:
                    error_name = type(e).__name__
                    error_msg = str(e)
                    groq_logger.warning(f"❌ LỖI ({error_name}) trên Groq model '{model_name}' (Key {key_idx}): {error_msg}")
            
            # All keys failed for the current model, warn and switch to next model
            groq_logger.warning(f"⚠️ Tất cả {num_keys} keys đều thất bại cho model '{model_name}'. Chuyển sang model tiếp theo...")
            
        # If we got here, all keys for all models failed!
        groq_logger.error("🔥 ĐÃ CẠN KIỆT TOÀN BỘ GROQ KEY VÀ MODEL. 🔥")
        raise GroqExhaustedError("All Groq keys and models exhausted")

# Singleton instance
groq_rotator = None

def get_groq_rotator() -> GroqRotator:
    global groq_rotator
    if groq_rotator is None:
        groq_rotator = GroqRotator()
    return groq_rotator
