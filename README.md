# Automatic Attendance System

**Face-recognition attendance with liveness detection.** Students look at the camera, the system recognizes them, asks for a quick random head turn so a photo cannot fool it, and saves the attendance. Absent students are worked out automatically and everything exports to Excel.

![Python](https://img.shields.io/badge/Python-3.12-blue) ![PyTorch](https://img.shields.io/badge/PyTorch-CUDA-orange) ![PySide6](https://img.shields.io/badge/UI-PySide6-green) ![SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey)

<!-- Add your own screenshots to docs/screenshots/ and uncomment:
![Live recognition](docs/screenshots/live.png)
![Attendance](docs/screenshots/attendance.png)
-->

---

## Table of contents

1. [Why this project](#why-this-project)
2. [Features](#features)
3. [How it works](#how-it-works)
4. [Requirements](#requirements)
5. [Installation](#installation)
6. [Quick start](#quick-start)
7. [The app, page by page](#the-app-page-by-page)
8. [Attendance rules](#attendance-rules)
9. [Settings reference](#settings-reference)
10. [Project structure](#project-structure)
11. [Data and privacy](#data-and-privacy)
12. [Troubleshooting](#troubleshooting)
13. [Limitations](#limitations)
14. [Roadmap](#roadmap)
15. [Acknowledgments and licenses](#acknowledgments-and-licenses)
16. [Author](#author)

---

## Why this project

Manual attendance has three problems:

| Problem | Effect |
|---|---|
| Roll call | Minutes of every lecture are lost calling names |
| Proxy attendance | A friend can say "present" for someone else |
| Paper registers | Records get lost, entries are missed, monthly totals take hours |

This system replaces roll call with a camera at the classroom door. It is automatic, contactless, and designed to resist fake attendance.

---

## Features

- **Multi-person recognition.** Works for a whole section, live, on a single PC.
- **GPU accelerated.** Detection and recognition run on an NVIDIA GPU through PyTorch for real-time speed (CPU works, but is slower).
- **Liveness check.** Before attendance is saved, the person must turn their head to a random side (left or right) and look back. Photos and phone videos fail this check.
- **Accuracy safeguards.** Quality gate (size, sharpness, head angle), face alignment, flip averaging, a winner-margin rule for look-alikes (for example siblings) and voting over several frames.
- **One record per person per day.** Standing longer in front of the camera never creates duplicates. Check-in time and last-seen time are stored.
- **Automatic absent list.** Absent means enrolled with no record for that date.
- **Modern desktop interface.** Live view, daily roster, people management with a similarity heatmap, reports with charts, and a settings page.
- **Reports and export.** Attendance percentage per student, average check-in time, CSV export that opens in Excel.
- **Private and offline.** Only numeric face fingerprints (embeddings) are stored, not photos. Nothing is uploaded.

---

## How it works

```
Camera frame
   |
   v
1. Detect      MTCNN finds each face: box, confidence, 5 landmarks (eyes, nose, mouth)
   |
   v
2. Quality gate   too far? turned away? blurry? -> skipped with a reason
   |
   v
3. Align + crop   rotate so the eyes are level, 20% margin, resize to 160x160
   |
   v
4. Embed          FaceNet (VGGFace2) turns the face AND its mirror image into
                  512 numbers each; the two are averaged -> one fingerprint
   |
   v
5. Match          compare with every enrolled person (cosine similarity)
                  score = mean of the person's 3 best samples
   |
   v
6. Decide         score >= threshold, and the winner beats the runner-up by a margin
   |
   v
7. Vote           the same name must win 5 of the last 7 frames
   |
   v
8. Liveness       random head-turn challenge, then the same person must return
   |
   v
9. Save           SQLite: one row per person per day
```

**Important concept:** no model is trained on your students. A pretrained face network converts any face into a 512-number *embedding*. Enrolling a person means saving about 50 embeddings of them. Recognition means finding the closest saved embeddings.

---

## Requirements

| Item | Recommended |
|---|---|
| OS | Windows 10 / 11 (developed and tested here) |
| Python | 3.10 - 3.12 |
| GPU | NVIDIA GPU with CUDA (developed on an RTX 2060). CPU also works, but slowly |
| Camera | Any USB or built-in webcam |
| Internet | Only for installation and the first model download |

---

## Installation

```bash
# 1. Get the code
git clone https://github.com/Talha-Idnan/Automatic-Attendence-System.git
cd Automatic-Attendence-System

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # Linux / macOS

# 3. Install PyTorch with CUDA (choose the command for your CUDA version at pytorch.org)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124

# 4. Install the remaining packages
pip install -r requirements.txt

# 5. Install the face models WITHOUT dependencies (keeps your CUDA PyTorch untouched)
pip install facenet-pytorch --no-deps
```

Check that PyTorch sees your GPU:

```bash
python -c "import torch; print(torch.cuda.is_available())"    # should print True
```

---

## Quick start

```bash
python main.py
```

1. Open **People** and press **Enroll new person**. Only one person may be in the frame.
2. Look at the camera and slowly turn your head a little. Auto-capture saves about one sample every 0.35 seconds. Aim for **50 samples**, then type the name and press **Save person**.
3. Repeat for every student.
4. Open **Live** and press **Start camera**. When a student is recognized the box turns yellow and asks for a head turn. After the turn, attendance is saved and the box turns green.
5. Open **Attendance** to see the roster for any day and **Reports** for percentages and charts.

The first start takes a few seconds while the model loads. The sidebar then shows the device in use, for example `Device: NVIDIA GeForce RTX 2060`. If it says `CPU (slow)`, PyTorch is the CPU build (see [Troubleshooting](#troubleshooting)).

---

## The app, page by page

| Page | What it does |
|---|---|
| **Live** | Camera with face boxes, FPS, liveness prompts, today's counters and an activity feed |
| **Attendance** | Daily roster (present / absent) with date picker, search, filter, manual *Mark present*, *Remove record*, CSV export |
| **People** | Enroll people, add samples, clean weak samples, delete, data-quality status and a face-similarity heatmap |
| **Reports** | People present per day (chart), per-person attendance %, average check-in, CSV exports |
| **Settings** | Every threshold of the pipeline as sliders, backup of the face data |

**Box colors on the Live page**

| Color | Meaning |
|---|---|
| Green | Recognized and verified, attendance saved |
| Yellow | Checking, or a liveness step (turn your head, then look back) |
| Red | Unknown person, or liveness failed |
| Gray (with a word) | Rejected by the quality gate: *too far*, *face the camera*, *blurry* |

**Similarity heatmap (People page):** green below 0.50, amber 0.50 to 0.70, red 0.70 and above. Red between non-relatives means bad enrollment data. Red between siblings is expected and handled by the winner-margin rule.

---

## Attendance rules

- **One row per person per date.** The database enforces it with `UNIQUE(name, date)`.
- **Check-in** is the first sighting of the day. **Last seen** is refreshed every few seconds while the person stays in view.
- **A new date starts a new row** (resets at midnight by the PC clock). There is no time-interval limit.
- **Absent** is calculated, not stored: enrolled students without a row for that date.
- **Teacher override:** *Mark present* adds a record at a time you type (HH:MM:SS). *Remove record* deletes a wrong one.
- **Session days** in Reports are days with at least one record, so holidays with nobody scanned are not counted. Attendance % = days present / session days.

---

## Settings reference

All values are on the **Settings** page and saved to `data/settings.json`. Defaults live in `core/config.py`.

| Setting | Default | Effect |
|---|---|---|
| Match threshold | 0.65 | Minimum similarity to accept a person. Higher = stricter |
| Winner margin | 0.08 | The best match must beat the runner-up by this much (protects against look-alikes) |
| Frames to confirm | 5 of 7 | How many recent frames must agree on a name |
| Update interval | 3 s | How often an already-present person's last-seen time is refreshed |
| Challenge time | 8 s | Time allowed to complete the head turn |
| Turn sensitivity | 0.30 | How far the head must turn. Lower = easier |
| Skip challenge for | 30 s | A verified person is not asked again for this long |
| Flip left / right | off | Turn on if "LEFT" feels like your right |
| Min face size | 60 px | Smaller faces are ignored |
| Sharpness | 20 | Blurrier frames are ignored |
| Max head angle | 0.35 | Faces turned further are not used for recognition |
| Camera index | 0 | Which webcam to use (restart the camera after changing) |

---

## Project structure

```
.
|-- main.py                  # entry point
|-- requirements.txt
|-- core/                    # logic (no UI)
|   |-- config.py            # settings dataclass + file paths
|   |-- engine.py            # camera, detection, embeddings, matching, liveness tracker
|   |-- facestore.py         # enrolled people, similarity analysis, clean()
|   `-- database.py          # SQLite attendance + CSV export
|-- ui/                      # PySide6 interface
|   |-- theme.py             # colors + global stylesheet
|   |-- widgets.py           # video overlay, chart, table painters
|   |-- workers.py           # background thread: camera + recognition
|   |-- main_window.py       # sidebar + page wiring
|   |-- live_page.py  attendance_page.py  people_page.py
|   |-- reports_page.py  settings_page.py
|   `-- enroll_dialog.py     # enrollment window
`-- data/                    # created automatically (git-ignored)
    |-- faces_v2.pkl         # enrolled face embeddings
    |-- attendance.db        # attendance records
    |-- settings.json        # your tuned settings
    `-- exports/             # CSV exports and backups
```

**Where to change things**

| I want to change | Go to |
|---|---|
| What happens when someone is recognized | `ui/workers.py` -> `_recognize` |
| The liveness rule | `core/engine.py` -> `Tracker._step` |
| The quality gate | `core/engine.py` -> `detect_and_embed` |
| A default threshold or a new setting | `core/config.py` -> `Settings`, then `ui/settings_page.py` |
| Late marking or a new database column | `core/database.py`, then `ui/attendance_page.py` |
| The report formula | `ui/reports_page.py` -> `refresh` |
| Colors and fonts | `ui/theme.py` |

---

## Data and privacy

- Faces are stored only as **512-number embeddings** in `data/faces_v2.pkl`. No photos are saved and nothing is sent over the network.
- Embeddings are still biometric data. Treat the file as private and **never commit it to GitHub**. The provided `.gitignore` excludes `data/`, `*.pkl` and `*.db`.
- Make sure you have the consent of everyone you enroll, and follow your institution's data policy.
- Back up `faces_v2.pkl` from **Settings > Back up face data**. Deleting it means everyone must enroll again.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `No camera found` | Close Zoom, Teams and browser tabs that use the camera. Windows Settings > Privacy > Camera > allow desktop apps |
| Sidebar shows `CPU (slow)` | PyTorch is the CPU build. Install the CUDA build: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124` |
| `ModuleNotFoundError: facenet_pytorch` | `pip install facenet-pytorch --no-deps` |
| "DLL initialization routine failed" | Start the app with `python main.py` (torch is imported before Qt there) |
| A stranger is recognized | Raise the threshold to 0.70 and the margin to 0.10 |
| A real student stays on "checking..." | Lower the margin to 0.05, or re-enroll with more varied samples |
| Too many "blurry" boxes | Add front light, or lower Sharpness to 10 |
| Too many "face the camera" boxes | Raise Max head angle to 0.45 |
| Head turn not detected | Lower Turn sensitivity to 0.22, or enable Flip left / right |
| Low FPS | Check the sidebar says GPU. Dim rooms also slow webcams |

---

## Limitations

- Needs a front-facing, well-lit face. Masks and very far faces fail.
- Siblings and twins are the hardest case and may stay on "checking..." longer.
- The liveness check blocks photos and phone videos, not 3D masks or advanced deepfakes. It is strong protection for a college system, not bank-level security.
- One record per day. There is no late status or timetable support yet.
- One camera on one PC, with no network sync.
- The first run needs internet to download the pretrained model.

---

## Roadmap

- [ ] Late / on-time marking with a cutoff time
- [ ] Subject-wise sessions from a timetable
- [ ] Stronger recognition model (ArcFace) for siblings
- [ ] Blink plus head-turn liveness, or a depth camera
- [ ] Alerts to students or parents for low attendance
- [ ] Web dashboard for teachers
- [ ] Multiple cameras and encrypted cloud backup

---

## Acknowledgments and licenses

- [facenet-pytorch](https://github.com/timesler/facenet-pytorch) (MTCNN and InceptionResnetV1) by Tim Esler, MIT license.
- Pretrained weights trained on the VGGFace2 dataset. Check the dataset and weights terms before any commercial use. This project is intended for educational and research use.
- [PySide6](https://doc.qt.io/qtforpython-6/) (Qt for Python), [OpenCV](https://opencv.org/), [PyTorch](https://pytorch.org/), SQLite.

Add a `LICENSE` file for your own code (for example MIT) before publishing.

---

## Author

**Talha** - college project.

Questions, bug reports and improvements are welcome through GitHub Issues.#   A u t o m a t i c - A t t e n d e n c e - S y s t e m - V 2  
 