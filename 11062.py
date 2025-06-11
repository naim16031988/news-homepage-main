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
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry, push_to_gateway

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
<head><title>RL Agent</title></head>
<body>
  <h1>New-agent</h1>
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

def track_emissions_realtime(work_fn):
    registry = CollectorRegistry()
    container_name = os.environ.get("CONTAINER_NAME", socket.gethostname())
    pushgateway_url = os.environ.get("PUSHGATEWAY_URL", "http://pushgateway:9091")
    job_name = os.environ.get("PUSH_JOB_NAME", "codecarbon_agent")

    cpu_power_gauge = Gauge('codecarbon_cpu_power', 'Estimated CPU power in watts', ['container'], registry=registry)
    ram_power_gauge = Gauge('codecarbon_ram_power', 'Estimated RAM power in watts', ['container'], registry=registry)
    total_energy_gauge = Gauge('codecarbon_total_energy', 'Total energy consumed (kWh)', ['container'], registry=registry)

    tracker = EmissionsTracker(measure_power_secs=1, log_level="error")
    tracker.start()

    def push_metrics():
        while not stop_event.is_set():
            time.sleep(5)
            emissions = tracker._measure.power
            cpu = emissions.cpu_power if emissions and emissions.cpu_power is not None else 0.0
            ram = emissions.ram_power if emissions and emissions.ram_power is not None else 0.0
            total = tracker._total_energy.kwh if tracker._total_energy else 0.0

            cpu_power_gauge.labels(container=container_name).set(cpu)
            ram_power_gauge.labels(container=container_name).set(ram)
            total_energy_gauge.labels(container=container_name).set(total)
            try:
                push_to_gateway(pushgateway_url, job=job_name, registry=registry)
            except Exception as e:
                print(f"[PushGateway Error] {e}")

    stop_event = threading.Event()
    push_thread = threading.Thread(target=push_metrics)
    push_thread.start()

    work_fn()

    stop_event.set()
    push_thread.join()
    tracker.stop()

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

    track_emissions_realtime(work)
    output = f"✅ Training complete for 5 episodes. Pushed metrics every 5 seconds to Pushgateway."
    return render_template_string(HTML_TEMPLATE, output=output)

@app.route("/test", methods=["POST"])
def test():
    steps = 0

    def work():
        nonlocal steps
        state = 0
        while state != N_STATES - 1:
            action = np.argmax(Q[state])
            state, _ = get_feedback(state, action)
            steps += 1

    track_emissions_realtime(work)
    output = f"Test episode:\nReached goal in {steps} steps using learned policy.\nPushed metrics every 5 seconds to Pushgateway."
    return render_template_string(HTML_TEMPLATE, output=output)

# Prometheus scrape endpoint
@app.route("/metrics", methods=["GET"])
def metrics():
    try:
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
    except Exception as e:
        return Response(f"# ERROR: {str(e)}", mimetype="text/plain")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
