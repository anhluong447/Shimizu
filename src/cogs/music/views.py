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
    embed.set_author(name=status, icon_url='https://i.imgur.com/JfETopg.png')
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

    @discord.ui.button(emoji='⏸️', style=discord.ButtonStyle.secondary, custom_id='ctrl_pause')
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message('Bot không ở trong voice!', ephemeral=True)
        self.player.auto_paused = False

        if vc.is_playing():
            vc.pause()
            self.player.pause_time = time.time()
            button.emoji = '▶️'
        elif vc.is_paused():
            self.player.total_paused += time.time() - self.player.pause_time
            vc.resume()
            button.emoji = '⏸️'
        await self._update_np(interaction)

    @discord.ui.button(emoji='⏭️', style=discord.ButtonStyle.primary, custom_id='ctrl_skip')
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            from src.core.config import REPEAT_ONE, REPEAT_OFF
            self.player.repeat_mode = REPEAT_OFF if self.player.repeat_mode == REPEAT_ONE else self.player.repeat_mode
            vc.stop()
            await interaction.response.send_message('⏭️ Đã bỏ qua!', ephemeral=True, delete_after=3)
        else:
            await interaction.response.send_message('Không có gì để skip!', ephemeral=True)

    @discord.ui.button(emoji='⏹️', style=discord.ButtonStyle.danger, custom_id='ctrl_stop')
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.queue.clear()
        vc = interaction.guild.voice_client
        if vc:
            vc.stop()
        await interaction.response.send_message('⏹️ Đã dừng và xóa hàng đợi!', ephemeral=True, delete_after=3)

    @discord.ui.button(emoji='🔀', style=discord.ButtonStyle.secondary, custom_id='ctrl_shuffle')
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.player.queue) < 2:
            return await interaction.response.send_message('Hàng đợi quá ít để trộn!', ephemeral=True)
        random.shuffle(self.player.queue)
        await interaction.response.send_message('🔀 Đã trộn hàng đợi!', ephemeral=True, delete_after=3)

    @discord.ui.button(emoji='🔁', style=discord.ButtonStyle.secondary, custom_id='ctrl_repeat')
    async def repeat(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.repeat_mode = (self.player.repeat_mode + 1) % 3
        await self._update_np(interaction)

    @discord.ui.button(emoji='✨', style=discord.ButtonStyle.secondary, custom_id='ctrl_autoplay')
    async def autoplay(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.autoplay = not self.player.autoplay
        await self._update_np(interaction)

    @discord.ui.button(emoji='🔉', style=discord.ButtonStyle.secondary, custom_id='ctrl_voldown')
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.volume = max(0.0, self.player.volume - 0.1)
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = self.player.volume
        await self._update_np(interaction)

    @discord.ui.button(emoji='🔊', style=discord.ButtonStyle.secondary, custom_id='ctrl_volup')
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.volume = min(2.0, self.player.volume + 0.1)
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = self.player.volume
        await self._update_np(interaction)

    async def _update_np(self, interaction):
        if not self.player.current:
            return await interaction.response.defer()
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
        self.results = results
        self.requester = requester
        options = []
        for i, r in enumerate(results):
            dur = int(r.get('duration') or 0)
            dur_str = f'{dur // 60}:{dur % 60:02d}' if dur else 'Live'
            uploader = r.get('uploader') or r.get('channel') or 'Unknown'
            options.append(discord.SelectOption(
                label=r.get('title', 'Unknown')[:100],
                description=f'{uploader} • {dur_str}'[:100],
                value=str(i),
            ))
        super().__init__(placeholder='🔍 Chọn bài hát...', options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        from .models import SongInfo
        idx = int(self.values[0])
        chosen_raw_data = self.results[idx]
        cog = interaction.client.get_cog('Music')
        if not cog:
            return

        player = cog.get_player(interaction)
        await interaction.response.edit_message(content=f'⏳ Đang thêm: **{chosen_raw_data.get("title", "Unknown")}**...', view=None)

        song = await SongInfo.from_url(chosen_raw_data, requester=self.requester, loop=interaction.client.loop)
        player.queue.append(song)
        # Chỉ kick-start loop nếu bot đang rảnh
        vc = interaction.guild.voice_client
        if vc and not (vc.is_playing() or vc.is_paused()):
            player.next.set()

        await interaction.edit_original_response(content=f'✅ Đã thêm: **{song.title}** `[{song.duration_str}]`')


class SearchView(discord.ui.View):
    def __init__(self, results, requester):
        super().__init__(timeout=30)
        self.add_item(SearchSelect(results, requester))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
