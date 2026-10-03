# ros2_ws

- `src/nexus_robot` — NEXUS ROS 2 package (launch files, Gazebo worlds, nodes).
- `src/unitree_go2_ros2` — third-party Unitree Go2 simulation. Repo mein vendored nahi hai; `nexus.repos` mein pinned hai.

## Setup (ROS 2 Jazzy)

```bash
cd ros2_ws
vcs import src < nexus.repos      # sudo apt install python3-vcstool
git -C src/unitree_go2_ros2 apply ../../patches/unitree_go2_ros2.patch
colcon build
source install/setup.bash
```

Upstream ki apni dependencies ke liye uska README dekho: https://github.com/khaledgabr77/unitree_go2_ros2.git
