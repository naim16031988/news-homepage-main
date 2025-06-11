from flask import Flask, render_template_string, Response
from codecarbon import EmissionsTracker
import numpy as np
import random
import logging
import io
import os
import socket
import pandas as pd
import threading
import time
from datetime import datetime
from prometheus_client import Gauge, CollectorRegistry, push_to_gateway

app = Flask(__name__)

# Q-learning setup
N_STATES = 5
ACTIONS = ['left', 'right']
EPSILON = 0.1
ALPHA = 0.1
GAMMA = 0.9
Q = np.zeros((N_STATES, len(ACTIONS)))

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head><title>RL_Agent</title></head>
<body>
  <h1>RL Agent Energy Tracker</h1>
  <form action="/train" method="post">
    <button type="submit">Train Agent</button>
  </form>
  <form action="/test" method="post">
    <button type="submit">Test Agent</button>
  </form>
  <pre style="white-space: pre-wrap;">{{ output }}</pre>
</body>
</html>
'''

def choose_action(state):
    return random.choice([0, 1]) if random.random() < EPSILON else np.argmax(Q[state])

def get_feedback(state, action):
    if ACTIONS[action] == 'right':
        if state == N_STATES - 2:
            return state + 1, 10
        elif state < N_STATES - 1:
            return state + 1, 0
    elif ACTIONS[action] == 'left' and state > 0:
        return state - 1, 0
    return state, 0

def extract_metrics_from_log(log_text):
    metrics = {'cpu_power': 0.0, 'ram_power': 0.0, 'energy_consumed': 0.0}
    for line in log_text.splitlines():
        if "RAM Power" in line:
            metrics['ram_power'] = float(line.split("RAM Power : ")[1].split(" ")[0])
        elif "power :" in line and "Delta energy consumed" in line:
            metrics['cpu_power'] = float(line.split("power : ")[1].split(" ")[0])
        elif "of electricity used" in line:
            metrics['energy_consumed'] = float(line.split()[0])
    return metrics

def push_metrics_to_gateway(metrics):
    registry = CollectorRegistry()
    container = os.environ.get("CONTAINER_NAME", socket.gethostname())
    job_name = os.environ.get("PUSH_JOB_NAME", "codecarbon_agent")
    gateway = os.environ.get("PUSHGATEWAY_URL", "http://pushgateway:9091")

    Gauge('codecarbon_cpu_power', 'CPU Power (W)', ['container'], registry=registry).labels(container).set(metrics['cpu_power'])
    Gauge('codecarbon_ram_power', 'RAM Power (W)', ['container'], registry=registry).labels(container).set(metrics['ram_power'])
    Gauge('codecarbon_total_energy', 'Energy Consumed (kWh)', ['container'], registry=registry).labels(container).set(metrics['energy_consumed'])

    try:
        push_to_gateway(gateway, job=job_name, registry=registry)
    except Exception as e:
        print(f"[PushGateway Error] {e}")

def track_emissions(work_fn):
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter('[codecarbon %(levelname)s @ %(asctime)s] %(message)s'))

    logger = logging.getLogger("codecarbon")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    tracker = EmissionsTracker(output_file=None, log_level="info", measure_power_secs=1)
    tracker.start()
    work_fn()
    tracker.stop()

    logger.removeHandler(handler)
    return log_stream.getvalue()

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_TEMPLATE, output="")

@app.route("/train", methods=["POST"])
def train():
    def work():
        for _ in range(5):
            state = 0
            while state != N_STATES - 1:
                action = choose_action(state)
                next_state, reward = get_feedback(state, action)
                Q[state, action] += ALPHA * (reward + GAMMA * np.max(Q[next_state]) - Q[state, action])
                state = next_state

    logs = track_emissions(work)
    metrics = extract_metrics_from_log(logs)
    push_metrics_to_gateway(metrics)

    output = f"✅ Training complete.\n🔌 Energy: {metrics['energy_consumed']*1000:.6f} Wh\n\n" + logs
    return render_template_string(HTML_TEMPLATE, output=output)

@app.route("/test", methods=["POST"])
def test():
    def work():
        nonlocal steps
        state = 0
        while state != N_STATES - 1:
            action = np.argmax(Q[state])
            state, _ = get_feedback(state, action)
            steps += 1

    steps = 0
    logs = track_emissions(work)
    metrics = extract_metrics_from_log(logs)
    push_metrics_to_gateway(metrics)

    output = f"🚀 Test complete: {steps} steps\n🔌 Energy: {metrics['energy_consumed']*1000:.6f} Wh\n\n" + logs
    return render_template_string(HTML_TEMPLATE, output=output)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
