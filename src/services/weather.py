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
                        data = await response.json(content_type=None)
                        
                        curr = data['current_condition'][0]
                        today = data['weather'][0]
                        tomorrow = data['weather'][1]
                        
                        def parse_hourly(target_time):
                            item = min(today['hourly'], key=lambda x: abs(int(x['time']) - target_time))
                            return {
                                'temp': item['tempC'],
                                'desc': item.get('lang_vi', [{'value': item['weatherDesc'][0]['value']}])[0]['value']
                            }

                        return {
                            'city': city.capitalize(),
                            'current': {
                                'temp': curr['temp_C'],
                                'desc': curr.get('lang_vi', [{'value': curr['weatherDesc'][0]['value']}])[0]['value'],
                                'feels_like': curr['FeelsLikeC'],
                                'humidity': curr['humidity'],
                                'icon': curr['weatherIconUrl'][0]['value']
                            },
                            'forecast': {
                                'morning': parse_hourly(900),
                                'noon': parse_hourly(1200),
                                'evening': parse_hourly(1800),
                                'night': parse_hourly(2100)
                            },
                            'tomorrow': {
                                'date': tomorrow['date'],
                                'min': tomorrow['mintempC'],
                                'max': tomorrow['maxtempC'],
                                'desc': tomorrow['hourly'][4].get('lang_vi', [{'value': tomorrow['hourly'][4]['weatherDesc'][0]['value']}])[0]['value']
                            }
                        }
                    return None
        except Exception as e:
            log.error(f"Weather error: {e}")
            return None
