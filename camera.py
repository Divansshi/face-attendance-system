import cv2
import subprocess
import json as json_module
from database import get_db
from datetime import datetime
import threading
import base64
import time

class AttendanceCamera:
    def __init__(self):
        self.camera = None
        self.is_running = False
        self.current_frame = None
        self.lock = threading.Lock()
        self.thread = None

    def _capture_loop(self):
        while self.is_running:
            if self.camera:
                ret, frame = self.camera.read()
                if ret:
                    with self.lock:
                        self.current_frame = frame
            time.sleep(0.05)

    def start(self):
        self.camera = cv2.VideoCapture(1)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        time.sleep(2)
        self.is_running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.camera:
            self.camera.release()
            self.camera = None
        self.current_frame = None

    def get_frame(self):
        with self.lock:
            if self.current_frame is None:
                return None
            return self.current_frame.copy()

    def frame_to_base64(self, frame):
        _, buffer = cv2.imencode('.jpg', frame)
        return base64.b64encode(buffer).decode('utf-8')

    def recognize_face(self, frame, course_code):
        conn = get_db()
        students = conn.execute(
            'SELECT * FROM students WHERE course = ? AND photo_path IS NOT NULL',
            (course_code,)
        ).fetchall()
        conn.close()

        if not students:
            return None, 'no_students'

        temp_path = 'static/temp_frame.jpg'
        cv2.imwrite(temp_path, frame)

        for student in students:
            try:
                result = subprocess.run(
                    ['python3', 'recognize.py', temp_path, student['photo_path']],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                data = json_module.loads(result.stdout.strip())
                if data.get('verified', False):
                    return student, 'match'
            except Exception as e:
                print(f"Recognize error for {student['full_name']}: {e}")
                continue

        return None, 'no_match'

    def record_attendance(self, student_id, course_code, snapshot_path=None, location='on-site'):
        conn = get_db()
        today = datetime.now().strftime('%Y-%m-%d')
        now = datetime.now().strftime('%H:%M')

        existing = conn.execute(
            'SELECT id FROM attendance WHERE student_id = ? AND course_code = ? AND date = ?',
            (student_id, course_code, today)
        ).fetchone()

        if not existing:
            conn.execute(
                'INSERT INTO attendance (student_id, course_code, date, time, snapshot_path, location) VALUES (?, ?, ?, ?, ?, ?)',
                (student_id, course_code, today, now, snapshot_path, location)
            )
            conn.commit()
            conn.close()
            return True

        conn.close()
        return False

camera = AttendanceCamera()