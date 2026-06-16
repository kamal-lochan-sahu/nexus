<div align="center">

# NEXUS
### Industry 5.0 Unified Robotics Intelligence Platform

[![Backend](https://img.shields.io/badge/Backend-Live-brightgreen)](https://nexus-backend-uq71.onrender.com/health)
[![Frontend](https://img.shields.io/badge/Frontend-Live-brightgreen)](https://nexus-sable-nine.vercel.app)
[![GitHub](https://img.shields.io/badge/GitHub-nexus-blue)](https://github.com/kamal-lochan-sahu/nexus)
[![ROS2](https://img.shields.io/badge/ROS2-Jazzy-blue)](https://docs.ros.org/en/jazzy/)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)

**Two Unitree Go2 robots. Six AI modules. One platform.**

🌐 **Live Demo:** [nexus-sable-nine.vercel.app](https://nexus-sable-nine.vercel.app)
🔗 **Backend API:** [nexus-backend-uq71.onrender.com](https://nexus-backend-uq71.onrender.com/health)

</div>

---

## What is NEXUS?

NEXUS is a full-stack Industry 5.0 robotics intelligence platform built on the Unitree Go2 quadruped robot. It integrates six AI modules — from natural language control to reinforcement learning navigation — into a single orchestrated system with a live dashboard, cloud backend, and factory arena simulation.

Built as a portfolio project targeting robotics roles at KUKA, Siemens, Bosch, and Festo.

---

## Six AI Modules

| Module | Phase | What it does |
|---|---|---|
| **NL2RC** | 1 | Natural language → robot command via Groq LLM |
| **CognitiveTwin** | 2 | LSTM failure prediction — joint health monitoring |
| **CoboSense** | 3 | ISO/TS 15066 human-robot safety, MediaPipe skeleton |
| **RoboRL** | 4 | PPO navigation — 85% success rate, 2M steps |
| **FlexCell** | 5 | Multi-robot coordination — asyncio priority scheduler |
| **EmbodiedGPT** | 6 | VLA pipeline — CLIP + YOLOv8 + Groq, ~2.3s latency |

---

## Architecture
┌─────────────────────────────────────────────┐

│           NEXUS Dashboard (Vercel)          │

│     React + TypeScript + 2Hz mock data      │

└─────────────────┬───────────────────────────┘

│ REST + WebSocket

┌─────────────────▼───────────────────────────┐

│         FastAPI Backend (Render.com)        │

│                                             │

│  ┌──────────────────────────────────────┐   │

│  │           Orchestrator               │   │

│  │  visual? → EmbodiedGPT              │   │

│  │  nav?    → RoboRL                   │   │

│  │  fleet?  → FlexCell                 │   │

│  │  default → NL2RC                    │   │

│  └──────────────────────────────────────┘   │

│                                             │

│  NL2RC │ CognitiveTwin │ CoboSense          │

│  RoboRL │ FlexCell │ EmbodiedGPT           │

└─────────────────┬───────────────────────────┘

│ ROS2 Bridge

┌─────────────────▼───────────────────────────┐

│     Gazebo Harmonic — nexus_arena.sdf       │

│  Go2-A (Zone A) │ Go2-B (Zone C)           │

│  4 zones │ 3 markers │ 2 obstacles         │

└─────────────────────────────────────────────┘

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/kamal-lochan-sahu/nexus.git
cd nexus

# 2. Backend
cd backend
pip install -r requirements.txt
export GROQ_API_KEY=your_key_here
uvicorn main:app --port 8000

# 3. Simulation (ROS2 + Gazebo required)
source ros2_ws/install/setup.bash
ros2 launch nexus_robot nexus_arena_launch.py

# 4. Demo controller
python3 demo_controller.py

# 5. Frontend (or use live: nexus-sable-nine.vercel.app)
cd frontend && npm run dev
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Robot | Unitree Go2 (quadruped) |
| Simulation | Gazebo Harmonic, ROS2 Jazzy |
| AI / ML | Groq Llama-3.1-8b, CLIP ViT-B/32, YOLOv8n, PPO |
| Backend | FastAPI, Python 3.12, SQLite WAL |
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Deploy | Vercel (frontend), Render.com (backend) |
| Hardware | AMD A4, 3.3GB RAM, Xubuntu 24.04 |

---

## IFR 2026 Trends Coverage

| Trend | NEXUS Module |
|---|---|
| Human-Robot Collaboration | CoboSense — ISO/TS 15066 |
| AI-driven Autonomy | RoboRL — PPO policy |
| Digital Twin | CognitiveTwin — LSTM predictor |
| Natural Language Interfaces | NL2RC — Groq LLM |
| Multi-robot Coordination | FlexCell — async scheduler |
| Vision-Language-Action | EmbodiedGPT — CLIP+YOLO+Groq |

---

## Project Structure
nexus/

├── backend/

│   ├── main.py                    # FastAPI app + lifespan

│   ├── core/orchestrator.py       # 4-route command router

│   ├── modules/

│   │   ├── nl2rc/                 # Phase 1

│   │   ├── cognitive_twin/        # Phase 2

│   │   ├── cobosense/             # Phase 3

│   │   ├── robo_rl/               # Phase 4

│   │   ├── flexcell/              # Phase 5

│   │   └── embodied_gpt/          # Phase 6

│   └── ros2/bridge.py

├── frontend/                      # Next.js dashboard

├── ros2_ws/

│   └── src/nexus_robot/

│       ├── worlds/nexus_arena.sdf

│       └── launch/nexus_arena_launch.py

├── demo_controller.py             # 2-minute demo script

└── render.yaml

---

## Demo

Run the 2-minute automated demo:

```bash
# Start backend first
cd backend && uvicorn main:app --port 8000 &

# Run demo (open dashboard in browser first)
python3 demo_controller.py
```

Timeline: NL2RC (0:12) → RoboRL (0:25) → EmbodiedGPT (0:40) → CoboSense (0:55) → FlexCell (1:15) → CognitiveTwin (1:30) → ESTOP (1:45)

---

<div align="center">

Built by [Kamal Lochan Sahu](https://github.com/kamal-lochan-sahu) — Berhampur, Odisha, India

*"From AMD A4 with 3.3GB RAM to a full Industry 5.0 platform."*

</div>
