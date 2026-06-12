import asyncio
from src.bot import bot
from src.core.config import TOKEN
from src.core.logger import log

async def main():
    async with bot:
        try:
            await bot.start(TOKEN)
        except Exception as e:
            log.critical(f"Bot failed to start: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("👋 Đang tắt bot...")
#Test 123