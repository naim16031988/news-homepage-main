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
from prometheus_client import Gauge, CollectorRegistry, push_to_gateway, generate_latest, CONTENT_TYPE_LATEST

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
  <h1>RL Agent</h1>
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

container_name = os.environ.get("CONTAINER_NAME", socket.gethostname())
pushgateway_url = os.environ.get("PUSHGATEWAY_URL", "http://pushgateway:9091")
job_name = os.environ.get("PUSH_JOB_NAME", "codecarbon_agent")

def push_metrics(cpu, ram, energy):
    registry = CollectorRegistry()
    Gauge('codecarbon_cpu_power', 'CPU power (W)', ['container'], registry=registry).labels(container=container_name).set(cpu)
    Gauge('codecarbon_ram_power', 'RAM power (W)', ['container'], registry=registry).labels(container=container_name).set(ram)
    Gauge('codecarbon_total_energy', 'Total energy (kWh)', ['container'], registry=registry).labels(container=container_name).set(energy)
    push_to_gateway(pushgateway_url, job=job_name, registry=registry)

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

def track_emissions_live(work_fn):
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter('[codecarbon %(levelname)s @ %(asctime)s] %(message)s'))
    logger = logging.getLogger("codecarbon")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    emissions_log = []

    def callback(emission_data):
        cpu = emission_data.cpu_power or 0.0
        ram = emission_data.ram_power or 0.0
        energy = emission_data.energy_consumed or 0.0
        push_metrics(cpu, ram, energy)

    tracker = EmissionsTracker(
        output_file=None,
        measure_power_secs=1,
        logging_callback=callback,
        log_level="info"
    )
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
        for episode in range(5):
            state = 0
            while state != N_STATES - 1:
                action = choose_action(state)
                next_state, reward = get_feedback(state, action)
                Q[state, action] += ALPHA * (reward + GAMMA * np.max(Q[next_state]) - Q[state, action])
                state = next_state

    logs = track_emissions_live(work)
    output = f"✅ Training complete.\n\n" + logs
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
    logs = track_emissions_live(work)
    output = f"✅ Test complete in {steps} steps.\n\n" + logs
    return render_template_string(HTML_TEMPLATE, output=output)

@app.route("/metrics", methods=["GET"])
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
