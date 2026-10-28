cmake_minimum_required(VERSION 3.8)
project(nexus_robot)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

# Python package: nexus_robot/nexus_robot/*.py  ->  import nexus_robot.fleet_node
ament_python_install_package(${PROJECT_NAME})

# Executables: ros2 run nexus_robot fleet_node / rl_policy_node
install(PROGRAMS
  scripts/fleet_node
  scripts/rl_policy_node
  DESTINATION lib/${PROJECT_NAME}
)

# Install worlds and launch directories
install(DIRECTORY worlds/ DESTINATION share/${PROJECT_NAME}/worlds)
install(DIRECTORY launch/ DESTINATION share/${PROJECT_NAME}/launch)

ament_package()
