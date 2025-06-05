Here is a working example to use CodeCarbon for measuring energy consumption of a Docker container in real time.

⸻

✅ Goal

Use CodeCarbon inside a container to monitor its own power consumption in real-time.

⸻

🧱 Requirements
	•	Docker installed
	•	Python 3 installed (in the image)
	•	CodeCarbon installed inside the container
	•	Internet access (for geolocation, unless you use manual config)

⸻

📦 Step-by-Step Setup

1. Create a Python script to monitor consumption

app.py

from codecarbon import EmissionsTracker
import time

tracker = EmissionsTracker(output_file="emissions.csv", measure_power_secs=1)
tracker.start()

# Simulate a workload
for i in range(60):  # 60 seconds of work
    _ = [x**2 for x in range(100000)]
    time.sleep(1)

tracker.stop()
print("Power measurement complete. Data saved in emissions.csv")


⸻

2. Create a Dockerfile

Dockerfile

FROM python:3.9-slim

# Install required packages
RUN pip install codecarbon

# Copy the app
COPY app.py /app.py

# Set location manually to avoid geolocation errors (Paris in this case)
ENV CODECARBON_COUNTRY=FRA
ENV CODECARBON_REGION=FR-IDF

CMD ["python", "app.py"]


⸻

3. Build and Run the Docker Container

docker build -t codecarbon-test .
docker run --rm -v $(pwd):/code codecarbon-test

-v $(pwd):/code mounts your local directory to access emissions.csv.

⸻

✅ Output

You’ll get an emissions.csv file with real-time energy consumption measurements:

timestamp	duration (s)	energy_consumed (kWh)	cpu_energy (kWh)	…
2025-06-05 10:00:01	1.0	0.000002	0.0000015	…
2025-06-05 10:00:02	1.0	0.000003	0.0000022	…


⸻

🔁 Live Monitoring (Optional)

If you want to display the energy in real time:

Add this inside the loop in app.py:

from codecarbon.core.outputs.csv import CSVOutput
output = CSVOutput(tracker._output_dir)
output._write_row(tracker._emissions_data[-1])


⸻

Would you like:
	•	A version that logs metrics to PostgreSQL or Prometheus?
	•	A real-time web dashboard with Flask + Chart.js?
