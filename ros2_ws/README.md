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

## Run the nodes

```bash
colcon build --packages-select nexus_robot
source install/setup.bash
ros2 run nexus_robot fleet_node
ros2 run nexus_robot rl_policy_node --ros-args -p goal_zone:=B -p active:=true
```

`rl_policy_node` needs `pip install stable-baselines3 torch`. It looks for the trained policy in
`models/ppo_go2/best_model.zip` (searching upwards from the source tree and from the current folder).
Set `NEXUS_POLICY_PATH` or the `policy_path` parameter to use another file.
