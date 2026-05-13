"""
NEXUS Phase 4 — RoboRL
Reward function unit tests — No ROS2 needed, pure Python.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

import numpy as np
from backend.modules.robo_rl.go2_env import Go2Env


@pytest.fixture
def env():
    e = Go2Env()
    e.reset(seed=42)
    return e


class TestRewardFunction:

    def test_goal_reached(self, env):
        """Goal ke paas → +100.0, terminated=True."""
        env._robot_pos = env._goal_pos.copy()
        env._robot_pos[0] += 0.1      # 0.1m away < GOAL_RADIUS (0.3m)
        env._obstacles = []
        reward, terminated = env._compute_reward()
        assert terminated is True
        assert reward == pytest.approx(100.0)

    def test_collision(self, env):
        """Collision → -100.0, terminated=True."""
        if not env._obstacles:
            env._obstacles = [(0.0, 0.0, 0.2)]
        ox, oy, _ = env._obstacles[0]
        env._robot_pos = np.array([ox, oy, 0.0], dtype=np.float32)
        # Make sure not at goal
        env._goal_pos = np.array([2.5, 2.5, 0.0], dtype=np.float32)
        reward, terminated = env._compute_reward()
        assert terminated is True
        assert reward == pytest.approx(-100.0)

    def test_boundary_violation(self, env):
        """Boundary → -1.0 penalty, NOT terminated."""
        env._robot_pos = np.array([3.5, 0.0, 0.0], dtype=np.float32)
        env._obstacles = []
        env._goal_pos  = np.array([2.5, 2.5, 0.0], dtype=np.float32)
        env._prev_dist = env._dist_to_goal()   # exact same dist = zero progress
        reward, terminated = env._compute_reward()
        assert terminated is False
        # boundary(-1.0) + timestep(-0.01) = -1.01
        assert reward == pytest.approx(-1.01)

    def test_moving_toward_goal(self, env):
        """Getting closer → +0.1 progress reward."""
        env._obstacles = []
        env._robot_pos = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        env._goal_pos  = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        env._prev_dist = 1.5       # was 1.5m, now ~1.0m → delta > 0
        reward, terminated = env._compute_reward()
        assert terminated is False
        # progress(0.1) + timestep(-0.01) = 0.09
        assert reward == pytest.approx(0.09)

    def test_no_progress_no_boundary(self, env):
        """Standing still, no boundary → only timestep penalty."""
        env._obstacles = []
        env._robot_pos = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        env._goal_pos  = np.array([2.0, 0.0, 0.0], dtype=np.float32)
        env._prev_dist = env._dist_to_goal()   # same dist = no progress
        reward, terminated = env._compute_reward()
        assert terminated is False
        assert reward == pytest.approx(-0.01)

    def test_observation_shape(self, env):
        """Observation shape (24,) float32."""
        obs, _ = env.reset(seed=0)
        assert obs.shape == (24,)
        assert obs.dtype == np.float32

    def test_observation_bounds(self, env):
        """Observation must be within defined space bounds."""
        for seed in range(5):
            obs, _ = env.reset(seed=seed)
            assert np.all(obs >= env.observation_space.low), "Obs below lower bound"
            assert np.all(obs <= env.observation_space.high), "Obs above upper bound"

    def test_action_space_bounds(self, env):
        """Action space bounds exactly as spec."""
        assert env.action_space.low[0]  == pytest.approx(0.0)
        assert env.action_space.high[0] == pytest.approx(0.5)
        assert env.action_space.low[1]  == pytest.approx(-1.0)
        assert env.action_space.high[1] == pytest.approx(1.0)

    def test_episode_truncation(self, env):
        """Episode must truncate at MAX_STEPS (1000)."""
        env.reset(seed=7)
        done, steps = False, 0
        while not done and steps < 1100:
            _, _, terminated, truncated, _ = env.step(env.action_space.sample())
            done = terminated or truncated
            steps += 1
        assert done is True
        assert steps <= 1001

    def test_zones_exist(self, env):
        """All 4 zones A B C D defined."""
        for zone in ["A", "B", "C", "D"]:
            assert zone in env.ZONES
            env2 = Go2Env(target_zone=zone)
            obs, info = env2.reset(seed=0)
            np.testing.assert_array_almost_equal(info["goal_pos"], env.ZONES[zone])

    def test_lidar_shape(self, env):
        """LiDAR returns 12 readings in [0, 5.0]."""
        lidar = env._compute_lidar()
        assert lidar.shape == (12,)
        assert np.all(lidar >= 0.0)
        assert np.all(lidar <= 5.0)
