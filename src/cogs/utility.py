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
        channel = None
        for guild in self.bot.guilds:
            channel = discord.utils.get(guild.text_channels, name='off-topic')
            if channel:
                break
        
        if not channel:
            log.warning("Could not find #off-topic channel for weather update.")
            return

        weather_data = await WeatherService.get_weather()
        
        embed = discord.Embed(
            title="🌤️ Bản tin thời tiết sáng sớm",
            description=weather_data,
            color=discord.Color.from_rgb(135, 206, 235),
            timestamp=datetime.datetime.now(TIMEZONE)
        )
        embed.set_footer(text="Chúc bạn một ngày tốt lành! 🌸")
        await channel.send(embed=embed)

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

    @commands.hybrid_command(name='weather', description='Xem dự báo thời tiết chi tiết.')
    @app_commands.describe(city='Tên thành phố (VD: Hanoi, Saigon)')
    async def weather(self, ctx, city: str = "Hanoi"):
        """Xem dự báo thời tiết chi tiết"""
        async with ctx.typing():
            weather_data = await WeatherService.get_weather(city)
            embed = discord.Embed(
                description=weather_data,
                color=discord.Color.from_str('#3498db')
            )
            embed.set_footer(text="Dữ liệu từ wttr.in")
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Utility(bot))
