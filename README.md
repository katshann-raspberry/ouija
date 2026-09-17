# ouija
Front end for transmitting G Code to the ouija board

Per Claude:

Setup notes:

* CNCjs must be running first on the Pi, listening on port 8000 by default. If it's the same Pi you'll open this in a browser on that Pi (or another machine on the LAN, pointing host at the Pi's IP).
* Auth token: CNCjs requires a token unless you've disabled auth in its config. Generate one from the CLI: cncjs --access-token-lifetime 30d (or use whatever token your existing CNCjs setup already issues) and paste it into the Token field.
* Serial port / baud: pick the /dev/serial/by-id/... entry once "Refresh Ports" lists it — that's the stable one for FluidNC over USB. 115200 is FluidNC's default.
* Jog buttons use $J= jog mode (Grbl-compatible, works on FluidNC) rather than plain G0, so moves are interruptible and don't queue up.
* File load reads the whole G-code file into memory and hands it to CNCjs's own gcode:load / gcode:start sender, which does the buffer-aware streaming — so you get the character-counting protocol for free rather than reimplementing it in this HTML.
