import aiohttp
from src.core.logger import log

class WeatherService:
    @staticmethod
    async def get_weather(city="Hanoi"):
        url = f"https://wttr.in/{city}?format=%l:+%C+%t+%h+%w&lang=vi"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        text = await response.text()
                        if ":" in text:
                            loc, details = text.split(":", 1)
                            return f"📍 **Địa điểm:** {loc.strip().capitalize()}\n📝 **Chi tiết:** {details.strip()}"
                        return text
                    else:
                        return "☔ Không thể lấy dữ liệu thời tiết lúc này."
        except Exception as e:
            log.error(f"Weather error: {e}")
            return f"❌ Lỗi khi lấy thời tiết: {e}"
