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

class ShareTarotView(discord.ui.View):
    def __init__(self, bot, embed):
        super().__init__(timeout=None)
        self.bot = bot
        self.embed = embed

    @discord.ui.button(label="Khoe Nhân Phẩm", style=discord.ButtonStyle.success, emoji="✨")
    async def share_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"🌟 **{interaction.user.display_name}** vừa rút được một quẻ Tarot cực xịn!",
            embed=self.embed,
            allowed_mentions=discord.AllowedMentions.none()
        )
        self.stop()

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

    def _draw(self, card_pool=None):
        if not card_pool:
            card_pool = self.cards
        card = random.choice(card_pool)
        reversed_ = random.random() < 0.35  # 35% chance reversed
        affinity = random.randint(10, 99)
        return card, reversed_, affinity

    def _build_card_embed(self, card, reversed_, affinity, mode="general", label=None):
        direction = "Ngược (Reversed)" if reversed_ else "Xuôi (Upright)"
        data = card['rev'] if reversed_ else card['up']
        arrow = "🔻" if reversed_ else "🔺"

        title = f"{card['emoji']} {card['name']}"
        if label:
            title = f"{label} — {title}"

        color = discord.Color.from_str('#8B0000') if reversed_ else discord.Color.from_str('#6a0dad')
        embed = discord.Embed(title=title, color=color)
        
        # Affinity Bar
        affinity_text = f"✨ Nhân phẩm: **{affinity}%**"
        if reversed_:
            affinity_text = f"🌑 Năng lượng: **{affinity}%**"
        embed.description = f"**{arrow} {direction}** | {affinity_text}\n"

        # Keywords
        kw_str = " • ".join(data['keywords'])
        embed.add_field(name="🔑 Từ khóa", value=f"*{kw_str}*", inline=False)
        
        # Description (General)
        embed.add_field(name="📜 Thông điệp chung", value=data['desc'], inline=False)
        
        # Love & Relationship (Only in love or draw mode if you want, but user wants them separate)
        if mode == "love":
            embed.add_field(name="💕 Tình duyên", value=data['love'], inline=False)
        
        # Career & Finance
        if mode == "work":
            embed.add_field(name="💼 Sự nghiệp & Tài chính", value=data['work'], inline=False)
        
        # Action
        embed.add_field(name="💡 Lời khuyên hành động", value=f">>> {data['action']}", inline=False)

        embed.set_thumbnail(url=card['img'])
        return embed

    @commands.hybrid_group(name='tarot', description='🔮 Hệ thống bói Tarot huyền bí.')
    async def tarot(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @tarot.command(name='draw', description='Rút 1 lá bài Tarot — Thông điệp cho bạn hôm nay (Cooldown 12h).')
    @app_commands.checks.cooldown(1, 43200, key=lambda i: (i.guild_id, i.user.id))
    async def draw(self, ctx):
        """Rút 1 lá bài Tarot — Thông điệp cho bạn hôm nay."""
        if not self.cards:
            return await ctx.send("❌ Không thể tải bộ bài Tarot.")

        user_id = str(ctx.author.id)
        
        # Animation
        wait_embed = discord.Embed(
            title="🔮 Vũ trụ đang gửi thông điệp...",
            description="Đang xào bài, xin hãy tĩnh tâm...",
            color=discord.Color.dark_purple()
        )
        wait_embed.set_image(url=SHUFFLE_GIF)
        msg = await ctx.send(embed=wait_embed, ephemeral=True)
        
        await asyncio.sleep(2.5)

        card, rev, affinity = self._draw()
        
        # Check history for personalized message
        personal_msg = ""
        if user_id in self.history:
            last_card = self.history[user_id].get('last_draw')
            if last_card == card['id']:
                personal_msg = "👁️‍🗨️ Lại là lá này à? Có vẻ Vũ trụ đang cố tình nhắc nhở bạn đấy, đừng phớt lờ!"
            elif rev and self.history[user_id].get('last_rev'):
                personal_msg = "👁️‍🗨️ Lại là một lá ngược. Năng lượng của bạn dạo này hơi tắc nghẽn rồi đấy bấy bi."

        # Save history
        self.history[user_id] = {
            'last_draw': card['id'],
            'last_rev': rev,
            'timestamp': datetime.now().isoformat()
        }
        self._save_history()

        embed = self._build_card_embed(card, rev, affinity, mode="general")
        embed.set_author(name=f"🔮 Trải bài của {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Shimizu Tarot", icon_url=self.bot.user.display_avatar.url)

        if personal_msg:
            embed.description = f"{embed.description}\n{personal_msg}"

        view = ShareTarotView(self.bot, embed)
        await msg.edit(embed=embed, view=view)

    @draw.error
    async def draw_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown) or isinstance(error, app_commands.CommandOnCooldown):
            hours, remainder = divmod(int(error.retry_after), 3600)
            minutes, _ = divmod(remainder, 60)
            await ctx.send(f"⏳ Vũ trụ cần thời gian nghỉ ngơi. Hãy quay lại rút quẻ ngày sau **{hours}h {minutes}m** nữa nhé!")
        else:
            log.error(f"Tarot draw error: {error}")

    @tarot.command(name='spread', description='Trải 3 lá — Quá Khứ / Hiện Tại / Tương Lai.')
    @app_commands.checks.cooldown(1, 3600, key=lambda i: (i.guild_id, i.user.id))
    async def spread(self, ctx):
        """Trải 3 lá bài Tarot — Quá Khứ / Hiện Tại / Tương Lai."""
        if not self.cards:
            return await ctx.send("❌ Không thể tải bộ bài Tarot.")

        # Animation
        wait_embed = discord.Embed(
            title="🔮 Đang liên kết với Dòng thời gian...",
            color=discord.Color.dark_purple()
        )
        wait_embed.set_image(url=SHUFFLE_GIF)
        msg = await ctx.send(embed=wait_embed, ephemeral=True)
        await asyncio.sleep(3)

        drawn = random.sample(self.cards, 3)
        labels = ["🕰️ Quá Khứ", "📍 Hiện Tại", "🔮 Tương Lai"]
        embeds = []

        for i, card in enumerate(drawn):
            rev = random.random() < 0.35
            affinity = random.randint(10, 99)
            embed = self._build_card_embed(card, rev, affinity, mode="spread", label=labels[i])
            if i == 0:
                embed.set_author(name=f"🔮 Dòng thời gian của {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
            if i == 2:
                embed.set_footer(text="Shimizu Tarot", icon_url=self.bot.user.display_avatar.url)
            embeds.append(embed)

        await msg.edit(embeds=embeds)

    @spread.error
    async def spread_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown) or isinstance(error, app_commands.CommandOnCooldown):
            minutes = int(error.retry_after) // 60
            await ctx.send(f"⏳ Nhìn thấu tương lai quá nhiều sẽ làm xáo trộn nhân quả. Vui lòng thử lại sau **{minutes} phút**.")

    @tarot.command(name='love', description='Rút 1 lá bài về Tình Duyên (Sử dụng bộ Cốc & Ẩn chính).')
    @app_commands.checks.cooldown(1, 1800, key=lambda i: (i.guild_id, i.user.id))
    async def love(self, ctx):
        if not self.cards: return
        
        # Filter for Love (Cups + specific Major cards)
        love_pool = [c for c in self.cards if c['type'] == 'cups' or c['id'] in ['major_2', 'major_3', 'major_6', 'major_17', 'major_19']]
        if not love_pool: love_pool = self.cards

        wait_embed = discord.Embed(title="💕 Đang kết nối với Cảm xúc...", color=discord.Color.from_str('#ff69b4'))
        wait_embed.set_image(url=SHUFFLE_GIF)
        msg = await ctx.send(embed=wait_embed, ephemeral=True)
        await asyncio.sleep(2.5)

        card, rev, affinity = self._draw(love_pool)
        embed = self._build_card_embed(card, rev, affinity, mode="love")
        embed.set_author(name=f"💕 Tình duyên của {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Shimizu Love Tarot", icon_url=self.bot.user.display_avatar.url)
        
        view = ShareTarotView(self.bot, embed)
        await msg.edit(embed=embed, view=view)

    @tarot.command(name='work', description='Rút 1 lá bài về Công Việc/Tài Chính (Bộ Tiền, Kiếm & Ẩn chính).')
    @app_commands.checks.cooldown(1, 1800, key=lambda i: (i.guild_id, i.user.id))
    async def work(self, ctx):
        if not self.cards: return
        
        # Filter for Work (Pentacles + Swords + specific Major cards)
        work_pool = [c for c in self.cards if c['type'] in ['pentacles', 'swords', 'wands'] or c['id'] in ['major_1', 'major_4', 'major_7', 'major_8', 'major_10', 'major_11']]
        if not work_pool: work_pool = self.cards

        wait_embed = discord.Embed(title="🪙 Đang tính toán Mệnh tài vận...", color=discord.Color.gold())
        wait_embed.set_image(url=SHUFFLE_GIF)
        msg = await ctx.send(embed=wait_embed, ephemeral=True)
        await asyncio.sleep(2.5)

        card, rev, affinity = self._draw(work_pool)
        embed = self._build_card_embed(card, rev, affinity, mode="work")
        embed.set_author(name=f"💼 Sự nghiệp của {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Shimizu Career Tarot", icon_url=self.bot.user.display_avatar.url)
        
        view = ShareTarotView(self.bot, embed)
        await msg.edit(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Tarot(bot))
