"""
NEXUS Phase 4 — Step 5
Policy evaluation — tests trained PPO on unseen environments.
Target: >85% success rate.

Run: python backend/modules/robo_rl/evaluate_policy.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from stable_baselines3 import PPO

from backend.modules.robo_rl.go2_env import Go2Env


# ── Config ──────────────────────────────────────────────────────────
MODEL_PATH     = "models/ppo_go2/best_model.zip"
N_EVAL_EPISODES = 100
DETERMINISTIC  = True


def evaluate(model_path: str, n_episodes: int) -> dict:
    print(f"\n{'='*55}")
    print(f"  NEXUS Phase 4 — PPO Policy Evaluation")
    print(f"{'='*55}")
    print(f"  Model     : {model_path}")
    print(f"  Episodes  : {n_episodes}")
    print(f"  Target SR : 85%")
    print(f"{'='*55}\n")

    # Load model
    model = PPO.load(model_path)
    print(f"✅ Model loaded")

    results = {
        "success": 0, "collision": 0, "timeout": 0, "boundary": 0,
        "rewards": [], "steps": [], "final_dists": [],
    }

    for ep in range(n_episodes):
        env  = Go2Env()
        obs, info = env.reset(seed=ep * 7)
        ep_reward = 0.0
        done = False

        while not done:
            action, _ = model.predict(obs, deterministic=DETERMINISTIC)
            obs, reward, terminated, truncated, info = env.step(action)
            ep_reward += reward
            done = terminated or truncated

        # Classify outcome
        dist = info["dist_to_goal"]
        results["rewards"].append(ep_reward)
        results["steps"].append(env._step_count)
        results["final_dists"].append(dist)

        if dist < Go2Env.GOAL_RADIUS:
            results["success"] += 1
            outcome = "✅ GOAL"
        elif info["collision"]:
            results["collision"] += 1
            outcome = "💥 COLLISION"
        elif truncated:
            results["timeout"] += 1
            outcome = "⏱  TIMEOUT"
        else:
            results["boundary"] += 1
            outcome = "🚧 BOUNDARY"

        if (ep + 1) % 10 == 0:
            sr = results["success"] / (ep + 1) * 100
            print(f"  Ep {ep+1:3d}/{n_episodes} | {outcome:14s} | "
                  f"reward={ep_reward:7.1f} | dist={dist:.2f}m | SR={sr:.0f}%")

        env.close()

    # Summary
    sr = results["success"] / n_episodes * 100
    print(f"\n{'='*55}")
    print(f"  RESULTS ({n_episodes} episodes)")
    print(f"{'='*55}")
    print(f"  Success rate  : {sr:.1f}%  {'✅ PASS' if sr >= 85 else '❌ FAIL'}")
    print(f"  Goals reached : {results['success']}/{n_episodes}")
    print(f"  Collisions    : {results['collision']}")
    print(f"  Timeouts      : {results['timeout']}")
    print(f"  Boundary hits : {results['boundary']}")
    print(f"  Mean reward   : {np.mean(results['rewards']):.2f} ± {np.std(results['rewards']):.2f}")
    print(f"  Mean steps    : {np.mean(results['steps']):.0f}")
    print(f"  Mean final dist: {np.mean(results['final_dists']):.2f}m")
    print(f"{'='*55}\n")

    return results, sr


def plot_results(results: dict, sr: float):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    # Outcome pie
    labels  = ["Success", "Collision", "Timeout", "Boundary"]
    counts  = [results["success"], results["collision"],
               results["timeout"], results["boundary"]]
    colors  = ["#4CAF50", "#f44336", "#FF9800", "#9C27B0"]
    axes[0].pie(counts, labels=labels, colors=colors,
                autopct="%1.0f%%", startangle=90)
    axes[0].set_title(f"Outcomes (SR={sr:.1f}%)")

    # Reward distribution
    axes[1].hist(results["rewards"], bins=20, color="#2196F3", edgecolor="white")
    axes[1].axvline(np.mean(results["rewards"]), color="red",
                    linestyle="--", label=f"Mean={np.mean(results['rewards']):.1f}")
    axes[1].set_xlabel("Episode reward")
    axes[1].set_ylabel("Count")
    axes[1].set_title("Reward distribution")
    axes[1].legend()

    # Final distance distribution
    axes[2].hist(results["final_dists"], bins=20, color="#FF9800", edgecolor="white")
    axes[2].axvline(Go2Env.GOAL_RADIUS, color="green",
                    linestyle="--", label=f"Goal radius ({Go2Env.GOAL_RADIUS}m)")
    axes[2].set_xlabel("Final distance to goal (m)")
    axes[2].set_ylabel("Count")
    axes[2].set_title("Final distance distribution")
    axes[2].legend()

    plt.suptitle("NEXUS Phase 4 — PPO Policy Evaluation", fontsize=13)
    plt.tight_layout()

    out = "models/ppo_go2/eval_results.png"
    plt.savefig(out, dpi=150)
    print(f"✅ Plot saved: {out}")


if __name__ == "__main__":
    results, sr = evaluate(MODEL_PATH, N_EVAL_EPISODES)
    plot_results(results, sr)
    sys.exit(0 if sr >= 85 else 1)
