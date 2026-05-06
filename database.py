import sqlite3

def get_db():
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Students table
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

    # Classes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT NOT NULL,
            course_name TEXT NOT NULL,
            lecturer TEXT NOT NULL,
            schedule TEXT
        )
    ''')

    # Attendance table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            course_code TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT DEFAULT 'present',
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    # Seed some classes
    cursor.execute('''
        INSERT OR IGNORE INTO classes (course_code, course_name, lecturer, schedule)
        VALUES
        ('CS301', 'Algorithms', 'Dr. Amirah', '10:00 AM Wed'),
        ('CS201', 'Data Structures', 'Dr. Amirah', '2:00 PM Wed'),
        ('CS401', 'Machine Learning', 'Dr. Amirah', '4:00 PM Wed')
    ''')

    conn.commit()
    conn.close()
    print("Database initialised.")

if __name__ == '__main__':
    init_db()