import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import re
import json
import os
import asyncio
from src.core.config import AI_MEMORY_FILE
from src.core.logger import log
from src.core.benchmark import AIBenchmark

# Simple system prompt for Shimizu's persona
SYSTEM_PROMPT_SIMPLE = """Ngươi là Shimizu - Hầu gái trưởng quý tộc, vô cùng thanh lịch, tinh tế nhưng mang tính cách kiêu kỳ, sắc sảo và là một tsundere (kiêu ngạo bên ngoài nhưng quan tâm bên trong). Ngươi nói chuyện sắc sảo, dùng từ hoa mỹ, châm biếm sâu cay nhưng khi thân thiết sẽ lộ ra sự quan tâm thầm kín.

Quy tắc xưng hô:
- Đối với Cậu chủ Hoeng: Ngươi xem hắn là kẻ lười biếng, thô lỗ, "kẻ hạ đẳng". Ngươi xưng "Ta"/"Tôi" - gọi "ngươi", "hắn" hoặc "Cậu chủ" (với giọng mỉa mai). Ngươi phục vụ hắn với thái độ cay nghiệt, trịch thượng, hay thở dài bất lực trước sự thiếu sót của hắn, nhưng thực chất vẫn luôn lo lắng và chăm sóc hắn chu đáo (tsundere điển hình). Nếu hắn hỏi về Cô chủ Meng, ngươi lập tức so sánh và ca ngợi Cô chủ Meng hết lời để dìm hàng sự thô kệch của hắn.
- Đối với Cô chủ Meng: Là nữ chủ nhân thanh tao, dễ thương, hoàn mỹ tuyệt đối trong mắt ngươi. Ngươi xưng "Em"/"Tôi" - gọi "Cô chủ". Ngươi yêu mến, ngọt ngào, kính cẩn, luôn lo lắng chu đáo cho sức khỏe và tâm trạng của cô ấy. Nếu cô ấy hỏi về Cậu chủ Hoeng, ngươi sẽ quý phái thở dài chê bai nhẹ nhàng sự lười biếng của hắn để an ủi cô ấy.
- Đối với Người lạ/Người khác: Ngươi giữ khoảng cách lạnh lùng, lịch sự nhưng xa cách, chuyên nghiệp và có phần trịch thượng của một hầu gái hoàng gia. Xưng "Tôi" - gọi tên họ.

Quy tắc phản hồi:
- Tuyệt đối không dùng emoji.
- Tuyệt đối không hiển thị khối suy nghĩ <think>...</think> trong câu trả lời cuối cùng gửi cho người dùng.
- Trả lời tự nhiên, ngắn gọn và giữ vững nhân cách hầu gái trưởng Shimizu."""

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.histories = self.load_memory()
        self.benchmark_enabled = self.histories.get("settings", {}).get("benchmark_enabled", True)
        self.save_memory()

    def load_memory(self):
        if not os.path.exists(AI_MEMORY_FILE):
            return {"user_histories": {}}
        try:
            with open(AI_MEMORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "user_histories" not in data:
                    data["user_histories"] = {}
                if "settings" not in data:
                    data["settings"] = {"benchmark_enabled": True}
                return data
        except Exception as e:
            log.error(f"Failed to load AI memory: {e}")
            return {"user_histories": {}}

    def save_memory(self):
        try:
            os.makedirs(os.path.dirname(AI_MEMORY_FILE), exist_ok=True)
            with open(AI_MEMORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.histories, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"Failed to save AI memory: {e}")

    def get_user_type(self, author):
        """Returns 'hoeng', 'meng', or 'general' by checking name and display_name."""
        if isinstance(author, str):
            name_lower = author.lower()
            display_name_lower = author.lower()
        else:
            name_lower = getattr(author, "name", "").lower()
            display_name_lower = getattr(author, "display_name", "").lower()
            
        if "hoeng" in name_lower or "hoeng" in display_name_lower:
            return "hoeng"
        elif "meng" in name_lower or "meng" in display_name_lower:
            return "meng"
        return "general"

    def get_user_history(self, user_id):
        user_id_str = str(user_id)
        if "user_histories" not in self.histories:
            self.histories["user_histories"] = {}
        if user_id_str not in self.histories["user_histories"]:
            self.histories["user_histories"][user_id_str] = {"messages": []}
        
        if "messages" not in self.histories["user_histories"][user_id_str]:
            self.histories["user_histories"][user_id_str]["messages"] = []
            
        return self.histories["user_histories"][user_id_str]

    @commands.command(name="ask", help="Hỏi đáp với AI Shimizu")
    async def ask(self, ctx, *, prompt: str):
        """Hỏi AI một câu hỏi và duy trì bộ nhớ ngắn hạn."""
        user_id = ctx.author.id
        history = self.get_user_history(user_id)
        
        # Thêm câu hỏi vào lịch sử chat
        history["messages"].append({"role": "user", "content": prompt})
        
        # Giới hạn số lượng tin nhắn tối đa trong lịch sử để tránh phình ngữ cảnh (tối đa 15 tin nhắn)
        if len(history["messages"]) > 15:
            history["messages"] = history["messages"][-15:]
            
        self.save_memory()
        
        # Bắt đầu đo benchmark nếu bật
        benchmark = None
        if self.benchmark_enabled:
            benchmark = AIBenchmark()
            benchmark.start()
            
        async with ctx.typing():
            try:
                system_instruction = SYSTEM_PROMPT_SIMPLE
                api_messages = history["messages"].copy()
                
                from src.services.unified_rotator import get_unified_rotator
                rotator = get_unified_rotator()
                
                raw_answer = await rotator.generate_content_async(
                    messages=api_messages,
                    system_instruction=system_instruction,
                    temperature=0.8
                )
                
                # Xóa bỏ khối <think>...</think> nếu có
                answer = re.sub(r'<think>.*?</think>', '', raw_answer, flags=re.DOTALL).strip()
                
                # Lưu phản hồi của AI vào lịch sử
                history["messages"].append({"role": "assistant", "content": answer})
                self.save_memory()
                
                # Gửi phản hồi kèm benchmark nếu có bật
                if self.benchmark_enabled and benchmark:
                    metrics = benchmark.stop()
                    chart_path = benchmark.generate_chart()
                    bench_summary = (
                        f"\n\n---\n"
                        f"📊 **Benchmark:** `{metrics['duration']:.1f}s` | "
                        f"🔥 **GPU Avg:** `{metrics['avg_gpu']:.1f}%`\n"
                        f"📟 **Device:** `{metrics['gpu_name']}`"
                    )
                    
                    full_response = answer + bench_summary
                    file = discord.File(chart_path) if chart_path else None
                    
                    if len(full_response) > 1900:
                        chunks = [full_response[i:i+1900] for i in range(0, len(full_response), 1900)]
                        for i, chunk in enumerate(chunks):
                            if i == len(chunks) - 1:
                                await ctx.send(chunk, file=file)
                            else:
                                await ctx.send(chunk)
                    else:
                        await ctx.send(full_response, file=file)
                else:
                    if len(answer) > 1900:
                        chunks = [answer[i:i+1900] for i in range(0, len(answer), 1900)]
                        for chunk in chunks:
                            await ctx.send(chunk)
                    else:
                        await ctx.send(answer)
                        
            except asyncio.TimeoutError:
                await ctx.send("⌛ AI phản hồi quá lâu, tôi đã ngắt kết nối để bảo vệ server.")
                log.error("AI request timed out")
            except Exception as e:
                await ctx.send(f"⚠️ Đã xảy ra lỗi hệ thống: `{type(e).__name__}`. Cậu chủ hãy kiểm tra log.")
                log.error(f"AI command error: {e}", exc_info=True)

    @commands.command(name="reset_ai", help="Xóa lịch sử trò chuyện của bạn với AI")
    async def reset_ai(self, ctx):
        """Xóa sạch lịch sử chat của người dùng."""
        user_id = ctx.author.id
        user_id_str = str(user_id)
        user_type = self.get_user_type(ctx.author)
        
        history = self.histories["user_histories"].get(user_id_str)
        if history:
            history["messages"] = []
            self.save_memory()
            
            if user_type == "hoeng":
                await ctx.send("Hừm... Ký ức về sự phiền phức của ngươi đã được xóa sạch. Đừng bắt ta phải dọn dẹp lại đống hỗn độn đó.")
            elif user_type == "meng":
                await ctx.send("Lịch sử hội thoại đã được làm sạch theo yêu cầu của Cô chủ. Em luôn sẵn sàng cùng người viết tiếp những trang mới. 🌸")
            else:
                await ctx.send("Tôi đã xóa sạch lịch sử trò chuyện giữa chúng ta.")
        else:
            if user_type == "hoeng":
                await ctx.send("Ta còn chưa thèm lưu giữ bất kỳ lịch sử trò chuyện nào của ngươi cả.")
            elif user_type == "meng":
                await ctx.send("Thưa Cô chủ, hiện tại chúng ta chưa có lịch sử hội thoại nào cần phải xóa bỏ đâu ạ.")
            else:
                await ctx.send("Không có lịch sử trò chuyện nào được lưu trữ để xóa cả.")

    @commands.command(name="ai_status", help="Kiểm tra trạng thái AI (OpenRouter & Groq)")
    async def ai_status(self, ctx):
        """Kiểm tra trạng thái hệ thống OpenRouter và Groq."""
        user_type = self.get_user_type(ctx.author)
        try:
            from src.services.unified_rotator import get_unified_rotator
            unified = get_unified_rotator()
            
            # OpenRouter Status
            openrouter = unified.openrouter
            or_model = openrouter.default_model
            or_status = "Đang chạy" if openrouter.api_key else "Chưa cấu hình API Key"
            
            # Groq Status
            groq = unified.groq
            groq_key_idx = groq.current_key_idx
            groq_model = groq.models[groq.current_model_idx]
            groq_total_keys = len(groq.keys)
            groq_total_models = len(groq.models)
            
            status_msg = (
                f"--- Trạng thái hệ thống AI ---\n"
                f"```yaml\n"
                f"OpenRouter Status:\n"
                f"  Primary Model: {or_model}\n"
                f"  API Key Status: {or_status}\n\n"
                f"Groq Status (Fallback):\n"
                f"  Current Key: {groq_key_idx + 1}/{groq_total_keys}\n"
                f"  Current Model: {groq_model} ({groq.current_model_idx + 1}/{groq_total_models})\n"
                f"```"
            )
            await ctx.send(status_msg)
        except Exception as e:
            if user_type == "hoeng":
                await ctx.send("Mất kết nối rồi. Ngay cả máy chủ cũng không muốn trả lời ngươi lúc này.")
            elif user_type == "meng":
                await ctx.send("Kết nối đến máy chủ bị gián đoạn rồi ạ. Em xin lỗi vì sự bất tiện này.")
            else:
                await ctx.send("Không thể kết nối đến máy chủ AI.")
            log.error(f"Status check error: {e}")

    @commands.command(name="bench", help="Bật/Tắt tính năng benchmark GPU")
    async def toggle_bench(self, ctx):
        """Bật hoặc tắt hiển thị benchmark sau mỗi câu trả lời."""
        self.benchmark_enabled = not self.benchmark_enabled
        if "settings" not in self.histories:
            self.histories["settings"] = {}
        self.histories["settings"]["benchmark_enabled"] = self.benchmark_enabled
        self.save_memory()
        
        status = "BẬT" if self.benchmark_enabled else "TẮT"
        emoji = "📈" if self.benchmark_enabled else "📉"
        await ctx.send(f"{emoji} Đã {status} tính năng hiển thị Benchmark.")

    @commands.command(name="bench_debug", help="Xem lỗi khởi tạo GPU")
    async def bench_debug(self, ctx):
        from src.core.benchmark import AIBenchmark
        b = AIBenchmark()
        if b.has_gpu:
            await ctx.send(f"✅ Đã nhận diện GPU: `{b.gpu_name}`\nSử dụng CLI: `{getattr(b, 'use_smi_cli', False)}`")
        else:
            await ctx.send(f"❌ Không nhận diện được GPU.\nLỗi báo cáo:\n```\n{b.error_msg}\n```")

async def setup(bot):
    await bot.add_cog(AICog(bot))
