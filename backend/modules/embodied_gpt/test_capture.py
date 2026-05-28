import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import cv2
import numpy as np
import time

class FrameCapture(Node):
    def __init__(self):
        super().__init__('frame_capture_test')
        self.captured = False
        self.frame = None
        self.sub = self.create_subscription(
            Image, '/d455/image', self.callback, 1)
        self.get_logger().info("Waiting for /d455/image topic...")

    def callback(self, msg):
        if self.captured:
            return
        self.get_logger().info(f"Frame received! {msg.width}x{msg.height}, {msg.encoding}")
        channels = len(msg.data) // (msg.width * msg.height)
        frame = np.frombuffer(msg.data, dtype=np.uint8)
        frame = frame.reshape((msg.height, msg.width, channels))
        if msg.encoding in ['rgb8', 'RGB8']:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        self.frame = frame
        self.captured = True

def main():
    rclpy.init()
    node = FrameCapture()
    start = time.time()
    while not node.captured and time.time() - start < 10.0:
        rclpy.spin_once(node, timeout_sec=0.5)
    if node.captured:
        cv2.imwrite('/tmp/nexus_test_frame.png', node.frame)
        print(f"Frame shape: {node.frame.shape}")
        print(f"Saved: /tmp/nexus_test_frame.png")
    else:
        print("TIMEOUT — no frame received")
        print("Check: ros2 topic list | grep d455")
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
