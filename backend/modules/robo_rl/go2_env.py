"""
NEXUS Phase 4 — RoboRL
Custom Gymnasium environment for Unitree Go2 robot navigation.

Factory floor: 6x6m arena, x,y ∈ [-3.0, +3.0]
Zones: A(top-left) B(top-right) C(bottom-left) D(bottom-right)

This is a MOCK environment for local dev + reward testing.
ROS2/Gazebo wrapper inherits from this class (Step 3).
"""

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from typing import Optional, Tuple, Dict


class Go2Env(gym.Env):
    metadata = {"render_modes": ["human", "rgb_array"]}

    # Arena
    ARENA_LIMIT = 3.0
    GOAL_RADIUS  = 0.3

    # Rewards
    REWARD_GOAL_REACHED  =  100.0
    REWARD_COLLISION     = -100.0
    REWARD_MOVING_TOWARD =    0.1
    REWARD_TIMESTEP      =   -0.01
    REWARD_BOUNDARY      =   -1.0

    # Episode
    MAX_STEPS = 1000

    # Zone centers
    ZONES = {
        "A": np.array([-2.5,  2.5, 0.0]),
        "B": np.array([ 2.5,  2.5, 0.0]),
        "C": np.array([-2.5, -2.5, 0.0]),
        "D": np.array([ 2.5, -2.5, 0.0]),
    }

    def __init__(self, render_mode: Optional[str] = None, target_zone: Optional[str] = None):
        super().__init__()
        self.render_mode = render_mode
        self.target_zone = target_zone

        # Observation space (24,)
        # [0:3]   robot position    (x, y, z)
        # [3:7]   orientation quat  (qx, qy, qz, qw)
        # [7:10]  goal direction    (dx, dy, dz) normalized
        # [10:22] lidar scan        (12 rays, 0–5m)
        # [22:24] velocity          (linear_x, angular_z)
        obs_low = np.array(
            [-3., -3., 0.] + [-1., -1., -1., -1.] + [-1., -1., -1.] +
            [0.0] * 12 + [-0.5, -1.0], dtype=np.float32
        )
        obs_high = np.array(
            [3., 3., 1.] + [1., 1., 1., 1.] + [1., 1., 1.] +
            [5.0] * 12 + [0.5, 1.0], dtype=np.float32
        )
        self.observation_space = spaces.Box(obs_low, obs_high, dtype=np.float32)

        # Action space (2,) continuous
        # [0] linear_x  : [0.0, 0.5] m/s
        # [1] angular_z : [-1.0, 1.0] rad/s
        self.action_space = spaces.Box(
            low=np.array([0.0, -1.0], dtype=np.float32),
            high=np.array([0.5,  1.0], dtype=np.float32),
            dtype=np.float32
        )

        # Internal state
        self._robot_pos  = np.zeros(3, dtype=np.float32)
        self._robot_quat = np.array([0., 0., 0., 1.], dtype=np.float32)
        self._robot_vel  = np.zeros(2, dtype=np.float32)
        self._goal_pos   = np.zeros(3, dtype=np.float32)
        self._lidar      = np.ones(12, dtype=np.float32) * 5.0
        self._step_count = 0
        self._prev_dist  = float("inf")
        self._obstacles  = []

    # ── RESET ───────────────────────────────────────────────────────
    def reset(self, *, seed=None, options=None) -> Tuple[np.ndarray, Dict]:
        super().reset(seed=seed)

        # Random robot spawn
        self._robot_pos = np.array([
            self.np_random.uniform(-2.5, 2.5),
            self.np_random.uniform(-2.5, 2.5),
            0.0
        ], dtype=np.float32)

        yaw = self.np_random.uniform(-np.pi, np.pi)
        self._robot_quat = self._yaw_to_quat(yaw)
        self._robot_vel  = np.zeros(2, dtype=np.float32)

        # Goal zone
        if self.target_zone and self.target_zone in self.ZONES:
            self._goal_pos = self.ZONES[self.target_zone].copy()
        else:
            zone = self.np_random.choice(list(self.ZONES.keys()))
            self._goal_pos = self.ZONES[zone].copy()

        # Ensure spawn != goal
        while np.linalg.norm(self._robot_pos[:2] - self._goal_pos[:2]) < 1.0:
            self._robot_pos[:2] = self.np_random.uniform(-2.5, 2.5, 2)

        # Random obstacles (3–6)
        self._obstacles = self._generate_obstacles(n=self.np_random.integers(3, 7))
        self._step_count = 0
        self._prev_dist  = self._dist_to_goal()
        self._lidar      = self._compute_lidar()

        obs  = self._get_obs()
        info = {"goal_pos": self._goal_pos.copy(), "spawn_pos": self._robot_pos.copy()}
        return obs, info

    # ── STEP ────────────────────────────────────────────────────────
    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        action   = np.clip(action, self.action_space.low, self.action_space.high)
        linear_x = float(action[0])
        angular_z = float(action[1])
        dt = 0.1  # 10Hz

        # Unicycle motion model
        yaw = self._quat_to_yaw(self._robot_quat)
        yaw += angular_z * dt
        self._robot_pos[0] += linear_x * np.cos(yaw) * dt
        self._robot_pos[1] += linear_x * np.sin(yaw) * dt
        self._robot_quat    = self._yaw_to_quat(yaw)
        self._robot_vel     = np.array([linear_x, angular_z], dtype=np.float32)

        self._lidar = self._compute_lidar()
        reward, terminated = self._compute_reward()
        self._step_count += 1
        truncated = self._step_count >= self.MAX_STEPS
        self._prev_dist = self._dist_to_goal()

        obs  = self._get_obs()
        info = {
            "dist_to_goal"  : self._dist_to_goal(),
            "step"          : self._step_count,
            "collision"     : self._check_collision(),
            "boundary_viol" : self._check_boundary(),
        }
        return obs, reward, terminated, truncated, info

    # ── REWARD ──────────────────────────────────────────────────────
    def _compute_reward(self) -> Tuple[float, bool]:
        reward, terminated = 0.0, False
        dist = self._dist_to_goal()

        # ① Goal reached
        if dist < self.GOAL_RADIUS:
            return self.REWARD_GOAL_REACHED, True

        # ② Collision
        if self._check_collision():
            return self.REWARD_COLLISION, True

        # ③ Boundary
        if self._check_boundary():
            reward += self.REWARD_BOUNDARY

        # ④ Progress toward goal
        if (self._prev_dist - dist) > 0:
            reward += self.REWARD_MOVING_TOWARD

        # ⑤ Timestep penalty
        reward += self.REWARD_TIMESTEP

        return reward, terminated

    # ── OBSERVATION ─────────────────────────────────────────────────
    def _get_obs(self) -> np.ndarray:
        goal_vec  = self._goal_pos - self._robot_pos
        goal_dist = np.linalg.norm(goal_vec) + 1e-8
        goal_dir  = (goal_vec / goal_dist).astype(np.float32)

        obs = np.concatenate([
            self._robot_pos,
            self._robot_quat,
            goal_dir,
            self._lidar,
            self._robot_vel,
        ]).astype(np.float32)

        assert obs.shape == (24,), f"Obs shape mismatch: {obs.shape}"
        return obs

    # ── HELPERS ─────────────────────────────────────────────────────
    def _dist_to_goal(self) -> float:
        return float(np.linalg.norm(self._robot_pos[:2] - self._goal_pos[:2]))

    def _check_collision(self) -> bool:
        for (ox, oy, r) in self._obstacles:
            if np.linalg.norm(self._robot_pos[:2] - np.array([ox, oy])) < (r + 0.25):
                return True
        return False

    def _check_boundary(self) -> bool:
        return abs(self._robot_pos[0]) > self.ARENA_LIMIT or abs(self._robot_pos[1]) > self.ARENA_LIMIT

    def _compute_lidar(self) -> np.ndarray:
        yaw    = self._quat_to_yaw(self._robot_quat)
        angles = yaw + np.linspace(0, 2 * np.pi, 12, endpoint=False)
        dists  = np.full(12, 5.0, dtype=np.float32)

        for i, angle in enumerate(angles):
            dx, dy = np.cos(angle), np.sin(angle)
            for t in np.arange(0.1, 5.0, 0.05):
                px = self._robot_pos[0] + dx * t
                py = self._robot_pos[1] + dy * t
                hit = False
                if abs(px) >= self.ARENA_LIMIT or abs(py) >= self.ARENA_LIMIT:
                    dists[i] = t
                    hit = True
                else:
                    for (ox, oy, r) in self._obstacles:
                        if np.linalg.norm(np.array([px - ox, py - oy])) < r:
                            dists[i] = t
                            hit = True
                            break
                if hit:
                    break
        return np.clip(dists, 0.0, 5.0)

    def _generate_obstacles(self, n: int) -> list:
        obstacles = []
        for _ in range(n):
            for _ in range(50):
                ox = self.np_random.uniform(-2.5, 2.5)
                oy = self.np_random.uniform(-2.5, 2.5)
                r  = 0.2
                far_from_spawn = np.linalg.norm([ox - self._robot_pos[0], oy - self._robot_pos[1]]) > 0.8
                far_from_goal  = np.linalg.norm([ox - self._goal_pos[0],  oy - self._goal_pos[1]])  > 0.8
                if far_from_spawn and far_from_goal:
                    obstacles.append((ox, oy, r))
                    break
        return obstacles

    @staticmethod
    def _yaw_to_quat(yaw: float) -> np.ndarray:
        return np.array([0., 0., np.sin(yaw / 2), np.cos(yaw / 2)], dtype=np.float32)

    @staticmethod
    def _quat_to_yaw(quat: np.ndarray) -> float:
        return 2.0 * np.arctan2(float(quat[2]), float(quat[3]))

    def render(self):
        pass  # FleetMap (Step 9) handles visualization

    def close(self):
        pass
