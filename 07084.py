import zmq
import cv2
import numpy as np

context = zmq.Context()
socket = context.socket(zmq.PULL)
socket.bind("tcp://*:6000")

print("[INFO] Viewer started, waiting for frames...")

frame_count = 0

while True:
    try:
        frame_bytes = socket.recv()
        print(f"[DEBUG] Received {len(frame_bytes)} bytes")

        jpg_array = np.frombuffer(frame_bytes, dtype=np.uint8)
        frame = cv2.imdecode(jpg_array, cv2.IMREAD_COLOR)

        if frame is not None and frame.size > 0:
            cv2.imshow("Live Video", frame)
            frame_count += 1

            # Save one frame to inspect
            if frame_count == 1:
                cv2.imwrite("first_frame.jpg", frame)
                print("[INFO] Saved 'first_frame.jpg' for inspection.")

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        else:
            print("❌ Frame is None or empty")

    except Exception as e:
        print(f"[ERROR] {e}")
        break

cv2.destroyAllWindows()
