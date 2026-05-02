import os
import json
import asyncio
import aiohttp
import discord
import datetime
import pytz
from discord.ext import commands, tasks

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.timezone = pytz.timezone('Asia/Ho_Chi_Minh')
        self.notifications_file = 'notifications.json'
        
        # Start loops
        self.weather_update.start()
        self.check_notifications.start()

    def cog_unload(self):
        self.weather_update.cancel()
        self.check_notifications.cancel()

    def load_notifications(self):
        if not os.path.exists(self.notifications_file):
            return []
        try:
            with open(self.notifications_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('notifications', [])
        except Exception as e:
            print(f"[ERROR] Failed to load notifications: {e}")
            return []

    def save_notifications(self, notifications):
        try:
            with open(self.notifications_file, 'w', encoding='utf-8') as f:
                json.dump({"notifications": notifications}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] Failed to save notifications: {e}")

    @tasks.loop(time=[datetime.time(hour=6, minute=0, tzinfo=pytz.timezone('Asia/Ho_Chi_Minh'))])
    async def weather_update(self):
        """Tự động gửi thông báo thời tiết vào 6:00 AM"""
        # Tìm channel #off-topic
        channel = None
        for guild in self.bot.guilds:
            channel = discord.utils.get(guild.text_channels, name='off-topic')
            if channel:
                break
        
        if not channel:
            print("[WARN] Could not find #off-topic channel for weather update.")
            return

        weather_data = await self.get_weather()
        
        embed = discord.Embed(
            title="🌤️ Bản tin thời tiết sáng sớm",
            description=weather_data,
            color=discord.Color.from_rgb(135, 206, 235), # Sky Blue
            timestamp=datetime.datetime.now(self.timezone)
        )
        embed.set_footer(text="Chúc bạn một ngày tốt lành! 🌸")
        
        await channel.send(embed=embed)

    async def get_weather(self, city="Hanoi"):
        url = f"https://wttr.in/{city}?format=%l:+%C+%t+%h+%w&lang=vi"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        text = await response.text()
                        # wttr.in format: "location: condition temp humidity wind"
                        if ":" in text:
                            loc, details = text.split(":", 1)
                            return f"📍 **Địa điểm:** {loc.strip().capitalize()}\n📝 **Chi tiết:** {details.strip()}"
                        return text
                    else:
                        return "☔ Không thể lấy dữ liệu thời tiết lúc này."
        except Exception as e:
            return f"❌ Lỗi khi lấy thời tiết: {e}"

    @tasks.loop(minutes=1)
    async def check_notifications(self):
        """Kiểm tra thông báo mỗi phút"""
        now = datetime.datetime.now(self.timezone)
        current_time = now.strftime("%H:%M")
        
        notifications = self.load_notifications()
        if not notifications:
            return

        for notif in notifications:
            if notif['time'] == current_time:
                # Tìm channel #general
                channel = None
                for guild in self.bot.guilds:
                    channel = discord.utils.get(guild.text_channels, name='general')
                    if channel:
                        break
                
                if channel:
                    msg = f"🔔 **THÔNG BÁO HẸN GIỜ** ({notif['time']})\n\n> {notif['message']}\n\n*Đặt bởi: {notif['user_name']}*"
                    await channel.send(msg)
                else:
                    print(f"[WARN] Could not find #general channel for notification at {current_time}")

    @commands.command(name='notify')
    async def notify(self, ctx, time: str, *, message: str):
        """Đặt thông báo lặp lại hàng ngày. HD: !notify 07:30 Dậy đi học thôi!"""
        try:
            # Validate time format
            datetime.datetime.strptime(time, "%H:%M")
            
            notifications = self.load_notifications()
            notifications.append({
                "time": time,
                "message": message,
                "user_id": ctx.author.id,
                "user_name": ctx.author.display_name,
                "created_at": datetime.datetime.now(self.timezone).isoformat()
            })
            self.save_notifications(notifications)
            
            await ctx.send(f"✅ Đã đặt thông báo vào lúc **{time}** hàng ngày.\n> *Nội dung:* {message}")
        except ValueError:
            await ctx.send("❌ Định dạng thời gian không đúng. Vui lòng dùng `HH:MM` (ví dụ: `07:30`, `22:00`).")

    @commands.command(name='reminders', aliases=['notifs'])
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

    @commands.command(name='delnotify', aliases=['rmnotify'])
    async def delnotify(self, ctx, index: int):
        """Xóa thông báo theo số thứ tự. HD: !delnotify 1"""
        notifications = self.load_notifications()
        if 1 <= index <= len(notifications):
            removed = notifications.pop(index - 1)
            self.save_notifications(notifications)
            await ctx.send(f"✅ Đã xóa thông báo lúc **{removed['time']}**.")
        else:
            await ctx.send("❌ Số thứ tự không hợp lệ. Dùng `!reminders` để xem danh sách.")

    @commands.command(name='testweather', hidden=True)
    async def testweather(self, ctx, city: str = "Hanoi"):
        """Kiểm tra nhanh thông tin thời tiết"""
        weather_data = await self.get_weather(city)
        embed = discord.Embed(
            title=f"🌤️ Dự báo thời tiết: {city}",
            description=weather_data,
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Utility(bot))
