import os
import json
import random
import asyncio
from datetime import datetime, timedelta
import discord
from discord.ext import commands
from discord import app_commands
from src.core.logger import log

TAROT_FILE = 'data/tarot.json'
TAROT_HISTORY_FILE = 'data/tarot_history.json'
SHUFFLE_GIF = 'https://media1.tenor.com/m/o6oJ7F-6hAMAAAAd/tarot-cards-reading.gif'

class TarotCardView(discord.ui.View):
    def __init__(self, bot, card, reversed_, affinity, personal_msg=""):
        super().__init__(timeout=600)
        self.bot = bot
        self.card = card
        self.reversed = reversed_
        self.affinity = affinity
        self.personal_msg = personal_msg
        self.show_love = False
        self.show_work = False
        self.embed = self._build_embed()

    def _build_embed(self):
        data = self.card['rev'] if self.reversed else self.card['up']
        direction = "Ngược (Reversed)" if self.reversed else "Xuôi (Upright)"
        arrow = "🔻" if self.reversed else "🔺"
        
        color = discord.Color.from_str('#8B0000') if self.reversed else discord.Color.from_str('#6a0dad')
        embed = discord.Embed(title=f"{self.card['emoji']} {self.card['name']}", color=color)
        
        affinity_text = f"✨ Nhân phẩm: **{self.affinity}%**"
        if self.reversed:
            affinity_text = f"🌑 Năng lượng: **{self.affinity}%**"
        
        embed.description = f"**{arrow} {direction}** | {affinity_text}\n"
        if self.personal_msg:
            embed.description += f"\n{self.personal_msg}"

        kw_str = " • ".join(data['keywords'])
        embed.add_field(name="🔑 Từ khóa", value=f"*{kw_str}*", inline=False)
        embed.add_field(name="📜 Thông điệp chung", value=data['desc'], inline=False)
        
        if self.show_love:
            embed.add_field(name="💕 Tình duyên", value=data['love'], inline=False)
        if self.show_work:
            embed.add_field(name="💼 Sự nghiệp & Tài chính", value=data['work'], inline=False)
            
        embed.add_field(name="💡 Lời khuyên hành động", value=f">>> {data['action']}", inline=False)
        embed.set_thumbnail(url=self.card['img'])
        embed.set_footer(text="Shimizu Tarot • Một quẻ duy nhất cho hiện tại", icon_url=self.bot.user.display_avatar.url)
        return embed

    @discord.ui.button(label="💕 Tình duyên", style=discord.ButtonStyle.secondary, emoji="❤️")
    async def love_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.show_love = True
        self.remove_item(button)
        self.embed = self._build_embed()
        await interaction.response.edit_message(embed=self.embed, view=self)

    @discord.ui.button(label="💼 Sự nghiệp", style=discord.ButtonStyle.secondary, emoji="💰")
    async def work_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.show_work = True
        self.remove_item(button)
        self.embed = self._build_embed()
        await interaction.response.edit_message(embed=self.embed, view=self)

    @discord.ui.button(label="✨ Khoe Nhân Phẩm", style=discord.ButtonStyle.success)
    async def share_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        share_embed = self.embed.copy()
        await interaction.response.send_message(
            f"🌟 **{interaction.user.display_name}** vừa rút được một quẻ Tarot cực xịn!",
            embed=share_embed,
            allowed_mentions=discord.AllowedMentions.none()
        )

