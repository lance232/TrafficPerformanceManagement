"""
OBS Recording/Streaming Scheduler
----------------------------------
Automatically starts and stops OBS recording + streaming at fixed
peak/off-peak observation windows, then hands the finished recording
off to process_video.py for vehicle counting and metrics.

Requires:
    - OBS Studio 28+ with the built-in obs-websocket server enabled
      (Tools > WebSocket Server Settings > Enable, note the port + password)
    - pip install obsws-python schedule

Run this script and leave it running on the laptop. It just waits and
fires actions at the scheduled times — it does not need network access
in between windows.
"""

import subprocess
import threading
import time
from datetime import datetime

import obsws_python as obs
import schedule

# ---- CONFIG -------------------------------------------------------------
OBS_HOST = "localhost"
OBS_PORT = 4455
OBS_PASSWORD = "your_obs_websocket_password"

# Each tuple = (start_time, stop_time), 24h "HH:MM" format
OBSERVATION_WINDOWS = [
    ("08:00", "09:00"),  # AM peak
    ("10:00", "11:00"),  # AM off-peak
    ("14:00", "15:00"),  # PM off-peak
    ("16:00", "17:00"),  # PM peak
]

PROCESS_SCRIPT = "process_video.py"
INTERSECTION_ID = "SM_SEASIDE_T1"
# -------------------------------------------------------------------------


def get_client():
    return obs.ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD, timeout=5)


def start_block(label):
    try:
        cl = get_client()
        cl.start_record()
        cl.start_stream()
        print(f"[{datetime.now()}] Started recording + streaming for block '{label}'")
    except Exception as e:
        print(f"[{datetime.now()}] ERROR starting block '{label}': {e}")


def stop_block(label):
    try:
        cl = get_client()
        record_status = cl.stop_record()
        cl.stop_stream()
        output_path = getattr(record_status, "output_path", None)
        print(f"[{datetime.now()}] Stopped block '{label}'. File: {output_path}")

        if output_path:
            threading.Thread(
                target=run_processing, args=(output_path, label), daemon=True
            ).start()
        else:
            print(
                f"[{datetime.now()}] WARNING: no output path returned, "
                f"check the OBS recording folder manually for block '{label}'"
            )
    except Exception as e:
        print(f"[{datetime.now()}] ERROR stopping block '{label}': {e}")


def run_processing(video_path, label):
    print(f"[{datetime.now()}] Processing '{video_path}' for block '{label}'...")
    result = subprocess.run(
        [
            "python", PROCESS_SCRIPT,
            "--video", video_path,
            "--intersection", INTERSECTION_ID,
            "--label", label,
        ],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"[{datetime.now()}] Processing finished for '{label}'.")
    else:
        print(f"[{datetime.now()}] Processing FAILED for '{label}':\n{result.stderr}")


def build_schedule():
    for start_t, stop_t in OBSERVATION_WINDOWS:
        label = f"{start_t}-{stop_t}"
        schedule.every().day.at(start_t).do(start_block, label=label)
        schedule.every().day.at(stop_t).do(stop_block, label=label)


if __name__ == "__main__":
    build_schedule()
    print("Scheduler running. Waiting for next observation window...")
    while True:
        schedule.run_pending()
        time.sleep(5)
