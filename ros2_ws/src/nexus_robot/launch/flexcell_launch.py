"""
FlexCell Launch — Two Go2 robots in headless Gazebo
Usage: ros2 launch nexus_robot flexcell_launch.py
"""

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
