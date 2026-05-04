import discord
from discord.ext import commands, tasks
import random
import time
from src.core.logger import log

class Presence(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # State tracking để tối ưu tài nguyên (chỉ update khi cần)
        self.current_mode = None  # 'music' hoặc 'idle'
        self.last_song_name = None
        self.last_paused_state = None
        self.last_idle_update = 0
        self.idle_change_interval = 600  # 10 phút mới đổi mood một lần
        
        self.idle_statuses = [
            "Đang coi mây bay ☁️",
            "Tui đang chờ nhạc nè... 🎵",
            "Đang coi thời tiết nha 🌦️",
            "Chill chill trong server 🌸",
            "Đang đọc tâm trí Meng... 🧠",
            "Lắng nghe con tim của em... ❤️",
            "Đang ngắm sao đêm ✨"
        ]
        
        self.presence_task.start()

    def cog_unload(self):
        self.presence_task.cancel()

    @tasks.loop(seconds=15)
    async def presence_task(self):
        """
        Quy trình tối ưu: 
        1. Kiểm tra nhạc mỗi 15s để đảm bảo cập nhật bài hát nhanh.
        2. Chỉ gọi API Discord khi có sự thay đổi (bài mới, pause/resume, hoặc hết hạn idle).
        """
        try:
            # 1. Kiểm tra trạng thái nhạc
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
            
            now = time.time()
            should_update = False
            new_activity = None
            
            # 2. Logic quyết định cập nhật
            if active_song:
                # CHẾ ĐỘ NGHE NHẠC: Ưu tiên cập nhật ngay khi đổi bài hoặc pause/resume
                if (self.current_mode != 'music' or 
                    active_song != self.last_song_name or 
                    is_paused != self.last_paused_state):
                    
                    should_update = True
                    self.current_mode = 'music'
                    self.last_song_name = active_song
                    self.last_paused_state = is_paused
                    
                    activity_name = f"{'⏸️ ' if is_paused else '🌸🎵 Đang nghe: '}{active_song}"
                    new_activity = discord.Activity(
                        type=discord.ActivityType.listening,
                        name=activity_name
                    )
            else:
                # CHẾ ĐỘ IDLE (Tâm trạng): Chỉ cập nhật khi vừa dừng nhạc hoặc sau 10 phút
                if (self.current_mode != 'idle' or 
                    now - self.last_idle_update > self.idle_change_interval):
                    
                    should_update = True
                    self.current_mode = 'idle'
                    self.last_song_name = None
                    self.last_paused_state = None
                    self.last_idle_update = now
                    
                    status = random.choice(self.idle_statuses)
                    new_activity = discord.Activity(
                        type=discord.ActivityType.watching,
                        name=status
                    )

            # 3. Chỉ thực hiện cập nhật nếu thực sự cần thiết (Tiết kiệm API & Tài nguyên)
            if should_update and new_activity:
                await self.bot.change_presence(activity=new_activity)
                
        except Exception as e:
            log.error(f"[PRESENCE] Error updating presence: {e}")

    @presence_task.before_loop
    async def before_presence_task(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Presence(bot))
