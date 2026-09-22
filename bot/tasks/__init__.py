"""
Bot Background Tasks Package Initialization
"""
from bot.tasks.auto_reminder import auto_remind_it
from bot.tasks.hub_sync import sync_hubs_with_db, sync_tickets_to_new_group
