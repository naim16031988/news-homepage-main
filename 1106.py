from flask import Flask, render_template_string
import numpy as np

app = Flask(__name__)

GRID_ROWS = 4
GRID_COLS = 4
N_STATES = GRID_ROWS * GRID_COLS
ACTIONS = ['up', 'down', 'left', 'right']

# Dummy Q-table: filled with random values or pre-trained ones
# Shape = (N_STATES, len(ACTIONS))
Q = np.random.rand(N_STATES, len(ACTIONS))

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head><title>Shortest Path Agent</title></head>
<body>
  <h1>RL Agent - Shortest Path</h1>
  <form action="/run" method="post">
    <button type="submit">Find Shortest Path (0,0 to 3,3)</button>
  </form>
  <pre>{{ output }}</pre>
</body>
</html>
'''

def state_to_coords(state):
    return divmod(state, GRID_COLS)

def coords_to_state(row, col):
    return row * GRID_COLS + col

def get_next_state(state, action):
    row, col = state_to_coords(state)
    if action == 'up' and row > 0:
        row -= 1
    elif action == 'down' and row < GRID_ROWS - 1:
        row += 1
    elif action == 'left' and col > 0:
        col -= 1
    elif action == 'right' and col < GRID_COLS - 1:
        col += 1
    return coords_to_state(row, col)

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_TEMPLATE, output="")

@app.route("/run", methods=["POST"])
def run():
    start = coords_to_state(0, 0)
    goal = coords_to_state(3, 3)

    path = [start]
    state = start
    steps = 0
    max_steps = 50

    while state != goal and steps < max_steps:
        action_index = np.argmax(Q[state])
        action = ACTIONS[action_index]
        next_state = get_next_state(state, action)
        if next_state == state:  # stuck
            break
        path.append(next_state)
        state = next_state
        steps += 1

    if state == goal:
        output = "✅ Reached goal!\n"
    else:
        output = "⚠️ Failed to reach goal.\n"

    output += f"Path taken ({steps} steps):\n"
    for s in path:
        r, c = state_to_coords(s)
        output += f"→ ({r}, {c})\n"

    return render_template_string(HTML_TEMPLATE, output=output)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
