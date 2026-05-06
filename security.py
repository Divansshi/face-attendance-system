from datetime import datetime, timedelta
from database import get_db

TESTING_TIME = True
TESTING_LOCATION = False
CAMPUS_IP_PREFIX = '127.0.0.'

def is_within_session_window(course_code, window_minutes=15):
    if TESTING_TIME:
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

def check_location(ip_address, course_code):
    conn = get_db()
    course = conn.execute(
        'SELECT hybrid FROM classes WHERE course_code = ?',
        (course_code,)
    ).fetchone()
    conn.close()

    if not course:
        return False, None, 'Course not found'

    is_hybrid = course['hybrid'] == 1

    if ip_address in ('127.0.0.1', '::1'):
        return True, 'on-site', 'Local network'

    on_campus = ip_address.startswith(CAMPUS_IP_PREFIX)

    if on_campus:
        return True, 'on-site', 'On campus network'

    if is_hybrid:
        return True, 'remote', 'Remote attendance allowed for this class'

    return False, None, 'You must be connected to the campus WiFi to mark attendance'