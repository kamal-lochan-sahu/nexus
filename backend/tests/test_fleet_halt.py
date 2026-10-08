"""Tests for the FlexCell emergency halt (FleetScheduler.halt_all / resume_robot)."""
from modules.flexcell.fleet_scheduler import FleetScheduler, RobotStatus


def test_halt_all_stops_every_robot_and_logs_it():
    scheduler = FleetScheduler()
    scheduler._states["go2_a"].status = RobotStatus.ACTIVE
    scheduler._states["go2_a"].speed = 0.4

    halted = scheduler.halt_all("emergency stop")

    assert sorted(halted) == ["go2_a", "go2_b"]
    assert all(state.status == RobotStatus.STOPPED for state in scheduler._states.values())
    assert scheduler._states["go2_a"].speed == 0.0
    events = [e for e in scheduler.get_coord_log() if e["event"] == "STOPPED"]
    assert len(events) == 2 and all(e["detail"] == "emergency stop" for e in events)


def test_stopped_robot_can_be_cleared_with_resume():
    scheduler = FleetScheduler()
    scheduler.halt_all("emergency stop")
    scheduler.resume_robot("go2_a")
    assert scheduler.get_robot_state("go2_a").status == RobotStatus.IDLE
    assert scheduler.get_robot_state("go2_b").status == RobotStatus.STOPPED
    assert any(e["event"] == "RESET" and e["robot"] == "go2_a" for e in scheduler.get_coord_log())


def test_resume_still_unpauses_a_paused_robot():
    scheduler = FleetScheduler()
    scheduler.pause_robot("go2_a", "too close")
    scheduler.resume_robot("go2_a")
    assert scheduler.get_robot_state("go2_a").status == RobotStatus.ACTIVE


def test_resume_leaves_an_idle_robot_alone():
    scheduler = FleetScheduler()
    scheduler.resume_robot("go2_b")
    assert scheduler.get_robot_state("go2_b").status == RobotStatus.IDLE
