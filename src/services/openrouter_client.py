import os
import logging
import aiohttp
from src.core.config import OPENROUTER_API_KEY

log = logging.getLogger("OpenRouterClient")

class OpenRouterClient:
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.models = [
            "openai/gpt-oss-120b:free",
            "nvidia/nemotron-3-super-120b-a12b:free",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "google/gemma-4-26b-a4b-it:free"
        ]
        self.current_model_idx = 0
        if not self.api_key:
            log.error("CRITICAL: Không tìm thấy OPENROUTER_API_KEY trong file .env")

    @property
    def default_model(self) -> str:
        return self.models[self.current_model_idx]

    def _rotate_model(self):
        old_model = self.models[self.current_model_idx]
        self.current_model_idx = (self.current_model_idx + 1) % len(self.models)
        new_model = self.models[self.current_model_idx]
        log.info(f"🔄 Đã đổi OpenRouter Model: {old_model} ➡️ {new_model}")

    async def generate_content_async(self, messages: list, system_instruction: str = None, temperature: float = 0.8) -> str:
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY không được cấu hình.")
            
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/anhluong447/Shimizu",
            "X-Title": "Shimizu Bot"
        }
        
        # Prepare messages
        final_messages = messages.copy()
        if system_instruction:
            # Check if there is already a system message in the list
            if not any(m.get("role") == "system" for m in final_messages):
                final_messages.insert(0, {"role": "system", "content": system_instruction})
                
        max_attempts = len(self.models)
        last_exception = None
        
        for attempt in range(max_attempts):
            model_name = self.models[self.current_model_idx]
            data = {
                "model": model_name,
                "messages": final_messages,
                "temperature": temperature
            }
            
            log.info(f"Calling OpenRouter model '{model_name}' (Attempt {attempt + 1}/{max_attempts})")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=data) as response:
                        if response.status == 200:
                            res_json = await response.json()
                            choices = res_json.get("choices", [])
                            if choices:
                                content = choices[0].get("message", {}).get("content", "")
                                log.info(f"✅ OpenRouter call to '{model_name}' succeeded.")
                                return content
                            else:
                                raise Exception(f"Empty choices received from OpenRouter API for model '{model_name}'")
                        else:
                            error_text = await response.text()
                            raise Exception(f"OpenRouter API error {response.status} for model '{model_name}': {error_text}")
            except Exception as e:
                log.warning(f"❌ Lỗi khi gọi OpenRouter model '{model_name}': {e}")
                last_exception = e
                self._rotate_model()
                
        if last_exception:
            raise last_exception
        raise Exception("OpenRouter rotation failed without throwing specific exception")

# Singleton helper
_openrouter_client = None

def get_openrouter_client() -> OpenRouterClient:
    global _openrouter_client
    if _openrouter_client is None:
        _openrouter_client = OpenRouterClient()
    return _openrouter_client
