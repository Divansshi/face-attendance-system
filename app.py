from flask import Flask, render_template

app = Flask(__name__, template_folder='.')

# ── Lecturer routes ──
@app.route('/lecturer/login')
def lecturer_login():
    return render_template('lecturer/login.html')

@app.route('/lecturer/dashboard')
def lecturer_dashboard():
    return render_template('lecturer/dashboard.html')

@app.route('/lecturer/enroll')
def lecturer_enroll():
    return render_template('lecturer/enroll.html')

@app.route('/lecturer/recognition')
def lecturer_recognition():
    return render_template('lecturer/recognition.html')

# ── Student routes ──
@app.route('/student/login')
def student_login():
    return render_template('student/login.html')

@app.route('/student/scan')
def student_scan():
    return render_template('student/scan.html')

@app.route('/student/success')
def student_success():
    return render_template('student/success.html')

@app.route('/student/error')
def student_error():
    return render_template('student/error.html')

@app.route('/student/record')
def student_record():
    return render_template('student/record.html')

# ── Entry point ──
if __name__ == '__main__':
    app.run(debug=True)