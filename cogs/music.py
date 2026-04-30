import discord
import asyncio
import yt_dlp
import itertools
from discord.ext import commands

# Cấu hình yt-dlp
ytdl_format_options = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)
# Đường dẫn tương đối từ gốc project
ffmpeg_exe = r'ffmpeg-8.1-essentials_build\bin\ffmpeg.exe'

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, executable=ffmpeg_exe, **ffmpeg_options), data=data)

class MusicPlayer:
    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.np = None
        self.volume = .5
        self.current = None

        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next.clear()

            try:
                async with asyncio.timeout(300):
                    source = await self.queue.get()
            except asyncio.TimeoutError:
                return self.destroy(self._guild)

            source.volume = self.volume
            self.current = source

            self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
            self.np = await self._channel.send(f'🎵 **Đang phát:** `{source.title}`')
            
            await self.next.wait()
            source.cleanup()
            self.current = None

    def destroy(self, guild):
        return self.bot.loop.create_task(self._cog.cleanup(guild))

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass
        try:
            del self.players[guild.id]
        except KeyError:
            pass

    def get_player(self, ctx):
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx)
            self.players[ctx.guild.id] = player
        return player

    @commands.command(name='play', aliases=['p'])
    async def play_(self, ctx, *, search: str):
        vc = ctx.voice_client
        if not vc:
            await ctx.invoke(self.join)

        player = self.get_player(ctx)
        async with ctx.typing():
            source = await YTDLSource.from_url(search, loop=self.bot.loop, stream=True)
            await player.queue.put(source)
        await ctx.send(f'✅ Đã thêm vào hàng đợi: `{source.title}`')

    @commands.command(name='join', aliases=['j'])
    async def join(self, ctx):
        if not ctx.author.voice:
            return await ctx.send("Bồ phải vào phòng voice trước!")
        destination = ctx.author.voice.channel
        if ctx.voice_client:
            await ctx.voice_client.move_to(destination)
        else:
            await destination.connect()

    @commands.command(name='skip', aliases=['s'])
    async def skip(self, ctx):
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send("Không có nhạc đang phát để skip!")
        ctx.voice_client.stop()
        await ctx.send("⏭️ Đã bỏ qua bài hiện tại.")

    @commands.command(name='queue', aliases=['q'])
    async def queue_info(self, ctx):
        player = self.get_player(ctx)
        if player.queue.empty():
            return await ctx.send("Hàng đợi đang trống không!")
        upcoming = list(itertools.islice(player.queue._queue, 0, 5))
        fmt = '\n'.join(f"**{i+1}.** `{song.title}`" for i, song in enumerate(upcoming))
        await ctx.send(f"📋 **Hàng đợi hiện tại:**\n{fmt}")

    @commands.command(name='stop', aliases=['leave'])
    async def stop(self, ctx):
        await self.cleanup(ctx.guild)
        await ctx.send("👋 Tạm biệt bồ!")

async def setup(bot):
    await bot.add_cog(Music(bot))
