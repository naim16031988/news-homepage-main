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




from flask import Flask, request, jsonify
import json
import requests
import time
import random
from collections import defaultdict

app = Flask(__name__)

# === Q-learning Parameters ===
q_table = defaultdict(float)
last_state = None
last_action = None
ALPHA = 0.1
GAMMA = 0.9
EPSILON = 0.1

# === Load machine list ===
def load_machine_data(file_path='machine_list.json'):
    with open(file_path, 'r') as file:
        return json.load(file)

# === Get username and password by IP ===
def get_user_name_by_ip(ip_address):
    machine_data = load_machine_data()
    for machine in machine_data:
        if machine['ip_address'] == ip_address:
            return machine['user_name']
    return None

def get_password_by_ip(ip_address):
    machine_data = load_machine_data()
    for machine in machine_data:
        if machine['ip_address'] == ip_address:
            return machine['Password']
    return None

# === Container count per VM ===
def get_container_count(prometheus_url):
    file_name = 'machine_list.json'
    with open(file_name, 'r') as file:
        vm_list = json.load(file)
    query = 'container_last_seen{name=~"agent1.*"} > time() - 10'
    query_url = f'{prometheus_url}/api/v1/query'

    try:
        response = requests.get(query_url, params={'query': query})
        response.raise_for_status()
        data = response.json().get('data', {}).get('result', [])
    except Exception as e:
        print(f"Error querying Prometheus: {e}")
        return [0] * len(vm_list)

    container_counts = {vm["ip_address"]: 0 for vm in vm_list}
    for metric in data:
        labels = metric.get("metric", {})
        raw_ip = labels.get("instance", "")
        ip = raw_ip.split(":")[0] if raw_ip else None
        if ip in container_counts:
            container_counts[ip] += 1

    return [container_counts[vm["ip_address"]] for vm in vm_list]

# === Initialize energy state at launch ===
def initialize_energy_state(prometheus_url, vm_ips):
    try:
        res = requests.get(f"{prometheus_url}/api/v1/query", params={"query": "scaph_host_energy_microjoules"})
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
                energy_state[ip] = {"energy": energy_uj, "time": now}
                break
        else:
            energy_state[ip] = {"energy": 0.0, "time": now}

    print("Initialized energy state:", energy_state)
    return energy_state

# === Compute power since last measurement ===
def get_last_consumed_energy(target_ip):
    global energy_state

    try:
        res = requests.get(f"{prometheus_url}/api/v1/query", params={"query": "scaph_host_energy_microjoules"})
        res.raise_for_status()
        results = res.json()["data"]["result"]
    except Exception as e:
        print(f"Error querying Prometheus: {e}")
        return None, energy_state[target_ip]["energy"], energy_state[target_ip]["time"]

    current_energy = None
    for metric in results:
        instance = metric["metric"].get("instance", "")
        ip_only = instance.split(":")[0]
        if ip_only == target_ip:
            current_energy = float(metric["value"][1])
            break

    if current_energy is None:
        print(f"No energy data found for {target_ip}")
        return None, energy_state[target_ip]["energy"], energy_state[target_ip]["time"]

    current_time = time.time()
    last_energy = energy_state[target_ip]["energy"]
    last_time = energy_state[target_ip]["time"]

    delta_energy_joules = (current_energy - last_energy) / 1_000_000
    delta_time_seconds = current_time - last_time
    power_watts = delta_energy_joules / delta_time_seconds if delta_time_seconds > 0 else 0.0

    energy_state[target_ip]["energy"] = current_energy
    energy_state[target_ip]["time"] = current_time

    return power_watts, current_energy, current_time

# === Q-learning helpers ===
def build_state(container_counts):
    return tuple(container_counts)

def select_action(state, vm_count):
    if random.random() < EPSILON:
        return random.randint(0, vm_count - 1)
    return max(range(vm_count), key=lambda a: q_table.get((state, a), 0))

def update_q_table(state, action, reward, next_state, vm_count):
    old_q = q_table.get((state, action), 0)
    future_q = max([q_table.get((next_state, a), 0) for a in range(vm_count)])
    q_table[(state, action)] = old_q + ALPHA * (reward + GAMMA * future_q - old_q)

# === Flask Routes ===
@app.route('/selected_vm_to_scale_up', methods=['GET'])
def selected_vm_to_scale_up():
    global last_state, last_action

    container_counts = get_container_count(prometheus_url)
    state = build_state(container_counts)
    action = select_action(state, len(container_counts))
    target_ip = vm_ips[action]

    power_watts, current_energy, current_time = get_last_consumed_energy(target_ip)
    reward = -power_watts

    container_counts[action] += 1
    next_state = build_state(container_counts)

    if last_state is not None and last_action is not None:
        update_q_table(last_state, last_action, reward, next_state, len(container_counts))

    last_state = state
    last_action = action

    return jsonify({
        "selected_vm_index": action,
        "selected_vm_ip": target_ip,
        "reward_power_watts": power_watts
    })

@app.route('/get_vm_to_scale_down', methods=['GET'])
def get_vm_to_scale_down():
    return jsonify({"message": "Scaling down logic not implemented yet."})

@app.route('/user_credentials', methods=['GET'])
def user_credentials():
    destination_node = request.args.get('destination_node')
    user_name = get_user_name_by_ip(destination_node)
    password = get_password_by_ip(destination_node)
    return jsonify({'username': user_name, 'password': password})

