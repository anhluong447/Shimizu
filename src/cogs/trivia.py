import os
import json
import random
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from src.core.config import SECRET_KEY
from src.services.crypto import decrypt_data
from src.core.logger import log

TRIVIA_ENC_FILE = 'data/trivia.ann'

class TriviaGameView(discord.ui.View):
    def __init__(self, bot, questions, target_player, partner_player, mode='self'):
        super().__init__(timeout=300)
        self.bot = bot
        self.questions = questions
        self.target_player = target_player
        self.partner_player = partner_player
        self.mode = mode # 'self' or 'guess'
        self.current_idx = 0
        self.answers = []
        self.last_interaction = None

    def create_embed(self):
        q_data = self.questions[self.current_idx]
        title = "🎮 Trivia Đôi: Hiểu Ý Đối Phương"
        if self.mode == 'self':
            desc = f"**Câu {self.current_idx + 1}/10: Về bản thân bạn**\n\n### {q_data['q']}"
            footer = "Chọn đáp án đúng nhất về bản thân bạn."
        else:
            desc = f"**Câu {self.current_idx + 1}/10: Đoán về {self.partner_player.display_name}**\n\n### {q_data['q']}"
            footer = f"Bạn nghĩ {self.partner_player.display_name} đã chọn đáp án nào?"

        embed = discord.Embed(title=title, description=desc, color=discord.Color.from_str('#ffb6c1'))
        embed.set_footer(text=footer)
        return embed

    def add_buttons(self):
        self.clear_items()
        q_data = self.questions[self.current_idx]
        for i, option in enumerate(q_data['o']):
            button = discord.ui.Button(label=option, custom_id=str(i), style=discord.ButtonStyle.secondary)
            button.callback = self.button_callback
            self.add_item(button)

    async def button_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.target_player.id:
            return await interaction.response.send_message("Đây không phải lượt của bạn!", ephemeral=True)
        
        self.answers.append(int(interaction.data['custom_id']))
        self.current_idx += 1

        if self.current_idx < len(self.questions):
            self.add_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            self.last_interaction = interaction
            await interaction.response.edit_message(content="✅ Đã xong phần này! Đang chờ đối phương...", embed=None, view=None)
            self.stop()

