"""
Root Telegram Bot Runner Entrypoint
Delegates execution to bot.runner package.
"""
from bot.runner import start_bot, sync_tickets_to_new_group, sync_hubs_with_db, auto_remind_it, run_bot_polling, config_watchdog

if __name__ == '__main__':
    start_bot()