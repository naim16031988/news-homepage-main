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










mimport time
import requests

def initialize_energy_state(prometheus_url, vm_ips):
    """
    At agent launch: fetch initial energy and timestamp per VM.

    Parameters:
        prometheus_url (str): URL of Prometheus server
        vm_ips (list[str]): List of VM IPs (e.g. ["192.168.0.11", "192.168.0.12"])

    Returns:
        dict: { ip: { 'energy': µJ, 'time': timestamp } }
    """
    try:
        res = requests.get(f"{prometheus_url}/api/v1/query", params={
            "query": "scaph_host_energy_microjoules"
        })
        res.raise_for_status()
        results = res.json()["data"]["result"]
    except Exception as e:
        print(f"Failed to query Prometheus at launch: {e}")
        return {}

    energy_state = {}
    now = time.time()

    for ip in vm_ips:
        for metric in results:
            instance = metric["metric"].get("instance", "")
            ip_only = instance.split(":")[0]
            if ip_only == ip:
                energy_uj = float(metric["value"][1])
                energy_state[ip] = {
                    "energy": energy_uj,
                    "time": now
                }
                break
        else:
            # No metric found
            energy_state[ip] = {
                "energy": 0.0,
                "time": now
            }

    return energy_state
