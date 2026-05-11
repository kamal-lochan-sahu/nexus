"""
CoboSense end-to-end test (no camera needed — simulation mode)
Run: source ../../venv/bin/activate && python test_cobosense.py
"""

import sys
import asyncio
import time

sys.path.insert(0, "../../")

from pose_tracker import PoseTracker, PoseResult
from intent_lstm import IntentClassifier
from speed_controller import SpeedController


def test_speed_controller():
    print("\n── SpeedController Tests ──────────────────────────")
    ctrl = SpeedController()
    cases = [
        ("A", "static"),
        ("A", "approaching"),
        ("B", "static"),
        ("B", "approaching"),
        ("B", "leaving"),
        ("C", "approaching"),
        ("C", "static"),
        ("NONE", "static"),
    ]
    all_pass = True
    for zone, intent in cases:
        spd = ctrl.get_target_speed(zone, intent, current_cmd_vel=0.5)
        expected_zero = zone == "A" or (zone == "B" and intent == "approaching")
        status = "✅" if (expected_zero == (spd == 0.0)) else "❌"
        if status == "❌": all_pass = False
        print(f"  {status} Zone {zone} + {intent:12s} → {spd:.2f} m/s")
    print(f"\n  SpeedController: {'ALL PASS ✅' if all_pass else 'SOME FAILED ❌'}")


def test_zone_classifier():
    print("\n── Zone Classifier Tests ──────────────────────────")
    cases = [
        (0.5, "A"), (1.4, "A"), (1.5, "A"),
        (1.6, "B"), (2.5, "B"), (3.0, "B"),
        (3.01, "C"), (5.0, "C"),
    ]
    all_pass = True
    for dist, expected in cases:
        got = PoseTracker.classify_zone(dist)
        status = "✅" if got == expected else "❌"
        if status == "❌": all_pass = False
        print(f"  {status} {dist:.2f}m → Zone {got} (expected {expected})")
    print(f"\n  ZoneClassifier: {'ALL PASS ✅' if all_pass else 'SOME FAILED ❌'}")


def test_intent_classifier():
    print("\n── IntentClassifier (no model — default) ──────────")
    clf = IntentClassifier()
    clf.load()  # Will warn if model.pt missing

    fake_landmarks = [{"x": 0.5, "y": 0.5, "z": 0.0, "v": 0.9}] * 33
    for i in range(12):
        intent, conf = clf.update(fake_landmarks)
    print(f"  Intent: {intent}, Conf: {conf:.2f}")
    print(f"  {'✅' if intent in ['static','leaving','approaching'] else '❌'} Valid intent returned")


def test_payload():
    print("\n── Payload Builder ────────────────────────────────")
    ctrl = SpeedController()
    payload = ctrl.build_safety_payload(
        zone="B", distance_m=2.1, intent="approaching",
        intent_conf=0.87, human_detected=True, current_cmd_vel=0.5
    )
    print(f"  payload: {payload}")
    assert payload["speed_override"] == 0.0, "Zone B + approaching must be 0"
    print("  ✅ Payload correct")


if __name__ == "__main__":
    print("=" * 55)
    print("  NEXUS CoboSense — Unit Tests")
    print("=" * 55)
    test_zone_classifier()
    test_speed_controller()
    test_intent_classifier()
    test_payload()
    print("\n" + "=" * 55)
    print("  All tests complete!")
    print("=" * 55)
