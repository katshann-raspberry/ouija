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
- `config/characters.json` for character coordinates and named positions.

The mapping follows the original `locations.json` format: `letters` contains
character keys and `buttons` contains named positions such as `Goodbye`, `Yes`,
and `No`. Each entry has `identifier`, `x`, and `y` fields; coordinates can be
numeric strings or numbers. Entries with both coordinates empty are unmeasured
and unavailable for submission. Partially filled or invalid coordinates are errors.
The JSON object keys identify locations; `identifier` is retained as metadata.

The supplied mapping includes seven unmeasured letters: B, C, D, F, K, M, and N.
Add an optional `Start` entry under `buttons` to move there after homing.
Without it, initialization finishes at the homed position.

Whitespace in submitted text is treated as a word boundary. The controller moves
to the configured `goodbye` position after each word.

## Raspberry Pi Service

Copy or symlink `systemd/ouijacnc.service` to:

```bash
/etc/systemd/system/ouijacnc.service
```

Then enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ouijacnc.service
```

The service runs as `spirit` and assumes the project lives at `/home/spirit/ouijacnc`. Adjust the unit if
you deploy it somewhere else.

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
