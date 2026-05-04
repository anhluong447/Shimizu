import aiohttp
from src.core.logger import log

class WeatherService:
    @staticmethod
    async def get_weather(city="Hanoi"):
        url = f"https://wttr.in/{city}?format=j1&lang=vi"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Current condition
                        curr = data['current_condition'][0]
                        temp = curr['temp_C']
                        desc = curr.get('lang_vi', [{'value': curr['weatherDesc'][0]['value']}])[0]['value']
                        humidity = curr['humidity']
                        feels_like = curr['FeelsLikeC']
                        
                        # Today's forecast (hourly)
                        today = data['weather'][0]
                        hourly = today['hourly']
                        
                        def get_hourly_info(target_time):
                            # Find closest time
                            item = min(hourly, key=lambda x: abs(int(x['time']) - target_time))
                            t = item['tempC']
                            d = item.get('lang_vi', [{'value': item['weatherDesc'][0]['value']}])[0]['value']
                            return f"{t}°C, {d}"

                        morning = get_hourly_info(900)
                        noon = get_hourly_info(1200)
                        evening = get_hourly_info(1800)
                        night = get_hourly_info(2100)
                        
                        # Tomorrow
                        tomorrow = data['weather'][1]
                        tmr_date = tomorrow['date']
                        tmr_min = tomorrow['mintempC']
                        tmr_max = tomorrow['maxtempC']
                        # Use noon (1200) for general description
                        tmr_desc = tomorrow['hourly'][4].get('lang_vi', [{'value': tomorrow['hourly'][4]['weatherDesc'][0]['value']}])[0]['value']

                        res = [
                            f"📍 **Thời tiết {city.capitalize()}**",
                            f"✨ **Hiện tại:** {temp}°C ({desc})",
                            f"🌡️ **Cảm giác như:** {feels_like}°C | 💧 **Độ ẩm:** {humidity}%",
                            "",
                            "📋 **Dự báo hôm nay:**",
                            f"🌅 **Sáng:** {morning}",
                            f"☀️ **Trưa:** {noon}",
                            f"🌆 **Chiều:** {evening}",
                            f"🌙 **Tối:** {night}",
                            "",
                            f"📅 **Ngày mai ({tmr_date}):**",
                            f"🌡️ {tmr_min}°C - {tmr_max}°C | ☁️ {tmr_desc}"
                        ]
                        return "\n".join(res)
                    else:
                        return "☔ Không thể lấy dữ liệu thời tiết lúc này."
        except Exception as e:
            log.error(f"Weather error: {e}")
            return f"❌ Lỗi khi lấy thời tiết: {e}"