class Trivia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {}

    def load_questions(self):
        if not os.path.exists(TRIVIA_ENC_FILE):
            return []
        try:
            with open(TRIVIA_ENC_FILE, 'r', encoding='utf-8') as f:
                enc_data = f.read()
            dec_data = decrypt_data(enc_data, SECRET_KEY)
            return json.loads(dec_data)
        except Exception as e:
            log.error(f"Trivia load error: {e}")
            return []

    @commands.hybrid_command(name='trivia', description='Bắt đầu trò chơi trắc nghiệm thấu hiểu cặp đôi.')
    async def trivia(self, ctx):
        """Bắt đầu trò chơi trắc nghiệm thấu hiểu cặp đôi."""
        if ctx.guild.id in self.active_sessions:
            return await ctx.send("❌ Đang có một phiên chơi đang diễn ra trong server này!")

        questions_pool = self.load_questions()
        if not questions_pool:
            return await ctx.send("❌ Không thể tải bộ câu hỏi. Vui lòng kiểm tra lại dữ liệu.")

        game_questions = random.sample(questions_pool, 10)
        
        embed = discord.Embed(
            title="🎮 Couple Trivia: Thử Thách Thấu Hiểu",
            description=(
                "Chào mừng hai bạn đến với game hiểu ý nhau! 🌸\n\n"
                "**Luật chơi:**\n"
                "1. Hai bạn cùng tham gia.\n"
                "2. Mỗi người trả lời 10 câu về bản thân.\n"
                "3. Sau đó mỗi người đoán câu trả lời của đối phương.\n"
                "4. Bot sẽ tính % thấu hiểu!\n\n"
                "Bấm nút dưới đây để tham gia (Cần đủ 2 người)."
            ),
            color=discord.Color.from_str('#ffb6c1')
        )

        view = discord.ui.View()
        players = []
        player_interactions = {}

        async def join_callback(interaction: discord.Interaction):
            if interaction.user in players:
                return await interaction.response.send_message("Bạn đã tham gia rồi!", ephemeral=True)
            if len(players) >= 2:
                return await interaction.response.send_message("Đã đủ 2 người chơi!", ephemeral=True)
            
            players.append(interaction.user)
            player_interactions[interaction.user] = interaction
            await interaction.response.send_message(f"✅ {interaction.user.display_name} đã tham gia!", delete_after=5)
            
            if len(players) == 2:
                await start_game()

        join_btn = discord.ui.Button(label="Tham gia", style=discord.ButtonStyle.primary)
        join_btn.callback = join_callback
        view.add_item(join_btn)

        msg = await ctx.send(embed=embed, view=view)

        async def start_game():
            join_btn.disabled = True
            await msg.edit(content="🚀 Trò chơi bắt đầu! Hãy kiểm tra tin nhắn ẩn bên dưới.", embed=None, view=None)
            
            p1, p2 = players
            i1 = player_interactions[p1]
            i2 = player_interactions[p2]
            
            # Phase 1: Self Answers
            v1 = TriviaGameView(self.bot, game_questions, p1, p2, mode='self')
            v1.add_buttons()
            v2 = TriviaGameView(self.bot, game_questions, p2, p1, mode='self')
            v2.add_buttons()

            await ctx.channel.send(f"➡️ **Giai đoạn 1:** {p1.mention} và {p2.mention} hãy trả lời về chính mình!", delete_after=10)
            
            # Gửi tin nhắn ẩn riêng biệt cho từng người thông qua interaction của họ
            await i1.followup.send(embed=v1.create_embed(), view=v1, ephemeral=True)
            await i2.followup.send(embed=v2.create_embed(), view=v2, ephemeral=True)

            await asyncio.gather(v1.wait(), v2.wait())
            
            # Xóa tin nhắn ẩn "Đã xong" của Giai đoạn 1
            try:
                await v1.last_interaction.delete_original_response()
                await v2.last_interaction.delete_original_response()
            except: pass

            # Phase 2: Guessing
            v1_guess = TriviaGameView(self.bot, game_questions, p1, p2, mode='guess')
            v1_guess.add_buttons()
            v2_guess = TriviaGameView(self.bot, game_questions, p2, p1, mode='guess')
            v2_guess.add_buttons()

            await ctx.channel.send(f"➡️ **Giai đoạn 2:** Bây giờ hãy thử đoán xem đối phương đã chọn gì!", delete_after=10)
            
            # Sử dụng interaction cuối cùng của Phase 1 để gửi tiếp tin nhắn ẩn cho Phase 2
            await v1.last_interaction.followup.send(embed=v1_guess.create_embed(), view=v1_guess, ephemeral=True)
            await v2.last_interaction.followup.send(embed=v2_guess.create_embed(), view=v2_guess, ephemeral=True)

            await asyncio.gather(v1_guess.wait(), v2_guess.wait())

            # Xóa tin nhắn ẩn "Đã xong" của Giai đoạn 2
            try:
                await v1_guess.last_interaction.delete_original_response()
                await v2_guess.last_interaction.delete_original_response()
            except: pass

            # Final Result
            score1 = 0 # P1 guesses for P2
            for i in range(10):
                if v1_guess.answers[i] == v2.answers[i]:
                    score1 += 1
            
            score2 = 0 # P2 guesses for P1
            for i in range(10):
                if v2_guess.answers[i] == v1.answers[i]:
                    score2 += 1
            
            total_percent = ((score1 + score2) / 20) * 100
            
            result_embed = discord.Embed(
                title="🏆 Kết Quả Thấu Hiểu",
                description=(
                    f"Cặp đôi: {p1.mention} ❤️ {p2.mention}\n\n"
                    f"👤 **{p1.display_name}** đoán đúng về đối phương: `{score1}/10`\n"
                    f"👤 **{p2.display_name}** đoán đúng về đối phương: `{score2}/10`\n\n"
                    f"### 📊 Mức độ thấu hiểu: `{total_percent}%`"
                ),
                color=discord.Color.from_str('#ff69b4')
            )

            if total_percent == 100:
                comment = "💎 Hai bạn sinh ra là dành cho nhau! Tuyệt vời!"
            elif total_percent >= 80:
                comment = "🌟 Hai bạn cực kỳ hiểu ý nhau đấy!"
            elif total_percent >= 50:
                comment = "🌸 Khá ổn, nhưng hãy dành thêm thời gian để tìm hiểu nhau nhé!"
            else:
                comment = "🍵 Có vẻ hai bạn cần phải 'update' thông tin về nhau nhiều hơn rồi!"
            
            result_embed.add_field(name="💬 Nhận xét của Shimizu", value=comment)
            await ctx.channel.send(embed=result_embed)
            
            # Dọn dẹp nốt tin nhắn gốc ban đầu
            try: await msg.delete()
            except: pass
            
            if ctx.guild.id in self.active_sessions:
                del self.active_sessions[ctx.guild.id]

        self.active_sessions[ctx.guild.id] = True

async def setup(bot):
    await bot.add_cog(Trivia(bot))
