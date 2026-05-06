from datetime import datetime, timedelta
from database import get_db

TESTING = True  # set to False when deploying for real

def is_within_session_window(course_code, window_minutes=15):
    if TESTING:
        return True, 'Testing mode — window bypassed'

    conn = get_db()
    course = conn.execute(
        'SELECT schedule FROM classes WHERE course_code = ?',
        (course_code,)
    ).fetchone()
    conn.close()

    if not course:
        return False, 'Course not found'

    try:
        now = datetime.now()
        class_time = datetime.strptime(course['schedule'], '%H:%M')
        class_today = now.replace(
            hour=class_time.hour,
            minute=class_time.minute,
            second=0,
            microsecond=0
        )

        window_start = class_today - timedelta(minutes=window_minutes)
        window_end = class_today + timedelta(minutes=window_minutes)

        if window_start <= now <= window_end:
            return True, 'Within window'
        elif now < window_start:
            opens_in = int((window_start - now).total_seconds() / 60)
            return False, f'Attendance opens in {opens_in} minutes'
        else:
            closed_ago = int((now - window_end).total_seconds() / 60)
            return False, f'Attendance window closed {closed_ago} minutes ago'

    except Exception as e:
        return False, str(e)

def has_marked_today(student_id, course_code):
    conn = get_db()
    today = datetime.now().strftime('%Y-%m-%d')
    existing = conn.execute(
        'SELECT id FROM attendance WHERE student_id = ? AND course_code = ? AND date = ?',
        (student_id, course_code, today)
    ).fetchone()
    conn.close()
    return existing is not None