"""
Backward-compatibility facade for bot_utils.
Forwards utility functions and keyboard builders to utils and bot packages.
"""
from utils.helpers import (
    get_adjusted_time,
    truncate_text,
    safe_edit_message,
    safe_send_content,
    send_ticket_to_group
)
from bot.keyboards import (
    get_report_keyboard,
    get_rating_keyboard
)