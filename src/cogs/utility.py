import os
import json
import discord
import datetime
from discord.ext import commands, tasks
from discord import app_commands
from src.core.config import TIMEZONE, NOTIFICATIONS_FILE
from src.services.weather import WeatherService
from src.core.logger import log

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Start loops
        self.weather_update.start()
        self.check_notifications.start()

    def cog_unload(self):
        self.weather_update.cancel()
        self.check_notifications.cancel()

    def load_notifications(self):
        if not os.path.exists(NOTIFICATIONS_FILE):
            return []
        try:
            with open(NOTIFICATIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('notifications', [])
        except Exception as e:
            log.error(f"Failed to load notifications: {e}")
            return []

    def save_notifications(self, notifications):
        try:
            with open(NOTIFICATIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump({"notifications": notifications}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"Failed to save notifications: {e}")

    @tasks.loop(time=[datetime.time(hour=6, minute=0, tzinfo=TIMEZONE)])
    async def weather_update(self):
        """Tự động gửi thông báo thời tiết vào 6:00 AM"""
        await self.bot.wait_until_ready()
        log.info("--- [AUTO] Bắt đầu kích hoạt bản tin thời tiết sáng sớm ---")
        
        channel = None
        for guild in self.bot.guilds:
            channel = discord.utils.get(guild.text_channels, name='off-topic')
            if channel:
                break
        
        if not channel:
            log.warning("[AUTO] Không tìm thấy channel #off-topic để gửi thời tiết.")
            return

        w = await WeatherService.get_weather("Hanoi")
        if not w:
            log.error("[AUTO] Không thể lấy dữ liệu thời tiết cho bản tin tự động.")
            return

        embed = self._create_weather_embed(w)
        embed.title = "🌤️ Bản tin thời tiết sáng sớm"
        await channel.send(embed=embed)
        log.info(f"[AUTO] Đã gửi bản tin thời tiết vào channel: {channel.name} ({channel.guild.name})")

    @commands.hybrid_command(name='testweather', description='[Admin] Chạy thử logic thông báo thời tiết tự động.')
    @commands.is_owner()
    async def testweather(self, ctx):
        """Chạy thử logic thông báo thời tiết tự động ngay lập tức."""
        await ctx.send("🔍 Đang chạy thử logic thông báo thời tiết...")
        await self.weather_update()
        await ctx.send("✅ Đã chạy xong logic weather_update.")

    def _create_weather_embed(self, w):
        """Helper để tạo embed thời tiết đẹp mắt."""
        embed = discord.Embed(
            title=f"🌤️ Báo Cáo Thời Tiết: {w['city']}",
            color=discord.Color.from_str('#A0C4FF') # Pastel Blue
        )
        
        embed.set_author(name="Trung tâm Khí tượng Shimizu", icon_url=self.bot.user.display_avatar.url)
        
        # 1. Current Condition (Blockquote)
        current_text = (
            f"🌡️ **Nhiệt độ:** {w['current']['temp']}°C *(Cảm giác: {w['current']['feels_like']}°C)*\n"
            f"💧 **Độ ẩm:** {w['current']['humidity']}%\n"
            f"☁️ **Trạng thái:** {w['current']['desc']}"
        )
        embed.add_field(name="📍 TÌNH TRẠNG HIỆN TẠI", value=f">>> {current_text}", inline=False)

        # 2. Hourly Grid (Aligned labels + Blockquote)
        f = w['forecast']
        hourly_text = (
            f"`🌅 Sáng ` **{f['morning']['temp']}°C** ⏤ *{f['morning']['desc']}*\n"
            f"`☀️ Trưa ` **{f['noon']['temp']}°C** ⏤ *{f['noon']['desc']}*\n"
            f"`🌆 Chiều` **{f['evening']['temp']}°C** ⏤ *{f['evening']['desc']}*\n"
            f"`🌙 Tối  ` **{f['night']['temp']}°C** ⏤ *{f['night']['desc']}*"
        )
        embed.add_field(name="🕒 DIỄN BIẾN HÔM NAY", value=f">>> {hourly_text}", inline=False)

        # 3. Tomorrow (Blockquote)
        t = w['tomorrow']
        tmr_text = (
            f"🌡️ **Nhiệt độ:** {t['min']}°C ➖ {t['max']}°C\n"
            f"☁️ **Trạng thái:** {t['desc']}"
        )
        
        # Format date: 2026-05-05 -> 05/05/2026
        date_parts = t['date'].split('-')
        fmt_date = f"{date_parts[2]}/{date_parts[1]}/{date_parts[0]}" if len(date_parts) == 3 else t['date']
        
        embed.add_field(name=f"📅 DỰ BÁO NGÀY MAI ({fmt_date})", value=f">>> {tmr_text}", inline=False)

        # Footer
        embed.set_footer(text="Dữ liệu thời gian thực từ wttr.in", icon_url="https://cdn-icons-png.flaticon.com/512/3222/3222801.png")
        embed.timestamp = datetime.datetime.now(TIMEZONE)
        return embed

    @tasks.loop(minutes=1)
    async def check_notifications(self):
        """Kiểm tra thông báo mỗi phút"""
        now = datetime.datetime.now(TIMEZONE)
        current_time = now.strftime("%H:%M")
        
        notifications = self.load_notifications()
        if not notifications:
            return

        for notif in notifications:
            if notif['time'] == current_time:
                channel = None
                for guild in self.bot.guilds:
                    channel = discord.utils.get(guild.text_channels, name='general')
                    if channel:
                        break
                
                if channel:
                    msg = f"🔔 **THÔNG BÁO HẸN GIỜ** ({notif['time']})\n\n> {notif['message']}\n\n*Đặt bởi: {notif['user_name']}*"
                    await channel.send(msg)

    @commands.hybrid_command(name='notify', description='Đặt thông báo lặp lại hàng ngày.')
    @app_commands.describe(time='Giờ thông báo (VD: 07:00)', message='Nội dung thông báo')
    async def notify(self, ctx, time: str, *, message: str):
        """Đặt thông báo lặp lại hàng ngày."""
        try:
            datetime.datetime.strptime(time, "%H:%M")
            
            notifications = self.load_notifications()
            notifications.append({
                "time": time,
                "message": message,
                "user_id": ctx.author.id,
                "user_name": ctx.author.display_name,
                "created_at": datetime.datetime.now(TIMEZONE).isoformat()
            })
            self.save_notifications(notifications)
            
            await ctx.send(f"✅ Đã đặt thông báo vào lúc **{time}** hàng ngày.")
        except ValueError:
            await ctx.send("❌ Định dạng thời gian không đúng. Vui lòng dùng `HH:MM`.")

    @commands.hybrid_command(name='reminders', aliases=['notifs'], description='Xem danh sách thông báo hiện có.')
    async def reminders(self, ctx):
        """Xem danh sách các thông báo hiện có"""
        notifications = self.load_notifications()
        if not notifications:
            await ctx.send("Hiện chưa có thông báo nào được đặt.")
            return

        embed = discord.Embed(title="🔔 Danh sách thông báo hàng ngày", color=discord.Color.gold())
        for i, notif in enumerate(notifications, 1):
            embed.add_field(
                name=f"{i}. Lúc {notif['time']}",
                value=f"📝 {notif['message']}\n👤 Đặt bởi: {notif['user_name']}",
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='delnotify', aliases=['rmnotify'], description='Xóa thông báo theo số thứ tự.')
    @app_commands.describe(index='Số thứ tự thông báo cần xóa')
    async def delnotify(self, ctx, index: int):
        """Xóa thông báo theo số thứ tự."""
        notifications = self.load_notifications()
        if 1 <= index <= len(notifications):
            removed = notifications.pop(index - 1)
            self.save_notifications(notifications)
            await ctx.send(f"✅ Đã xóa thông báo lúc **{removed['time']}**.")
        else:
            await ctx.send("❌ Số thứ tự không hợp lệ.")

    @commands.hybrid_command(name='weather', description='Xem dự báo thời tiết chuyên nghiệp.')
    @app_commands.describe(city='Tên thành phố (VD: Hanoi, Saigon)')
    async def weather(self, ctx, city: str = "Hanoi"):
        """Xem dự báo thời tiết chuyên nghiệp"""
        async with ctx.typing():
            w = await WeatherService.get_weather(city)
            if not w:
                return await ctx.send("☔ Không thể lấy dữ liệu thời tiết lúc này.")

            embed = self._create_weather_embed(w)
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Utility(bot))
