import discord
from discord.ext import commands
from src.services.db_service import get_db_service
import json
from datetime import datetime

class DebugCog(commands.Cog, name="Debug"):
    """Owner-only debug commands cho Shimizu living entity system."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = get_db_service()

    # ─── PSYCHE ───────────────────────────────────────────────

    @commands.command(name="debug_psyche")
    @commands.is_owner()
    async def debug_psyche(self, ctx):
        """Hiển thị psyche state hiện tại."""
        rows = self.db._get_conn().execute(
            "SELECT * FROM psyche_log ORDER BY logged_at DESC LIMIT 1"
        ).fetchone()
        
        if not rows:
            await ctx.send("```Chưa có psyche data. Living entity chưa được khởi tạo.```")
            return
        
        r = dict(rows)
        
        def bar(val: float, width: int = 8) -> str:
            filled = round(val * width)
            return "█" * filled + "░" * (width - filled)
        
        msg = f"""```
SHIMIZU PSYCHE STATE — {r['logged_at']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
energy        {bar(r['energy'])}  {r['energy']:.2f}
curiosity     {bar(r['curiosity'])}  {r['curiosity']:.2f}
restlessness  {bar(r['restlessness'])}  {r['restlessness']:.2f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
interest    : {r['current_interest'] or '(none)'}
unresolved  : {r['unresolved'] or '(none)'}
trigger     : {r['trigger']}
```"""
        await ctx.send(msg)

    @commands.command(name="debug_psyche_history")
    @commands.is_owner()
    async def debug_psyche_history(self, ctx, limit: int = 10):
        """Xem psyche thay đổi như thế nào theo thời gian."""
        rows = self.db._get_conn().execute(
            "SELECT * FROM psyche_log ORDER BY logged_at DESC LIMIT ?", (limit,)
        ).fetchall()
        
        if not rows:
            await ctx.send("```Chưa có data.```")
            return
        
        lines = ["```", f"PSYCHE HISTORY (last {limit})", "━" * 60]
        for r in reversed(rows):
            r = dict(r)
            time_str = r['logged_at'][11:16]  # HH:MM
            lines.append(
                f"{time_str}  E:{r['energy']:.2f} C:{r['curiosity']:.2f} R:{r['restlessness']:.2f}  [{r['trigger']}]"
            )
        lines.append("```")
        await ctx.send("\n".join(lines))

    # ─── HEARTBEAT ────────────────────────────────────────────

    @commands.command(name="debug_heartbeat")
    @commands.is_owner()
    async def debug_heartbeat(self, ctx, limit: int = 10):
        """Xem 10 heartbeat ticks gần nhất — gate nào pass/fail, có act không."""
        rows = self.db.get_heartbeat_log(limit=limit)
        
        if not rows:
            await ctx.send("```Chưa có heartbeat log. Heartbeat loop chưa chạy.```")
            return
        
        lines = ["```", f"HEARTBEAT LOG (last {limit} ticks)", "━" * 60]
        for r in reversed(rows):
            time_str = r['tick_at'][11:16]
            failed = json.loads(r['gates_failed'] or '[]')
            action = r['action_taken'] or '—'
            score = f"{r['signals_score']:.2f}" if r['signals_score'] else "n/a"
            
            if failed:
                status = f"✗ SKIP [{', '.join(failed)}]"
            elif action != '—':
                status = f"✓ ACT  [{action}]"
            else:
                status = f"~ EVAL score={score} → no act"
            
            lines.append(f"{time_str}  {status}")
            if r['action_reason'] and action != '—':
                lines.append(f"       reason: {r['action_reason']}")
        
        lines.append("```")
        await ctx.send("\n".join(lines))

    # ─── DREAM CYCLE ──────────────────────────────────────────

    @commands.command(name="debug_dream")
    @commands.is_owner()
    async def debug_dream(self, ctx):
        """Xem kết quả Dream Cycle đêm qua."""
        r = self.db.get_latest_dream()
        
        if not r:
            await ctx.send("```Dream Cycle chưa bao giờ chạy.```")
            return
        
        agenda = json.loads(r['agenda_created'] or '[]')
        belief = json.loads(r['belief_update']) if r['belief_update'] else None
        delta_str = f"+{r['energy_delta']:.2f}" if r['energy_delta'] >= 0 else f"{r['energy_delta']:.2f}"
        
        lines = [
            "```",
            f"DREAM CYCLE — {r['ran_at']}",
            "━" * 50,
            f"Episodes reviewed : {r['episodes_reviewed']}",
            f"Energy delta      : {delta_str}",
            f"New interest      : {r['new_interest'] or '(none)'}",
            f"Unresolved        : {r['unresolved'] or '(none)'}",
            f"Agenda created    : {len(agenda)} item(s)",
        ]
        for i, a in enumerate(agenda, 1):
            lines.append(f"  [{i}] {a}")
        if belief:
            lines.append(f"Belief update     : {belief}")
        lines.append("```")
        await ctx.send("\n".join(lines))

    # ─── MEMORY & FACTS ───────────────────────────────────────

    @commands.command(name="debug_memory")
    @commands.is_owner()
    async def debug_memory(self, ctx, user: discord.Member = None):
        """Xem facts và episodes đã lưu của một user."""
        target = user or ctx.author
        user_id = str(target.id)
        
        facts = self.db.get_facts(user_id)
        episodes = self.db.get_episodes(user_id)
        
        lines = ["```", f"MEMORY — {target.display_name}", "━" * 50]
        
        lines.append(f"FACTS ({len(facts)}):")
        if facts:
            for k, v in facts.items():
                lines.append(f"  {k}: {v}")
        else:
            lines.append("  (trống)")
        
        lines.append(f"\nEPISODES ({len(episodes)}):")
        if episodes:
            for ep in episodes[-5:]:  # 5 gần nhất
                lines.append(f"  [{ep.get('created_at', '')[:10]}] {ep.get('summary', '')[:60]}...")
        else:
            lines.append("  (trống)")
        
        lines.append("```")
        await ctx.send("\n".join(lines))

    @commands.command(name="debug_scores")
    @commands.is_owner()
    async def debug_scores(self, ctx, limit: int = 10):
        """Xem response quality scores gần nhất."""
        rows = self.db._get_conn().execute(
            "SELECT user_id, score, user_msg, bot_reply, created_at FROM responses ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        
        if not rows:
            await ctx.send("```Chưa có response data.```")
            return
        
        lines = ["```", f"RESPONSE SCORES (last {limit})", "━" * 50]
        score_map = {1: "★☆☆☆☆", 2: "★★☆☆☆", 3: "★★★☆☆", 4: "★★★★☆", 5: "★★★★★"}
        for r in rows:
            r = dict(r)
            stars = score_map.get(r['score'], "?")
            time_str = r['created_at'][11:16]
            user_short = r['user_msg'][:30] + "..." if len(r['user_msg']) > 30 else r['user_msg']
            lines.append(f"{time_str}  {stars}  \"{user_short}\"")
        lines.append("```")
        await ctx.send("\n".join(lines))

    # ─── FORCE TRIGGERS ───────────────────────────────────────

    @commands.command(name="debug_force_heartbeat")
    @commands.is_owner()
    async def debug_force_heartbeat(self, ctx):
        """Bypass tất cả gates, chạy heartbeat decision ngay bây giờ."""
        cog = self.bot.get_cog("AwarenessCog")
        if not cog or not hasattr(cog, 'shimizu_heartbeat'):
            await ctx.send("```Heartbeat loop chưa được implement trong AwarenessCog.```")
            return
        
        await ctx.send("```Forcing heartbeat tick (all gates bypassed)...```")
        await cog.shimizu_heartbeat.coro(cog, force=True)

    @commands.command(name="debug_force_dream")
    @commands.is_owner()
    async def debug_force_dream(self, ctx):
        """Chạy Dream Cycle ngay lập tức, không cần server offline."""
        cog = self.bot.get_cog("AwarenessCog")
        if not cog or not hasattr(cog, 'run_dream_cycle'):
            await ctx.send("```Dream Cycle chưa được implement trong AwarenessCog.```")
            return
        
        await ctx.send("```Running Dream Cycle now...```")
        await cog.run_dream_cycle()
        await ctx.send("```Done. Dùng !debug_dream để xem kết quả.```")

    @commands.command(name="debug_force_entropy")
    @commands.is_owner()
    async def debug_force_entropy(self, ctx):
        """Trigger entropy action ngay — test xem bot sẽ làm gì khi restless."""
        cog = self.bot.get_cog("AwarenessCog")
        if not cog or not hasattr(cog, 'entropy_action'):
            await ctx.send("```Entropy engine chưa được implement trong AwarenessCog.```")
            return
        
        await ctx.send("```Triggering entropy action...```")
        from src.services.psyche_service import load_psyche
        psyche = load_psyche()
        guilds = self.bot.guilds
        if not guilds:
            await ctx.send("```Không tìm thấy Guild nào để chạy entropy action.```")
            return
        guild = guilds[0]
        await cog.entropy_action(psyche, guild, force=True)

    @commands.command(name="debug_set_psyche")
    @commands.is_owner()
    async def debug_set_psyche(self, ctx, field: str, value: float):
        """
        Override một psyche field để test behavior.
        Usage: !debug_set_psyche restlessness 0.9
        Fields: energy, curiosity, restlessness
        """
        valid_fields = ["energy", "curiosity", "restlessness"]
        if field not in valid_fields:
            await ctx.send(f"```Field không hợp lệ. Dùng: {', '.join(valid_fields)}```")
            return
        if not 0.0 <= value <= 1.0:
            await ctx.send("```Value phải từ 0.0 đến 1.0```")
            return
        
        from src.services.psyche_service import load_psyche, save_psyche
        try:
            psyche = load_psyche()
            setattr(psyche, field, value)
            save_psyche(psyche, trigger="manual")
            await ctx.send(f"```✓ Set {field} = {value:.2f} (saved and logged to psyche_log)```")
        except Exception as e:
            await ctx.send(f"```Error setting psyche field: {e}```")

    # ─── DB HEALTH ────────────────────────────────────────────

    @commands.command(name="debug_db")
    @commands.is_owner()
    async def debug_db(self, ctx):
        """Kiểm tra sức khỏe DB — row counts, disk size."""
        conn = self.db._get_conn()
        
        tables = ["user_facts", "episodes", "message_history", "responses",
                  "search_cache", "heartbeat_log", "psyche_log", "dream_log"]
        
        lines = ["```", "DB HEALTH", "━" * 40]
        total = 0
        for table in tables:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                lines.append(f"  {table:<20} {count:>6} rows")
                total += count
            except Exception:
                lines.append(f"  {table:<20}  (table not found)")
        
        lines.append("━" * 40)
        lines.append(f"  {'TOTAL':<20} {total:>6} rows")
        
        # DB file size
        import os
        db_path = "data/shimizu.db"
        if os.path.exists(db_path):
            size_kb = os.path.getsize(db_path) // 1024
            lines.append(f"  DB size: {size_kb} KB")
        
        lines.append("```")
        await ctx.send("\n".join(lines))

    @commands.command(name="debug_cleanup")
    @commands.is_owner()
    async def debug_cleanup(self, ctx, days: int = 7):
        """Xóa logs cũ hơn N ngày. Default: 7 ngày."""
        self.db.cleanup_old_logs(days=days)
        await ctx.send(f"```✓ Đã xóa logs cũ hơn {days} ngày.```")

    # ─── HELP ─────────────────────────────────────────────────

    @commands.command(name="debug_help")
    @commands.is_owner()
    async def debug_help(self, ctx):
        """Liệt kê tất cả debug commands."""
        msg = """```
SHIMIZU DEBUG COMMANDS (owner only)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OBSERVE
  !debug_psyche              Psyche state hiện tại
  !debug_psyche_history [N]  Lịch sử thay đổi psyche
  !debug_heartbeat [N]       N heartbeat ticks gần nhất
  !debug_dream               Kết quả Dream Cycle đêm qua
  !debug_memory [@user]      Facts + episodes của user
  !debug_scores [N]          Response quality scores
  !debug_db                  DB health + row counts
 
FORCE TRIGGER (để test)
  !debug_force_heartbeat     Bypass gates, chạy heartbeat ngay
  !debug_force_dream         Chạy Dream Cycle ngay
  !debug_force_entropy       Trigger entropy action ngay
  !debug_set_psyche <field> <0.0-1.0>
                             Override psyche field
 
MAINTENANCE
  !debug_cleanup [days]      Xóa logs cũ (default: 7 ngày)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```"""
        await ctx.send(msg)

async def setup(bot):
    await bot.add_cog(DebugCog(bot))
