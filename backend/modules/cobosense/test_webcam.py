"""
Live webcam test for CoboSense pose_tracker.
Press q to quit.
Usage: python test_webcam.py [camera_index]
"""

import sys
import cv2
import time

sys.path.insert(0, ".")

from pose_tracker import PoseTracker

def main():
    cam = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    tracker = PoseTracker(model_complexity=0)
    cap = cv2.VideoCapture(cam)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print(f"❌ Camera {cam} not available")
        print("   Check: ls /dev/video*")
        sys.exit(1)

    print("✅ Camera opened. Press q to quit.")
    print("   Move toward/away camera to see zone change.")

    frame_n = 0
    fps_t = time.time()
    fps = 0.0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_n += 1

        if frame_n % 2 == 0:   # Even → MediaPipe
            result = tracker.process_frame(frame)
            display = result.frame_annotated.copy()
            if result.human_detected:
                print(
                    f"\rZone:{result.zone} | "
                    f"Dist:{result.distance_m:.2f}m | "
                    f"Conf:{result.confidence:.2f} | FPS:{fps:.1f}",
                    end="", flush=True
                )
        else:
            display = frame

        # FPS
        if frame_n % 20 == 0:
            fps = 20 / (time.time() - fps_t + 1e-6)
            fps_t = time.time()

        cv2.putText(display, f"FPS:{fps:.1f}", (550, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,0), 2)

        cv2.imshow("CoboSense — Press q to quit", display)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    print()
    cap.release()
    tracker.close()
    cv2.destroyAllWindows()
    print("Done.")

if __name__ == "__main__":
    main()