class Tarot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cards = self._load_cards()
        self.history = self._load_history()

    def _load_cards(self):
        try:
            with open(TAROT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log.error(f"[TAROT] Failed to load cards: {e}")
            return []

    def _load_history(self):
        if not os.path.exists(TAROT_HISTORY_FILE):
            return {}
        try:
            with open(TAROT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def _save_history(self):
        with open(TAROT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)

    def _draw(self):
        card = random.choice(self.cards)
        reversed_ = random.random() < 0.35
        affinity = random.randint(10, 99)
        return card, reversed_, affinity

    @commands.hybrid_group(name='tarot', description='🔮 Hệ thống bói Tarot huyền bí.')
    async def tarot(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @tarot.command(name='draw', description='Rút 1 lá bài Tarot duy nhất (Cooldown 12h).')
    @app_commands.checks.cooldown(1, 43200, key=lambda i: (i.guild_id, i.user.id))
    async def draw(self, ctx):
        if not self.cards:
            return await ctx.send("❌ Không thể tải bộ bài Tarot.")

        user_id = str(ctx.author.id)
        wait_embed = discord.Embed(title="🔮 Vũ trụ đang gửi thông điệp...", color=discord.Color.dark_purple())
        wait_embed.set_image(url=SHUFFLE_GIF)
        msg = await ctx.send(embed=wait_embed, ephemeral=True)
        
        await asyncio.sleep(2.5)
        card, rev, affinity = self._draw()
        
        personal_msg = ""
        if user_id in self.history:
            last_card = self.history[user_id].get('last_draw')
            if last_card == card['id']:
                personal_msg = "👁️‍🗨️ Lại là lá này à? Có vẻ Vũ trụ đang cố tình nhắc nhở bạn đấy!"
            elif rev and self.history[user_id].get('last_rev'):
                personal_msg = "👁️‍🗨️ Lại là một lá ngược. Năng lượng của bạn dạo này hơi tắc nghẽn rồi đấy."

        self.history[user_id] = {'last_draw': card['id'], 'last_rev': rev, 'timestamp': datetime.now().isoformat()}
        self._save_history()

        view = TarotCardView(self.bot, card, rev, affinity, personal_msg)
        await msg.edit(embed=view.embed, view=view)

    @draw.error
    async def draw_error(self, ctx, error):
        if isinstance(error, (commands.CommandOnCooldown, app_commands.CommandOnCooldown)):
            hours, remainder = divmod(int(error.retry_after), 3600)
            minutes, _ = divmod(remainder, 60)
            await ctx.send(f"⏳ Hãy quay lại rút quẻ ngày sau **{hours}h {minutes}m** nữa nhé!", ephemeral=True)

    @tarot.command(name='spread', description='Trải 3 lá — Quá Khứ / Hiện Tại / Tương Lai.')
    @app_commands.checks.cooldown(1, 3600, key=lambda i: (i.guild_id, i.user.id))
    async def spread(self, ctx):
        if not self.cards: return
        wait_embed = discord.Embed(title="🔮 Đang liên kết với Dòng thời gian...", color=discord.Color.dark_purple())
        wait_embed.set_image(url=SHUFFLE_GIF)
        msg = await ctx.send(embed=wait_embed, ephemeral=True)
        await asyncio.sleep(3)

        drawn = random.sample(self.cards, 3)
        labels = ["🕰️ Quá Khứ", "📍 Hiện Tại", "🔮 Tương Lai"]
        embeds = []
        for i, card in enumerate(drawn):
            rev = random.random() < 0.35
            affinity = random.randint(10, 99)
            
            data = card['rev'] if rev else card['up']
            color = discord.Color.from_str('#8B0000') if rev else discord.Color.from_str('#6a0dad')
            embed = discord.Embed(title=f"{labels[i]} — {card['emoji']} {card['name']}", color=color)
            embed.description = f"**{'🔻 Ngược' if rev else '🔺 Xuôi'}** | Nhân phẩm: **{affinity}%**\n"
            embed.add_field(name="📜 Thông điệp", value=data['desc'], inline=False)
            embed.add_field(name="💡 Lời khuyên", value=f">>> {data['action']}", inline=False)
            embed.set_thumbnail(url=card['img'])
            if i == 2: embed.set_footer(text="Shimizu Tarot")
            embeds.append(embed)

        await msg.edit(embeds=embeds)

async def setup(bot):
    await bot.add_cog(Tarot(bot))
