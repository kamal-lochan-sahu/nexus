#!/usr/bin/env python3
"""
NEXUS Phase 8 — Demo Controller
2-minute automated demo script for OBS recording.
Run: python3 demo_controller.py
"""
import time
import requests
import json
import sys
import os

BACKEND = "http://localhost:8000"
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
BOLD    = "\033[1m"
RESET   = "\033[0m"
DIM     = "\033[2m"

DEMO_STEPS = [
    # (timestamp_sec, label, command_or_None, description)
    (0,   "SYSTEM",  None,
     "Dashboard online — 6 modules active"),
    (12,  "NL2RC",   "Go2-A walk to zone B",
     "Direct command → Go2-A navigating"),
    (25,  "ROBO_RL", "Enable autonomous patrol",
     "PPO policy active — path finding live"),
    (40,  "VISION",  "Inspect the yellow marker",
     "CLIP + YOLO analyzing zone B marker"),
    (55,  "SAFETY",  None,
     "CoboSense: human detected → speed 0.5→0.1"),
    (75,  "FLEET",   "Full factory patrol",
     "FlexCell: both robots split zones A+D"),
    (90,  "TWIN",    None,
     "CognitiveTwin: RR_hip 43% — failure in 47hrs"),
    (105, "ESTOP",   "STOP ALL",
     "Emergency stop — all robots halted"),
    (115, "STATUS",  None,
     "Overview: 6/6 modules green — 0 incidents"),
    (120, "END",     None,
     "NEXUS — Industry 5.0 robotics platform"),
]

def send_command(command: str) -> dict:
    try:
        r = requests.post(
            f"{BACKEND}/command",
            json={"command": command},
            timeout=8,
        )
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def print_header():
    os.system("clear")
    print(f"{BOLD}{CYAN}")
    print("╔══════════════════════════════════════════════════════╗")
    print("║          NEXUS — Industry 5.0 Demo Controller       ║")
    print("║       github.com/kamal-lochan-sahu/nexus            ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"{RESET}")

def print_step(ts, label, command, desc, result=None):
    ts_str = f"{ts//60:02d}:{ts%60:02d}"
    color  = {
        "NL2RC":   CYAN,
        "ROBO_RL": GREEN,
        "VISION":  YELLOW,
        "SAFETY":  YELLOW,
        "FLEET":   CYAN,
        "TWIN":    GREEN,
        "ESTOP":   RED,
        "STATUS":  GREEN,
        "SYSTEM":  BOLD,
        "END":     BOLD,
    }.get(label, RESET)

    print(f"\n{DIM}{'─'*54}{RESET}")
    print(f"{BOLD}[{ts_str}] {color}{label}{RESET}  {desc}")
    if command:
        print(f"  {DIM}CMD:{RESET} \"{command}\"")
    if result:
        module = result.get("module") or result.get("result", {}).get("module", "")
        status = result.get("status", "")
        stage  = result.get("stage", "")
        if module:
            print(f"  {GREEN}→ module: {module}  status: {status}{RESET}")
        elif status:
            print(f"  {GREEN}→ status: {status}  stage: {stage}{RESET}")

def main():
    print_header()

    # Backend health check
    try:
        r = requests.get(f"{BACKEND}/health", timeout=3)
        data = r.json()
        print(f"{GREEN}✅ Backend online — {data.get('version', 'NEXUS')}{RESET}")
    except Exception:
        print(f"{RED}❌ Backend offline! Start: cd backend && python3 -m uvicorn main:app --port 8000{RESET}")
        sys.exit(1)

    print(f"\n{BOLD}Starting demo in 3 seconds...{RESET}")
    for i in range(3, 0, -1):
        print(f"  {i}...", end="", flush=True)
        time.sleep(1)
    print(f"\n{GREEN}🎬 RECORDING — GO!{RESET}\n")

    start_time = time.time()
    step_idx = 0

    while step_idx < len(DEMO_STEPS):
        elapsed   = time.time() - start_time
        ts, label, command, desc = DEMO_STEPS[step_idx]

        if elapsed >= ts:
            result = None
            if command:
                result = send_command(command)
            print_step(ts, label, command, desc, result)
            step_idx += 1
        else:
            # Progress bar
            remaining = ts - elapsed
            bar_len   = int((elapsed / 120) * 40)
            bar       = "█" * bar_len + "░" * (40 - bar_len)
            print(f"\r  {DIM}[{bar}] {elapsed:05.1f}s  next: {label} in {remaining:.0f}s{RESET}",
                  end="", flush=True)
            time.sleep(0.2)

    elapsed = time.time() - start_time
    print(f"\n\n{BOLD}{GREEN}✅ Demo complete in {elapsed:.1f}s{RESET}")
    print(f"{DIM}  nexus-sable-nine.vercel.app{RESET}\n")

if __name__ == "__main__":
    main()
