"""
Post-recording vehicle counting + delay/LOS computation.

Runs once per finished 1-hour recording (called automatically by
obs_scheduler.py, or run manually for testing). Reads the saved video
file, counts vehicles crossing a defined line, computes basic traffic
performance indicators, and writes the results to SQL Server.

The counting logic here is a lightweight OpenCV baseline so the pipeline
is testable end-to-end without Camlytics. If Camlytics is your primary
detector in the final build, swap count_vehicles() for a function that
parses Camlytics' exported CSV instead — everything downstream
(indicators + database write) stays the same.

Usage:
    python process_video.py --video path/to/file.mp4 \
        --intersection SM_SEASIDE_T1 --label 08:00-09:00
"""

import argparse
import datetime as dt

import cv2
import pyodbc

# ---- CONFIG -------------------------------------------------------------
DB_CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=your_server_name;"
    "DATABASE=TrafficDB;"
    "UID=your_username;"
    "PWD=your_password;"
)

# y-coordinate (in pixels) of the counting line — tune to your camera angle
COUNT_LINE_Y = 300
MIN_CONTOUR_AREA = 900

# Rough capacity assumption for one T-intersection approach; replace with
# your thesis's actual capacity value per lane/approach
CAPACITY_VEH_PER_HR = 1800
# -------------------------------------------------------------------------


def count_vehicles(video_path):
    """Simple background-subtraction line-crossing counter."""
    cap = cv2.VideoCapture(video_path)
    bg_subtractor = cv2.createBackgroundSubtractorMOG2(detectShadows=True)

    counted_vehicles = 0
    recent_crossings = []  # remembers recent y-crossings to avoid double counts
    frame_count = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_count += 1

        fg_mask = bg_subtractor.apply(frame)
        _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for c in contours:
            if cv2.contourArea(c) < MIN_CONTOUR_AREA:
                continue
            x, y, w, h = cv2.boundingRect(c)
            cy = y + h // 2

            crossed_recently = any(abs(cy - prev) < 15 for prev in recent_crossings)
            if not crossed_recently and (COUNT_LINE_Y - 10 <= cy <= COUNT_LINE_Y + 10):
                counted_vehicles += 1
                recent_crossings.append(cy)

        recent_crossings = recent_crossings[-50:]  # cap memory use

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    duration_sec = frame_count / fps
    cap.release()

    return counted_vehicles, duration_sec


def compute_indicators(vehicle_count, duration_sec, capacity_veh_per_hr=CAPACITY_VEH_PER_HR):
    """Basic V/C ratio and LOS classification.
    Replace the LOS thresholds with the ones from your thresholds table."""
    hourly_volume = vehicle_count * (3600 / duration_sec) if duration_sec else 0
    vc_ratio = hourly_volume / capacity_veh_per_hr if capacity_veh_per_hr else 0

    if vc_ratio < 0.6:
        los = "A"
    elif vc_ratio < 0.7:
        los = "B"
    elif vc_ratio < 0.8:
        los = "C"
    elif vc_ratio < 0.9:
        los = "D"
    elif vc_ratio < 1.0:
        los = "E"
    else:
        los = "F"

    return hourly_volume, vc_ratio, los


def save_to_db(intersection_id, label, vehicle_count, hourly_volume, vc_ratio, los):
    conn = pyodbc.connect(DB_CONN_STR)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO TrafficMetrics
            (intersection_id, observation_label, recorded_at,
             vehicle_count, hourly_volume, vc_ratio, los)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        intersection_id, label, dt.datetime.now(),
        vehicle_count, hourly_volume, vc_ratio, los,
    )
    conn.commit()
    cursor.close()
    conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, help="Path to the finished recording")
    parser.add_argument("--intersection", required=True, help="Intersection identifier")
    parser.add_argument("--label", required=True, help="Observation window label, e.g. 08:00-09:00")
    args = parser.parse_args()

    vehicle_count, duration_sec = count_vehicles(args.video)
    hourly_volume, vc_ratio, los = compute_indicators(vehicle_count, duration_sec)

    print(f"Vehicles counted: {vehicle_count}")
    print(f"Duration (s): {duration_sec:.1f}")
    print(f"Hourly volume: {hourly_volume:.0f}")
    print(f"V/C ratio: {vc_ratio:.2f}  LOS: {los}")

    save_to_db(args.intersection, args.label, vehicle_count, hourly_volume, vc_ratio, los)
    print("Saved to database.")


if __name__ == "__main__":
    main()
