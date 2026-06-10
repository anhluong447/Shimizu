import logging
from src.services.openrouter_client import get_openrouter_client
from src.services.groq_rotator import get_groq_rotator
from src.services.gemini_rotator import get_rotator as get_gemini_rotator

log = logging.getLogger("UnifiedRotator")

class UnifiedRotator:
    def __init__(self):
        self.openrouter = get_openrouter_client()
        self.groq = get_groq_rotator()
        self.gemini = get_gemini_rotator()

    async def generate_content_async(self, messages: list, system_instruction: str = None, temperature: float = 0.8) -> str:
        """Thử Groq trước, nếu tất cả các key/model của Groq bị cạn kiệt thì chuyển sang OpenRouter làm dự phòng."""
        try:
            log.info("Attempting to generate content using Groq rotator...")
            return await self.groq.generate_content_async(
                messages=messages,
                system_instruction=system_instruction,
                temperature=temperature
            )
        except Exception as e:
            log.warning(f"Groq rotator call failed: {e}. Falling back to OpenRouter...")
            try:
                return await self.openrouter.generate_content_async(
                    messages=messages,
                    system_instruction=system_instruction,
                    temperature=temperature
                )
            except Exception as oe:
                log.error(f"OpenRouter fallback also failed: {oe}")
                return "Cả Groq và OpenRouter hiện tại đều không khả dụng. Vui lòng thử lại sau."

# Singleton instance
unified_rotator = None

def get_unified_rotator() -> UnifiedRotator:
    global unified_rotator
    if unified_rotator is None:
        unified_rotator = UnifiedRotator()
    return unified_rotator
