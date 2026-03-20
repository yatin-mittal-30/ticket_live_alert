# Keep your Mac running for the local agent (~48h)

Use this when the laptop stays at home **plugged in** and you want `main.py` to keep checking without macOS putting the machine to sleep.

## Critical: lid and power

| Setup | Result |
|--------|--------|
| **Lid open** + power adapter | Best for 24/7 local runs. |
| **Lid closed**, no external display | Mac usually **sleeps** → agent **stops** until wake. |
| **Lid closed** + external display + power (**clamshell**) | Usually stays awake; verify in **Battery** settings. |
| **Battery only** | Can sleep sooner; **plug in** for the next two days. |

## 1) Use the stay-awake launcher (foreground)

From the project folder:

```bash
chmod +x run_local_stay_awake.sh   # once
./run_local_stay_awake.sh
```

This wraps the agent in `caffeinate` so **idle sleep is blocked while the process runs**. When you stop the script (Ctrl+C), normal sleep rules return.

## 1b) Daemon (background + logs) — best for 24–48h

Starts `caffeinate` + agent under `nohup`, writes **PID** to `.agent.pid`, logs to `logs/`:

```bash
cd /path/to/ticket_booking_agent
./start_local_daemon.sh
./status_local_daemon.sh    # is it running?
./stop_local_daemon.sh      # when finished
```

- `logs/agent.log` — full text log, **daily rotation**, 14 days kept  
- `logs/checks.jsonl` — **one JSON object per check**  
- `logs/daemon.out` — shell-level output  

**Manual alternative** (no PID file helpers):

```bash
nohup ./run_local_stay_awake.sh >> logs/daemon.out 2>&1 &
echo $!   # stop later: kill PID
```

## 2) macOS System Settings (while on power adapter)

Paths vary slightly by macOS version; search in Settings for **sleep** or **power**.

1. **System Settings → Battery** (or **Energy**)
2. Open **Options…** (or **Power Adapter** settings).
3. Enable options such as:
   - **Prevent automatic sleeping on power adapter when the display is off** (wording may vary)
   - Avoid **Low Power Mode** on the adapter if it forces sleep sooner
4. **Lock Screen**: you can set **Turn display off after** to a longer time or **Never** if you need the screen on (optional; `caffeinate -d` already reduces display sleep while the script runs)

## 3) Optional: `pmset` (admin — reversible)

Shows current power settings:

```bash
pmset -g
```

**Only on AC power**, you can disable sleep until you revert (example — adjust values to match your `pmset -g` output before changing):

```bash
sudo pmset -c sleep 0
sudo pmset -c disksleep 0
# optional: never dim display timeout on AC (0 = never)
sudo pmset -c displaysleep 0
```

**Revert later** (example defaults; your Mac may differ):

```bash
sudo pmset -c sleep 10
sudo pmset -c disksleep 10
sudo pmset -c displaysleep 10
```

Use `pmset -g` before/after so you know what you changed.

## 4) Things that still stop the agent

- **Logout**, **restart**, **shutdown**, **updates that reboot**
- **Force quit** Terminal / Python
- **`kill`** on the process
- **Sleep** if `caffeinate` is not running (e.g. you used plain `python main.py` without the wrapper)
- **Lid closed** without clamshell setup → often sleep

## 5) After the two days

- Stop the agent: Ctrl+C or `kill` the `nohup` PID.
- Revert any `pmset` changes you made.
- Battery/Options: restore your preferred sleep-on-power settings.
