def create_progress_bar(current, total, length=15):
    if total <= 0: return '──' + '🔘' + '──'
    percent = current / total
    filled = int(length * percent)
    bar = '▬' * filled + '🔘' + '─' * (length - filled - 1)
    return bar

def format_duration(seconds):
    if not seconds:
        return 'Live'
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'
