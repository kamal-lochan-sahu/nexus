cmake_minimum_required(VERSION 3.8)
project(nexus_robot)

find_package(ament_cmake REQUIRED)

# Install worlds and launch directories
install(DIRECTORY worlds/ DESTINATION share/${PROJECT_NAME}/worlds)
install(DIRECTORY launch/ DESTINATION share/${PROJECT_NAME}/launch)

ament_package()
