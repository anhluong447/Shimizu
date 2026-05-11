import os
import logging
from datetime import datetime
from google import genai
from google.genai import types
from google.genai.errors import APIError

from src.core.config import GEMINI_API_KEYS, GEMINI_ROTATION_LOG

# Setup dedicated logger for rotation
rotation_logger = logging.getLogger("GeminiRotation")
rotation_logger.setLevel(logging.INFO)

# Ensure logs directory exists
os.makedirs(os.path.dirname(GEMINI_ROTATION_LOG), exist_ok=True)

# File handler
file_handler = logging.FileHandler(GEMINI_ROTATION_LOG, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s'))
rotation_logger.addHandler(file_handler)

class GeminiRotator:
    def __init__(self):
        self.keys = GEMINI_API_KEYS
        if not self.keys:
            rotation_logger.error("CRITICAL: Không tìm thấy GEMINI_API_KEYS trong file .env")
            raise ValueError("GEMINI_API_KEYS không được cấu hình.")

        self.models = [
            "gemini-2.5-flash",
            "gemma-3-27b",
            "gemma-3-12b",
            "gemma-4-26b",
            "gemma-4-31b",
            "gemini-3-flash",
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash-lite"
        ]
        
        self.current_key_idx = 0
        self.current_model_idx = 0
        self._initialize_client()

    def _initialize_client(self):
        """Khởi tạo GenAI client với Key hiện tại."""
        key = self.keys[self.current_key_idx]
        self.client = genai.Client(api_key=key)
        # Ẩn bớt độ dài key trong log cho an toàn
        masked_key = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else key
        rotation_logger.info(f"Đã nạp Client với Key [{self.current_key_idx}]: {masked_key}")

    def _rotate_model(self):
        """Chuyển sang Model tiếp theo. Nếu hết Model, đổi Key."""
        old_model = self.models[self.current_model_idx]
        self.current_model_idx += 1
        
        if self.current_model_idx >= len(self.models):
            rotation_logger.warning(f"Đã thử hết toàn bộ {len(self.models)} Models của Key [{self.current_key_idx}]. Tiến hành đổi Key...")
            self.current_model_idx = 0
            self.current_key_idx += 1
            
            if self.current_key_idx >= len(self.keys):
                rotation_logger.error("🔥 ĐÃ CẠN KIỆT TOÀN BỘ KEY VÀ MODEL. HỆ THỐNG DỪNG HOẠT ĐỘNG! 🔥")
                raise Exception("Out of API Keys and Models")
                
            self._initialize_client()
            
        new_model = self.models[self.current_model_idx]
        rotation_logger.info(f"🔄 Đã đổi Model: {old_model} ➡️ {new_model} (Key {self.current_key_idx})")

    async def generate_content_async(self, prompt: str = None, messages: list = None, system_instruction: str = None, temperature: float = 0.8) -> str:
        """Thử gọi API, nếu lỗi sẽ tự động xoay Model và Key.
        Hỗ trợ truyền prompt đơn giản HOẶC cấu trúc messages [{"role": "user/assistant/system", "content": ...}]"""
        max_attempts = len(self.keys) * len(self.models)
        
        # Xử lý messages thành định dạng của Gemini
        contents = []
        if messages:
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                # Bắt system prompt nếu chưa có
                if role == "system":
                    if not system_instruction:
                        system_instruction = content
                    continue
                
                # Chuyển assistant -> model
                if role == "assistant":
                    role = "model"
                    
                contents.append(
                    types.Content(role=role, parts=[types.Part.from_text(text=content)])
                )
                
        if prompt:
            contents.append(
                types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
            )
            
        if not contents:
            return "Lỗi: Không có nội dung để gửi cho AI."
        
        for attempt in range(max_attempts):
            model_name = self.models[self.current_model_idx]
            key_idx = self.current_key_idx
            
            try:
                rotation_logger.info(f"Đang gọi model '{model_name}' (Key {key_idx})")
                
                config_kwargs = {"temperature": temperature}
                if system_instruction:
                    config_kwargs["system_instruction"] = system_instruction
                    
                config = types.GenerateContentConfig(**config_kwargs)
                
                if hasattr(self.client, 'aio'):
                    response = await self.client.aio.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=config
                    )
                else:
                    import asyncio
                    def sync_call():
                        return self.client.models.generate_content(
                            model=model_name,
                            contents=contents,
                            config=config
                        )
                    response = await asyncio.to_thread(sync_call)
                
                rotation_logger.info(f"✅ Gọi model '{model_name}' (Key {key_idx}) THÀNH CÔNG.")
                return response.text
                
            except Exception as e:
                error_name = type(e).__name__
                error_msg = str(e)
                rotation_logger.warning(f"❌ LỖI ({error_name}) trên model '{model_name}' (Key {key_idx}): {error_msg}")
                
                try:
                    self._rotate_model()
                except Exception as fatal_e:
                    return "Hệ thống AI hiện đang quá tải toàn bộ. Vui lòng thử lại sau."
        
        return "Lỗi nội bộ: Đã thử quá số lần cho phép nhưng không thành công."

    async def embed_content_async(self, text: str, task_type: str = None) -> list:
        """Tạo embedding vector từ văn bản. Sử dụng gemini-embedding-2."""
        max_attempts = len(self.keys)
        # gemini-embedding-2 là model embedding mới nhất
        model_name = "gemini-embedding-2"
        
        for attempt in range(max_attempts):
            key_idx = self.current_key_idx
            try:
                # gemini-embedding-2 không dùng task_type nhưng hỗ trợ output_dimensionality
                config = types.EmbedContentConfig(
                    output_dimensionality=768
                )
                
                if hasattr(self.client, 'aio'):
                    response = await self.client.aio.models.embed_content(
                        model=model_name,
                        contents=text,
                        config=config
                    )
                else:
                    import asyncio
                    def sync_call():
                        return self.client.models.embed_content(
                            model=model_name,
                            contents=text,
                            config=config
                        )
                    response = await asyncio.to_thread(sync_call)
                
                if response and response.embeddings:
                    return response.embeddings[0].values
                
            except Exception as e:
                rotation_logger.warning(f"❌ LỖI Embedding ({model_name}) trên Key {key_idx}: {e}")
                # Nếu model 2 không tìm thấy (hiếm), thử fallback sang model 001
                if "not found" in str(e).lower() and model_name == "gemini-embedding-2":
                    model_name = "gemini-embedding-001"
                    rotation_logger.info(f"🔄 Fallback sang model embedding: {model_name}")
                    continue
                
                # Đổi sang key tiếp theo
                self.current_key_idx = (self.current_key_idx + 1) % len(self.keys)
                self._initialize_client()
                
        return []

# Singleton instance
gemini_rotator = None

def get_rotator() -> GeminiRotator:
    global gemini_rotator
    if gemini_rotator is None:
        gemini_rotator = GeminiRotator()
    return gemini_rotator
