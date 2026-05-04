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

    @tasks.loop(seconds=20)
    async def presence_task(self):
        try:
            # 1. Check for active music
            music_cog = self.bot.get_cog('Music')
            active_song = None
            is_paused = False
            
            if music_cog and hasattr(music_cog, 'players'):
                for player in music_cog.players.values():
                    if player.current:
                        vc = player.guild.voice_client
                        if vc:
                            active_song = player.current.title
                            is_paused = vc.is_paused()
                            break
            
            if active_song:
                # Set "Listening to"
                activity_name = f"{'⏸️ ' if is_paused else 'Đang nghe:'}{active_song}"
                activity = discord.Activity(
                    type=discord.ActivityType.listening,
                    name=activity_name
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

    @commands.Cog.listener()
    async def on_song_start(self, guild_id, song):
        """Listener triggered by MusicPlayer (if implemented) or we can just wait for the task."""
        # Since the task runs every 20s, it's pretty fast. 
        # But we can trigger an immediate update if we want.
        self.presence_task.restart()

    @presence_task.before_loop
    async def before_presence_task(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Presence(bot))
