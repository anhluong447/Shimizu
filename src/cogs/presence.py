import discord
from discord.ext import commands, tasks
import random
import asyncio
from src.core.logger import log

class Presence(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.presence_task.start()
        self.idle_statuses = [
            "Watching the clouds ☁️",
            "Waiting for music... 🎵",
            "Checking /weather 🌦️",
            "Chilling in the server 🌸",
            "Reading /meng memories... 🧠",
            "Listening to your heart ❤️",
            "Watching stars ✨"
        ]

    def cog_unload(self):
        self.presence_task.cancel()

    @tasks.loop(minutes=1)
    async def presence_task(self):
        try:
            # 1. Check for active music
            music_cog = self.bot.get_cog('Music')
            active_song = None
            
            if music_cog and hasattr(music_cog, 'players'):
                for player in music_cog.players.values():
                    if player.current and player.vc and player.vc.is_playing():
                        active_song = player.current.title
                        break
            
            if active_song:
                # Set "Listening to"
                activity = discord.Activity(
                    type=discord.ActivityType.listening,
                    name=active_song
                )
            else:
                # Set random idle status
                status = random.choice(self.idle_statuses)
                activity = discord.Activity(
                    type=discord.ActivityType.watching,
                    name=status
                )
            
            await self.bot.change_presence(activity=activity)
            
        except Exception as e:
            log.error(f"[PRESENCE] Error updating presence: {e}")

    @presence_task.before_loop
    async def before_presence_task(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Presence(bot))
