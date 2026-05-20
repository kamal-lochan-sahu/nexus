#!/usr/bin/env python3
"""
NEXUS Phase 5 — Remaining Files Setup
Run from: ~/projects/nexus/
Creates + patches:
  1. main.py         — flexcell router + lifespan + WS fleet payload
  2. orchestrator.py — multi-robot routing to FlexCell
  3. Gazebo world    — two Go2 robots with namespaces
  4. Frontend page   — fleet dashboard
  5. e2e test script
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
if not (ROOT / "backend").exists():
    print("ERROR: Run from ~/projects/nexus/")
    sys.exit(1)

BACKEND = ROOT / "backend"
CREATED = []
PATCHED = []
ERRORS  = []

# ─── Helpers ────────────────────────────────────────────────────────────────

def write_file(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        print(f"  [SKIP]    {rel}")
        return
    p.write_text(content, encoding="utf-8")
    print(f"  [CREATE]  {rel}")
    CREATED.append(rel)


def patch_file(rel: str, marker: str, insert: str, after: bool = True):
    """Insert `insert` once near `marker` line. Skip if already patched."""
    p = ROOT / rel
    if not p.exists():
        print(f"  [MISS]    {rel} (file not found)")
        ERRORS.append(rel)
        return
    text = p.read_text(encoding="utf-8")
    if insert.strip().splitlines()[0].strip() in text:
        print(f"  [ALREADY] {rel}")
        return
    if marker not in text:
        print(f"  [WARN]    {rel} — marker not found: {repr(marker[:40])}")
        ERRORS.append(rel)
        return
    idx = text.index(marker)
    if after:
        idx = text.index("\n", idx) + 1
    text = text[:idx] + insert + text[idx:]
    p.write_text(text, encoding="utf-8")
    print(f"  [PATCH]   {rel}")
    PATCHED.append(rel)


# ════════════════════════════════════════════════════════════════════════════
# 1. PATCH main.py — flexcell import
# ════════════════════════════════════════════════════════════════════════════

patch_file(
    "backend/main.py",
    "from modules.cobosense.cobosense_router import cobosense_router, set_service",
    "\nfrom modules.flexcell.flexcell_router import router as flexcell_router\n"
    "from modules.flexcell.fleet_scheduler import get_scheduler\n"
    "from modules.flexcell.conflict_resolver import get_resolver\n",
)

# ════════════════════════════════════════════════════════════════════════════
# 2. PATCH main.py — include flexcell router
# ════════════════════════════════════════════════════════════════════════════

patch_file(
    "backend/main.py",
    "app.include_router(cobosense_router)",
    "\napp.include_router(flexcell_router)    # /flexcell/* endpoints\n",
)

# ════════════════════════════════════════════════════════════════════════════
# 3. PATCH main.py — lifespan: start FlexCell scheduler + resolver
# ════════════════════════════════════════════════════════════════════════════

patch_file(
    "backend/main.py",
    "print(\"[NEXUS] CoboSense Layer 3 Safety — ACTIVE\")",
    "\n    # ── FlexCell — Multi-robot coordination ─────────────────────\n"
    "    scheduler = get_scheduler()\n"
    "    resolver  = get_resolver()\n"
    "    await scheduler.start()\n"
    "    await resolver.start()\n"
    "    print(\"[NEXUS] FlexCell Multi-robot Coordination — ACTIVE\")\n",
)

# ════════════════════════════════════════════════════════════════════════════
# 4. PATCH main.py — lifespan shutdown: stop FlexCell
# ════════════════════════════════════════════════════════════════════════════

patch_file(
    "backend/main.py",
    "cobosense_svc.stop()",
    "\n    await scheduler.stop()\n"
    "    await resolver.stop()\n",
)

# ════════════════════════════════════════════════════════════════════════════
# 5. PATCH main.py — build_ws_payload: add fleet data
# ════════════════════════════════════════════════════════════════════════════

patch_file(
    "backend/main.py",
    '"safety": safety,',
    '\n        "fleet": get_scheduler().get_fleet_status(),\n',
)

# ════════════════════════════════════════════════════════════════════════════
# 6. PATCH orchestrator.py — multi-robot routing
# ════════════════════════════════════════════════════════════════════════════

patch_file(
    "backend/core/orchestrator.py",
    "NAV_KEYWORDS = [",
    "# Multi-robot keywords → FlexCell\n"
    "FLEET_KEYWORDS = [\n"
    "    \"patrol\", \"both robots\", \"all robots\", \"fleet\",\n"
    "    \"coordinate\", \"inspect zone\", \"guard zone\",\n"
    "    \"entire floor\", \"factory floor\",\n"
    "]\n\n",
    after=False,
)

patch_file(
    "backend/core/orchestrator.py",
    "cmd_lower = command.lower().strip()",
    "\n        # ── Route: multi-robot task → FlexCell ─────────────────────\n"
    "        if self._is_fleet_task(cmd_lower):\n"
    "            return self._handle_fleet(command)\n",
)

patch_file(
    "backend/core/orchestrator.py",
    "def _is_navigation(self, cmd: str) -> bool:",
    "\n    # ── FLEET (FlexCell) ────────────────────────────────────────────\n"
    "    def _is_fleet_task(self, cmd: str) -> bool:\n"
    "        return any(kw in cmd for kw in FLEET_KEYWORDS)\n\n"
    "    def _handle_fleet(self, command: str) -> Dict[str, Any]:\n"
    "        return {\n"
    "            \"module\": \"flexcell\",\n"
    "            \"action\": \"decompose\",\n"
    "            \"goal\":   command,\n"
    "            \"status\": \"queued\",\n"
    "        }\n\n",
    after=False,
)

# ════════════════════════════════════════════════════════════════════════════
# 7. Gazebo world — two Go2 robots
# ════════════════════════════════════════════════════════════════════════════

write_file("ros2_ws/src/nexus_robot/worlds/flexcell_world.sdf", """\
<?xml version="1.0" ?>
<sdf version="1.9">
  <world name="flexcell_world">

    <!-- Physics -->
    <physics name="1ms" type="ignored">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>

    <!-- Plugins -->
    <plugin filename="gz-sim-physics-system"
            name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-scene-broadcaster-system"
            name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-user-commands-system"
            name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-sensors-system"
            name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>

    <!-- Ground plane -->
    <model name="ground_plane">
      <static>true</static>
      <link name="link">
        <collision name="collision">
          <geometry><plane><normal>0 0 1</normal><size>20 20</size></plane></geometry>
        </collision>
        <visual name="visual">
          <geometry><plane><normal>0 0 1</normal><size>20 20</size></plane></geometry>
          <material>
            <ambient>0.8 0.8 0.8 1</ambient>
            <diffuse>0.8 0.8 0.8 1</diffuse>
          </material>
        </visual>
      </link>
    </model>

    <!-- Zone markers (visual only) -->
    <!-- Zone A top-left -->
    <model name="zone_A">
      <static>true</static>
      <pose>-1.5 1.5 0.01 0 0 0</pose>
      <link name="link">
        <visual name="v">
          <geometry><box><size>3 3 0.01</size></box></geometry>
          <material><ambient>0.2 0.6 0.2 0.3</ambient></material>
        </visual>
      </link>
    </model>
    <!-- Zone B top-right -->
    <model name="zone_B">
      <static>true</static>
      <pose>1.5 1.5 0.01 0 0 0</pose>
      <link name="link">
        <visual name="v">
          <geometry><box><size>3 3 0.01</size></box></geometry>
          <material><ambient>0.2 0.2 0.8 0.3</ambient></material>
        </visual>
      </link>
    </model>
    <!-- Zone C bottom-left -->
    <model name="zone_C">
      <static>true</static>
      <pose>-1.5 -1.5 0.01 0 0 0</pose>
      <link name="link">
        <visual name="v">
          <geometry><box><size>3 3 0.01</size></box></geometry>
          <material><ambient>0.8 0.6 0.2 0.3</ambient></material>
        </visual>
      </link>
    </model>
    <!-- Zone D bottom-right -->
    <model name="zone_D">
      <static>true</static>
      <pose>1.5 -1.5 0.01 0 0 0</pose>
      <link name="link">
        <visual name="v">
          <geometry><box><size>3 3 0.01</size></box></geometry>
          <material><ambient>0.8 0.2 0.6 0.3</ambient></material>
        </visual>
      </link>
    </model>

    <!-- Go2-A spawns at zone A center -->
    <include>
      <uri>model://go2</uri>
      <name>go2_a</name>
      <pose>-1.5 1.5 0.3 0 0 0</pose>
      <experimental:params>
        <param name="//plugin[@name='gz::sim::systems::Diff​Drive']/namespace">go2_a</param>
        <param name="//plugin[@name='gz::sim::systems::OdometryPublisher']/odom_topic">go2_a/odom</param>
      </experimental:params>
    </include>

    <!-- Go2-B spawns at zone C center -->
    <include>
      <uri>model://go2</uri>
      <name>go2_b</name>
      <pose>-1.5 -1.5 0.3 0 0 1.57</pose>
      <experimental:params>
        <param name="//plugin[@name='gz::sim::systems::Diff​Drive']/namespace">go2_b</param>
        <param name="//plugin[@name='gz::sim::systems::OdometryPublisher']/odom_topic">go2_b/odom</param>
      </experimental:params>
    </include>

    <!-- Ambient light -->
    <light name="sun" type="directional">
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.8 0.8 0.8 1</diffuse>
      <specular>0.2 0.2 0.2 1</specular>
      <direction>-0.5 0.1 -0.9</direction>
    </light>

  </world>
