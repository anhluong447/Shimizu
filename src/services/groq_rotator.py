import os
import logging
import asyncio
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

        # Cleaned model list for high-quality chat interaction - ONLY best model
        self.models = [
            "llama-3.3-70b-versatile"
        ]
        
        self.current_key_idx = 0
        self.current_model_idx = 0
        self._initialize_client()

    def _initialize_client(self):
        """Khởi tạo Groq client với Key hiện tại."""
        key = self.keys[self.current_key_idx]
        self.client = AsyncGroq(api_key=key)
        masked_key = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else key
        groq_logger.info(f"Đã nạp Groq Client với Key [{self.current_key_idx}]: {masked_key}")

    def _rotate_model(self):
        """Chuyển sang Model tiếp theo. Nếu hết Model, đổi Key."""
        old_model = self.models[self.current_model_idx]
        self.current_model_idx += 1
        
        if self.current_model_idx >= len(self.models):
            groq_logger.warning(f"Đã thử hết toàn bộ {len(self.models)} Models của Groq Key [{self.current_key_idx}]. Tiến hành đổi Key...")
            self.current_model_idx = 0
            self.current_key_idx += 1
            
            if self.current_key_idx >= len(self.keys):
                groq_logger.error("🔥 ĐÃ CẠN KIỆT TOÀN BỘ GROQ KEY VÀ MODEL. 🔥")
                raise GroqExhaustedError("All Groq keys and models exhausted")
                
            self._initialize_client()
            
        new_model = self.models[self.current_model_idx]
        groq_logger.info(f"🔄 Đã đổi Groq Model: {old_model} ➡️ {new_model} (Key {self.current_key_idx})")

    async def generate_content_async(self, messages: list, system_instruction: str = None, temperature: float = 0.7, max_tokens: int = 4096) -> str:
        """Thử gọi API, nếu lỗi sẽ tự động xoay Model và Key."""
        max_attempts = len(self.keys) * len(self.models)
        
        # Merge system_instruction into messages if provided
        final_messages = messages.copy()
        if system_instruction:
            # Check if there's already a system message
            if not any(m.get("role") == "system" for m in final_messages):
                final_messages.insert(0, {"role": "system", "content": system_instruction})
        
        for attempt in range(max_attempts):
            model_name = self.models[self.current_model_idx]
            key_idx = self.current_key_idx
            
            try:
                groq_logger.info(f"Đang gọi Groq model '{model_name}' (Key {key_idx})")
                
                chat_completion = await self.client.chat.completions.create(
                    messages=final_messages,
                    model=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                
                groq_logger.info(f"✅ Gọi Groq model '{model_name}' (Key {key_idx}) THÀNH CÔNG.")
                return chat_completion.choices[0].message.content
                
            except Exception as e:
                error_name = type(e).__name__
                error_msg = str(e)
                groq_logger.warning(f"❌ LỖI ({error_name}) trên Groq model '{model_name}' (Key {key_idx}): {error_msg}")
                
                try:
                    self._rotate_model()
                except GroqExhaustedError:
                    raise # Re-raise to the caller
                except Exception as fatal_e:
                    raise GroqExhaustedError(f"Fatal error during rotation: {str(fatal_e)}")
        
        raise GroqExhaustedError("Max attempts reached without success")

# Singleton instance
groq_rotator = None

def get_groq_rotator() -> GroqRotator:
    global groq_rotator
    if groq_rotator is None:
        groq_rotator = GroqRotator()
    return groq_rotator
