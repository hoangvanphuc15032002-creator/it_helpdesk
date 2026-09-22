"""
Bot Handlers Package
Assembles all Telegram message & callback handlers into the bot instance.
"""
from bot.handlers.commands import register_command_handlers
from bot.handlers.routing import register_routing_handlers
from bot.handlers.callbacks import register_callback_handlers

def setup_bot_handlers(current_bot):
    register_command_handlers(current_bot)
    register_routing_handlers(current_bot)
    register_callback_handlers(current_bot)
