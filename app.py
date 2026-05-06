from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from database import get_db, init_db
from camera import camera
from security import is_within_session_window, has_marked_today, check_location
from datetime import datetime
from werkzeug.utils import secure_filename
import cv2
import subprocess
import json as json_module
import os
import time

app = Flask(__name__)
app.secret_key = 'attendai-dev-secret-2026'

UPLOAD_FOLDER = 'static/photos'
SNAPSHOT_FOLDER = 'static/snapshots'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SNAPSHOT_FOLDER, exist_ok=True)

with app.app_context():
    init_db()

def verify_faces(img1_path, img2_path):
    try:
        result = subprocess.run(
            ['python3', 'recognize.py', img1_path, img2_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        data = json_module.loads(result.stdout.strip())
        return data.get('verified', False)
    except Exception as e:
        print(f"Verify error: {e}")
        return False

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
            'schedule': c['schedule'],
            'hybrid': c['hybrid']
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
        SELECT s.full_name, s.student_id, a.time, a.snapshot_path, a.location
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

@app.route('/lecturer/audit')
def lecturer_audit():
    conn = get_db()
    records = conn.execute('''
        SELECT a.id, s.full_name, s.student_id, a.course_code,
               a.date, a.time, a.snapshot_path, a.location
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
        ORDER BY a.date DESC, a.time DESC
    ''').fetchall()
    conn.close()
    return render_template('lecturer/audit.html', records=records)

@app.route('/lecturer/classes', methods=['GET', 'POST'])
def lecturer_classes():
    conn = get_db()
    if request.method == 'POST':
        course_code = request.form['course_code']
        hybrid = 1 if request.form.get('hybrid') == 'on' else 0
        conn.execute(
            'UPDATE classes SET hybrid = ? WHERE course_code = ?',
            (hybrid, course_code)
        )
        conn.commit()
        flash(f'{course_code} updated successfully')

    classes = conn.execute('SELECT * FROM classes').fetchall()
    conn.close()
    return render_template('lecturer/classes.html', classes=classes)

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
    try:
        student_id = session.get('student_id')
        if not student_id:
            return jsonify({'status': 'error', 'message': 'Not logged in'})

        ip = request.remote_addr
        allowed, location_label, location_message = check_location(ip, 'CS301')
        if not allowed:
            return jsonify({'status': 'error', 'message': location_message})

        allowed_time, time_message = is_within_session_window('CS301')
        if not allowed_time:
            return jsonify({'status': 'error', 'message': time_message})

        if has_marked_today(student_id, 'CS301'):
            return jsonify({'status': 'error', 'message': 'You have already marked attendance today'})

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

        if verify_faces(temp_path, student['photo_path']):
            snapshot_filename = f"{student_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            snapshot_path = os.path.join(SNAPSHOT_FOLDER, snapshot_filename)
            cv2.imwrite(snapshot_path, frame)

            conn = get_db()
            today = datetime.now().strftime('%Y-%m-%d')
            now = datetime.now().strftime('%H:%M')
            conn.execute(
                'INSERT INTO attendance (student_id, course_code, date, time, snapshot_path, location) VALUES (?, ?, ?, ?, ?, ?)',
                (student_id, 'CS301', today, now, snapshot_path, location_label)
            )
            conn.commit()
            conn.close()
            return jsonify({'status': 'match', 'location': location_label})
        else:
            return jsonify({'status': 'no_match'})

    except Exception as e:
        print(f"Route error: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/student/success')
def student_success():
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
        SELECT date, time, status, course_code, location
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
    try:
        course_code = request.json.get('course_code', 'CS301')
        frame = camera.get_frame()
        if frame is None:
            return jsonify({'status': 'error', 'message': 'No camera frame available'})

        student, result = camera.recognize_face(frame, course_code)

        if result == 'match':
            snapshot_filename = f"{student['student_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            snapshot_path = os.path.join(SNAPSHOT_FOLDER, snapshot_filename)
            cv2.imwrite(snapshot_path, frame)
            recorded = camera.record_attendance(
                student['student_id'], course_code, snapshot_path
            )
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

    except Exception as e:
        print(f"Camera recognize error: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5001, threaded=True, use_reloader=False)