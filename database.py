import os
import sqlite3

DB_PATH = os.environ.get(
    'DB_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'attendance.db')
)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            student_id TEXT UNIQUE NOT NULL,
            course TEXT NOT NULL,
            photo_path TEXT,
            face_encoding BLOB
        )
    ''')

    # Older databases predate enrolled_at; add it so demo data can expire
    columns = [row[1] for row in cursor.execute('PRAGMA table_info(students)')]
    if 'enrolled_at' not in columns:
        cursor.execute('ALTER TABLE students ADD COLUMN enrolled_at TEXT')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT UNIQUE NOT NULL,
            course_name TEXT NOT NULL,
            lecturer TEXT NOT NULL,
            schedule TEXT,
            hybrid INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            course_code TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT DEFAULT 'present',
            snapshot_path TEXT,
            location TEXT DEFAULT 'on-site',
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    cursor.execute('''
        INSERT OR IGNORE INTO classes (course_code, course_name, lecturer, schedule, hybrid)
        VALUES
        ('CS301', 'Algorithms', 'Dr. Amirah', '10:00', 0),
        ('CS201', 'Data Structures', 'Dr. Amirah', '14:00', 1),
        ('CS401', 'Machine Learning', 'Dr. Amirah', '16:00', 0)
    ''')

    conn.commit()
    conn.close()
    print("Database initialised.")

if __name__ == '__main__':
    init_db()


def purge_expired_students(max_age_hours):
    """Delete students enrolled more than max_age_hours ago, with their attendance and photos.

    Used in demo mode so visitors' face photos don't accumulate on the server.
    Returns the number of students removed.
    """
    conn = get_db()
    expired = conn.execute(
        "SELECT student_id, photo_path FROM students "
        "WHERE enrolled_at IS NULL OR enrolled_at < datetime('now', ?)",
        (f'-{int(max_age_hours)} hours',)
    ).fetchall()
    for student in expired:
        snapshots = conn.execute(
            'SELECT snapshot_path FROM attendance WHERE student_id = ?', (student['student_id'],)
        ).fetchall()
        for path in [student['photo_path']] + [row['snapshot_path'] for row in snapshots]:
            if path and os.path.exists(path):
                os.remove(path)
        conn.execute('DELETE FROM attendance WHERE student_id = ?', (student['student_id'],))
        conn.execute('DELETE FROM students WHERE student_id = ?', (student['student_id'],))
    conn.commit()
    conn.close()
    return len(expired)