</sdf>
""")

# ════════════════════════════════════════════════════════════════════════════
# 8. Gazebo launch script
# ════════════════════════════════════════════════════════════════════════════

write_file("ros2_ws/src/nexus_robot/launch/flexcell_launch.py", """\
\"\"\"
FlexCell Launch — Two Go2 robots in headless Gazebo
Usage: ros2 launch nexus_robot flexcell_launch.py
\"\"\"

from launch import LaunchDescription
from launch.actions import ExecuteProcess, TimerAction
from launch_ros.actions import Node
import os

WORLD = os.path.join(
    os.path.dirname(__file__), "..", "worlds", "flexcell_world.sdf"
)


def generate_launch_description():
    # Gazebo headless
    gazebo = ExecuteProcess(
        cmd=["gz", "sim", "-r", "-s", "--headless-rendering", WORLD],
        output="screen",
    )

    # ROS2-Gazebo bridge — Go2-A
    bridge_a = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="bridge_go2_a",
        arguments=[
            "/go2_a/cmd_vel@geometry_msgs/msg/Twist@gz.msgs.Twist",
            "/go2_a/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
        ],
        output="screen",
    )

    # ROS2-Gazebo bridge — Go2-B
    bridge_b = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="bridge_go2_b",
        arguments=[
            "/go2_b/cmd_vel@geometry_msgs/msg/Twist@gz.msgs.Twist",
            "/go2_b/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
        ],
        output="screen",
    )

    # Fleet node — starts after 3s (wait for Gazebo)
    fleet = TimerAction(
        period=3.0,
        actions=[
            Node(
                package="nexus_robot",
                executable="fleet_node",
                name="fleet_node",
                output="screen",
            )
        ],
    )

    return LaunchDescription([gazebo, bridge_a, bridge_b, fleet])
