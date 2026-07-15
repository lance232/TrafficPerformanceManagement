# How to run the system (operational checklist)

Use this as your daily/ongoing checklist once everything is already set up
(see README.md for first-time setup). This is what to do to actually run a
multi-week data collection period.

## Before starting a collection period

- [ ] Camera is powered on and connected (check V380 Pro app shows the live feed)
- [ ] Laptop's power settings: **sleep disabled** (Settings → System → Power &
      Battery → Screen and sleep → set to "Never")
- [ ] Windows Update active hours set, or updates paused, so it won't reboot mid-collection
- [ ] Laptop plugged into reliable power (UPS/battery backup recommended if
      power at the site is unstable)
- [ ] `OBS_PASSWORD` in `obs_scheduler.py` matches OBS's current WebSocket password
- [ ] `OBSERVATION_WINDOWS` in `obs_scheduler.py` set to your real schedule:
  ```python
  OBSERVATION_WINDOWS = [
      ("08:00", "09:00"),
      ("10:00", "11:00"),
      ("14:00", "15:00"),
      ("16:00", "17:00"),
  ]
  ```
- [ ] `DB_CONN_STR` in `process_video.py` points to your real SQL Server, not placeholders
- [ ] `COUNT_LINE_Y` / `MIN_CONTOUR_AREA` calibrated against real footage from the mounted camera

## Every time you start the system (e.g. each morning, or once for the whole run)

Start these three things, in this order, and leave all three windows open:

**1. MediaMTX** (in its own terminal)
```bash
cd C:\mediamtx
mediamtx.exe
```
Wait for the startup log lines confirming RTMP/HLS listeners are up.

**2. OBS Studio**
Open it normally. Confirm:
- Window Capture source is showing the V380 app's live feed
- Stream settings still point to `rtmp://localhost:1935/live`

**3. The scheduler** (in its own terminal, from the project folder)
```bash
python obs_scheduler.py
```
You should see:
```
Scheduler running. Waiting for next observation window...
```

Leave all three running. The scheduler will automatically start/stop
recording and streaming at your 4 daily windows, every day, without
needing to be restarted — it runs continuously in the background.

## Checking on it without being at the PC

Every event is now logged to **`pipeline.log`** in the project folder
(alongside the terminal output), including:
- Every start/stop of a recording+streaming block
- The recorded file path
- Whether processing succeeded or failed, and why

You can open `pipeline.log` in any text editor to check history — for
example, to confirm all 4 windows ran correctly yesterday, or to see the
exact error if something failed overnight.

## If something goes wrong mid-collection

- **A block didn't start/stop**: check `pipeline.log` for a
  `ConnectionRefusedError` — usually means OBS or MediaMTX wasn't running,
  or OBS's WebSocket server got disabled.
- **Recording happened but no metrics**: check `pipeline.log` for a
  "Processing FAILED" line — the error message will point to whether it's
  a video-reading issue or a database connection issue.
- **The PC restarted unexpectedly**: you'll need to manually restart
  MediaMTX, OBS, and `obs_scheduler.py` again (see the 3-step start
  sequence above). Check `pipeline.log` to see which windows were missed
  while it was down.

## After the collection period ends

- Stop `obs_scheduler.py` (Ctrl+C in its terminal)
- Close OBS and MediaMTX
- Review `pipeline.log` for a full record of every window across the run
- Confirm all expected rows are present in the `TrafficMetrics` SQL table