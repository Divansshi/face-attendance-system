from functools import wraps
from datetime import datetime
import os

import cv2
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

from database import get_db, init_db
from security import is_within_session_window, has_marked_today, check_location, DEMO_MODE
import face_engine

app = Flask(__name__)
# Cloud Run sits behind Google's proxy; trust its X-Forwarded-* headers so request.remote_addr is the real client IP.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-change-me')
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB — enough for a photo or webcam frame
# A webcam capture arrives as a base64 form field; Flask's default cap for plain fields is 500 KB.
app.config['MAX_FORM_MEMORY_SIZE'] = 8 * 1024 * 1024

LECTURER_EMAIL = os.environ.get('LECTURER_EMAIL', 'amirah@university.edu')
LECTURER_PASSWORD = os.environ.get('LECTURER_PASSWORD', 'password')

UPLOAD_FOLDER = 'static/photos'
SNAPSHOT_FOLDER = 'static/snapshots'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SNAPSHOT_FOLDER, exist_ok=True)

with app.app_context():
    init_db()


@app.context_processor
def inject_demo_flag():
    return {
        'demo_mode': DEMO_MODE,
        'demo_email': LECTURER_EMAIL if DEMO_MODE else None,
        'demo_password': LECTURER_PASSWORD if DEMO_MODE else None,
    }


def lecturer_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('lecturer'):
            return redirect(url_for('lecturer_login'))
        return view(*args, **kwargs)
    return wrapped


def save_snapshot(student_id, frame):
    filename = f"{student_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    path = os.path.join(SNAPSHOT_FOLDER, filename)
    cv2.imwrite(path, frame)
    return path


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/healthz')
def healthz():
    return 'ok'

# ── Lecturer routes ──

@app.route('/lecturer/login', methods=['GET', 'POST'])
def lecturer_login():
    if request.method == 'POST':
        if request.form['email'] == LECTURER_EMAIL and request.form['password'] == LECTURER_PASSWORD:
            session['lecturer'] = 'Dr. Amirah'
            return redirect(url_for('lecturer_dashboard'))
        return render_template('lecturer/login.html', error='Invalid email or password')
    return render_template('lecturer/login.html')

@app.route('/lecturer/dashboard')
@lecturer_required
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
                           greeting=('Good morning' if datetime.now().hour < 12
                                     else 'Good afternoon' if datetime.now().hour < 18
                                     else 'Good evening'),
                           today=datetime.now().strftime('%A, %-d %B %Y'))

@app.route('/lecturer/enroll', methods=['GET', 'POST'])
@lecturer_required
def lecturer_enroll():
    if request.method == 'POST':
        full_name = request.form['name']
        student_id = request.form['sid']
        course = request.form['course']
        photo = request.files.get('photo')
        captured = request.form.get('captured_photo')

        image = None
        if captured:
            image = face_engine.decode_image(captured)
        elif photo and photo.filename:
            image = face_engine.decode_bytes(photo.read())

        if image is None:
            flash('Please upload or capture a photo')
            return redirect(url_for('lecturer_enroll'))
        if not face_engine.has_face(image):
            flash('No face found in that photo — try a clearer, front-facing one')
            return redirect(url_for('lecturer_enroll'))

        conn = get_db()
        exists = conn.execute('SELECT 1 FROM students WHERE student_id = ?', (student_id,)).fetchone()
        conn.close()
        if exists:
            flash('Student ID already exists')
            return redirect(url_for('lecturer_enroll'))

        safe_id = ''.join(ch for ch in student_id if ch.isalnum()) or 'student'
        photo_path = os.path.join(UPLOAD_FOLDER, f"{safe_id}.jpg")
        cv2.imwrite(photo_path, image)

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

    conn = get_db()
    classes = conn.execute('SELECT course_code, course_name FROM classes').fetchall()
    conn.close()
    return render_template('lecturer/enroll.html', classes=classes)

