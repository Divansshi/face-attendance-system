<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=F8A5C2&height=160&section=header&text=AttendAI&fontSize=48&fontColor=ffffff&fontAlignY=36&desc=Face-recognition%20attendance%20for%20universities&descSize=16&descAlignY=58" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Flask-3.1-000000?style=for-the-badge&logo=flask&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenCV-4.13-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white" />
  <img src="https://img.shields.io/badge/TensorFlow-2.21-FF6F00?style=for-the-badge&logo=tensorflow&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" />
</p>

<p align="center">
  No roll calls, no sign-in sheets. Students look at a camera and AttendAI does the rest.
</p>

---

## ✨ What it does

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>👩‍🏫 Lecturer portal</h3>
      <ul>
        <li>Enroll students with a reference photo</li>
        <li>Manage classes, schedules and hybrid mode</li>
        <li>Run live recognition sessions</li>
        <li>Audit log of every scan, with the captured snapshot</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <h3>🎓 Student portal</h3>
      <ul>
        <li>Log in with a student ID</li>
        <li>Start the webcam and mark attendance by face</li>
        <li>Instant success or error feedback</li>
        <li>View your own attendance record</li>
      </ul>
    </td>
  </tr>
</table>

### 🛡️ Anti-cheating rules

| | Rule | How it works |
|:-:|---|---|
| ⏱️ | **Time window** | Attendance only opens 15 minutes either side of the scheduled class time |
| 🔁 | **Once per day** | A second scan for the same class on the same day is rejected |
| 📍 | **On campus** | The client IP must be on the campus network. Hybrid classes allow remote scans, tagged `remote`. |
| 📸 | **Proof** | Every successful match saves a timestamped snapshot for the lecturer's audit log |

---

## ⚙️ How it works

```mermaid
flowchart LR
    A([Student clicks<br/>Mark attendance]) --> B{Within class<br/>time window?}
    B -- no --> X([❌ Rejected])
    B -- yes --> C{Already marked<br/>today?}
    C -- yes --> X
    C -- no --> D{On campus network<br/>or hybrid class?}
    D -- no --> X
    D -- yes --> E[Grab live frame<br/>from OpenCV thread]
    E --> F[DeepFace.verify<br/>live frame vs enrolled photo]
    F -- no match --> X
    F -- match --> G[(Save snapshot +<br/>attendance row)]
    G --> H([✅ Marked present])
```

- **Face verification** uses DeepFace. It runs in a separate subprocess (`recognize.py`) so the TensorFlow model stays isolated from the Flask request thread.
- **Camera capture** runs on a background thread with a lock around the latest frame, so the live feed and recognition requests don't block each other.
- **Data** lives in SQLite across three tables: `students`, `classes` and `attendance`.

```mermaid
erDiagram
    STUDENTS ||--o{ ATTENDANCE : marks
    CLASSES  ||--o{ ATTENDANCE : "recorded for"
    STUDENTS {
        text student_id PK
        text full_name
        text course
        text photo_path
    }
    CLASSES {
        text course_code PK
        text course_name
        text schedule
        int  hybrid
    }
    ATTENDANCE {
        text student_id FK
        text course_code FK
        text date
        text time
        text snapshot_path
        text location
    }
```

---

## 🎨 UI design

Early wireframes for the main screens:

<table>
  <tr>
    <td align="center"><img src="docs/screenshots/lecturer-dashboard.png" width="400"/><br/><sub>Lecturer dashboard</sub></td>
    <td align="center"><img src="docs/screenshots/lecturer-enroll.png" width="400"/><br/><sub>Enroll a student</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="docs/screenshots/student-self-scan.png" width="400"/><br/><sub>Student self-scan</sub></td>
    <td align="center"><img src="docs/screenshots/student-confirmation-success.png" width="400"/><br/><sub>Attendance confirmed</sub></td>
  </tr>
</table>

---

## 🧰 Tech stack

| Layer | Tools |
|---|---|
| **Backend** | Python, Flask, Gunicorn |
| **Computer vision** | DeepFace, OpenCV (headless), TensorFlow / Keras, MTCNN, RetinaFace |
| **Database** | SQLite |
| **Frontend** | Jinja templates, HTML, CSS, vanilla JavaScript |
| **Deployment** | Nixpacks config for the X11 libraries OpenCV needs |

---

## 🚀 Run it locally

```bash
git clone https://github.com/Divansshi/face-attendance-system.git
cd face-attendance-system
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5001**.

<details>
<summary><b>⚙️ Configuration</b></summary>

<br/>

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Flask session signing key | `dev-only-change-me` |
| `LECTURER_EMAIL` | Lecturer login email | `amirah@university.edu` |
| `LECTURER_PASSWORD` | Lecturer login password | `password` |

In `security.py`, set `CAMPUS_IP_PREFIX` to your network's IP range. For development, set `TESTING_TIME` and `TESTING_LOCATION` to `True` to bypass the time and location checks.

Enrolled photos and snapshots are written to `static/photos/` and `static/snapshots/`. Both are git-ignored, so biometric data never gets committed.

</details>

<details>
<summary><b>📁 Project structure</b></summary>

<br/>

```
app.py          Flask routes for the lecturer, student and camera endpoints
camera.py       Threaded OpenCV capture
recognize.py    DeepFace verification, run as a subprocess
security.py     Time-window, duplicate and location rules
database.py     SQLite schema and seed classes
templates/      Lecturer and student pages
docs/           Planning notes and UI wireframes
```

</details>

---

## 🔭 What's next

- [ ] Liveness detection, so a printed photo can't pass
- [ ] Threshold tuning for lookalikes
- [ ] Browser-side camera capture (right now the webcam must be on the machine running the app)
- [ ] Multi-class support in the student scan flow
- [ ] Real lecturer accounts with hashed passwords
- [ ] CSV export of attendance records

---

<p align="center">
  Built by <b>Divansshi Mukunthan</b><br/>
  <a href="https://www.linkedin.com/in/divansshiii">LinkedIn</a> · <a href="https://github.com/Divansshi">GitHub</a>
</p>

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=F8A5C2&height=100&section=footer" />
</p>
