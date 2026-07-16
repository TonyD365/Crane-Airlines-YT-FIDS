# Crane Airlines — YouTube FIDS

An airport-style **Flight Information Display System** that renders a departure
board with Pillow and broadcasts it to YouTube Live through FFmpeg, 24×7.

```
FlightManager ──▶ FrameContext ──▶ FidsRenderer ──▶ StreamEngine ──▶ YouTube
  (data)            (snapshot)       (Pillow)         (FFmpeg)         (RTMP)
```

There is no web server, no browser, no dashboard: the process has exactly one
job — never go dark.

---

## Features

- Real airport board look: black canvas, white type, yellow accents, zebra rows
- Master clock with blinking colon, updated every second
- `BOARDING` / `LAST CALL` / `FINAL CALL` blink; `DELAYED` shows a new time
- Automatic paging when there are more flights than rows, with page dots
- Right-to-left scrolling welcome ticker
- Self-animating offline timetable (no API, no network)
- FFmpeg supervision: crash detection, exponential backoff, automatic reconnect
- Nothing can kill the loop: every collaborator failure is logged and survived
- 1920×1080 @ 30 FPS at roughly **7 ms of CPU per frame**

---

## Architecture

| Module | Responsibility | Knows about |
| --- | --- | --- |
| `crane_fids/config.py` | Environment → immutable `Config` | nothing |
| `crane_fids/models.py` | `Flight`, `FlightStatus`, `BoardKind` | nothing |
| `crane_fids/flight_manager.py` | `FlightProvider` protocol, static timetable, caching | models |
| `crane_fids/renderer/` | Theme, layout, fonts, layers, `FidsRenderer` | models, Pillow |
| `crane_fids/stream_engine.py` | FFmpeg child process supervision | config |
| `crane_fids/application.py` | Frame clock, pacing, health, composition root | all of the above |
| `app.py` | CLI entry point | application |

Design rules enforced across the code base:

- **The renderer never learns where data comes from.** It only sees a
  `FrameContext` value object. Swapping the static timetable for JSON, a REST
  API or a database means writing a new `FlightProvider` — nothing else changes.
- **The board is a list of layers.** A logo, weather, ads or an arrivals page
  are new `Layer` subclasses appended to the stack, not edits to existing code.
- **Static vs dynamic.** Static layers (chrome, header, column titles) are
  painted once into a cached background; dynamic layers cache their own region
  and repaint only when their `cache_key` changes. That is what buys 30 FPS.
- **Failures degrade the picture, never the process.** A broken layer, provider
  or encoder is logged and skipped; FFmpeg is restarted with backoff.
- Everything logs through `logging`; `print` is not used anywhere.

### Render loop

```
Application.run()
  └─ every 1/FPS seconds, on a drift-free monotonic schedule:
       flights = FlightManager.current_flights(now)   # cached, refreshed every 30 s
       frame   = FidsRenderer.render_bytes(ctx)       # reused buffer, RGB24
       StreamEngine.write(frame)                      # dropped if FFmpeg is down
```

If the host cannot keep up, the loop re-bases its schedule and logs how many
frame slots were dropped instead of accumulating an unrecoverable backlog.

---

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Look at the board without streaming anything:
python app.py --preview preview.png

# 2. Dry run: renders continuously, discards frames (no RTMP_URL set):
python app.py

# 3. Broadcast:
export RTMP_URL="rtmp://a.rtmp.youtube.com/live2/xxxx-xxxx-xxxx-xxxx-xxxx"
python app.py
```

`--preview-seconds 7.5` renders the frame as it would look 7.5 s into the
stream, which is handy for checking blink and scroll phases.

## Docker

```bash
docker build -t crane-fids .
docker run --rm \
  -e RTMP_URL="rtmp://a.rtmp.youtube.com/live2/<stream-key>" \
  -e WIDTH=1920 -e HEIGHT=1080 -e FPS=30 \
  -e TZ=America/Toronto \
  crane-fids