@app.route('/lecturer/recognition')
@lecturer_required
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
@lecturer_required
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
@lecturer_required
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
    student_id = session.get('student_id')
    if not student_id:
        return jsonify({'status': 'error', 'message': 'Not logged in'})

    conn = get_db()
    student = conn.execute(
        'SELECT * FROM students WHERE student_id = ? AND photo_path IS NOT NULL',
        (student_id,)
    ).fetchone()
    conn.close()
    if not student:
        return jsonify({'status': 'error', 'message': 'No photo enrolled for this student'})

    course_code = student['course']

    allowed, location_label, location_message = check_location(request.remote_addr, course_code)
    if not allowed:
        return jsonify({'status': 'error', 'message': location_message})

    allowed_time, time_message = is_within_session_window(course_code)
    if not allowed_time:
        return jsonify({'status': 'error', 'message': time_message})

    if has_marked_today(student_id, course_code):
        return jsonify({'status': 'error', 'message': 'You have already marked attendance today'})

    frame = face_engine.decode_image((request.get_json(silent=True) or {}).get('image'))
    if frame is None:
        return jsonify({'status': 'error', 'message': 'No camera frame received — start the camera first'})

    try:
        verified, reason = face_engine.verify(frame, student['photo_path'])
    except Exception as e:
        app.logger.exception('Verification failed')
        return jsonify({'status': 'error', 'message': 'Verification failed, please try again'})

    if reason == 'no_face':
        return jsonify({'status': 'no_face'})
    if not verified:
        return jsonify({'status': 'no_match'})

    snapshot_path = save_snapshot(student_id, frame)
    conn = get_db()
    conn.execute(
        'INSERT INTO attendance (student_id, course_code, date, time, snapshot_path, location) VALUES (?, ?, ?, ?, ?, ?)',
        (student_id, course_code, datetime.now().strftime('%Y-%m-%d'),
         datetime.now().strftime('%H:%M'), snapshot_path, location_label)
    )
    conn.commit()
    conn.close()
    session['last_course'] = course_code
    return jsonify({'status': 'match', 'location': location_label})

@app.route('/student/success')
def student_success():
    conn = get_db()
    course = conn.execute(
        'SELECT course_code, course_name FROM classes WHERE course_code = ?',
        (session.get('last_course', 'CS301'),)
    ).fetchone()
    conn.close()
    return render_template('student/success.html',
                           name=session.get('student_name', 'Student'),
                           course=course,
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

    course = conn.execute(
        'SELECT c.course_code, c.course_name FROM students s JOIN classes c ON c.course_code = s.course WHERE s.student_id = ?',
        (student_id,)
    ).fetchone()
    # Total sessions held = distinct days anyone was marked in this course
    total_classes = conn.execute(
        'SELECT COUNT(DISTINCT date) as cnt FROM attendance WHERE course_code = ?',
        (course['course_code'] if course else '',)
    ).fetchone()['cnt']

    attended = len(records)
    percentage = round((attended / total_classes * 100)) if total_classes > 0 else 0
    below = percentage < 80

    conn.close()
    return render_template('student/record.html',
                           records=records,
                           course=course,
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

# ── Lecturer live recognition ──

@app.route('/camera/recognize', methods=['POST'])
@lecturer_required
def camera_recognize():
    payload = request.get_json(silent=True) or {}
    course_code = payload.get('course_code', 'CS301')
    frame = face_engine.decode_image(payload.get('image'))
    if frame is None:
        return jsonify({'status': 'error', 'message': 'No camera frame received'})

    conn = get_db()
    students = conn.execute(
        'SELECT * FROM students WHERE course = ? AND photo_path IS NOT NULL', (course_code,)
    ).fetchall()
    conn.close()
    if not students:
        return jsonify({'status': 'error', 'message': 'No enrolled students with photos'})

    by_id = {s['student_id']: s for s in students}
    matched_id, reason = face_engine.identify(
        frame, [(s['student_id'], s['photo_path']) for s in students]
    )
    if reason == 'no_face':
        return jsonify({'status': 'no_face'})
    if matched_id is None:
        return jsonify({'status': 'no_match'})

    student = by_id[matched_id]
    recorded = not has_marked_today(student['student_id'], course_code)
    if recorded:
        snapshot_path = save_snapshot(student['student_id'], frame)
        conn = get_db()
        conn.execute(
            'INSERT INTO attendance (student_id, course_code, date, time, snapshot_path, location) VALUES (?, ?, ?, ?, ?, ?)',
            (student['student_id'], course_code, datetime.now().strftime('%Y-%m-%d'),
             datetime.now().strftime('%H:%M'), snapshot_path, 'on-site')
        )
        conn.commit()
        conn.close()
    return jsonify({
        'status': 'match',
        'name': student['full_name'],
        'student_id': student['student_id'],
        'recorded': recorded,
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=not DEMO_MODE, threaded=True, use_reloader=False)
