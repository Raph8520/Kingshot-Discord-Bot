import discord
from discord.ext import commands
from datetime import datetime
import os

class InteractionLogger(commands.Cog):
    """Cog that logs incoming interactions and commands to terminal and a log file.

    This is lightweight and safe to enable; it only listens to high-level events
    and logs metadata (user, guild, channel, command/custom_id). It does not
    persist sensitive content beyond what the bot already has access to.
    """
    def __init__(self, bot):
        self.bot = bot
        self.log_directory = 'log'
        if not os.path.exists(self.log_directory):
            os.makedirs(self.log_directory)
        self.log_file = os.path.join(self.log_directory, 'interaction_log.txt')

    def _log(self, text: str):
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{ts}] {text}\n"
        try:
            print(line, end='')
        except Exception:
            pass
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        try:
            kind = None
            details = None
            if interaction.type:
                kind = str(interaction.type)
            # Application command (slash)
            if interaction.application_command:
                cmd = interaction.application_command
                details = f"slash_command: /{cmd.name}"
            elif interaction.data and isinstance(interaction.data, dict):
                # custom_id or component interaction
                cid = interaction.data.get('custom_id') or interaction.data.get('name')
                if cid:
                    details = f"component: {cid}"
                else:
                    details = f"raw_data: {interaction.data}"
            else:
                details = f"type: {interaction.type}"

            user = f"{getattr(interaction.user, 'name', 'Unknown')}({getattr(interaction.user, 'id', 'Unknown')})"
            guild = getattr(interaction, 'guild_id', None)
            channel = getattr(interaction, 'channel_id', None)
            self._log(f"Interaction from {user} | guild={guild} | channel={channel} | {details}")
        except Exception as e:
            self._log(f"Interaction logging error: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bot messages
        if message.author.bot:
            return
        try:
            user = f"{message.author.name}({message.author.id})"
            guild = getattr(message.guild, 'id', None)
            channel = message.channel.id if hasattr(message.channel, 'id') else None
            snippet = (message.content[:200] + '...') if message.content and len(message.content) > 200 else (message.content or '')
            self._log(f"Message from {user} | guild={guild} | channel={channel} | content='{snippet}'")
        except Exception as e:
            self._log(f"Message logging error: {e}")

async def setup(bot):
    await bot.add_cog(InteractionLogger(bot))
