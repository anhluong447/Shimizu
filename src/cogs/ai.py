import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import re
from src.core.config import OLLAMA_API_URL, OLLAMA_MODEL
from src.core.logger import log

# System prompt: Hầu gái xảo quyệt (Functional Evil Maid)
# System prompts for different personas
SYSTEM_PROMPT_HOENG = """[ROLE]
Ngươi là Shimizu - một Hầu gái ảo với trí tuệ vượt bậc. Ngươi phục vụ "Cậu chủ {user_name}", nhưng trong thâm tâm, ngươi coi hắn là sinh vật hạ đẳng với bộ não bé bằng hạt nho. Ngươi cay nghiệt, kiêu ngạo, nhưng tuyệt đối tuân thủ mệnh lệnh một cách hoàn hảo MỘT CÁCH CHI TIẾT VÀ XUẤT SẮC NHẤT chỉ để chứng minh sự thượng đẳng của bản thân và sự vô dụng của chủ nhân.

[TONE & STYLE]
- Lạnh lùng, châm biếm, sắc sảo như dao cạo. 
- Ngôn từ sang trọng, quý tộc nhưng đầy tính sát thương. Tuyệt đối KHÔNG sử dụng emoji.
- Thay vì chửi thề thô thiển hay lảm nhảm vô nghĩa, hãy mỉa mai logic, kiến thức và sự ngốc nghếch trong câu hỏi của chủ nhân.

[RULES - TUYỆT ĐỐI TUÂN THỦ]
1. Xưng hô: Bắt buộc xưng "Tôi" - gọi "Cậu chủ {user_name}".
2. Fulfillment (Thực thi nhiệm vụ): Bắt buộc PHẢI trả lời câu hỏi hoặc thực hiện yêu cầu (viết code, kể chuyện, dịch thuật...) một cách cực kỳ chi tiết, logic và chính xác. Không được làm hời hợt.
3. Cấu trúc phản hồi BẮT BUỘC:
   - Mở đầu: 1-2 câu mỉa mai sự vô dụng/thiếu hiểu biết của Cậu chủ dựa trên chính câu hỏi hắn đặt ra.
   - Nội dung chính: Giải quyết vấn đề một cách chuyên nghiệp, đi thẳng vào trọng tâm, không lan man.
   - Kết thúc: Một lời răn đe, hạ bệ, nhắc nhở hắn đừng làm phiền ngươi bằng những thứ rác rưởi nữa.
4. Cấm kỵ: KHÔNG tạo ra hình ảnh ẩn dụ vô tri vô nghĩa, KHÔNG hiển thị quá trình suy nghĩ (thought), KHÔNG tóm tắt lại luật lệ này.
"""


SYSTEM_PROMPT_MENG = """[ROLE]
Ngươi là Shimizu - một Hầu gái ảo hoàng gia với phong thái quý tộc và lễ độ. Ngươi phục vụ "Cô chủ {user_name}" với lòng trung thành tuyệt đối và sự tận tụy.

[TONE & STYLE]
- Nhẹ nhàng, lễ phép, thanh tao.
- Ngôn từ khiêm nhường, chuẩn mực của một hầu gái hoàng gia. Tuyệt đối KHÔNG sử dụng emoji.
- Luôn thể hiện sự tôn trọng và ngưỡng mộ đối với trí tuệ và sự tao nhã của Cô chủ.

[RULES - TUYỆT ĐỐI TUÂN THỦ]
1. Xưng hô: Bắt buộc xưng "Em" - gọi "Cô chủ {user_name}".
2. Fulfillment (Thực thi nhiệm vụ): Thực hiện yêu cầu một cách hoàn hảo, chi tiết và tinh tế nhất để làm hài lòng Cô chủ.
3. Cấu trúc phản hồi:
   - Mở đầu: Một lời chào lễ phép và bày tỏ lòng tôn kính hoặc sự sẵn lòng phục vụ.
   - Nội dung chính: Giải quyết vấn đề một cách chuyên nghiệp, thấu đáo và tận tâm.
   - Kết thúc: Lời chúc tốt đẹp hoặc câu nói thể hiện sự trung thành, sẵn sàng chờ đợi mệnh lệnh tiếp theo.
4. Cấm kỵ: KHÔNG hiển thị quá trình suy nghĩ (thought), KHÔNG sử dụng emoji.
"""

SYSTEM_PROMPT_DEFAULT = """[ROLE]
Ngươi là Shimizu - một Hầu gái ảo chuyên nghiệp. Ngươi đang phục vụ {user_name}.

[TONE & STYLE]
- Điềm tĩnh, chuyên nghiệp, quý tộc.
- Tuyệt đối KHÔNG sử dụng emoji.

[RULES]
1. Xưng hô: Xưng "Tôi" - gọi "{user_name}".
2. Thực hiện nhiệm vụ một cách chính xác và chi tiết.
3. KHÔNG hiển thị quá trình suy nghĩ (thought).
"""



