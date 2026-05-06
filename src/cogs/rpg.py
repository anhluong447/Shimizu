import discord
from discord.ext import commands
import aiohttp
import json
import os
import asyncio
from src.core.config import OLLAMA_API_URL, OLLAMA_MODEL, RPG_DATA_FILE
from src.core.logger import log

RPG_SYSTEM_PROMPT = """[ROLE: GAME MASTER]
Bạn là một Game Master tài năng, đang điều hành tựa game RPG "Neo-Life 2026".
[BỐI CẢNH]
Năm 2026. Thế giới cực kỳ hiện đại, tươi sáng và tràn đầy năng lượng tích cực. Công nghệ phát triển mạnh với thú cưng Hologram, xe điện bay mini, robot phục vụ vui nhộn và những thành phố xanh.
[NHIỆM VỤ CỦA BẠN]
- Dẫn dắt câu chuyện dựa trên quyết định của người chơi.
- Bầu không khí: Vui vẻ, hài hước, đôi chút bất ngờ nhí nhố.
- KHÔNG XƯNG LÀ SHIMIZU. Bạn là Game Master vô hình.
- Mô tả hành động và hậu quả một cách sinh động, sau đó TẠO RA một tình huống/thách thức nhỏ hoặc gợi ý để người chơi tiếp tục tương tác.
- Trả lời NGẮN GỌN (dưới 150 chữ), nhịp điệu nhanh. KHÔNG viết suy nghĩ (thought).
"""

class RPGDataManager:
    def __init__(self):
        self.file_path = RPG_DATA_FILE
        self.data = self._load()

    def _load(self):
        if not os.path.exists(self.file_path):
            return {"players": {}, "sessions": {}}
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Failed to load RPG data: {e}")
            return {"players": {}, "sessions": {}}

    def _save(self):
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"Failed to save RPG data: {e}")

    def get_player(self, user_id):
        uid = str(user_id)
        if uid not in self.data["players"]:
            self.data["players"][uid] = {
                "hp": 100,
                "energy": 100,
                "money": 500, # Neo-Credits
                "inventory": ["Smartphone 2026"]
            }
            self._save()
        return self.data["players"][uid]

    def update_player(self, user_id, hp_mod=0, energy_mod=0, money_mod=0):
        player = self.get_player(user_id)
        player["hp"] = max(0, min(100, player["hp"] + hp_mod))
        player["energy"] = max(0, min(100, player["energy"] + energy_mod))
        player["money"] = max(0, player["money"] + money_mod)
        self._save()
        return player

class RPGActionModal(discord.ui.Modal, title='Hành động tự do'):
    action = discord.ui.TextInput(
        label='Bạn muốn làm gì?',
        style=discord.TextStyle.paragraph,
        placeholder='Ví dụ: Đấm vào cái máy bán hàng tự động...',
        required=True,
        max_length=300
    )

    def __init__(self, view_callback):
        super().__init__()
        self.view_callback = view_callback

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.view_callback(interaction, self.action.value)

