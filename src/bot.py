import os
import discord
from discord.ext import commands
from src.core.config import PREFIX, TOKEN
from src.core.logger import log

class ShimizuBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=PREFIX, intents=intents)

    async def setup_hook(self):
        log.info("--- Loading modules ---")
        await self.load_all_cogs()
        log.info("--- Modules loaded ---")

    async def load_all_cogs(self):
        cogs_dir = os.path.join(os.path.dirname(__file__), 'cogs')
        for item in os.listdir(cogs_dir):
            if item.startswith('__'):
                continue
                
            item_path = os.path.join(cogs_dir, item)
            
            # Load root .py files as extensions
            if os.path.isfile(item_path) and item.endswith('.py'):
                module_path = f'src.cogs.{item[:-3]}'
                try:
                    await self.load_extension(module_path)
                    log.info(f'[LOAD] {module_path}')
                except Exception as e:
                    log.error(f'[ERROR] {module_path}: {e}')
                    
            # Load directories as package extensions (if they have __init__.py)
            elif os.path.isdir(item_path):
                if os.path.exists(os.path.join(item_path, '__init__.py')):
                    module_path = f'src.cogs.{item}'
                    try:
                        await self.load_extension(module_path)
                        log.info(f'[LOAD] {module_path}')
                    except Exception as e:
                        log.error(f'[ERROR] {module_path}: {e}')

    async def reload_all_cogs(self):
        for extension in list(self.extensions):
            try:
                await self.reload_extension(extension)
                log.info(f'🔄 Đã nạp lại: {extension}')
            except Exception as e:
                log.error(f'❌ Lỗi khi nạp lại {extension}: {e}')

    async def on_ready(self):
        log.info(f'Bot {self.user.name} is online!')
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"{PREFIX}play"))

    async def on_message(self, message):
        if message.author.bot:
            return
        
        # Log để debug xem bot có nhận được tin nhắn không
        log.info(f"Message from {message.author}: {message.content}")

        # Lệnh debug nhanh
        if message.content == f"{PREFIX}modules":
            loaded = ", ".join(self.extensions.keys()) or "None"
            await message.channel.send(f"📦 **Loaded modules:** `{loaded}`")
            return

        await self.process_commands(message)

bot = ShimizuBot()
