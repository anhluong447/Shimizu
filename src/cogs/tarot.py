import os
import json
import random
import discord
from discord.ext import commands
from discord import app_commands
from src.core.logger import log

TAROT_FILE = 'data/tarot.json'

class Tarot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cards = self._load_cards()

    def _load_cards(self):
        try:
            with open(TAROT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log.error(f"[TAROT] Failed to load cards: {e}")
            return []

    def _draw(self):
        card = random.choice(self.cards)
        reversed_ = random.random() < 0.35  # 35% chance reversed
        return card, reversed_

    def _build_card_embed(self, card, reversed_, label=None):
        direction = "Ngược (Reversed)" if reversed_ else "Xuôi (Upright)"
        meaning = card['rev'] if reversed_ else card['up']
        arrow = "🔻" if reversed_ else "🔺"

        title = f"{card['emoji']} {card['name']}"
        if label:
            title = f"{label} — {title}"

        embed = discord.Embed(
            title=title,
            description=f"**{arrow} {direction}**\n\n>>> {meaning}",
            color=discord.Color.from_str('#6a0dad') if not reversed_ else discord.Color.from_str('#8B0000')
        )
        embed.set_thumbnail(url=card['img'])
        return embed

    @commands.hybrid_group(name='tarot', description='🔮 Hệ thống bói Tarot huyền bí.')
    async def tarot(self, ctx):
        """🔮 Hệ thống bói Tarot huyền bí."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @tarot.command(name='draw', description='Rút 1 lá bài Tarot — Thông điệp cho bạn hôm nay.')
    async def draw(self, ctx):
        """Rút 1 lá bài Tarot — Thông điệp cho bạn hôm nay."""
        if not self.cards:
            return await ctx.send("❌ Không thể tải bộ bài Tarot.")

        card, rev = self._draw()
        embed = self._build_card_embed(card, rev)
        embed.set_author(name=f"🔮 Thông điệp dành cho {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Major Arcana • Shimizu Tarot", icon_url=self.bot.user.display_avatar.url)
        await ctx.send(embed=embed)

    @tarot.command(name='spread', description='Trải 3 lá — Quá Khứ / Hiện Tại / Tương Lai.')
    async def spread(self, ctx):
        """Trải 3 lá bài Tarot — Quá Khứ / Hiện Tại / Tương Lai."""
        if not self.cards:
            return await ctx.send("❌ Không thể tải bộ bài Tarot.")

        drawn = random.sample(self.cards, 3)
        labels = ["🕰️ Quá Khứ", "📍 Hiện Tại", "🔮 Tương Lai"]
        embeds = []

        for i, card in enumerate(drawn):
            rev = random.random() < 0.35
            embed = self._build_card_embed(card, rev, label=labels[i])
            if i == 0:
                embed.set_author(name=f"🔮 Trải bài cho {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
            if i == 2:
                embed.set_footer(text="Major Arcana • Shimizu Tarot", icon_url=self.bot.user.display_avatar.url)
            embeds.append(embed)

        await ctx.send(embeds=embeds)

    @tarot.command(name='love', description='Rút 1 lá bài về chuyện tình cảm.')
    async def love(self, ctx):
        """Rút 1 lá bài Tarot về chuyện tình cảm."""
        if not self.cards:
            return await ctx.send("❌ Không thể tải bộ bài Tarot.")

        card, rev = self._draw()
        embed = self._build_card_embed(card, rev)
        embed.set_author(name=f"💕 Tình duyên của {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Major Arcana • Shimizu Tarot", icon_url=self.bot.user.display_avatar.url)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Tarot(bot))