""")

# ════════════════════════════════════════════════════════════════════════════
# 9. Frontend — Fleet Dashboard page
# ════════════════════════════════════════════════════════════════════════════

write_file("frontend/app/fleet/page.tsx", """\
\"use client\";

import React, { useEffect, useState, useCallback } from \"react\";
import RobotCard  from \"../components/fleet/RobotCard\";
import TaskQueue  from \"../components/fleet/TaskQueue\";
import CoordLog   from \"../components/fleet/CoordLog\";

const API = process.env.NEXT_PUBLIC_API_URL ?? \"http://localhost:8000\";
const WS  = API.replace(\"http\", \"ws\") + \"/ws\";

interface FleetStatus {
  tasks_active:         number;
  tasks_pending:        number;
  coordination_events:  number;
  go2_a_task:           string;
  go2_b_task:           string;
  go2_a_status:         string;
  go2_b_status:         string;
  go2_a_position:       { x: number; y: number };
  go2_b_position:       { x: number; y: number };
}

const DEFAULT_FLEET: FleetStatus = {
  tasks_active: 0, tasks_pending: 0, coordination_events: 0,
  go2_a_task: \"idle\", go2_b_task: \"idle\",
  go2_a_status: \"idle\", go2_b_status: \"idle\",
  go2_a_position: { x: 0, y: 0 },
  go2_b_position: { x: 0, y: 0 },
};

export default function FleetPage() {
  const [fleet,    setFleet]    = useState<FleetStatus>(DEFAULT_FLEET);
  const [coordLog, setCoordLog] = useState<any[]>([]);
  const [tasks,    setTasks]    = useState<any[]>([]);
  const [goal,     setGoal]     = useState(\"\");
  const [loading,  setLoading]  = useState(false);
  const [msg,      setMsg]      = useState(\"\");

  // WebSocket — real-time fleet status
  useEffect(() => {
    const ws = new WebSocket(WS);
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.fleet) setFleet(data.fleet);
      } catch {}
    };
    return () => ws.close();
  }, []);

  // Poll coord log every 2s
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const res  = await fetch(API + \"/flexcell/log\");
        const data = await res.json();
        setCoordLog(data.conflict_events ?? []);
      } catch {}
    }, 2000);
    return () => clearInterval(id);
  }, []);

  const submitGoal = useCallback(async () => {
    if (!goal.trim()) return;
    setLoading(true);
    setMsg(\"\");
    try {
      const res  = await fetch(API + \"/flexcell/task\", {
        method:  \"POST\",
        headers: { \"Content-Type\": \"application/json\" },
        body:    JSON.stringify({ goal }),
      });
      const data = await res.json();
      setTasks(data.tasks ?? []);
      setMsg(\"Accepted — \" + (data.tasks?.length ?? 0) + \" tasks assigned\");
      setGoal(\"\");
    } catch (e: any) {
      setMsg(\"Error: \" + e.message);
    } finally {
      setLoading(false);
    }
  }, [goal]);

  const robotAction = async (robot: string, action: string) => {
    await fetch(`${API}/flexcell/robot/${robot}/${action}`, { method: \"POST\" });
  };

  const activeTasks = tasks
    .filter((t: any) =>
      (t.robot === \"go2_a\" && fleet.go2_a_task.includes(t.task?.toLowerCase())) ||
      (t.robot === \"go2_b\" && fleet.go2_b_task.includes(t.task?.toLowerCase()))
    )
    .map((t: any) => ({ ...t, status: \"active\" as const }));

  const allTasksForQueue = tasks.map((t: any) => ({
    ...t,
    status: \"active\" as const,
  }));

  return (
    <main className=\"min-h-screen bg-[#0a0f1e] text-white p-6\">
      <div className=\"max-w-5xl mx-auto flex flex-col gap-6\">

        {/* Header */}
        <div>
          <h1 className=\"text-2xl font-bold text-white\">FlexCell Fleet</h1>
          <p className=\"text-white/40 text-sm\">
            Multi-robot coordination — Industry 5.0
          </p>
        </div>

        {/* Stats bar */}
        <div className=\"grid grid-cols-3 gap-3\">
          {[
            { label: \"Active Tasks\",   value: fleet.tasks_active },
            { label: \"Pending\",        value: fleet.tasks_pending },
            { label: \"Coord Events\",   value: fleet.coordination_events },
          ].map(s => (
            <div key={s.label}
              className=\"rounded-xl bg-white/5 border border-white/10 p-4 text-center\">
              <div className=\"text-2xl font-bold text-cyan-400\">{s.value}</div>
              <div className=\"text-xs text-white/40 mt-1\">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Robot cards */}
        <div className=\"flex gap-4 flex-wrap\">
          <RobotCard
            robotId=\"go2_a\"
            status={fleet.go2_a_status}
            task={fleet.go2_a_task}
            position={fleet.go2_a_position}
            battery={85}
            speed={0.3}
            onCommand={() => {}}
            onPause={() => robotAction(\"go2_a\", \"pause\")}
            onStop={() => robotAction(\"go2_a\", \"stop\")}
          />
          <RobotCard
            robotId=\"go2_b\"
            status={fleet.go2_b_status}
            task={fleet.go2_b_task}
            position={fleet.go2_b_position}
            battery={92}
            speed={0.3}
            onCommand={() => {}}
            onPause={() => robotAction(\"go2_b\", \"pause\")}
            onStop={() => robotAction(\"go2_b\", \"stop\")}
          />
        </div>

        {/* Goal input */}
        <div className=\"rounded-2xl border border-white/10 bg-white/5 p-4 flex flex-col gap-3\">
          <label className=\"text-sm font-medium text-white/70\">
            High-Level Goal
          </label>
          <div className=\"flex gap-2\">
            <input
              value={goal}
              onChange={e => setGoal(e.target.value)}
              onKeyDown={e => e.key === \"Enter\" && submitGoal()}
              placeholder=\"e.g. Patrol entire factory floor\"
              className=\"flex-1 bg-white/10 border border-white/10 rounded-xl
                         px-4 py-2 text-sm text-white placeholder-white/30
                         outline-none focus:ring-1 focus:ring-cyan-500\"
            />
            <button
              onClick={submitGoal}
              disabled={loading}
              className=\"px-5 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50
                         text-white text-sm font-medium rounded-xl transition\"
            >
              {loading ? \"...\" : \"DEPLOY\"}
            </button>
          </div>
          {msg && (
            <p className=\"text-xs text-green-400\">{msg}</p>
          )}
        </div>

        {/* Task queue + Coord log */}
        <div className=\"grid grid-cols-1 md:grid-cols-2 gap-4\">
          <TaskQueue tasks={allTasksForQueue} pending={fleet.tasks_pending} />
          <CoordLog  events={coordLog} />
        </div>

      </div>
    </main>
  );
}
""")

# ════════════════════════════════════════════════════════════════════════════
# 10. End-to-end API test (MODE B — no Gazebo)
# ════════════════════════════════════════════════════════════════════════════

write_file("backend/modules/flexcell/test_e2e_api.py", """\
\"\"\"
FlexCell — End-to-end API test
Tests FastAPI endpoints directly (no Gazebo needed)
Run: python test_e2e_api.py
\"\"\"

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from httpx import AsyncClient, ASGITransport


async def main():
    # Import app after path setup
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "main", Path(__file__).parents[2] / "main.py"
    )

    print("\\nFlexCell E2E API Test")
    print("=" * 50)

    # Direct module test (avoids full app startup)
    from modules.flexcell.task_decomposer import get_decomposer
    from modules.flexcell.fleet_scheduler import get_scheduler
    from modules.flexcell.flexcell_router import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:

        # Test 1: POST /flexcell/task
        print("\\n[1] POST /flexcell/task")
        r = await client.post("/flexcell/task", json={"goal": "Patrol entire factory floor"})
        print(f"    Status  : {r.status_code}")
        data = r.json()
        print(f"    Tasks   : {len(data.get('tasks', []))}")
        for t in data.get("tasks", []):
            print(f"      [{t['robot']}] {t['task']} zone={t['params'].get('zone','?')}")
        print(f"    Reasoning: {data.get('reasoning','')}")

        # Test 2: GET /flexcell/status
        print("\\n[2] GET /flexcell/status")
        r = await client.get("/flexcell/status")
        print(f"    Status  : {r.status_code}")
        s = r.json()
        print(f"    Active  : {s.get('tasks_active')}")
        print(f"    Go2-A   : {s.get('go2_a_task')} ({s.get('go2_a_status')})")
        print(f"    Go2-B   : {s.get('go2_b_task')} ({s.get('go2_b_status')})")

        # Test 3: Pause + resume
        print("\\n[3] Robot pause/resume")
        r = await client.post("/flexcell/robot/go2_a/pause")
        print(f"    Pause go2_a : {r.json().get('status')}")
        r = await client.post("/flexcell/robot/go2_a/resume")
        print(f"    Resume go2_a: {r.json().get('status')}")

        # Test 4: GET /flexcell/log
        print("\\n[4] GET /flexcell/log")
        r = await client.get("/flexcell/log")
        log = r.json()
        print(f"    Coord events: {len(log.get('coord_log', []))}")

        # Test 5: Empty goal → 422
        print("\\n[5] Empty goal → expect 400")
        r = await client.post("/flexcell/task", json={"goal": ""})
        print(f"    Status: {r.status_code} (expected 400)")

    print("\\n" + "=" * 50)
    print("E2E API tests complete.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
""")

# ════════════════════════════════════════════════════════════════════════════
# Summary
# ════════════════════════════════════════════════════════════════════════════

print()
print("=" * 56)
print("PHASE 5 REMAINING — DONE")
print("=" * 56)
print(f"  Created : {len(CREATED)}")
for f in CREATED:
    print(f"    + {f}")
print(f"  Patched : {len(PATCHED)}")
for f in PATCHED:
    print(f"    ~ {f}")
if ERRORS:
    print(f"  Errors  : {len(ERRORS)}")
    for f in ERRORS:
        print(f"    ! {f}")
print("=" * 56)
print()
print("Test commands:")
print("  # API test (MODE B):")
print("  cd ~/projects/nexus/backend")
print("  python modules/flexcell/test_e2e_api.py")
print()
print("  # Full backend (MODE A):")
print("  uvicorn main:app --host 0.0.0.0 --port 8000 --reload")
print()
print("  # Gazebo (MODE A, separate terminal):")
print("  cd ~/projects/nexus/ros2_ws")
print("  ros2 launch nexus_robot flexcell_launch.py")
print()
