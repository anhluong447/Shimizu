import discord
import time
import random
from src.core.config import REPEAT_OFF, REPEAT_ONE, REPEAT_LABELS, AUTOPLAY_LABELS
from src.utils.formatters import create_progress_bar

def build_np_embed(song, paused=False, repeat=REPEAT_OFF, audio_filter='Normal', autoplay=False, volume=0.5, current_time=0):
    status = '⏸️ Đang tạm dừng' if paused else '🎵 Đang phát'
    embed = discord.Embed(
        title=song.title,
        url=song.url,
        color=discord.Color.from_str('#FF6B9D') if not paused else discord.Color.greyple(),
    )
    embed.set_author(name=status)
    if song.thumbnail:
        embed.set_thumbnail(url=song.thumbnail)
    
    bar = create_progress_bar(current_time, song.duration)
    cur_str = f'{int(current_time // 60)}:{int(current_time % 60):02d}'
    dur_str = song.duration_str
    
    embed.add_field(name='⏱️ Tiến trình', value=f'`{cur_str}` {bar} `{dur_str}`', inline=False)
    embed.add_field(name='🎤 Kênh', value=f'`{song.uploader}`', inline=True)
    embed.add_field(name='🔊 Âm lượng', value=f'`{int(volume * 100)}%`', inline=True)
    embed.add_field(name='🔊 Bộ lọc', value=f'`{audio_filter}`', inline=True)
    embed.add_field(name='🔁 Lặp lại', value=f'`{REPEAT_LABELS[repeat]}`', inline=True)
    embed.add_field(name='✨ Autoplay', value=f'`{AUTOPLAY_LABELS[autoplay]}`', inline=True)
    embed.set_footer(text=f'Yêu cầu bởi {song.requester.display_name}', icon_url=song.requester.display_avatar.url)
    return embed

class ControllerView(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=None)
        self.player = player

    @discord.ui.button(emoji='⏸️', style=discord.ButtonStyle.secondary)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc: return
        
        if vc.is_playing():
            vc.pause()
            self.player.pause_time = time.time()
        elif vc.is_paused():
            self.player.total_paused += time.time() - self.player.pause_time
            vc.resume()
        await self._update_np(interaction)

    @discord.ui.button(emoji='⏭️', style=discord.ButtonStyle.primary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            if self.player.repeat_mode == REPEAT_ONE:
                self.player.repeat_mode = REPEAT_OFF
            vc.stop()
            await interaction.response.send_message('⏭️ Đã bỏ qua!', ephemeral=True, delete_after=3)

    @discord.ui.button(emoji='⏹️', style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.queue.clear()
        vc = interaction.guild.voice_client
        if vc: vc.stop()
        await interaction.response.send_message('⏹️ Đã dừng!', ephemeral=True, delete_after=3)

    @discord.ui.button(emoji='🔀', style=discord.ButtonStyle.secondary)
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.player.queue) < 2:
            return await interaction.response.send_message('Hàng đợi quá ít!', ephemeral=True)
        lst = list(self.player.queue)
        random.shuffle(lst)
        self.player.queue.clear()
        self.player.queue.extend(lst)
        await interaction.response.send_message('🔀 Đã trộn!', ephemeral=True, delete_after=3)

    async def _update_np(self, interaction):
        if not self.player.current: return
        vc = interaction.guild.voice_client
        paused = vc.is_paused() if vc else False
        embed = build_np_embed(
            self.player.current, 
            paused=paused, 
            repeat=self.player.repeat_mode, 
            audio_filter=self.player.filter_name, 
            autoplay=self.player.autoplay, 
            volume=self.player.volume,
            current_time=self.player.get_current_time()
        )
        await interaction.response.edit_message(embed=embed, view=self)

class SearchSelect(discord.ui.Select):
    def __init__(self, results, requester):
        options = []
        for i, r in enumerate(results):
            dur = int(r.get('duration') or 0)
            dur_str = f'{dur // 60}:{dur % 60:02d}'
            options.append(discord.SelectOption(
                label=r.get('title', 'Unknown')[:100],
                description=f"{r.get('uploader', 'Unknown')} • {dur_str}",
                value=str(i),
            ))
        super().__init__(placeholder='🔍 Chọn bài hát...', options=options)
        self.results = results
        self.requester = requester

    async def callback(self, interaction: discord.Interaction):
        from .models import SongInfo
        idx = int(self.values[0])
        data = self.results[idx]
        cog = interaction.client.get_cog('Music')
        player = cog.get_player(interaction)
        await interaction.response.edit_message(content=f"⏳ Đang thêm: **{data.get('title')}**...", view=None)
        song = await SongInfo.from_url(data, requester=self.requester, loop=interaction.client.loop)
        player.queue.append(song)
        if not interaction.guild.voice_client.is_playing():
            player.next.set()
        await interaction.edit_original_response(content=f"✅ Đã thêm: **{song.title}**")

class SearchView(discord.ui.View):
    def __init__(self, results, requester):
        super().__init__(timeout=30)
        self.add_item(SearchSelect(results, requester))
