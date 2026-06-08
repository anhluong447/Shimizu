import os
import logging
import aiohttp
from src.core.config import OPENROUTER_API_KEY

log = logging.getLogger("OpenRouterClient")

class OpenRouterClient:
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.default_model = "sao10k/l3-lunaris-8b"
        if not self.api_key:
            log.error("CRITICAL: Không tìm thấy OPENROUTER_API_KEY trong file .env")

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
                
        data = {
            "model": self.default_model,
            "messages": final_messages,
            "temperature": temperature
        }
        
        log.info(f"Calling OpenRouter model '{self.default_model}'")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    res_json = await response.json()
                    choices = res_json.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        log.info(f"✅ OpenRouter call to '{self.default_model}' succeeded.")
                        return content
                    else:
                        raise Exception("Empty choices received from OpenRouter API")
                else:
                    error_text = await response.text()
                    raise Exception(f"OpenRouter API error {response.status}: {error_text}")

# Singleton helper
_openrouter_client = None

def get_openrouter_client() -> OpenRouterClient:
    global _openrouter_client
    if _openrouter_client is None:
        _openrouter_client = OpenRouterClient()
    return _openrouter_client