```

The image installs `ffmpeg`, DejaVu and Liberation fonts, runs as an
unprivileged user, and uses `tini` as PID 1 so that `SIGTERM` reaches the
application and FFmpeg is reaped correctly.

## Render deployment

The service is a **worker**, not a web service (it listens on no port).

1. Push this repository to GitHub.
2. In Render: *New* → *Blueprint*, point it at the repo. `render.yaml` creates
   the worker on the Starter plan.
3. Set `RTMP_URL` in the dashboard (it is `sync: false`, so it never lives in
   git).
4. Deploy. `Logs` should show `FFmpeg started` followed by periodic
   `Health: fps=…` lines.

Never scale beyond `numInstances: 1` — two workers would push two video streams
into the same YouTube ingest.

**Sizing.** A Starter instance is ~0.5 CPU, which comfortably runs
1280×720 @ 25 FPS with `FFMPEG_PRESET=veryfast` (the blueprint default).
1920×1080 @ 30 FPS wants a Standard instance or larger; libx264, not the
renderer, is the bottleneck.

## YouTube setup

1. YouTube Studio → *Go Live* → *Stream* (a persistent, reusable key).
2. Copy *Stream URL* (`rtmp://a.rtmp.youtube.com/live2`) and *Stream key*, then
   set `RTMP_URL = <stream-url>/<stream-key>`.
3. Latency: **Normal** — the board is not interactive and a long GOP is cheaper.
4. Because the picture is nearly static, the encoder is configured with
   `-tune stillimage`, a 2 s keyframe interval and a silent AAC track (YouTube
   rejects video-only ingests).
5. The stream key is a credential: it is only ever read from the environment and
   is redacted in every log line.

---

## Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `RTMP_URL` | *(empty)* | Full ingest URL incl. stream key. Empty ⇒ dry run |
| `AIRPORT_NAME` | `CRANE INTERNATIONAL AIRPORT` | Header subtitle |
| `AIRLINE_NAME` | `CRANE AIRLINES` | Header title |
| `BOARD_TITLE` | `DEPARTURES` | Board title |
| `TICKER_TEXT` | welcome message | Scrolling message |
| `TIMEZONE_LABEL` | `LOCAL TIME` | Caption under the clock |
| `TZ` | container default | Standard POSIX timezone, e.g. `America/Toronto` |
| `WIDTH` / `HEIGHT` | `1920` / `1080` | Frame size (must be even) |
| `FPS` | `30` | Frame rate (1–60) |
| `ROWS_PER_PAGE` | `10` | Flights per page |
| `PAGE_SECONDS` | `15` | Seconds a page stays on screen |
| `FLIGHT_REFRESH_SECONDS` | `30` | How often the provider is polled |
| `VIDEO_BITRATE` / `VIDEO_MAXRATE` / `VIDEO_BUFSIZE` | `4500k` / `4500k` / `9000k` | x264 rate control |
| `FFMPEG_PRESET` | `veryfast` | x264 preset |
| `GOP_SECONDS` | `2` | Keyframe interval |
| `AUDIO_ENABLED` | `true` | Silent AAC track (keep on for YouTube) |
| `FFMPEG_BINARY` | `ffmpeg` | Path to FFmpeg |
| `FFMPEG_LOGLEVEL` | `warning` | FFmpeg log level |
| `RESTART_BACKOFF` / `RESTART_BACKOFF_MAX` | `2` / `60` | Reconnect backoff, seconds |
| `FONT_DIR` | `assets/fonts` | Extra font directory, searched first |
| `LOG_LEVEL` | `INFO` | `DEBUG`…`CRITICAL` |

Any malformed value fails fast at start-up with an explicit message.

## Fonts

`assets/fonts/FIDS-Bold.ttf` and `FIDS-Regular.ttf` override everything else if
present; otherwise Inter, Roboto, DejaVu Sans and Liberation Sans are tried in
order. See `assets/fonts/README.md`.

## Development

```bash
pip install -r requirements-dev.txt
pytest          # unit tests: no FFmpeg, no network
ruff check .
mypy crane_fids app.py
```

## Extending

| Goal | What to write | What to change |
| --- | --- | --- |
| Flights from JSON / REST / DB | a `FlightProvider` | one line in `build_application` |
| Arrivals page | reuse `BoardKind.ARRIVALS` + a second `FlightManager` | layer stack order |
| Logo, weather, ads | a `Layer` (or `CachedRegionLayer`) | append to `default_layers` |
| New airport theme | a `Theme` (and optionally a `Layout`) | pass it to `FidsRenderer` |

## Licence

MIT.
