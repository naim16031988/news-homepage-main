import time
import subprocess
import requests

PROMETHEUS = "http://<prometheus-ip>:9090/api/v1/query"
CONTAINER_IMAGE = "agent1"
SSH_USER = "user"
VM_IPS = ["vm1", "vm2"]

def get_container_cpu():
    query = 'sum(rate(container_cpu_usage_seconds_total{image="agent1"}[1m]))'
    r = requests.get(PROMETHEUS, params={"query": query})
    result = r.json()
    try:
        return float(result["data"]["result"][0]["value"][1])
    except:
        return 0.0

def launch_agent_on_vm(vm):
    cmd = f"ssh {SSH_USER}@{vm} 'docker run -d --network agent-net --label traefik.enable=true --label traefik.http.routers.agent1.rule=PathPrefix(`/agent1`) --label traefik.http.services.agent1.loadbalancer.server.port=5000 {CONTAINER_IMAGE}'"
    subprocess.call(cmd, shell=True)

def autoscale_loop():
    while True:
        cpu = get_container_cpu()
        print("Current CPU:", cpu)
        if cpu > 0.8:  # 80%
            print("Scaling up!")
            launch_agent_on_vm(VM_IPS[1])
        time.sleep(30)

autoscale_loop()
