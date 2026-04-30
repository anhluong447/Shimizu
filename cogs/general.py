import discord
from discord.ext import commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        """Kiểm tra độ trễ của bot"""
        await ctx.send(f'🏓 Pong! Latency: {round(self.bot.latency * 1000)}ms')

    @commands.command()
    async def hello(self, ctx):
        """Chào hỏi người dùng"""
        await ctx.send(f'Chào bồ {ctx.author.name}! Mình là Shimizu, hân hạnh được phục vụ! 🌸')

async def setup(bot):
    await bot.add_cog(General(bot))