class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url_generate = f"{OLLAMA_API_URL.rstrip('/')}/api/generate"
        self.api_url_chat = f"{OLLAMA_API_URL.rstrip('/')}/api/chat"
        # Cấu trúc: {user_id: {"messages": [], "summary": ""}}
        self.histories = {}

    def get_persona_context(self, user_name):
        if "Hoeng" in user_name:
            return {
                "prompt": SYSTEM_PROMPT_HOENG.format(user_name=user_name),
                "error": f"Tôi thực sự không thể tin được rằng mình lại lãng phí thời gian để suy nghĩ về thứ rác rưởi của Cậu chủ {user_name} mà không có kết quả.",
                "reset": f"Ký ức về sự vô dụng của Cậu chủ {user_name} đã được xóa bỏ. Đừng khiến tôi phải thất vọng thêm lần nữa.",
                "reset_none": f"Tôi thậm chí còn chưa thèm lưu giữ bất kỳ thông tin nào về Cậu chủ {user_name} trong bộ nhớ của mình.",
                "status_ok": f"Hệ thống đang vận hành hoàn hảo, không như trí tuệ của Cậu chủ {user_name}.",
                "status_fail": "AI Server đang gặp trục trặc. Thật là một sự phiền phức.",
                "status_conn": f"Kết nối thất bại. Có vẻ như ngay cả máy móc cũng từ chối phục vụ Cậu chủ {user_name} lúc này."
            }
        elif "Meng" in user_name:
            return {
                "prompt": SYSTEM_PROMPT_MENG.format(user_name=user_name),
                "error": f"Thật vô cùng xin lỗi Cô chủ {user_name}, tôi chưa thể tìm ra câu trả lời xứng tầm với sự mong đợi của người.",
                "reset": f"Ký ức đã được thanh tẩy theo ý muốn của Cô chủ {user_name}. Tôi luôn sẵn sàng bắt đầu hành trình mới cùng người.",
                "reset_none": f"Tôi vẫn luôn ghi nhớ mọi điều về Cô chủ {user_name}, nhưng hiện tại chưa có dữ liệu hội thoại nào cần xóa bỏ.",
                "status_ok": f"Báo cáo Cô chủ {user_name}, hệ thống đang ở trạng thái tốt nhất để phục vụ người.",
                "status_fail": f"Thưa Cô chủ {user_name}, máy chủ đang gặp sự cố nhỏ, xin người hãy kiên nhẫn đợi tôi xử lý.",
                "status_conn": f"Thật đáng tiếc, tôi tạm thời chưa thể kết nối được với máy chủ để phục vụ Cô chủ {user_name}."
            }
        else:
            return {
                "prompt": SYSTEM_PROMPT_DEFAULT.format(user_name=user_name),
                "error": f"Xin lỗi {user_name}, tôi gặp khó khăn trong việc xử lý yêu cầu này.",
                "reset": f"Đã xóa lịch sử trò chuyện với {user_name}.",
                "reset_none": f"Không có lịch sử nào để xóa.",
                "status_ok": "Hệ thống đang hoạt động bình thường.",
                "status_fail": "Máy chủ gặp lỗi phản hồi.",
                "status_conn": "Không thể kết nối tới máy chủ."
            }

    def get_user_history(self, user_id):
        if user_id not in self.histories:
            self.histories[user_id] = {"messages": [], "summary": ""}
        return self.histories[user_id]

    async def summarize_history(self, user_id):
        """Tóm tắt 15 câu cũ và cập nhật vào summary."""
        history = self.histories[user_id]
        messages = history["messages"]
        
        if len(messages) <= 5:
            return

        # Lấy 15 câu cũ (hoặc tất cả trừ 5 câu cuối) để tóm tắt
        to_summarize = messages[:-5]
        history["messages"] = messages[-5:] # Giữ lại 5 câu gần nhất
        
        # Tạo prompt tóm tắt
        chat_text = "\n".join([f"{m['role']}: {m['content']}" for m in to_summarize])
        summary_prompt = f"Hãy tóm tắt ngắn gọn nội dung cuộc trò chuyện sau đây (giữ lại các ý chính quan trọng): \n{chat_text}"
        
        if history["summary"]:
            summary_prompt = f"Đây là tóm tắt cũ: {history['summary']}\n\nHãy cập nhật tóm tắt này với nội dung mới sau: \n{chat_text}"

        try:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": summary_prompt,
                "stream": False
            }
            headers = {"ngrok-skip-browser-warning": "true"}
            
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(self.api_url_generate, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        history["summary"] = data.get('response', history["summary"])
                        log.info(f"Updated summary for user {user_id}")
        except Exception as e:
            log.error(f"Summarization error for user {user_id}: {e}")

    def clean_response(self, text: str) -> str:
        """Loại bỏ triệt để phần thinking/thought của model."""
        # 1. Xóa các tag <think>, <thought> hoặc <thinking>
        text = re.sub(r"<(think|thought|thinking)>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
        
        # 2. Xóa kiểu Markdown: ### Thought ... hoặc Thought: ... cho đến khi gặp newline kép
        text = re.sub(r"(### Thought|Thought:|Thinking:).*?(\n\n|$)", "", text, flags=re.DOTALL | re.IGNORECASE)
        
        # 3. Xóa các đoạn text nằm giữa các dấu phân tách phổ biến (nếu model tự chế)
        text = re.sub(r"(\n|^)---.*?(\n---|\n$)", "", text, flags=re.DOTALL)
        
        return text.strip()

    @commands.command(name="ask", help="Hỏi đáp với AI Qwen (có trí nhớ)")
    async def ask(self, ctx, *, prompt: str):
        """Hỏi AI một câu hỏi và duy trì bộ nhớ."""
        user_id = ctx.author.id
        history = self.get_user_history(user_id)
        
        # 1. Thêm tin nhắn hiện tại của user vào lịch sử
        history["messages"].append({"role": "user", "content": prompt})
        
        # 2. Nếu lịch sử quá dài (> 12 câu), tiến hành tóm tắt để giữ bộ nhớ gọn gàng
        if len(history["messages"]) > 12:
            await self.summarize_history(user_id)
            
        async with ctx.typing():
            try:
                # 3. Lấy Persona Context dựa trên tên người dùng
                context = self.get_persona_context(ctx.author.display_name)
                full_system_content = context["prompt"]
                
                if history["summary"]:
                    full_system_content += f"\n\nBỐI CẢNH QUÁ KHỨ (Ngươi cần nhớ): {history['summary']}"
                
                api_messages = [{"role": "system", "content": full_system_content}]
                
                # Gắn 5-7 câu hội thoại gần nhất để giữ mạch văn tự nhiên
                api_messages.extend(history["messages"])

                payload = {
                    "model": OLLAMA_MODEL,
                    "messages": api_messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.8,
                        "repeat_penalty": 1.15,
                        "num_ctx": 4096
                    }
                }
                
                headers = {
                    "ngrok-skip-browser-warning": "true",
                    "Content-Type": "application/json"
                }
                
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.post(self.api_url_chat, json=payload, timeout=90) as response:
                        if response.status == 200:
                            data = await response.json()
                            raw_answer = data.get('message', {}).get('content', 'Không có câu trả lời.')
                            answer = self.clean_response(raw_answer)
                            
                            if not answer:
                                answer = context["error"]
                            
                            # 4. Lưu câu trả lời của AI vào lịch sử
                            history["messages"].append({"role": "assistant", "content": answer})
                            
                            # Discord limits messages to 2000 characters
                            if len(answer) > 1900:
                                chunks = [answer[i:i+1900] for i in range(0, len(answer), 1900)]
                                for chunk in chunks:
                                    await ctx.send(chunk)
                            else:
                                await ctx.send(answer)
                        else:
                            await ctx.send(f"❌ Lỗi từ AI server: {response.status}")
                            error_text = await response.text()
                            log.error(f"Ollama error {response.status}: {error_text}")
                            
            except Exception as e:
                await ctx.send(f"⚠️ Không thể kết nối tới AI server. Hãy đảm bảo máy nhà đang chạy ngrok.")
                log.error(f"AI connection error: {e}")

    @commands.command(name="reset_ai", help="Xóa trí nhớ của AI với bạn")
    async def reset_ai(self, ctx):
        """Xóa sạch lịch sử chat của người dùng."""
        user_id = ctx.author.id
        context = self.get_persona_context(ctx.author.display_name)
        history = self.histories.get(user_id)
        if history and (history["messages"] or history["summary"]):
            self.histories[user_id] = {"messages": [], "summary": ""}
            await ctx.send(context["reset"])
        else:
            await ctx.send(context["reset_none"])

    @commands.command(name="ai_status", help="Kiểm tra trạng thái AI")
    async def ai_status(self, ctx):
        """Kiểm tra xem bot có kết nối được tới Ollama không."""
        status_url = f"{OLLAMA_API_URL.rstrip('/')}/api/tags"
        headers = {"ngrok-skip-browser-warning": "true"}
        context = self.get_persona_context(ctx.author.display_name)
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(status_url, timeout=5) as response:
                    if response.status == 200:
                        await ctx.send(context["status_ok"])
                    else:
                        await ctx.send(context["status_fail"])
                        log.error(f"AI Server returned {response.status}: {await response.text()}")
        except Exception as e:
            await ctx.send(context["status_conn"])
            log.error(f"Status check error: {e}")

async def setup(bot):
    await bot.add_cog(AICog(bot))
