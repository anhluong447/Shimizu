import logging
from src.services.groq_rotator import get_groq_rotator, GroqExhaustedError
from src.services.gemini_rotator import get_rotator as get_gemini_rotator

log = logging.getLogger("UnifiedRotator")

class UnifiedRotator:
    def __init__(self):
        self.groq = get_groq_rotator()
        self.gemini = get_gemini_rotator()

    async def generate_content_async(self, messages: list, system_instruction: str = None, temperature: float = 0.8) -> str:
        """Thử Groq trước, nếu hết key thì chuyển sang Gemini."""
        try:
            log.info("Attempting to generate content using Groq...")
            return await self.groq.generate_content_async(
                messages=messages,
                system_instruction=system_instruction,
                temperature=temperature
            )
        except GroqExhaustedError:
            log.warning("Groq API exhausted. Falling back to Gemini...")
            try:
                return await self.gemini.generate_content_async(
                    messages=messages,
                    system_instruction=system_instruction,
                    temperature=temperature
                )
            except Exception as e:
                log.error(f"Gemini also failed: {e}")
                return "Cả Groq và Gemini đều hiện đang không khả dụng. Vui lòng thử lại sau."
        except Exception as e:
            log.error(f"Unexpected error in Groq call: {e}")
            # Optional: Fallback to Gemini on ANY error if you want to be safe, 
            # but usually we only want to fallback on exhaustion.
            # For now, let's fallback on any major error to ensure service availability.
            log.info("Falling back to Gemini due to unexpected Groq error...")
            return await self.gemini.generate_content_async(
                messages=messages,
                system_instruction=system_instruction,
                temperature=temperature
            )

# Singleton instance
unified_rotator = None

def get_unified_rotator() -> UnifiedRotator:
    global unified_rotator
    if unified_rotator is None:
        unified_rotator = UnifiedRotator()
    return unified_rotator
