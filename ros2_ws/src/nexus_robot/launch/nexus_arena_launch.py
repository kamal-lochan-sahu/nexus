"""
NEXUS Phase 8 — Step 2
Factory arena launch — headless, RAM-aware (~800MB total).

Spawns:
  go2_a → Zone A (-1.5,  1.5, 0.375)
  go2_b → Zone C (-1.5, -1.5, 0.375)
"""

import os
import launch_ros
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution


def generate_launch_description():

    # ── Package paths ────────────────────────────────────────────────
    go2_desc = launch_ros.substitutions.FindPackageShare(
        package="unitree_go2_description").find("unitree_go2_description")
    go2_sim = launch_ros.substitutions.FindPackageShare(
        package="unitree_go2_sim").find("unitree_go2_sim")

    xacro_path    = os.path.join(go2_desc, "urdf/unitree_go2_robot.xacro")
    arena_sdf     = os.path.join(
        get_package_share_directory("nexus_robot"),
        "worlds", "nexus_arena.sdf"
    )
    ros_ctrl_cfg  = os.path.join(go2_sim, "config/ros_control/ros_control.yaml")
    pkg_ros_gz    = get_package_share_directory("ros_gz_sim")

    # ── Args ─────────────────────────────────────────────────────────
    declare_sim_time = DeclareLaunchArgument(
        "use_sim_time", default_value="true")

    # ── Gazebo headless ──────────────────────────────────────────────
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz, "launch", "gz_sim.launch.py")),
        launch_arguments={
            "gz_args": arena_sdf + " -r -s --headless-rendering",
        }.items(),
    )

    # ── Shared robot description ─────────────────────────────────────
    robot_desc_param = {
        "robot_description": Command([
            "xacro ", xacro_path,
            " robot_controllers:=", ros_ctrl_cfg
        ])
    }

    robot_state_pub = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="screen",
        parameters=[robot_desc_param, {"use_sim_time": True}],
    )

    # ── Spawn go2_a — Zone A (-1.5, 1.5) ────────────────────────────
    spawn_go2_a = TimerAction(period=3.0, actions=[
        Node(
            package="ros_gz_sim",
            executable="create",
            output="screen",
            arguments=[
                "-name",  "go2_a",
                "-topic", "robot_description",
                "-x",     "-1.5",
                "-y",     "1.5",
                "-z",     "0.375",
                "-Y",     "0.0",
            ],
        )
    ])

    # ── Spawn go2_b — Zone C (-1.5, -1.5) ───────────────────────────
    spawn_go2_b = TimerAction(period=6.0, actions=[
        Node(
            package="ros_gz_sim",
            executable="create",
            output="screen",
            arguments=[
                "-name",  "go2_b",
                "-topic", "robot_description",
                "-x",     "-1.5",
                "-y",     "-1.5",
                "-z",     "0.375",
                "-Y",     "1.57",
            ],
        )
    ])

    # ── ROS-GZ bridge (both robots) ──────────────────────────────────
    gz_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="nexus_gz_bridge",
        output="screen",
        parameters=[{"use_sim_time": True}],
        arguments=[
            # Clock
            "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock",
            # go2_a
            "/go2_a/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
            "/go2_a/odom@nav_msgs/msg/Odometry@gz.msgs.Odometry",
            # go2_b
            "/go2_b/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
            "/go2_b/odom@nav_msgs/msg/Odometry@gz.msgs.Odometry",
            # Camera (EmbodiedGPT)
            "/d455/image@sensor_msgs/msg/Image[gz.msgs.Image",
            # Joint states
            "/joint_states@sensor_msgs/msg/JointState@gz.msgs.Model",
            # TF
            "/tf@tf2_msgs/msg/TFMessage@gz.msgs.Pose_V",
        ],
    )

    # ── map→odom static TF ───────────────────────────────────────────
    map_to_odom_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        arguments=[
            "--x", "0", "--y", "0", "--z", "0",
            "--roll", "0", "--pitch", "0", "--yaw", "0",
            "--frame-id", "map", "--child-frame-id", "odom",
        ],
        parameters=[{"use_sim_time": True}],
    )

    return LaunchDescription([
        declare_sim_time,
        gz_sim,
        robot_state_pub,
        spawn_go2_a,
        spawn_go2_b,
        gz_bridge,
        map_to_odom_tf,
    ])