if __name__ == '__main__':
    vm_ips = ['10.18.6.11']
    prometheus_url = 'http://10.18.6.11:9090'
    energy_state = initialize_energy_state(prometheus_url, vm_ips)
    app.run(host='0.0.0.0', port=5050)















from flask import Flask, jsonify, request
from collections import defaultdict
import random
import requests
import json
import time
import subprocess

app = Flask(__name__)

# Q-learning parameters
q_table = defaultdict(float)
ALPHA = 0.1
GAMMA = 0.9
EPSILON = 0.1

# Prometheus setup
prometheus_url = 'http://10.18.6.11:9090'
host_ips = ["10.18.6.11", "10.18.6.12"]
vm_ips = []

# Agent memory
last_state = None
last_action = None
last_energy = None
last_time = None

def get_vm_ips():
    with open('machine_list.json') as f:
        data = json.load(f)
    return [vm['ip'].split(":")[0] for vm in data]

def get_user_name_by_ip(ip):
    with open('machine_list.json') as f:
        data = json.load(f)
    for vm in data:
        if vm['ip'].startswith(ip):
            return vm['username']
    return None

def get_password_by_ip(ip):
    with open('machine_list.json') as f:
        data = json.load(f)
    for vm in data:
        if vm['ip'].startswith(ip):
            return vm['password']
    return None

def get_container_count(prometheus_url):
    query = 'count(container_last_seen{{instance=~".*"}}) by (instance)'
    response = requests.get(f'{prometheus_url}/api/v1/query', params={'query': query})
    result = response.json().get('data', {}).get('result', [])
    counts = {r['metric']['instance'].split(':')[0]: int(r['value'][1]) for r in result}
    return [counts.get(ip, 0) for ip in vm_ips]

def get_average_total_energy_microjoules(ips):
    total_energy = 0
    count = 0
    for ip in ips:
        query = f'sum(scaph_host_energy_microjoules{{instance="{ip}:9100"}})'
        response = requests.get(f'{prometheus_url}/api/v1/query', params={'query': query})
        try:
            value = float(response.json()['data']['result'][0]['value'][1])
            total_energy += value
            count += 1
        except:
            continue
    return total_energy if count > 0 else None

def update_q_table(state, action, reward, next_state, vm_count):
    current_q = q_table[(state, action)]
    max_next_q = max(q_table.get((next_state, a), 0.0) for a in range(vm_count))
    new_q = current_q + ALPHA * (reward + GAMMA * max_next_q - current_q)
    q_table[(state, action)] = new_q

def select_action(state, vm_count):
    if random.random() < EPSILON:
        return random.randint(0, vm_count - 1)
    q_values = [q_table[(state, a)] for a in range(vm_count)]
    return q_values.index(max(q_values))

def finalize_last_action_reward(current_state):
    global last_state, last_action, last_energy, last_time, q_table
    if last_state is None or last_action is None or last_energy is None or last_time is None:
        return
    current_energy = get_average_total_energy_microjoules(host_ips)
    current_time = time.time()
    delta_energy = current_energy - last_energy
    delta_time = current_time - last_time
    if delta_time > 0:
        power_watts = delta_energy / (delta_time * 1_000_000)
        reward = -power_watts
    else:
        reward = 0.0
    update_q_table(last_state, last_action, reward, current_state, len(vm_ips))
    last_state = None
    last_action = None
    last_energy = None
    last_time = None

@app.route('/selected_vm_to_scale_up', methods=['GET'])
def selected_vm_to_scale_up():
    global last_state, last_action, last_energy, last_time
    container_counts = get_container_count(prometheus_url)
    current_state = tuple(container_counts)
    finalize_last_action_reward(current_state)
    action = select_action(current_state, len(container_counts))
    selected_vm_ip = vm_ips[action]
    username = get_user_name_by_ip(selected_vm_ip)
    password = get_password_by_ip(selected_vm_ip)
    command = f'sshpass -p {password} ssh -o StrictHostKeyChecking=no {username}@{selected_vm_ip} "docker run -d your_image"'
    subprocess.run(command, shell=True)
    last_state = current_state
    last_action = action
    last_energy = get_average_total_energy_microjoules(host_ips)
    last_time = time.time()
    return jsonify({
        "selected_vm_index": action,
        "selected_vm_ip": selected_vm_ip
    })

@app.route('/get_vm_to_scale_down', methods=['GET'])
def get_vm_to_scale_down():
    container_counts = get_container_count(prometheus_url)
    current_state = tuple(container_counts)
    finalize_last_action_reward(current_state)
    if all(c == 0 for c in container_counts):
        return jsonify({"status": "No containers to scale down."})
    action = container_counts.index(max(container_counts))
    selected_vm_ip = vm_ips[action]
    username = get_user_name_by_ip(selected_vm_ip)
    password = get_password_by_ip(selected_vm_ip)
    command = f'sshpass -p {password} ssh -o StrictHostKeyChecking=no {username}@{selected_vm_ip} "docker rm -f $(docker ps -q --filter name=agent1 | head -n 1)"'
    subprocess.run(command, shell=True)
    return jsonify({
        "scaled_down_vm_index": action,
        "scaled_down_vm_ip": selected_vm_ip,
        "status": "One container stopped from the most saturated VM."
    })

if __name__ == '__main__':
    vm_ips = get_vm_ips()
    app.run(host='0.0.0.0', port=5050)


