import sqlite3

def get_db():
    conn = sqlite3.connect('attendance.db')
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

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT UNIQUE NOT NULL,
            course_name TEXT NOT NULL,
            lecturer TEXT NOT NULL,
            schedule TEXT
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
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    cursor.execute('''
        INSERT OR IGNORE INTO classes (course_code, course_name, lecturer, schedule)
        VALUES
        ('CS301', 'Algorithms', 'Dr. Amirah', '10:00'),
        ('CS201', 'Data Structures', 'Dr. Amirah', '14:00'),
        ('CS401', 'Machine Learning', 'Dr. Amirah', '16:00')
    ''')

    conn.commit()
    conn.close()
    print("Database initialised.")

if __name__ == '__main__':
    init_db()