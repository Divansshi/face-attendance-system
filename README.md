# AttendAI

Built by Divansshi to explore live image recognition and get hands-on with ML libraries in a real project.

The idea was simple — instead of calling names or passing around a sheet, students just look at a camera. AttendAI handles the rest.

## What it does

Two portals. Lecturer and student.

Lecturers can enroll students with a photo, manage classes, toggle hybrid mode for remote attendance, and review an audit trail of every scan with the face snapshot attached.

Students log in with their student ID, start the webcam, and mark attendance by looking at the camera. The system matches their live face against their enrolled photo using DeepFace.

There are a few anti-cheat measures baked in — attendance only opens in a 15 minute window around class time, you can only mark once per day, and it checks your IP to confirm you're on campus (unless the class is hybrid).

## Stack

- Flask
- DeepFace + OpenCV
- SQLite
- Vanilla HTML/CSS

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/attendance-system.git
cd attendance-system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

App runs at `http://localhost:5001`

## Logins

| Portal | URL | Login |
|---|---|---|
| Lecturer | `/lecturer/login` | `amirah@university.edu` / `password` |
| Student | `/student/login` | enrolled student ID |

## Config

In `security.py` — set `CAMPUS_IP_PREFIX` to your network's IP range. `TESTING_TIME` and `TESTING_LOCATION` can be flipped to `True` during development to bypass those checks.

## Not yet implemented

- Liveness detection (prevent photo spoofing)
- Lookalike threshold tuning