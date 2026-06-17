from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")

# Flash message support via cookie-based approach
# Messages are stored as JSON in a signed cookie, then cleared after reading
_flash_messages = {}  # session_id -> messages (fallback for in-memory)

def _get_flashed_messages(with_categories=False):
    """Get flashed messages. Returns list of (category, message) tuples if with_categories=True,
    otherwise just list of messages."""
    return []  # Placeholder - flash messages are handled via redirect query params in this app
templates.env.globals["get_flashed_messages"] = _get_flashed_messages
