from datetime import datetime


def current_time() -> datetime:
    # Auction close times come from <input type="datetime-local"> as naive local timestamps.
    return datetime.now()
