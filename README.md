To install and configure Scaphandre on a virtual machine (VM) to receive energy metrics from a QEMU/KVM hypervisor, follow these detailed steps:

⸻

🧰 Prerequisites
	•	Hypervisor: A host machine running QEMU/KVM with libvirt.
	•	Guest VM: A virtual machine managed by the hypervisor.
	•	Scaphandre: Installed on both the hypervisor and the guest VM.
	•	Filesystem Sharing: virtiofs support enabled for sharing filesystems between host and guest.

⸻

🖥️ On the Hypervisor (Host Machine)

1. Install Scaphandre

Download and install the latest Scaphandre binary:

wget https://github.com/hubblo-org/scaphandre/releases/latest/download/scaphandre-linux-x86_64
chmod +x scaphandre-linux-x86_64
sudo mv scaphandre-linux-x86_64 /usr/local/bin/scaphandre

2. Run Scaphandre with the QEMU Exporter

Start Scaphandre to compute per-VM energy metrics:

sudo scaphandre qemu

This will generate energy metrics for each VM in /var/lib/libvirt/scaphandre/DOMAIN_NAME, where DOMAIN_NAME is the name of your VM.

3. Create a tmpfs Mount Point for the VM

For each VM, create a temporary filesystem to store its metrics:

sudo mkdir -p /var/lib/libvirt/scaphandre/DOMAIN_NAME
sudo mount -t tmpfs tmpfs_DOMAIN_NAME /var/lib/libvirt/scaphandre/DOMAIN_NAME -o size=5m

Replace DOMAIN_NAME with your VM’s actual name.

4. Configure the VM to Access the Metrics

Edit the VM’s libvirt XML configuration:

sudo virsh edit DOMAIN_NAME

Within the <devices> section, add:

<filesystem type='mount' accessmode='passthrough'>
    <driver type='virtiofs'/>
    <source dir='/var/lib/libvirt/scaphandre/DOMAIN_NAME'/>
    <target dir='scaphandre'/>
    <readonly/>
</filesystem>

If you encounter an error regarding virtiofs requiring shared memory, add the following within the <domain> section:

<memoryBacking>
  <source type='memfd'/>
  <access mode='shared'/>
</memoryBacking>

Save the configuration and restart the VM:

sudo virsh shutdown DOMAIN_NAME
sudo virsh start DOMAIN_NAME


⸻

🖥️ On the Guest VM

1. Install Scaphandre

Inside the VM, download and install Scaphandre:

wget https://github.com/hubblo-org/scaphandre/releases/latest/download/scaphandre-linux-x86_64
chmod +x scaphandre-linux-x86_64
sudo mv scaphandre-linux-x86_64 /usr/local/bin/scaphandre

2. Mount the Shared Filesystem

Create a mount point and mount the shared directory:

sudo mkdir -p /var/scaphandre
sudo mount -t 9p -o trans=virtio scaphandre /var/scaphandre

3. Run Scaphandre in VM Mode

Start Scaphandre to read the metrics provided by the hypervisor:

scaphandre --vm prometheus

This will expose the energy metrics on port 8080. You can access them via:

http://<VM_IP>:8080/metrics


⸻

🔄 Summary

By following these steps:
	•	The hypervisor computes and shares per-VM energy metrics using Scaphandre.
	•	The guest VM accesses these metrics through a shared filesystem.
	•	Scaphandre on the VM reads and exposes the metrics, enabling monitoring tools like Prometheus to collect them.

This setup allows for accurate energy monitoring within virtualized environments, facilitating energy-aware scheduling and analysis.

⸻

For more detailed information, refer to the official Scaphandre documentation: Propagate power consumption metrics from hypervisor to virtual machines (Qemu/KVM).import psycopg2
from datetime import datetime

# Adjust these as needed
DB_CONFIG = {
    "host": "localhost",      # or IP of PostgreSQL container
    "port": 5432,
    "dbname": "mydb",
    "user": "myuser",
    "password": "mypass"
}

try:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO energy_usage (timestamp, agent_id, task_type, energy_wh, node_name)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        datetime.utcnow(),
        "test_agent",
        "test_task",
        1.23,
        "test_node"
    ))

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Inserted test row successfully.")

except Exception as e:
    print("❌ Failed to insert row:", e)







import socket
import pandas as pd
from datetime import datetime
from codecarbon import EmissionsTracker
import psycopg2

# Config — adjust these
DB_CONFIG = {
    "host": "localhost",       # Use 'localhost' or actual IP
    "port": 5432,
    "dbname": "mydb",
    "user": "myuser",
    "password": "mypass"
}

AGENT_ID = "agent1"
TASK_TYPE = "train"
NODE_NAME = socket.gethostname()

# Start CodeCarbon tracking
tracker = EmissionsTracker(output_file="energy_temp.csv", log_level="error")
tracker.start()

