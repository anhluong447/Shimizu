import logging
from src.services.openrouter_client import get_openrouter_client
from src.services.groq_rotator import get_groq_rotator

log = logging.getLogger("UnifiedRotator")

class UnifiedRotator:
    def __init__(self):
        self.openrouter = get_openrouter_client()
        self.groq = get_groq_rotator()

    async def generate_content_async(self, messages: list, system_instruction: str = None, temperature: float = 0.8) -> str:
        """Thử OpenRouter trước, nếu lỗi thì chuyển sang Groq làm dự phòng."""
        try:
            log.info("Attempting to generate content using OpenRouter...")
            return await self.openrouter.generate_content_async(
                messages=messages,
                system_instruction=system_instruction,
                temperature=temperature
            )
        except Exception as e:
            log.warning(f"OpenRouter call failed: {e}. Falling back to Groq...")
            try:
                return await self.groq.generate_content_async(
                    messages=messages,
                    system_instruction=system_instruction,
                    temperature=temperature
                )
            except Exception as ge:
                log.error(f"Groq fallback also failed: {ge}")
                return "Cả OpenRouter và Groq hiện tại đều không khả dụng. Vui lòng thử lại sau."

# Singleton instance
unified_rotator = None

def get_unified_rotator() -> UnifiedRotator:
    global unified_rotator
    if unified_rotator is None:
        unified_rotator = UnifiedRotator()
    return unified_rotator
