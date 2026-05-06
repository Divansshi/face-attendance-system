# Project Planning

## Problem Statement
Lecturers and institutions struggle with inaccurate, time-consuming manual attendance because paper registers are slow and vulnerable to proxy attendance. This system automates attendance marking using real-time facial recognition — identifying registered individuals via webcam, logging presence with timestamps, and surfacing analytics through a web dashboard — eliminating manual effort and preventing buddy-punching.

## Target Users
- Primary: University lecturers
- Secondary: Department admins

## User Stories

| ID | Role     | I want to...                         | So that...                          |
|----|----------|-------------------------------------|--------------------------------------|
| 1  | Lecturer | Enroll a student's face once        | System recognises them every session |
| 2  | Lecturer | Auto-mark attendance on startup     | Save time from manual roll call      |
| 3  | Lecturer | View daily attendance dashboard     | Get instant class overview           |
| 4  | Lecturer | Export attendance as CSV            | Submit records to department         |
| 5  | Admin    | View historical attendance records  | Track trends and patterns            |
| 6  | System   | Flag unrecognised faces             | Alert lecturer of unknown persons    |

## MVP Features
- [ ] Face enrollment (webcam capture + save)
- [ ] Real-time recognition with name overlay
- [ ] Attendance logging (once per session, no duplicates)
- [ ] SQLite database
- [ ] Dashboard — today's attendance
- [ ] CSV export

## Won't Build (deliberate scope cuts)
- Cloud face database
- SMS/email alerts
- Authentication/login

## Tech Stack
- Python 3.10+, OpenCV, face_recognition, Flask, SQLite, pandas
- Frontend: HTML, Tailwind CSS (CDN), Chart.js

## Deployment Target
- Local demo (camera-dependent)
- Render.com for dashboard/UI preview
