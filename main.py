import os
import discord
import asyncio
from discord.ext import commands
from dotenv import load_dotenv

# Load biến môi trường
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

class ShimizuBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        """Hàm này chạy khi bot khởi động, dùng để load Cogs"""
        print("--- Đang tải các module ---")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f'✅ Đã tải: {filename}')
                except Exception as e:
                    print(f'❌ Lỗi khi tải {filename}: {e}')
        print("--- Hoàn tất tải module ---")

    async def on_ready(self):
        print(f'🚀 {self.user.name} đã trực tuyến!')
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="!play"))

bot = ShimizuBot()

async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Đang tắt bot...")
