# OuijaCNC

A small Flask app for driving a FluidNC-controlled ESP32 from a Raspberry Pi.

The browser submits text. The backend translates that text into configured XY
coordinates and streams G-code to FluidNC over `/dev/ttyUSB0`.

## Local Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
flask --app ouijacnc.web run --host 0.0.0.0 --port 8080
```

The app uses the Pi's stable CP2102 USB serial device path at `115200`.

For development without the controller attached:

```bash
OUIJACNC_DRY_RUN=1 flask --app ouijacnc.web run --host 0.0.0.0 --port 8080
```

## Configuration

Edit:

- `config/settings.json` for serial settings, startup behavior, and G-code templates.
- `locations.json` for character coordinates and named positions.

The mapping follows the original `locations.json` format: `letters` contains
character keys and `buttons` contains named positions such as `Goodbye`, `Yes`,
and `No`. Each entry has `identifier`, `x`, and `y` fields; coordinates can be
numeric strings or numbers. Entries with both coordinates empty are unmeasured
and unavailable for submission. Partially filled or invalid coordinates are errors.
The JSON object keys identify locations; `identifier` is retained as metadata.

The seven previously blank letters B, C, D, F, K, M, and N now have estimated
coordinates. Each is marked with `source: "calculated"` and a `comment` field
because JSON does not support ordinary comments. All measured values are retained.
Verify the estimates on the board, especially M and N, before relying on them.

The estimates assume A-N form the upper arc and O-Z form the lower arc. Using
the measured upper-row letters A, E, G, H, I, J, and L, a least-squares spacing
fit gives `x = 8.134191 + 22.068015 * i`, where A has index 0. A quadratic fit
gives `y = -0.0011001811 * x*x + 0.36492167 * x + 133.694664`. Coordinates are
rounded to 0.1 mm. M and N extrapolate beyond the measured part of the arc.
This is an approximate curve, not a measured board calibration.

Add an optional `Start` entry under `buttons` to move there after homing.
Without it, initialization finishes at the homed position.

Whitespace in submitted text is treated as a word boundary. The controller pauses
for `gcode.word_pause_seconds` (1.5 seconds) between words, then moves to `goodbye`
once at the end of the message. Empty text does not move the machine.

For consecutive identical letters within a word, the magnet moves off the letter
and back before continuing. `gcode.repeat_gesture.distance_mm` defaults to 20 mm;
set it to 0 to disable the gesture. The `up` letters A-N use positive Y and the
`down` letters O-Z use negative Y. Both moves use the existing `move_template`.
The full sequence, including excursions, is checked against the configured bounds
before motion begins. An invalid excursion rejects the job instead of shortening
the gesture. Identical letters across word boundaries get only the word pause.
Digits currently have no repeat gesture, but can be added to an `up` or `down` set.

The Yes, No, and Goodbye buttons queue a single move to the corresponding named
position. These commands wait their turn after earlier submissions and stay at
the selected position. Text entry still spells words, including "yes" and "no".

## Raspberry Pi Service

The service runs as `spirit` from `/home/spirit/repos/ouija`, using Waitress in a
single process so only one controller owns the serial connection.

On the Pi, prepare the checkout and install the service:

```bash
cd /home/spirit/repos/ouija
git fetch origin
git switch ouija-cnc
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
sudo install -m 644 systemd/ouijacnc.default /etc/default/ouijacnc
sudo install -m 644 systemd/ouijacnc.service /etc/systemd/system/ouijacnc.service
sudo systemctl daemon-reload
sudo systemctl enable --now ouijacnc.service
```

The supplied environment file starts in dry-run mode. Open
`http://ouija.lan:8080` to check the website. To enable real motion, set
`OUIJACNC_DRY_RUN=0` in `/etc/default/ouijacnc`, then run
`sudo systemctl restart ouijacnc`. This opens the serial port and homes the
machine. Subsequent boots and process restarts also home it. The web Restart
button queues another initialization after any queued work; it is not a stop.

View service status and logs with:

```bash
systemctl status ouijacnc --no-pager
journalctl -u ouijacnc -n 50 --no-pager
```

For later updates, stop the service while updating the checkout and dependencies:

```bash
sudo systemctl stop ouijacnc
git pull --ff-only
.venv/bin/pip install -r requirements.txt
sudo systemctl start ouijacnc
```

Do not reinstall the supplied environment file during ordinary updates: it would
reset the selected dry-run setting. The service starts at boot without a GitHub
connection; pulling updates is a separate step.

The service user needs serial access:

```bash
sudo usermod -aG dialout spirit
```

Log out and back in after changing groups.

## SSH Setup For Testing

From your development machine:

```bash
ssh spirit@ouija.lan
```

If SSH is not enabled on the Pi:

```bash
sudo raspi-config
```

Then choose `Interface Options` -> `SSH` -> enable.

If you want me to run commands on the Pi from this workspace, the easiest path is
to make sure `ssh spirit@ouija.lan` works without an interactive password prompt from
this machine, usually by adding your public key:

```bash
ssh-copy-id spirit@ouija.lan
```

After that, I can use `ssh spirit@ouija.lan ...` from this workspace.

## Legacy CNCjs Interface

The original `test.html` interface and images are retained. That interface requires
CNCjs running on port 8000; the Flask app connects directly to FluidNC instead.
Do not run both senders against the serial device at the same time.