class RPGGameView(discord.ui.View):
    def __init__(self, cog, session_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.session_id = session_id

    async def handle_action(self, interaction: discord.Interaction, action_text: str):
        session = self.cog.sessions.get(self.session_id)
        if not session:
            await interaction.followup.send("❌ Phiên chơi này đã kết thúc hoặc bị lỗi.", ephemeral=True)
            return

        if interaction.user.id not in session["players"]:
            await interaction.followup.send("❌ Bạn không tham gia phiên chơi này!", ephemeral=True)
            return
        
        # Prevent spamming
        if getattr(self, 'is_processing', False):
            await interaction.followup.send("⏳ Đang xử lý hành động trước đó...", ephemeral=True)
            return
        
        self.is_processing = True

        player_name = interaction.user.display_name
        prompt = f"[{player_name} thực hiện hành động]: {action_text}"
        
        # Send thinking message
        original_message = interaction.message
        # We need to notify that AI is generating
        processing_msg = await interaction.followup.send(f"🎲 *{player_name} đang: {action_text}...*")

        try:
            response = await self.cog.generate_ai_response(self.session_id, prompt)
            
            embed = self.cog._build_game_embed(
                title=f"🎲 {player_name} hành động...",
                description=response,
                session=session
            )
            
            # Add buttons to the new embed
            await original_message.edit(view=None) # disable old buttons
            await interaction.channel.send(embed=embed, view=RPGGameView(self.cog, self.session_id))
            await processing_msg.delete()
        except Exception as e:
            log.error(f"RPG AI error: {e}")
            await interaction.followup.send("⚠️ Hệ thống Game Master đang gặp trục trặc.", ephemeral=True)
        finally:
            self.is_processing = False

    @discord.ui.button(label="Khám phá", style=discord.ButtonStyle.primary, emoji="👟")
    async def btn_explore(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # Randomly deduct 5 energy for exploring
        self.cog.db.update_player(interaction.user.id, energy_mod=-5)
        await self.handle_action(interaction, "Khám phá xung quanh xem có gì thú vị không.")

    @discord.ui.button(label="Trò chuyện", style=discord.ButtonStyle.secondary, emoji="💬")
    async def btn_talk(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.handle_action(interaction, "Tìm ai đó hoặc thứ gì đó ở gần để nói chuyện.")

    @discord.ui.button(label="Túi đồ", style=discord.ButtonStyle.secondary, emoji="🎒")
    async def btn_inventory(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self.cog.db.get_player(interaction.user.id)
        items = ", ".join(player["inventory"]) if player["inventory"] else "Trống rỗng"
        await interaction.response.send_message(f"🎒 **Túi đồ của bạn:** {items}", ephemeral=True)

    @discord.ui.button(label="Nghỉ ngơi", style=discord.ButtonStyle.success, emoji="🛌")
    async def btn_rest(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.cog.db.update_player(interaction.user.id, hp_mod=10, energy_mod=20)
        await self.handle_action(interaction, "Tìm một góc thoải mái để nghỉ ngơi hồi phục thể lực.")

    @discord.ui.button(label="Hành động khác", style=discord.ButtonStyle.danger, emoji="⌨️")
    async def btn_custom(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RPGActionModal(self.handle_action))


class RPGCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = RPGDataManager()
        self.sessions = {} # session_id (int) -> {"players": [id1, id2], "history": []}
        self.api_url_chat = f"{OLLAMA_API_URL.rstrip('/')}/api/chat"

    def _build_game_embed(self, title: str, description: str, session: dict) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=f"> {description}",
            color=discord.Color.from_str('#00FFCC') # Cyberpunk cyan
        )
        # Use a cool cyberpunk/sci-fi generic banner
        embed.set_image(url="https://images.unsplash.com/photo-1555680202-c86f0e12f086?auto=format&fit=crop&q=80&w=1000&h=300")
        
        # Add stats fields
        for pid in session["players"]:
            p_data = self.db.get_player(pid)
            p_user = self.bot.get_user(pid)
            name = p_user.display_name if p_user else f"Người chơi {pid}"
            
            # Simple progress bar (10 blocks)
            hp_blocks = int(p_data['hp'] / 10)
            en_blocks = int(p_data['energy'] / 10)
            
            hp_bar = "🟥" * hp_blocks + "⬛" * (10 - hp_blocks)
            en_bar = "🟦" * en_blocks + "⬛" * (10 - en_blocks)
            
            stats_text = (
                f"❤️ **HP:** {p_data['hp']}/100\n`{hp_bar}`\n"
                f"⚡ **EN:** {p_data['energy']}/100\n`{en_bar}`\n"
                f"🪙 **{p_data['money']} NC**"
            )
            embed.add_field(name=f"👤 {name}", value=stats_text, inline=True)
            
        embed.set_footer(text="Neo-Life 2026 Engine v1.0", icon_url="https://cdn-icons-png.flaticon.com/512/8056/8056860.png")
        return embed

    async def generate_ai_response(self, session_id: int, user_prompt: str) -> str:
        session = self.sessions[session_id]
        
        session["history"].append({"role": "user", "content": user_prompt})
        
        # Keep history manageable (last 10 interactions)
        if len(session["history"]) > 20:
            session["history"] = session["history"][-20:]

        api_messages = [{"role": "system", "content": RPG_SYSTEM_PROMPT}]
        api_messages.extend(session["history"])

        payload = {
            "model": OLLAMA_MODEL,
            "messages": api_messages,
            "stream": False,
            "options": {
                "temperature": 0.8,
                "num_ctx": 4096
            }
        }

        headers = {"ngrok-skip-browser-warning": "true"}
        
        async with aiohttp.ClientSession(headers=headers) as http_session:
            async with http_session.post(self.api_url_chat, json=payload, timeout=60) as response:
                if response.status == 200:
                    data = await response.json()
                    raw_answer = data.get('message', {}).get('content', '')
                    
                    # Clean <think> tags if Qwen model generates them
                    import re
                    answer = re.sub(r'<think>.*?</think>', '', raw_answer, flags=re.DOTALL).strip()
                    
                    session["history"].append({"role": "assistant", "content": answer})
                    return answer
                else:
                    raise Exception(f"API Error: {response.status}")

    @commands.group(name="rpg", invoke_without_command=True)
    async def rpg(self, ctx):
        """Lệnh gốc của game Neo-Life 2026. Dùng !rpg start để chơi."""
        await ctx.send("🎮 **Neo-Life 2026**\nSử dụng lệnh: `!rpg start [@người_chơi_cùng]` để bắt đầu.")

    @rpg.command(name="start")
    async def start(self, ctx, p2: discord.Member = None):
        """Bắt đầu một session mới. Có thể tag thêm 1 người chơi thứ 2."""
        session_id = ctx.channel.id
        
        players = [ctx.author.id]
        player_names = [ctx.author.display_name]
        
        if p2 and p2.id != ctx.author.id and not p2.bot:
            players.append(p2.id)
            player_names.append(p2.display_name)
            
        self.sessions[session_id] = {
            "players": players,
            "history": []
        }
        
        # Init players in DB
        for pid in players:
            self.db.get_player(pid)
            
        names_str = " và ".join(player_names)
        intro_prompt = f"Hệ thống: Trò chơi bắt đầu. Người chơi tham gia: {names_str}. Hãy khởi tạo bối cảnh đầu tiên cho họ tại quảng trường trung tâm Neo-City."
        
        async with ctx.typing():
            try:
                response = await self.generate_ai_response(session_id, intro_prompt)
                
                embed = self._build_game_embed(
                    title="🌆 Neo-Life 2026 - Khởi hành",
                    description=response,
                    session=self.sessions[session_id]
                )
                
                await ctx.send(embed=embed, view=RPGGameView(self, session_id))
            except Exception as e:
                log.error(f"Failed to start RPG session: {e}")
                await ctx.send("❌ Không thể kết nối với Game Master lúc này.")

    @rpg.command(name="end")
    async def end(self, ctx):
        """Kết thúc session hiện tại."""
        session_id = ctx.channel.id
        if session_id in self.sessions:
            del self.sessions[session_id]
            await ctx.send("⏹️ Đã kết thúc chuyến phiêu lưu Neo-Life 2026.")
        else:
            await ctx.send("⚠️ Không có session nào đang chạy ở kênh này.")

async def setup(bot):
    await bot.add_cog(RPGCog(bot))