# Your workload (simulate)
for _ in range(10**6): pass  # replace with real task

tracker.stop()

# Read energy from CSV
df = pd.read_csv("energy_temp.csv")
energy_wh = df.tail(1)["energy_consumed"].values[0] * 1000
timestamp = datetime.utcnow()

# Insert into PostgreSQL
try:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO energy_usage (timestamp, agent_id, task_type, energy_wh, node_name) VALUES (%s, %s, %s, %s, %s)",
        (timestamp, AGENT_ID, TASK_TYPE, energy_wh, NODE_NAME)
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Logged {energy_wh:.3f} Wh for {AGENT_ID} on {NODE_NAME}")
except Exception as e:
    print(f"❌ Failed to log to PostgreSQL: {e}")
    
    
    
    
    from flask import Flask, render_template_string
from codecarbon import EmissionsTracker
import numpy as np
import random
import pandas as pd
import psycopg2
from datetime import datetime

app = Flask(__name__)

# DB configuration (adjust to match your PostgreSQL setup)
DB_CONFIG = {
    "dbname": "your_db",
    "user": "your_user",
    "password": "your_pass",
    "host": "localhost",
    "port": 5432,
}

AGENT_ID = "agent1"  # change this for each agent

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
<head><title>RL_Agent_1</title></head>
<body>
  <h1>RL_Agent_1</h1>
  <form action="/train" method="post">
    <button type="submit">Train Agent</button>
  </form>
  <form action="/test" method="post">
    <button type="submit">Test Agent</button>
  </form>
  <pre>{{ output }}</pre>
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

def log_to_postgres(agent_id, task_type, energy_wh):
    timestamp = datetime.utcnow()
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO energy_usage (timestamp, agent_id, task_type, energy_wh) VALUES (%s, %s, %s, %s)",
        (timestamp, agent_id, task_type, energy_wh)
    )
    conn.commit()
    cur.close()
    conn.close()

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_TEMPLATE, output="")

@app.route("/train", methods=["POST"])
def train():
    tracker = EmissionsTracker(output_file="web_emissions.csv", log_level="error")
    tracker.start()

    for episode in range(5):
        state = 0
        while state != N_STATES - 1:
            action = choose_action(state)
            next_state, reward = get_feedback(state, action)
            Q[state, action] += ALPHA * (reward + GAMMA * np.max(Q[next_state]) - Q[state, action])
            state = next_state

    tracker.stop()

    df = pd.read_csv("web_emissions.csv")
    energy_wh = df.tail(1)['energy_consumed'].values[0] * 1000

    log_to_postgres(AGENT_ID, "train", energy_wh)

    output = f"✅ Training complete for 5 episodes.\n🔌 Energy consumed (train): {energy_wh:.8f} Wh"
    return render_template_string(HTML_TEMPLATE, output=output)

@app.route("/test", methods=["POST"])
def test():
    tracker = EmissionsTracker(output_file="web_emissions.csv", log_level="error")
    tracker.start()

    output = "Test episode:\n"
    state = 0
    steps = 0
    while state != N_STATES - 1:
        action = np.argmax(Q[state])
        state, _ = get_feedback(state, action)
        steps += 1

    tracker.stop()

    df = pd.read_csv("web_emissions.csv")
    energy_wh = df.tail(1)['energy_consumed'].values[0] * 1000

    log_to_postgres(AGENT_ID, "test", energy_wh)

    output += f"Reached goal in {steps} steps using learned policy.\n"
    output += f"🔌 Energy consumed (test): {energy_wh:.8f} Wh"
    return render_template_string(HTML_TEMPLATE, output=output)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)



# Frontend Mentor - News homepage https://naim16031988.github.io/news-homepage-main/

![Design preview for the News homepage coding challenge](./design/desktop-preview.jpg)

## Welcome! 👋

Thanks for checking out this front-end coding challenge.

