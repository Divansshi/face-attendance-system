from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from database import get_db, init_db
from camera import camera
from datetime import datetime
from werkzeug.utils import secure_filename
import cv2
from deepface import DeepFace
import os
import time

app = Flask(__name__)
app.secret_key = 'attendai-dev-secret-2026'

UPLOAD_FOLDER = 'static/photos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

with app.app_context():
    init_db()

# ── Lecturer routes ──

@app.route('/lecturer/login', methods=['GET', 'POST'])
def lecturer_login():
    if request.method == 'POST':
        if request.form['email'] == 'amirah@university.edu' and request.form['password'] == 'password':
            session['lecturer'] = 'Dr. Amirah'
            return redirect(url_for('lecturer_dashboard'))
        return render_template('lecturer/login.html', error='Invalid email or password')
    return render_template('lecturer/login.html')

@app.route('/lecturer/dashboard')
def lecturer_dashboard():
    conn = get_db()
    classes = conn.execute('SELECT * FROM classes').fetchall()

    class_data = []
    for c in classes:
        total = conn.execute(
            'SELECT COUNT(*) as cnt FROM students WHERE course = ?',
            (c['course_code'],)
        ).fetchone()['cnt']

        attended = conn.execute(
            'SELECT COUNT(DISTINCT student_id) as cnt FROM attendance WHERE course_code = ? AND date = ?',
            (c['course_code'], datetime.now().strftime('%Y-%m-%d'))
        ).fetchone()['cnt']

        rate = round((attended / total * 100)) if total > 0 else 0

        class_data.append({
            'code': c['course_code'],
            'name': c['course_name'],
            'total': total,
            'rate': rate,
            'schedule': c['schedule']
        })

    conn.close()
    return render_template('lecturer/dashboard.html',
                           classes=class_data,
                           today=datetime.now().strftime('%A, %-d %B %Y'))

@app.route('/lecturer/enroll', methods=['GET', 'POST'])
def lecturer_enroll():
    if request.method == 'POST':
        full_name = request.form['name']
        student_id = request.form['sid']
        course = request.form['course']
        photo = request.files.get('photo')

        photo_path = None
        if photo and photo.filename:
            filename = secure_filename(f"{student_id}.jpg")
            photo_path = os.path.join(UPLOAD_FOLDER, filename)
            photo.save(photo_path)

        conn = get_db()
        try:
            conn.execute(
                'INSERT INTO students (full_name, student_id, course, photo_path) VALUES (?, ?, ?, ?)',
                (full_name, student_id, course, photo_path)
            )
            conn.commit()
            flash('Student enrolled successfully')
            return redirect(url_for('lecturer_dashboard'))
        except Exception:
            flash('Student ID already exists')
            return redirect(url_for('lecturer_enroll'))
        finally:
            conn.close()

    return render_template('lecturer/enroll.html')

@app.route('/lecturer/recognition')
def lecturer_recognition():
    conn = get_db()
    today = datetime.now().strftime('%Y-%m-%d')

    present = conn.execute('''
        SELECT s.full_name, s.student_id, a.time
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
        WHERE a.course_code = 'CS301' AND a.date = ?
        ORDER BY a.time ASC
    ''', (today,)).fetchall()

    all_students = conn.execute(
        'SELECT * FROM students WHERE course = "CS301"'
    ).fetchall()

    present_ids = [p['student_id'] for p in present]
    absent = [s for s in all_students if s['student_id'] not in present_ids]

    conn.close()
    return render_template('lecturer/recognition.html',
                           present=present,
                           absent=absent)

@app.route('/lecturer/logout')
def lecturer_logout():
    session.pop('lecturer', None)
    return redirect(url_for('lecturer_login'))

# ── Student routes ──

@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        student_id = request.form['student_id']
        conn = get_db()
        student = conn.execute(
            'SELECT * FROM students WHERE student_id = ?', (student_id,)
        ).fetchone()
        conn.close()

        if student:
            session['student_id'] = student['student_id']
            session['student_name'] = student['full_name']
            return redirect(url_for('student_scan'))
        return render_template('student/login.html', error='Student ID not found')

    return render_template('student/login.html')

@app.route('/student/scan')
def student_scan():
    return render_template('student/scan.html',
                           name=session.get('student_name', 'Student'))

