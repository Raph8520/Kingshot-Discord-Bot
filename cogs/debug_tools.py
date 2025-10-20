import discord
from discord.ext import commands
import traceback
import os
from datetime import datetime


class DebugTools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="debug_load_gift_ops", with_app_command=True, description="Admin: attempt to load the GiftOperations cog and report any short error")
    async def debug_load_gift_ops(self, ctx: commands.Context):
        # Permission: only allow configured admins in settings DB (consistent with other cogs)
        try:
            settings_conn = __import__('sqlite3').connect('db/settings.sqlite')
            sc = settings_conn.cursor()
            sc.execute("SELECT id FROM admin")
            admins = [r[0] for r in sc.fetchall()]
            settings_conn.close()
        except Exception:
            admins = []

        if ctx.author.id not in admins:
            await ctx.reply("You are not authorized to run debug commands.", ephemeral=True)
            return

        # Try to load the cog and capture exceptions
        try:
            if ctx.bot.get_cog('GiftOperations'):
                await ctx.reply('GiftOperations is already loaded.', ephemeral=True)
                return

            await ctx.bot.load_extension('cogs.gift_operations')
            await ctx.reply('GiftOperations loaded successfully.', ephemeral=True)
            print('[debug_tools] Successfully dynamically loaded cogs.gift_operations')
        except Exception as e:
            # Write full traceback to alliance_errors.txt for parity with alliance handling
            try:
                log_dir = os.path.join(os.getcwd(), 'log')
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                log_path = os.path.join(log_dir, 'alliance_errors.txt')
                with open(log_path, 'a', encoding='utf-8') as lf:
                    lf.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] DebugTools failed to load GiftOperations: {e}\n")
                    lf.write(''.join(traceback.format_exception(type(e), e, e.__traceback__)))
                    lf.write('\n')
            except Exception as write_e:
                print(f"[debug_tools] Failed to write log: {write_e}")

            # Print full traceback to console so it appears in your terminal
            print('[debug_tools] Exception while loading cogs.gift_operations:')
            traceback.print_exc()

            short_msg = str(e).split('\n')[0][:300]
            try:
                await ctx.reply(f'Failed to load GiftOperations (error: {short_msg}). See alliance_errors.txt for full traceback.', ephemeral=True)
            except Exception:
                # If reply fails, fallback to channel message
                await ctx.send(f'Failed to load GiftOperations (error: {short_msg}). See alliance_errors.txt for full traceback.')


async def setup(bot):
    await bot.add_cog(DebugTools(bot))
