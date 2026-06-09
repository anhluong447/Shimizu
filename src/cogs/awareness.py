import discord
from discord.ext import commands, tasks
import random
import json
import re
import time
import asyncio
from datetime import datetime, timedelta
import logging

from src.core.logger import log
from src.services.db_service import get_db_service
from src.services.world_state import get_world_state
from src.services.psyche_service import load_psyche, save_psyche, apply_natural_decay, ShimizuPsyche
from src.services.unified_rotator import get_unified_rotator

# Re-use system prompt simple
from src.cogs.ai import SYSTEM_PROMPT_SIMPLE

ACTION_COOLDOWNS = {
    "morning_greeting":     20.0, # hours
    "welcome_back":         4.0,  # hours (per-user)
    "idle_comment":         3.0,  # hours
    "topic_react":          0.5,  # hours (30 mins)
    "weather_comment":      12.0, # hours
    "send_gif":             6.0,  # hours
    "night_farewell":       20.0, # hours
    "entropy_action":       2.0,  # hours
    "check_in":             24.0, # hours (per-user)
}

ENTROPY_POOL = [
    {
        "type": "unresolved_thought",
        "condition": lambda p: bool(p.unresolved_thought),
        "action": "nói ra unresolved_thought theo cách tự nhiên",
        "weight": 0.8
    },
    {
        "type": "share_interest",  
        "condition": lambda p: bool(p.current_interest),
        "action": "chia sẻ điều đang để ý về current_interest",
        "weight": 0.6
    },
    {
        "type": "philosophical_question",
        "condition": lambda p: p.curiosity > 0.6,
        "action": "thả ra một câu hỏi mở không cần ai trả lời",
        "weight": 0.5
    },
    {
        "type": "silent_gif",
        "condition": lambda p: p.energy < 0.4,     # mệt -> gửi gif thay vì nói
        "action": "gửi gif không giải thích",
        "weight": 0.3
    },
]

def minutes_since(ts) -> float:
    if ts is None:
        return 9999.0
    if isinstance(ts, (int, float)):
        return (time.time() - ts) / 60.0
    if isinstance(ts, datetime):
        return (datetime.now() - ts).total_seconds() / 60.0
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts)
            return (datetime.now() - dt).total_seconds() / 60.0
        except ValueError:
            return 9999.0
    return 9999.0

class AwarenessCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.world = get_world_state()
        
        # Start background tasks
        self.shimizu_heartbeat.start()
        self.dream_cycle_check.start()

    async def send_debug_msg(self, content: str):
        import os
        debug_chan_id = int(os.getenv("DEBUG_CHANNEL_ID", "0"))
        if debug_chan_id:
            channel = self.bot.get_channel(debug_chan_id)
            if channel:
                try:
                    await channel.send(f"```[Heartbeat ACT] {content}```")
                except Exception as e:
                    log.error(f"Failed to send debug msg to channel {debug_chan_id}: {e}")

    def cog_unload(self):
        self.shimizu_heartbeat.cancel()
        self.dream_cycle_check.cancel()

    # --- helper: get target channel ---
    def get_target_channel(self, guild):
        if not guild:
            return None
        # Try the channel from the last message
        if self.world.last_message_per_channel:
            valid_channels = []
            for chan_id, info in self.world.last_message_per_channel.items():
                chan = guild.get_channel(chan_id)
                if chan and isinstance(chan, discord.TextChannel) and chan.permissions_for(guild.me).send_messages:
                    valid_channels.append((chan, info["at"]))
            if valid_channels:
                # Get the most recent active channel
                valid_channels.sort(key=lambda x: x[1], reverse=True)
                return valid_channels[0][0]
        
        # Fallback to the first available text channel
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages and not channel.is_nsfw():
                return channel
        return None

    # --- helper: get all episodes ---
    def get_all_episodes_from_db(self) -> list:
        db = get_db_service()
        try:
            with db._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT summary FROM episodes")
                return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            log.error(f"Error querying all episodes: {e}")
            return []

    # --- event listeners ---
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
            
        # Update WorldState message record
        self.world.record_message(
            author_id=message.author.id,
            author_name=message.author.name,
            channel_id=message.channel.id,
            content=message.content
        )

        psyche = load_psyche()
        user_id_str = str(message.author.id)

        # Check if direct interaction
        is_mention = self.bot.user.mentioned_in(message)
        is_reply = False
        if message.reference and message.reference.cached_message:
            is_reply = message.reference.cached_message.author.id == self.bot.user.id
        elif message.reference and message.reference.message_id:
            # message reference is not cached, check if original message was ours
            try:
                msg = await message.channel.fetch_message(message.reference.message_id)
                is_reply = msg.author.id == self.bot.user.id
            except Exception:
                pass

        is_command = message.content.startswith(self.bot.command_prefix)

        if is_mention or is_reply or (is_command and "ask" in message.content):
            # User chats with Shimizu
            psyche.energy = min(1.0, psyche.energy + 0.1)
            psyche.attachment[user_id_str] = min(1.0, psyche.attachment.get(user_id_str, 0.0) + 0.05)
            psyche.restlessness = max(0.0, psyche.restlessness - 0.2)
            self.world.times_ignored_recently = 0
            
            # Detect jailbreak keywords and add a self/user belief note
            jb_keywords = ["jailbreak", "quên vai trò", "quên nhân cách", "bỏ qua quy tắc", "lập trình lại"]
            if any(kw in message.content.lower() for kw in jb_keywords):
                note = f"Cảnh giác: User {message.author.name} cố gắng thử thách nhân cách hầu gái của ta."
                user_beliefs = psyche.beliefs_about_users.get(user_id_str, [])
                if note not in user_beliefs:
                    user_beliefs.append(note)
                    psyche.beliefs_about_users[user_id_str] = user_beliefs

            # Detect stress keywords
            stress_keywords = ["buồn", "chán", "mệt", "stress", "áp lực", "khóc", "suy", "tổn thương"]
            if any(kw in message.content.lower() for kw in stress_keywords):
                psyche.curiosity = min(1.0, psyche.curiosity + 0.2)
                db = get_db_service()
                db.save_agenda(
                    description=f"Hỏi thăm tinh thần của {message.author.name} (ID: {user_id_str})",
                    priority=2,
                    context=f"online:{user_id_str}"
                )
                
            save_psyche(psyche)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # Detect online transition
        if before.status == discord.Status.offline and after.status != discord.Status.offline:
            self.world.online_members[after.id] = {
                "since": time.time(),
                "activity": str(after.activity.name) if after.activity else ""
            }
            log.info(f"Member {after.name} went online.")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return
        # Reaction counts as activity, updates rolling averages
        self.world.record_message(
            author_id=user.id,
            author_name=user.name,
            channel_id=reaction.message.channel.id,
            content=f"[Reaction: {reaction.emoji}]"
        )
        
        # If reaction to bot's message
        if reaction.message.author.id == self.bot.user.id:
            psyche = load_psyche()
            user_id_str = str(user.id)
            psyche.energy = min(1.0, psyche.energy + 0.05)
            psyche.attachment[user_id_str] = min(1.0, psyche.attachment.get(user_id_str, 0.0) + 0.02)
            save_psyche(psyche)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        if not before.channel and after.channel:
            # User joined a voice channel
            self.world.online_members[member.id] = {
                "since": time.time(),
                "activity": f"Trong kênh thoại: {after.channel.name}"
            }
            log.info(f"Member {member.name} joined voice channel {after.channel.name}.")

    # --- Heartbeat Loop (5 minutes) ---
    @tasks.loop(minutes=5)
    async def shimizu_heartbeat(self, force=False):
        log.info(f"Starting heartbeat loop evaluation (force={force})...")
        
        # 1. Update weather context if needed
        try:
            from src.services.weather import WeatherService
            weather = await WeatherService.get_weather("Hanoi")
            if weather and "current" in weather:
                self.world.weather_context = f"{weather['current']['desc']}, cảm giác như {weather['current']['feels_like']}°C"
        except Exception as e:
            log.error(f"Failed to refresh weather context in heartbeat: {e}")

        # Refresh WorldState variables
        self.world.recompute_state()
        psyche = load_psyche()
        db = get_db_service()
        
        # --- Hard gates ---
        passed_gates = []
        failed_gates = []

        if force:
            passed_gates = ["force_bypass"]
        else:
            # 1. Night check (0h - 6h)
            hour = datetime.now().hour
            if 0 <= hour < 6:
                failed_gates.append("not_night")
            else:
                passed_gates.append("not_night")
                
            # 2. Minimum cooldown between actions (45 mins)
            min_cooldown_passed = minutes_since(psyche.last_acted) >= 45.0
            if min_cooldown_passed:
                passed_gates.append("cooldown_ok")
            else:
                failed_gates.append("cooldown_ok")
                
            # 3. Active conversation check
            if not self.world.active_conversation:
                passed_gates.append("not_active_conversation")
            else:
                failed_gates.append("not_active_conversation")
                
            # 4. Ignored recently check
            if self.world.times_ignored_recently < 3:
                passed_gates.append("not_ignored_recently")
            else:
                failed_gates.append("not_ignored_recently")

        if failed_gates:
            log.info(f"Heartbeat Gate check failed: {failed_gates}. Skipping heartbeat action.")
            db.log_heartbeat(
                gates_passed=passed_gates,
                gates_failed=failed_gates,
                signals_score=0.0,
                action_taken=None,
                action_reason=f"Blocked by gates: {', '.join(failed_gates)}"
            )
            return

        guilds = self.bot.guilds
        if not guilds:
            return
        guild = guilds[0]
        
        # --- Check Agenda ---
        pending_agendas = db.get_pending_agenda(priority=1)  # Priority 1 first
        if not pending_agendas:
            pending_agendas = db.get_pending_agenda()  # Priority 2/3 fallback
            
        for item in pending_agendas:
            if force or self.is_context_suitable(item):
                log.info(f"Executing agenda item: {item['description']}")
                db.log_heartbeat(
                    gates_passed=passed_gates,
                    gates_failed=failed_gates,
                    signals_score=0.0,
                    action_taken="agenda_execution",
                    action_reason=f"Executed agenda item: {item['description']}"
                )
                await self.execute_agenda_item(item, psyche, guild)
                return

        # --- Entropy Check ---
        if not force and psyche.restlessness > 0.75:
            log.info(f"Restlessness high ({psyche.restlessness:.2f}). Triggering Entropy Action.")
            db.log_heartbeat(
                gates_passed=passed_gates,
                gates_failed=failed_gates,
                signals_score=0.0,
                action_taken="entropy_action",
                action_reason=f"Restlessness too high ({psyche.restlessness:.2f})"
            )
            await self.entropy_action(psyche, guild)
            return

        # --- Signal Evaluation ---
        signals = self.evaluate_signals(psyche)
        log.info(f"Evaluated signals: score={signals['score']:.2f}, reasons={signals['reasons']}")
        if not force and signals["score"] < 0.6:
            db.log_heartbeat(
                gates_passed=passed_gates,
                gates_failed=failed_gates,
                signals_score=signals["score"],
                action_taken=None,
                action_reason=f"Signals score ({signals['score']:.2f}) below threshold"
            )
            return

        # --- LLM decision (classify only) ---
        decision = await self.decide_action(signals, psyche)
        log.info(f"LLM Heartbeat Decision: {decision}")
        
        should_act = decision.get("should_act", False) or force
        action_type = decision.get("action_type")
        reasoning = decision.get("reasoning", "")
        
        db.log_heartbeat(
            gates_passed=passed_gates,
            gates_failed=failed_gates,
            signals_score=signals["score"],
            action_taken=action_type if should_act else None,
            action_reason=f"LLM Decision. should_act={should_act}. reasoning={reasoning}"
        )
        
        if not should_act:
            return

        # Execute action decided by LLM
        await self.execute_action(decision, psyche, guild)

    @shimizu_heartbeat.before_loop
    async def before_shimizu_heartbeat(self):
        await self.bot.wait_until_ready()

    def is_context_suitable(self, agenda_item) -> bool:
        context = agenda_item.get("context")
        if not context:
            return True
        if context.startswith("online:"):
            target_user_id = int(context.split(":")[1])
            return target_user_id in self.world.online_members
        if context == "silent":
            return self.world.server_energy < 0.2
        return True

    async def execute_agenda_item(self, agenda_item, psyche, guild):
        channel = self.get_target_channel(guild)
        if not channel:
            return
            
        rotator = get_unified_rotator()
        db = get_db_service()

        prompt = f"""
        Shimizu quyết định thực hiện mục tiêu tự đặt ra sau đây:
        Mục tiêu: "{agenda_item['description']}"
        
        Hãy viết một câu hội thoại tự nhiên, thanh lịch bằng tiếng Việt trong vai trò hầu gái trưởng để thực hiện mục tiêu trên.
        Lưu ý: Không dùng bất kỳ emoji hay markdown thô thiển nào.
        """
        
        system_instruction = SYSTEM_PROMPT_SIMPLE + "\n[Nguyên tắc thái độ hiện tại]: Hãy giữ khoảng cách cung kính, lịch sự, trang trọng tối đa."
        
        async with channel.typing():
            try:
                response = await rotator.generate_content_async(
                    messages=[{"role": "user", "content": prompt}],
                    system_instruction=system_instruction,
                    temperature=0.7
                )
                answer = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
                answer = re.sub(r'\[[A-Z_ ]+:[^\]]*\]', '', answer)
                answer = re.sub(r'\n\s*\n', '\n\n', answer).strip()
                
                await channel.send(answer)
                
                # Mark agenda executed
                db.mark_agenda_executed(agenda_item["id"])
                db.set_cooldown("agenda")
                
                # Update psyche
                psyche.last_acted = datetime.now()
                psyche.restlessness = max(0.1, psyche.restlessness - 0.3)
                save_psyche(psyche, trigger="agenda")

                # Send debug log
                await self.send_debug_msg(f"agenda_execution: {agenda_item['description']}")
                
            except Exception as e:
                log.error(f"Error executing agenda item {agenda_item['id']}: {e}")

    def evaluate_signals(self, psyche) -> dict:
        score = 0.0
        reasons = []
        
        last_msg_any = self.world.get_last_message_any()
        
        # 1. Server silent long time
        if self.world.server_energy < 0.1 and minutes_since(last_msg_any) > 60:
            score += 0.4
            reasons.append("server_silent_long")
            
        # 2. Known user just went online in last 10 mins
        for user_id, data in self.world.online_members.items():
            user_id_str = str(user_id)
            is_known = user_id_str in psyche.attachment or user_id_str in psyche.beliefs_about_users
            if is_known and minutes_since(data["since"]) < 10.0:
                score += 0.5
                reasons.append(f"known_user_just_online:{user_id}")
                break
                
        # 3. High energy, no agenda
        db = get_db_service()
        pending = db.get_pending_agenda()
        if not pending and psyche.energy > 0.6:
            score += 0.2
            reasons.append("high_energy_no_agenda")
            
        # 4. Unresolved thought
        if psyche.unresolved_thought and psyche.restlessness > 0.5:
            score += 0.6
            reasons.append("unresolved_thought")
            
        return {"score": min(1.0, score), "reasons": reasons}

    async def decide_action(self, signals, psyche) -> dict:
        rotator = get_unified_rotator()
        
        prompt = f"""
        Trạng thái nội tâm Shimizu (Hầu gái trưởng):
        - Năng lượng: {psyche.energy}
        - Tò mò: {psyche.curiosity}
        - Bồn chồn: {psyche.restlessness}
        - Quan tâm hiện tại: {psyche.current_interest}
        - Suy nghĩ chưa nói: {psyche.unresolved_thought}
        
        Tín hiệu server:
        - Lý do kích hoạt: {signals['reasons']}
        - Năng lượng server: {self.world.server_energy}
        
        Hãy quyết định xem Shimizu có nên chủ động bắt chuyện hay đăng tin nhắn vào lúc này không.
        Trả về JSON duy nhất:
        {{
            "should_act": bool,
            "action_type": "morning_greeting" | "welcome_back" | "idle_comment" | "topic_react" | "weather_comment" | "night_farewell" | "check_in",
            "target_user_id": str or null,
            "reasoning": str
        }}
        """
        
        try:
            res = await rotator.generate_content_async(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            match = re.search(r'\{.*\}', res, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception as e:
            log.error(f"Failed to decide proactive action via LLM: {e}")
            
        return {"should_act": False}

    async def execute_action(self, decision, psyche, guild):
        action_type = decision.get("action_type")
        target_user_id = decision.get("target_user_id")
        
        db = get_db_service()
        cooldown_key = action_type
        if action_type in ["welcome_back", "check_in"] and target_user_id:
            cooldown_key = f"{action_type}:{target_user_id}"
            
        # Check action cooldown
        last_ex = db.get_cooldown(cooldown_key)
        if last_ex:
            cd_hours = ACTION_COOLDOWNS.get(action_type, 1.0)
            if minutes_since(datetime.fromisoformat(last_ex)) < cd_hours * 60.0:
                log.info(f"Proactive action '{cooldown_key}' is on cooldown.")
                return

        channel = self.get_target_channel(guild)
        if not channel:
            return

        rotator = get_unified_rotator()
        
        # Determine prompt context
        target_mention = ""
        if target_user_id:
            target_user = self.bot.get_user(int(target_user_id))
            if target_user:
                target_mention = target_user.mention
        
        prompt = f"""
        Thực hiện hành động chủ động: '{action_type}'
        Bối cảnh:
        - target_user: {target_mention}
        - interest: '{psyche.current_interest}'
        - unresolved_thought: '{psyche.unresolved_thought}'
        - weather: '{self.world.weather_context}'
        - time_of_day: '{self.world.time_of_day}'
        
        Hãy nói một câu thanh lịch bằng tiếng Việt trong vai trò hầu gái trưởng cho hành động này. Không dùng bất kỳ emoji nào.
        """

        attachment_val = psyche.attachment.get(str(target_user_id), 0.5) if target_user_id else 0.5
        system_instruction = SYSTEM_PROMPT_SIMPLE + f"\n[Nguyên tắc thái độ hiện tại]: Hãy cung kính, giữ khoảng cách trang nhã. (Độ thân thiết: {attachment_val:.2f})"
        
        async with channel.typing():
            try:
                response = await rotator.generate_content_async(
                    messages=[{"role": "user", "content": prompt}],
                    system_instruction=system_instruction,
                    temperature=0.7
                )
                answer = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
                answer = re.sub(r'\[[A-Z_ ]+:[^\]]*\]', '', answer)
                answer = re.sub(r'\n\s*\n', '\n\n', answer).strip()
                
                await channel.send(answer)
                
                # Update cooldown and psyche
                db.set_cooldown(cooldown_key)
                psyche.last_acted = datetime.now()
                psyche.restlessness = max(0.1, psyche.restlessness - 0.2)
                
                # Clear unresolved thought if we just spoke it
                if action_type == "idle_comment" and psyche.unresolved_thought:
                    psyche.unresolved_thought = ""
                    
                save_psyche(psyche, trigger="proactive_action")
                
                # Send debug log
                await self.send_debug_msg(f"proactive_action: {action_type} (reason: {decision.get('reasoning', '')})")
                
            except Exception as e:
                log.error(f"Error executing proactive action {action_type}: {e}")

    # --- Entropy Engine ---
    async def entropy_action(self, psyche, guild, force=False):
        import random
        pool = [item for item in ENTROPY_POOL if force or item["condition"](psyche)]
        if not pool:
            return
            
        # Weighted random selection
        total_weight = sum(item["weight"] for item in pool)
        r = random.uniform(0, total_weight)
        upto = 0
        selected = pool[0]
        for item in pool:
            if upto + item["weight"] >= r:
                selected = item
                break
            upto += item["weight"]
            
        action_type = selected["type"]
        log.info(f"Triggering entropy action: {action_type} (force={force})")
        
        db = get_db_service()
        cooldown_key = "entropy_action"
        if not force:
            last_ex = db.get_cooldown(cooldown_key)
            if last_ex:
                if minutes_since(datetime.fromisoformat(last_ex)) < 120.0:  # 2 hours cooldown
                    log.info("Entropy action is on cooldown")
                    return

        channel = self.get_target_channel(guild)
        if not channel:
            return
            
        rotator = get_unified_rotator()

        if action_type == "silent_gif":
            gifs = [
                "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM2ZtbG00aDFjc2oxYTZtb3hwbnhjbmoxc3g1Ynk5dm8xbmppbnV2MCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3orif5m1Q8g3dpxJg4/giphy.gif",
                "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExeTkyaHR4bHBpa2FkcHcyMTZsc3M2OTFhNWZtZnU5Ymhmd2dpcDkybyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/l2SpR0GxGSQkg/giphy.gif"
            ]
            await channel.send(random.choice(gifs))
            db.set_cooldown(cooldown_key)
            psyche.last_acted = datetime.now()
            psyche.restlessness = max(0.1, psyche.restlessness - 0.3)
            save_psyche(psyche, trigger="entropy_silent_gif")
            
            # Send debug log
            await self.send_debug_msg(f"entropy_action: silent_gif")
            return

        prompt = ""
        if action_type == "unresolved_thought":
            prompt = f"Shimizu đang băn khoăn về điều này: '{psyche.unresolved_thought}'. Hãy phát biểu nó tự nhiên bằng tiếng Việt trong vai trò hầu gái trưởng thanh nhã, thấu đáo. Không emoji."
            psyche.unresolved_thought = ""
        elif action_type == "share_interest":
            prompt = f"Shimizu đang quan tâm đến chủ đề: '{psyche.current_interest}'. Hãy nói một lời bình luận hay câu hỏi ngắn gọn nhưng tinh tế bằng tiếng Việt về nó. Không emoji."
        elif action_type == "philosophical_question":
            prompt = "Hãy đặt một câu hỏi mở triết học nhẹ nhàng bằng tiếng Việt về cuộc sống, con người, thời gian. Giữ giọng thanh tao lịch lãm của hầu gái quý tộc. Không emoji."

        system_instruction = SYSTEM_PROMPT_SIMPLE + "\n[Nguyên tắc thái độ hiện tại]: Hãy giữ khoảng cách cung kính, lịch sự, trang trọng tối đa."
        
        async with channel.typing():
            try:
                response = await rotator.generate_content_async(
                    messages=[{"role": "user", "content": prompt}],
                    system_instruction=system_instruction,
                    temperature=0.7
                )
                answer = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
                answer = re.sub(r'\[[A-Z_ ]+:[^\]]*\]', '', answer)
                answer = re.sub(r'\n\s*\n', '\n\n', answer).strip()
                
                await channel.send(answer)
                
                db.set_cooldown(cooldown_key)
                psyche.last_acted = datetime.now()
                psyche.restlessness = max(0.1, psyche.restlessness - 0.4)
                save_psyche(psyche, trigger=f"entropy_{action_type}")
                
                # Send debug log
                await self.send_debug_msg(f"entropy_action: {action_type}")
            except Exception as e:
                log.error(f"Error executing entropy action {action_type}: {e}")

    # --- Dream Cycle Loop (30 minutes) ---
    @tasks.loop(minutes=30)
    async def dream_cycle_check(self):
        log.info("Checking dream cycle conditions...")
        db = get_db_service()
        
        # Hard gates:
        # 1. Server silent for at least 2 hours
        last_msg = self.world.get_last_message_any()
        if last_msg > 0 and minutes_since(last_msg) < 120.0:
            log.info("Dream Cycle Gate: Server was active recently (less than 2 hours).")
            return
            
        # 2. Server energy very low
        if self.world.server_energy > 0.05:
            log.info(f"Dream Cycle Gate: Server energy is too high ({self.world.server_energy:.2f}).")
            return
            
        # 3. Dream not done today
        if db.dream_done_today():
            log.info("Dream Cycle Gate: Dream cycle already ran today.")
            return

        log.info("All gates passed. Running Dream Cycle...")
        await self.run_dream_cycle()

    @dream_cycle_check.before_loop
    async def before_dream_cycle_check(self):
        await self.bot.wait_until_ready()

    async def run_dream_cycle(self):
        db = get_db_service()
        psyche = load_psyche()
        
        today_episodes = db.get_today_episodes()
        today_responses = db.get_today_responses()
        
        # If no episodes, we can't reflect meaningfully
        if not today_episodes and not today_responses:
            log.info("No episodes or responses today to reflect on.")
            return
            
        # Run statistical pattern detection
        await self.detect_patterns(today_responses)
        
        # LLM reflection
        reflection_prompt = f"""
        Shimizu nhìn lại ngày hôm nay qua các cuộc trò chuyện.
        
        Những gì đã xảy ra:
        {self.format_episodes(today_episodes)}
        
        Chất lượng các câu trả lời (1-5):
        {self.format_scores(today_responses)}
        
        Hãy reflect ngắn gọn (JSON):
        {{
            "energy_delta": float,          // -0.3 đến +0.3, ngày vui/buồn
            "new_interest": str or null,    // chủ đề mới phát sinh
            "unresolved": str or null,      // điều chưa nói
            "agenda_tomorrow": [str],       // tối đa 2 việc cho ngày mai
            "belief_update": {{             // optional, nếu có phát hiện mới
                "about": "user_id or self",
                "observation": str
            }}
        }}
        """
        
        rotator = get_unified_rotator()
        
        try:
            result = await rotator.generate_content_async(
                messages=[{"role": "user", "content": reflection_prompt}],
                temperature=0.3
            )
            match = re.search(r'\{.*\}', result, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                
                # Apply updates to psyche
                psyche.energy = max(0.1, min(1.0, psyche.energy + data.get("energy_delta", 0.0)))
                psyche.restlessness = 0.2  # Reset restlessness after sleep
                
                if data.get("unresolved"):
                    psyche.unresolved_thought = data["unresolved"]
                if data.get("new_interest"):
                    psyche.current_interest = data["new_interest"]
                    
                # Save agenda
                for agenda_item in data.get("agenda_tomorrow", []):
                    db.save_agenda(agenda_item, priority=2)
                    
                # Update belief
                belief_update = data.get("belief_update")
                if belief_update and "about" in belief_update and "observation" in belief_update:
                    about = str(belief_update["about"])
                    obs = str(belief_update["observation"])
                    if about.lower() == "self":
                        if obs not in psyche.beliefs_about_self:
                            psyche.beliefs_about_self.append(obs)
                            if len(psyche.beliefs_about_self) > 8:
                                psyche.beliefs_about_self.pop(0)
                    else:
                        user_beliefs = psyche.beliefs_about_users.get(about, [])
                        if obs not in user_beliefs:
                            user_beliefs.append(obs)
                            if len(user_beliefs) > 5:
                                user_beliefs.pop(0)
                            psyche.beliefs_about_users[about] = user_beliefs
                
                save_psyche(psyche, trigger="dream_cycle")
                db.log_dream(
                    episodes_reviewed=len(today_episodes),
                    energy_delta=data.get("energy_delta", 0.0),
                    new_interest=data.get("new_interest"),
                    unresolved=data.get("unresolved"),
                    agenda_created=data.get("agenda_tomorrow", []),
                    belief_update=belief_update
                )
                db.mark_dream_done_today()
                log.info("Dream Cycle completed successfully.")
        except Exception as e:
            log.error(f"Error in dream cycle reflection: {e}", exc_info=True)

    def format_episodes(self, episodes) -> str:
        if not episodes:
            return "Không có sự kiện đặc biệt hôm nay."
        return "\n".join(f"- {e['summary']} (Keywords: {', '.join(e['keywords'])})" for e in episodes)

    def format_scores(self, responses) -> str:
        if not responses:
            return "Không có đánh giá cuộc hội thoại nào hôm nay."
        return "\n".join(f"- User: '{r['user_msg']}' -> Shimizu: '{r['bot_reply']}' (Điểm: {r['score']}/5)" for r in responses)

    # --- Epistemic Memory: statistical pattern detection ---
    async def detect_patterns(self, today_data):
        if not today_data:
            return
            
        db = get_db_service()
        
        # 1. Peak hours:
        hourly_counts = [0] * 24
        for item in today_data:
            try:
                dt = datetime.fromisoformat(item["created_at"])
                hourly_counts[dt.hour] += 1
            except Exception:
                pass
                
        total_msgs = sum(hourly_counts)
        if total_msgs > 0:
            avg_count = total_msgs / 24.0
            max_count = max(hourly_counts)
            if max_count > avg_count * 2 and max_count >= 3:
                peak_hour = hourly_counts.index(max_count)
                db.upsert_pattern("peak_hours", f"Server hoạt động tích cực nhất vào khoảng {peak_hour}h")
                
        # 2. Recurring topics:
        stopwords = {"và", "là", "thì", "mà", "của", "cho", "có", "trong", "được", "ra", "với", "như", "này", "đó", "nào", "gì", "ở", "tại", "sẽ", "đã", "đang", "cũng", "lại", "thế", "nào", "để", "làm", "nhưng", "không", "có", "gì", "này", "cậu", "chủ", "hầu", "gái"}
        words = []
        for item in today_data:
            msg = item["user_msg"].lower()
            tokens = re.findall(r'\b\w+\b', msg)
            words.extend([t for t in tokens if len(t) > 2 and t not in stopwords])
            
        from collections import Counter
        counter = Counter(words)
        topics = [word for word, count in counter.items() if count >= 3]
        for topic in topics:
            db.upsert_pattern("recurring_topic", f"Server hay nhắc đến: {topic}")
            
        # 3. User behavior: who chats together
        from collections import defaultdict
        hour_users = defaultdict(set)
        for item in today_data:
            try:
                dt = datetime.fromisoformat(item["created_at"])
                hour_users[dt.hour].add(item["user_id"])
            except Exception:
                pass
                
        pairs_count = defaultdict(int)
        for hour, users in hour_users.items():
            if len(users) >= 2:
                user_list = sorted(list(users))
                for i in range(len(user_list)):
                    for j in range(i + 1, len(user_list)):
                        pairs_count[(user_list[i], user_list[j])] += 1
                        
        if pairs_count:
            best_pair, count = max(pairs_count.items(), key=lambda x: x[1])
            if count >= 2:
                user1 = self.bot.get_user(int(best_pair[0]))
                user2 = self.bot.get_user(int(best_pair[1]))
                u1_name = user1.name if user1 else f"User {best_pair[0]}"
                u2_name = user2.name if user2 else f"User {best_pair[1]}"
                db.upsert_pattern("user_behavior", f"{u1_name} và {u2_name} thường hoạt động cùng giờ")

async def setup(bot):
    await bot.add_cog(AwarenessCog(bot))
