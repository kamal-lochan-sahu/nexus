"""Checks on the nexus_robot ROS 2 package that need no ROS installation."""
import importlib.util
import re
import xml.dom.minidom
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "ros2_ws" / "src" / "nexus_robot"
HIDDEN = ("\u200b", "\u200c", "\u200d", "\ufeff", "\u00a0")


def load_policy_module():
    spec = importlib.util.spec_from_file_location("nexus_policy_path", PKG / "nexus_robot" / "policy_path.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pp = load_policy_module()


def make_policy(folder: Path) -> Path:
    path = folder / "models" / "ppo_go2" / "best_model.zip"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"zip")
    return path


@pytest.fixture(autouse=True)
def no_env(monkeypatch):
    monkeypatch.delenv("NEXUS_POLICY_PATH", raising=False)


# ── policy lookup ─────────────────────────────────────────────────

def test_the_real_repository_policy_is_found_from_the_source_tree():
    found = pp.find_policy(module_file=str(PKG / "nexus_robot" / "rl_policy_node.py"))
    assert found and found.endswith("models/ppo_go2/best_model.zip") and Path(found).is_file()


def test_explicit_path_wins(tmp_path, monkeypatch):
    explicit = tmp_path / "mine.zip"
    explicit.write_bytes(b"zip")
    monkeypatch.setenv("NEXUS_POLICY_PATH", str(make_policy(tmp_path / "env")))
    assert pp.find_policy(str(explicit)) == str(explicit)


def test_explicit_path_that_does_not_exist_is_an_error_not_a_guess(tmp_path):
    make_policy(tmp_path)   # a policy exists in the tree, but the explicit path must not be replaced
    assert pp.find_policy(str(tmp_path / "typo.zip"), module_file=str(tmp_path / "a" / "x.py")) is None


def test_environment_variable_is_used(tmp_path, monkeypatch):
    policy = make_policy(tmp_path)
    monkeypatch.setenv("NEXUS_POLICY_PATH", str(policy))
    assert pp.find_policy(module_file=str(tmp_path / "elsewhere" / "x.py"), cwd=str(tmp_path / "elsewhere")) == str(policy)


def test_environment_variable_pointing_nowhere_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_POLICY_PATH", str(tmp_path / "nope.zip"))
    assert pp.find_policy(module_file=str(tmp_path / "x.py")) is None


def test_found_in_a_parent_folder_of_the_module(tmp_path):
    policy = make_policy(tmp_path)
    module = tmp_path / "ros2_ws" / "src" / "pkg" / "pkg" / "node.py"
    module.parent.mkdir(parents=True)
    assert pp.find_policy(module_file=str(module), cwd=str(tmp_path / "nowhere")) == str(policy)


def test_found_in_a_parent_folder_of_the_current_directory(tmp_path):
    policy = make_policy(tmp_path / "repo")
    work = tmp_path / "repo" / "ros2_ws"
    work.mkdir(parents=True)
    other = tmp_path / "install" / "pkg"
    other.mkdir(parents=True)
    assert pp.find_policy(module_file=str(other / "node.py"), cwd=str(work)) == str(policy)


def test_nothing_found_gives_none(tmp_path):
    assert pp.find_policy(module_file=str(tmp_path / "a" / "x.py"), cwd=str(tmp_path)) is None


# ── world files ───────────────────────────────────────────────────

WORLDS = sorted((PKG / "worlds").glob("*.sdf"))


def test_both_worlds_are_there():
    assert [w.name for w in WORLDS] == ["flexcell_world.sdf", "nexus_arena.sdf"]


@pytest.mark.parametrize("world", WORLDS, ids=lambda w: w.name)
def test_world_is_well_formed_xml(world):
    xml.dom.minidom.parse(str(world))


@pytest.mark.parametrize("world", WORLDS, ids=lambda w: w.name)
def test_world_has_no_hidden_characters(world):
    text = world.read_text(encoding="utf-8")
    assert not [c for c in HIDDEN if c in text]


@pytest.mark.parametrize("world", WORLDS, ids=lambda w: w.name)
def test_experimental_prefix_is_declared_when_used(world):
    text = world.read_text(encoding="utf-8")
    if "experimental:" in text:
        assert 'xmlns:experimental="' in text


# ── executables and packaging ─────────────────────────────────────

SCRIPTS = ["fleet_node", "rl_policy_node"]


@pytest.mark.parametrize("name", SCRIPTS)
def test_script_is_an_executable_that_calls_main_of_its_module(name):
    script = PKG / "scripts" / name
    lines = script.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "#!/usr/bin/env python3"
    assert f"from nexus_robot.{name} import main" in lines
    assert script.stat().st_mode & 0o111, "scripts must be executable"
    assert re.search(r"^def main\(", (PKG / "nexus_robot" / f"{name}.py").read_text(encoding="utf-8"), re.M)


def test_the_python_package_has_an_init_file():
    assert (PKG / "nexus_robot" / "__init__.py").is_file()


def test_cmake_installs_the_package_and_both_executables():
    cmake = (PKG / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "ament_python_install_package(${PROJECT_NAME})" in cmake
    for name in SCRIPTS:
        assert f"scripts/{name}" in cmake
    assert "DESTINATION lib/${PROJECT_NAME}" in cmake


def test_package_xml_declares_what_the_nodes_import():
    manifest = (PKG / "package.xml").read_text(encoding="utf-8")
    for dep in ("ament_cmake_python", "rclpy", "geometry_msgs", "nav_msgs", "sensor_msgs", "std_msgs", "python3-numpy"):
        assert f">{dep}<" in manifest


def test_launch_files_only_start_executables_that_are_installed():
    launch = (PKG / "launch" / "flexcell_launch.py").read_text(encoding="utf-8")
    for name in re.findall(r'executable="(fleet_node|rl_policy_node)"', launch):
        assert (PKG / "scripts" / name).is_file()


def test_the_rl_node_no_longer_hardcodes_a_relative_policy_path():
    source = (PKG / "nexus_robot" / "rl_policy_node.py").read_text(encoding="utf-8")
    assert "../../../../../../" not in source and "find_policy(" in source