@app.route('/student/scan/recognize', methods=['POST'])
def student_scan_recognize():
    student_id = session.get('student_id')
    if not student_id:
        return jsonify({'status': 'error', 'message': 'Not logged in'})

    frame = camera.get_frame()
    if frame is None:
        return jsonify({'status': 'error', 'message': 'No camera frame — click Start camera first'})

    conn = get_db()
    student = conn.execute(
        'SELECT * FROM students WHERE student_id = ? AND photo_path IS NOT NULL',
        (student_id,)
    ).fetchone()
    conn.close()

    if not student:
        return jsonify({'status': 'error', 'message': 'No photo enrolled for this student'})

    temp_path = 'static/temp_frame.jpg'
    cv2.imwrite(temp_path, frame)

    try:
        result = DeepFace.verify(
            img1_path=temp_path,
            img2_path=student['photo_path'],
            enforce_detection=False
        )
        if result['verified']:
            camera.record_attendance(student_id, 'CS301')
            return jsonify({'status': 'match'})
        else:
            return jsonify({'status': 'no_match'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/student/success')
def student_success():
    student_id = session.get('student_id')
    if student_id:
        conn = get_db()
        today = datetime.now().strftime('%Y-%m-%d')
        now = datetime.now().strftime('%H:%M')

        existing = conn.execute(
            'SELECT id FROM attendance WHERE student_id = ? AND course_code = ? AND date = ?',
            (student_id, 'CS301', today)
        ).fetchone()

        if not existing:
            conn.execute(
                'INSERT INTO attendance (student_id, course_code, date, time) VALUES (?, ?, ?, ?)',
                (student_id, 'CS301', today, now)
            )
            conn.commit()
        conn.close()

    return render_template('student/success.html',
                           name=session.get('student_name', 'Student'),
                           time=datetime.now().strftime('%H:%M'),
                           date=datetime.now().strftime('%a %-d %b'))

@app.route('/student/error')
def student_error():
    return render_template('student/error.html')

@app.route('/student/record')
def student_record():
    student_id = session.get('student_id')
    if not student_id:
        return redirect(url_for('student_login'))

    conn = get_db()

    records = conn.execute('''
        SELECT date, time, status, course_code
        FROM attendance
        WHERE student_id = ?
        ORDER BY date DESC
    ''', (student_id,)).fetchall()

    total_classes = conn.execute(
        'SELECT COUNT(*) as cnt FROM attendance WHERE course_code = "CS301"'
    ).fetchone()['cnt']

    attended = len(records)
    percentage = round((attended / total_classes * 100)) if total_classes > 0 else 0
    below = percentage < 80

    conn.close()
    return render_template('student/record.html',
                           records=records,
                           percentage=percentage,
                           attended=attended,
                           total=total_classes,
                           below=below,
                           name=session.get('student_name', 'Student'))

@app.route('/student/logout')
def student_logout():
    session.pop('student_id', None)
    session.pop('student_name', None)
    return redirect(url_for('student_login'))

# ── Camera routes ──

@app.route('/camera/start')
def camera_start():
    try:
        camera.start()
        time.sleep(2)
        return jsonify({'status': 'started'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/camera/stop')
def camera_stop():
    camera.stop()
    return jsonify({'status': 'stopped'})

@app.route('/camera/feed')
def camera_feed():
    frame = camera.get_frame()
    if frame is None:
        return jsonify({'error': 'no frame'}), 400
    img_data = camera.frame_to_base64(frame)
    return jsonify({'frame': img_data})

@app.route('/camera/recognize', methods=['POST'])
def camera_recognize():
    course_code = request.json.get('course_code', 'CS301')
    frame = camera.get_frame()
    if frame is None:
        return jsonify({'status': 'error', 'message': 'No camera frame available'})

    student, result = camera.recognize_face(frame, course_code)

    if result == 'match':
        recorded = camera.record_attendance(student['student_id'], course_code)
        return jsonify({
            'status': 'match',
            'name': student['full_name'],
            'student_id': student['student_id'],
            'recorded': recorded
        })
    elif result == 'no_students':
        return jsonify({'status': 'error', 'message': 'No enrolled students with photos'})
    else:
        return jsonify({'status': 'no_match'})

if __name__ == '__main__':
    app.run(debug=True, port=5001)