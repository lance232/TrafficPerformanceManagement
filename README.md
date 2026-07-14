# Traffic Performance Management System — SM Seaside Merging T-Intersection, Cebu City

Automated traffic monitoring prototype using a solar-powered 4G CCTV camera,
OBS Studio, and MediaMTX to record and live-stream footage, then OpenCV/Camlytics
to compute vehicle counts and Level of Service (LOS) for scheduled peak and
off-peak observation windows.

## How it works

```
V380 Pro camera (4G/solar)
        |
V380 Pro app (Windows, shows live feed)
        |
OBS Studio (Window Capture of the app, records locally AND streams out)
        |                                   |
  Local .mp4 recording              MediaMTX (RTMP in -> HLS out)
        |                                   |
process_video.py                    Website video player (hls.js)
(vehicle count, V/C ratio, LOS)     (live view during observation windows)
        |
   SQL Server database
        |
   Website dashboard (metrics)
```

The camera can't be streamed to directly (it's a consumer P2P camera, not
an open RTSP/RTMP source), so OBS captures the V380 Pro app's window as a
workaround. OBS then does two things at once: saves a full-quality local
recording (used for vehicle counting) and pushes a live stream to MediaMTX,
which converts it into a format (HLS) that a website can actually play.

## What's been built and confirmed working so far

- [x] V380 Pro camera confirmed showing a live feed on a Windows laptop via the V380 Pro app
- [x] OBS Studio capturing that app window (Window Capture source)
- [x] OBS WebSocket server enabled (for scripted automation)
- [x] Manual test recording produced a working .mp4 file
- [x] MediaMTX installed and running, receiving OBS's RTMP stream
- [x] Live stream confirmed playable end-to-end via VLC
- [x] `process_video.py` tested against a real recorded file (counting logic works,
      but calibration of the counting line is still a to-do — see below)
- [ ] `obs_scheduler.py` — writes the automated start/stop schedule, not yet tested live
- [ ] Website video embed (hls.js) — not yet built
- [ ] SQL Server database and connection — not yet set up (placeholder credentials in the script)

## Setup instructions

### 1. Camera and OBS

1. Set up the V380 Pro camera and confirm the live feed shows in the V380 Pro
   Windows app.
2. In OBS, add the V380 Pro app window as a **Window Capture** source (not
   Display Capture), cropped to just the video pane.
3. In OBS: **Tools -> WebSocket Server Settings** -> enable it, set a password,
   note the port (default `4455`). This is required for `obs_scheduler.py` to
   control OBS automatically.
4. Set OBS's recording output path (Settings -> Output -> Recording).

### 2. MediaMTX (turns the OBS stream into something a website can play)

1. Download the **Windows release** (not the source-code zip) from
   https://github.com/bluenviron/mediamtx/releases — look for
   `mediamtx_vX.X.X_windows_amd64.zip`.
2. Extract it, then run `mediamtx.exe` from that folder. Leave the terminal
   window open — it needs to keep running.
3. In OBS: **Settings -> Stream**
   - Service: `Custom`
   - Server: `rtmp://localhost:1935/live`
   - Stream Key: `smseaside` (or any name you choose)
4. Click **Start Streaming** in OBS. In the MediaMTX terminal you should see:
   ```
   INF [path live/smseaside] stream is available and online, 2 tracks (H264, MPEG-4 Audio)
   INF [RTMP] [conn ...] is publishing to path 'live/smseaside'
   ```
5. Test playback with **VLC** (Media -> Open Network Stream) using:
   ```
   http://localhost:8888/live/smseaside/index.m3u8
   ```
   If the feed plays, the pipeline works end to end.

### 3. Python scripts

Install dependencies:
```bash
pip install -r requirements.txt
```
Also install the Microsoft ODBC Driver 17 for SQL Server
(needed for the database write in `process_video.py`):
https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

**`process_video.py`** — run manually against any recorded file to test vehicle
counting:
```bash
python process_video.py --video "C:\path\to\your_file.mp4" --intersection SM_SEASIDE_T1 --label test
```
Before trusting the output, calibrate:
- `COUNT_LINE_Y` — the pixel row vehicles cross; check a still frame from your
  actual camera angle and set this manually
- `MIN_CONTOUR_AREA` — raise it if noise/small movement is triggering false
  counts, lower it if smaller vehicles are being missed
- `CAPACITY_VEH_PER_HR` and the LOS thresholds — replace with your thesis's
  actual values

**`obs_scheduler.py`** — automates start/stop recording+streaming at the 4
daily observation windows, then automatically runs `process_video.py` on the
finished file. Fill in `OBS_PASSWORD` (the WebSocket password from step 1)
before running:
```bash
python obs_scheduler.py
```
Recommended: test with a temporary near-future time window first before
relying on the real schedule (08:00-09:00, 10:00-11:00, 14:00-15:00, 16:00-17:00).

### 4. Database

Create the destination table once in SQL Server:
```sql
CREATE TABLE TrafficMetrics (
    id INT IDENTITY PRIMARY KEY,
    intersection_id VARCHAR(50),
    observation_label VARCHAR(20),
    recorded_at DATETIME,
    vehicle_count INT,
    hourly_volume FLOAT,
    vc_ratio FLOAT,
    los CHAR(1)
);
```
Then update `DB_CONN_STR` in `process_video.py` with your actual server,
database, username, and password.

### 5. Website (not yet built)

Once MediaMTX is confirmed stable, the website will embed the HLS URL
(`http://<server>:8888/live/smseaside/index.m3u8`) using `hls.js` in a
`<video>` tag, and separately poll the SQL Server-backed metrics for the
live dashboard numbers.

## Known limitations

- The camera -> app -> OBS chain depends on the V380 Pro app's UI staying in
  the same position; an app update could shift the video pane and break the
  OBS capture crop.
- Live video has a few seconds of latency (camera -> cloud -> app -> OBS ->
  MediaMTX -> browser) — acceptable for a monitoring dashboard, not for
  frame-accurate timing.
- `obs_scheduler.py` does not auto-retry if it loses connection to OBS
  mid-window (e.g. app crash, laptop sleep).
- Vehicle counting in `process_video.py` uses a lightweight OpenCV
  background-subtraction baseline; if Camlytics is used as the primary
  detector instead, replace `count_vehicles()` with a function that parses
  Camlytics' exported results — everything downstream stays the same.