[Frontend Mentor](https://www.frontendmentor.io) challenges help you improve your coding skills by building realistic projects.

**To do this challenge, you need a good understanding of HTML and CSS, and basic JavaScript.**

## The challenge

Your challenge is to build out this news website homepage and get it looking as close to the design as possible.

You can use any tools you like to help you complete the challenge. So if you've got something you'd like to practice, feel free to give it a go.

Your users should be able to:

- View the optimal layout for the interface depending on their device's screen size
- See hover and focus states for all interactive elements on the page

Want some support on the challenge? [Join our Slack community](https://www.frontendmentor.io/slack) and ask questions in the **#help** channel.

## Where to find everything

Your task is to build out the project to the designs inside the `/design` folder. You will find both a mobile and a desktop version of the design. 

The designs are in JPG static format. Using JPGs will mean that you'll need to use your best judgment for styles such as `font-size`, `padding` and `margin`. 

If you would like the design files (we provide Sketch & Figma versions) to inspect the design in more detail, you can [subscribe as a PRO member](https://www.frontendmentor.io/pro).

All the required assets for this project are in the `/assets` folder. The images are already exported for the correct screen size and optimized.

We also include variable and static font files for the required fonts for this project. You can choose to either link to Google Fonts or use the local font files to host the fonts yourself. Note that we've removed the static font files for the font weights that aren't needed for this project.

There is also a `style-guide.md` file containing the information you'll need, such as color palette and fonts.

## Building your project

Feel free to use any workflow that you feel comfortable with. Below is a suggested process, but do not feel like you need to follow these steps:

1. Initialize your project as a public repository on [GitHub](https://github.com/). Creating a repo will make it easier to share your code with the community if you need help. If you're not sure how to do this, [have a read-through of this Try Git resource](https://try.github.io/).
2. Configure your repository to publish your code to a web address. This will also be useful if you need some help during a challenge as you can share the URL for your project with your repo URL. There are a number of ways to do this, and we provide some recommendations below.
3. Look through the designs to start planning out how you'll tackle the project. This step is crucial to help you think ahead for CSS classes to create reusable styles.
4. Before adding any styles, structure your content with HTML. Writing your HTML first can help focus your attention on creating well-structured content.
5. Write out the base styles for your project, including general content styles, such as `font-family` and `font-size`.
6. Start adding styles to the top of the page and work down. Only move on to the next section once you're happy you've completed the area you're working on.

## Deploying your project

As mentioned above, there are many ways to host your project for free. Our recommend hosts are:

- [GitHub Pages](https://pages.github.com/)
- [Vercel](https://vercel.com/)
- [Netlify](https://www.netlify.com/)

You can host your site using one of these solutions or any of our other trusted providers. [Read more about our recommended and trusted hosts](https://medium.com/frontend-mentor/frontend-mentor-trusted-hosting-providers-bf000dfebe).

## Create a custom `README.md`

We strongly recommend overwriting this `README.md` with a custom one. We've provided a template inside the [`README-template.md`](./README-template.md) file in this starter code.

The template provides a guide for what to add. A custom `README` will help you explain your project and reflect on your learnings. Please feel free to edit our template as much as you like.

Once you've added your information to the template, delete this file and rename the `README-template.md` file to `README.md`. That will make it show up as your repository's README file.

## Submitting your solution

Submit your solution on the platform for the rest of the community to see. Follow our ["Complete guide to submitting solutions"](https://medium.com/frontend-mentor/a-complete-guide-to-submitting-solutions-on-frontend-mentor-ac6384162248) for tips on how to do this.

Remember, if you're looking for feedback on your solution, be sure to ask questions when submitting it. The more specific and detailed you are with your questions, the higher the chance you'll get valuable feedback from the community.

## Sharing your solution

There are multiple places you can share your solution:

1. Share your solution page in the **#finished-projects** channel of the [Slack community](https://www.frontendmentor.io/slack). 
2. Tweet [@frontendmentor](https://twitter.com/frontendmentor) and mention **@frontendmentor**, including the repo and live URLs in the tweet. We'd love to take a look at what you've built and help share it around.
3. Share your solution on other social channels like LinkedIn.
4. Blog about your experience building your project. Writing about your workflow, technical choices, and talking through your code is a brilliant way to reinforce what you've learned. Great platforms to write on are [dev.to](https://dev.to/), [Hashnode](https://hashnode.com/), and [CodeNewbie](https://community.codenewbie.org/).

We provide templates to help you share your solution once you've submitted it on the platform. Please do edit them and include specific questions when you're looking for feedback. 

The more specific you are with your questions the more likely it is that another member of the community will give you feedback.

## Got feedback for us?

We love receiving feedback! We're always looking to improve our challenges and our platform. So if you have anything you'd like to mention, please email hi[at]frontendmentor[dot]io.

This challenge is completely free. Please share it with anyone who will find it useful for practice.

**Have fun building!** 🚀
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'cadvisor-machine-a'
    static_configs:
      - targets: ['localhost:8080']

  - job_name: 'cadvisor-machine-b'
    static_configs:
      - targets: ['<Machine-B-IP>:8080']
docker run -d \
  --name=prometheus \
  -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus


To run Prometheus in Docker and track cAdvisor metrics from two different machines, follow these steps on each machine:

⸻

1. Setup cAdvisor on Both Machines

On Machine A and Machine B, run:

docker run -d \
  --name=cadvisor \
  --volume=/:/rootfs:ro \
  --volume=/var/run:/var/run:ro \
  --volume=/sys:/sys:ro \
  --volume=/var/lib/docker/:/var/lib/docker:ro \
  --publish=8080:8080 \
  --detach=true \
  --name=cadvisor \
  gcr.io/cadvisor/cadvisor:latest

Verify access by visiting:
	•	http://<Machine-A-IP>:8080/metrics
	•	http://<Machine-B-IP>:8080/metrics

⸻

2. Configure Prometheus on a Central Machine

Let’s assume Prometheus will run on Machine A.

Create prometheus.yml

Create a file prometheus.yml with the following content:

global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'cadvisor-machine-a'
    static_configs:
      - targets: ['localhost:8080']

  - job_name: 'cadvisor-machine-b'
    static_configs:
      - targets: ['<Machine-B-IP>:8080']

Replace <Machine-B-IP> with the actual IP address of Machine B.

⸻

3. Run Prometheus Docker Container

docker run -d \
  --name=prometheus \
  -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus

Verify Prometheus is running:
	•	Go to http://<Machine-A-IP>:9090
	•	Navigate to “Targets” to check both cAdvisor instances are being scraped.

⸻

Optional: Docker Network & Firewall Notes
	•	Ensure ports 8080 (for cAdvisor) and 9090 (for Prometheus) are open in firewalls/security groups.
	•	If machines are in the same Docker network (e.g., in a swarm), you can use service/container names instead of I
 To include the node (host machine) where each container is running, we can extract the instance label from cAdvisor metrics — this typically represents the IP:port of the cAdvisor exporter running on the node.

Here’s an updated Python script that shows:
	•	Container name
	•	Container ID
	•	Node (IP or hostname where the container is running)

⸻

✅ Updated Python Script

import requests

PROMETHEUS_URL = "http://localhost:9090"  # Change to your Prometheus server address

def query_prometheus(promql):
    url = f"{PROMETHEUS_URL}/api/v1/query"
    response = requests.get(url, params={'query': promql})
    data = response.json()
    if data["status"] != "success":
        raise Exception(f"Query failed: {data}")
    return data["data"]["result"]

def get_containers_info():
    # Use a cAdvisor metric that includes container name, ID, and instance (node)
    results = query_prometheus('container_last_seen')

    containers = []
    for result in results:
        labels = result.get("metric", {})
        name = labels.get("container", "unknown")
        container_id = labels.get("id", "unknown")
        node_instance = labels.get("instance", "unknown")  # This is often IP:port of the node

        # Filter out infrastructure or empty containers
        if name and name not in ["", "/", "POD"]:
            containers.append({
                "name": name,
                "id": container_id,
                "node": node_instance
            })

    return containers

if __name__ == "__main__":
    containers = get_containers_info()
    print("Running containers:")
    for c in containers:
        print(f"Name: {c['name']}, ID: {c['id']}, Node: {c['node']}")


⸻

✅ Example Output

Running containers:
Name: nginx-container, ID: /docker/18b3d2f12345..., Node: 192.168.1.10:8080
Name: redis-db, ID: /docker/ae1298371abc..., Node: 192.168.1.11:8080


⸻

✅ Notes
	•	The instance field (e.g., 192.168.1.10:8080) refers to the cAdvisor instance, which usually runs per host.
	•	You can map this IP to a hostname manually or use an external node label (if available via Prometheus).

⸻

Would you like:
	•	The instance IP resolved to hostnames?
	•	To export the result as JSON, CSV, or into a database?

 import requests

PROMETHEUS_URL = "http://localhost:9090"  # Change to your Prometheus server address

def query_prometheus(promql):
    url = f"{PROMETHEUS_URL}/api/v1/query"
    response = requests.get(url, params={'query': promql})
    data = response.json()
    if data["status"] != "success":
        raise Exception(f"Query failed: {data}")
    return data["data"]["result"]

def get_containers_info():
    # Use a cAdvisor metric that includes container name, ID, and instance (node)
    results = query_prometheus('container_last_seen')

    containers = []
    for result in results:
        labels = result.get("metric", {})
        name = labels.get("container", "unknown")
        container_id = labels.get("id", "unknown")
        node_instance = labels.get("instance", "unknown")  # This is often IP:port of the node

        # Filter out infrastructure or empty containers
        if name and name not in ["", "/", "POD"]:
            containers.append({
                "name": name,
                "id": container_id,
                "node": node_instance
            })

    return 


    

import json
import random

# Example input: replace these with your real data
containers = [
    {"name": "nginx", "image": "nginx:latest"},
    {"name": "redis", "image": "redis:alpine"},
    {"name": "myapp", "image": "myapp:v1"}
]

nodes = ["node1", "node2", "node3"]

# Random mapping
mapped = []
for container in containers:
    assigned_node = random.choice(nodes)
    mapped.append({
        "container_name": container["name"],
        "image": container["image"],
        "assigned_node": assigned_node
    })

# Save to JSON
with open("mapping.json", "w") as f:
    json.dump(mapped, f, indent=4)

print("Mapping saved to mapping.json")

