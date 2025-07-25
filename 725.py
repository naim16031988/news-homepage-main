from flask import Flask, request, jsonify
import json
import requests
import time
import random
from collections import defaultdict

app = Flask(__name__)

# === Configuration ===
prometheus_url = 'http://10.18.6.11:9090'
host_ips = ["10.18.6.11", "10.18.6.12"]  # Physical machines for energy tracking

# === Q-learning Parameters ===
q_table = defaultdict(float)
last_state = None
last_action = None
ALPHA = 0.1
GAMMA = 0.9
EPSILON = 0.1

# === VM & Host State ===
vm_ips = []
host_energy_state = {}

# === Load VM definitions ===
def load_machine_data(file_path='machine_list.json'):
    with open(file_path, 'r') as file:
        return json.load(file)

def get_vm_ips():
    data = load_machine_data()
    return [entry['ip_address'] for entry in data]

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

# === Prometheus Container Count ===
def get_container_count(prometheus_url):
    vm_list = load_machine_data()
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

# === Initialize energy state ===
def initialize_energy_state(prometheus_url, ips):
    try:
        res = requests.get(f"{prometheus_url}/api/v1/query", params={"query": "scaph_host_energy_microjoules"})
        res.raise_for_status()
        results = res.json()["data"]["result"]
    except Exception as e:
        print(f"Failed to query Prometheus: {e}")
        return {}

    energy_state = {}
    now = time.time()
    for ip in ips:
        for metric in results:
            instance = metric["metric"].get("instance", "")
            ip_only = instance.split(":")[0]
            if ip_only == ip:
                energy_uj = float(metric["value"][1])
                energy_state[ip] = {"energy": energy_uj, "time": now}
                break
        else:
            energy_state[ip] = {"energy": 0.0, "time": now}
    return energy_state

# === Energy delta per host ===
def get_last_consumed_energy(ip):
    try:
        res = requests.get(f"{prometheus_url}/api/v1/query", params={"query": "scaph_host_energy_microjoules"})
        res.raise_for_status()
        results = res.json()["data"]["result"]
    except Exception as e:
        print(f"Error querying Prometheus: {e}")
        return None, host_energy_state[ip]["energy"], host_energy_state[ip]["time"]

    current_energy = None
    for metric in results:
        instance = metric["metric"].get("instance", "")
        ip_only = instance.split(":")[0]
        if ip_only == ip:
            current_energy = float(metric["value"][1])
            break

    if current_energy is None:
        return None, host_energy_state[ip]["energy"], host_energy_state[ip]["time"]

    current_time = time.time()
    last_energy = host_energy_state[ip]["energy"]
    last_time = host_energy_state[ip]["time"]

    delta_joules = (current_energy - last_energy) / 1_000_000
    delta_seconds = current_time - last_time
    power_watts = delta_joules / delta_seconds if delta_seconds > 0 else 0.0

    return power_watts, current_energy, current_time

# === Mean power from all hosts ===
def get_average_power_from_hosts():
    total_power = 0
    count = 0
    global host_energy_state

    for ip in host_ips:
        last_energy = host_energy_state[ip]["energy"]
        last_time = host_energy_state[ip]["time"]
        power, current_energy, current_time = get_last_consumed_energy(ip)

        if power is not None:
            total_power += power
            count += 1
            host_energy_state[ip]["energy"] = current_energy
            host_energy_state[ip]["time"] = current_time

    return total_power / count if count > 0 else None

# === Q-learning core ===
def build_state(container_counts):
    return tuple(container_counts)

def select_action(state, vm_count):
    if random.random() < EPSILON:
        return random.randint(0, vm_count - 1)
    return max(range(vm_count), key=lambda a: q_table.get((state, a), 0))

def update_q_table(state, action, reward, next_state, vm_count):
    old_q = q_table.get((state, action), 0)
    max_future_q = max([q_table.get((next_state, a), 0) for a in range(vm_count)])
    q_table[(state, action)] = old_q + ALPHA * (reward + GAMMA * max_future_q - old_q)

# === Flask API Routes ===
@app.route('/selected_vm_to_scale_up', methods=['GET'])
def selected_vm_to_scale_up():
    global last_state, last_action

    container_counts = get_container_count(prometheus_url)
    state = build_state(container_counts)
    action = select_action(state, len(container_counts))
    selected_vm_ip = vm_ips[action]

    power_watts = get_average_power_from_hosts()
    reward = -power_watts if power_watts is not None else 0

    container_counts[action] += 1
    next_state = build_state(container_counts)

    if last_state is not None and last_action is not None:
        update_q_table(last_state, last_action, reward, next_state, len(container_counts))

    last_state = state
    last_action = action

    return jsonify({
        "selected_vm_index": action,
        "selected_vm_ip": selected_vm_ip,
        "reward_power_watts": power_watts
    })

@app.route('/user_credentials', methods=['GET'])
def user_credentials():
    destination_node = request.args.get('destination_node')
    user_name = get_user_name_by_ip(destination_node)
    password = get_password_by_ip(destination_node)
    return jsonify({'username': user_name, 'password': password})

@app.route('/get_vm_to_scale_down', methods=['GET'])
def get_vm_to_scale_down():
    return jsonify({"message": "Scaling down logic not implemented yet."})

# === Run the app ===
if __name__ == '__main__':
    vm_ips = get_vm_ips()
    host_energy_state = initialize_energy_state(prometheus_url, host_ips)
    app.run(host='0.0.0.0', port=5050)
