# Installing SolarBridge 1.0.1

Step-by-step guide. For the feature overview and configuration see [README.en.md](README.en.md); Russian version — [INSTALL.md](INSTALL.md).

## Requirements

| Machine | You need |
|---|---|
| Master (next to the inverter) | Linux with systemd (Debian/Raspbian/Ubuntu), Python 3.10+, a USB-RS485 adapter wired to the HIDEN HS-20-5548 PRO inverter bus |
| Receiver (VPS / second box) | Linux with systemd, Python 3.10+, a public address reachable from the master |

- The only external dependency is `pyserial>=3.5`: standard library, SQLite, venv.
- Privileges: run the installer with `sudo` (it creates the `sbridge` user, the venv and the systemd service). Afterwards the service runs as an unprivileged user.
- Time: keep NTP on the master — frames are stamped with the master's clock.

## Unpacking

The package is a cumulative zip (it is updated as a whole). Unpack it anywhere and run the installer from there:

```bash
unzip solarbridge-1.0.1.zip -d ~/solarbridge-src
cd ~/solarbridge-src
sudo python3 install.py
```

No arguments, no flags. Re-running `install.py` on an already installed machine opens the management menu (see below).

## Installation: MASTER

Run `sudo python3 install.py`, pick the role **"Master — the inverter is on RS485, this machine feeds receivers"** and answer the prompts:

1. **Serial adapter.** The installer scans `/dev/serial/by-id/*` and `/dev/ttyUSB*` and offers what it found. Prefer a by-id/by-path path — it survives ttyUSB renumbering. To inspect ports manually: `ls -l /dev/serial/by-id/` and `ls -l /dev/serial/by-path/`.
2. **Inverter Modbus slave id** — default `4` (the factory address of the HIDEN HS-20-5548 PRO).
3. **Port speed** — default `19200`.
4. **Dashboard port** — default `8090`. The master box is normally not exposed: its dashboard listens on `127.0.0.1`.
5. **History depth** — default `730` days (~7.6 GB at a 60 s frame).
6. **Receiver backfill window** — default `60` days.
7. **Batteries (experimental)** — off by default. If you accept: the port of the dedicated battery-bus adapter and the module DIP addresses (e.g. `2,3`; there is no bus auto-scan).
8. **Minimum free disk percentage** — default `10`. Below the threshold the master stops writing to its own DB and sends frames to receivers only (the dashboard shows a warning). `0` — no check.
9. **Dashboard login/password** — off by default. If enabled: set a login and a password — they go into the `user_list` file (format `login:password`, plaintext, mode 0640) and `SB_AUTH=1` lands in `.env`. After the first sign-in the browser keeps the token for 30 days.

The installer then: generates a `master_id` of the form `hostname-XXXXXXXX` (a random suffix, protection against an impostor master; written to `.env` and never changed afterwards), creates the `sbridge` user (dialout group), the `/opt/solarbridge` directory, a venv, installs `pyserial`, writes `/opt/solarbridge/.env`, creates an empty `receivers.list`, installs the `solarbridge.service` systemd unit and waits up to 30 s for `/healthz`. It finishes with:

```
SolarBridge 1.0.1 installed and running: http://127.0.0.1:8090
```

## Installation: RECEIVER

On the VPS: unpack the same zip, `sudo python3 install.py`, pick the role **"Receiver — accepts frames from the master"**:

1. **Token** — printed on the master when the receiver was added (see below). 64 hex characters are expected.
2. **Dashboard port** — default `8090`. The receiver wizard sets `SB_DASH_HOST=0.0.0.0` so the master can reach the receiver directly. If the receiver will sit behind nginx — confirm that in step 4 and set `SB_DASH_HOST=127.0.0.1` in `.env` (the "Configure .env" menu item).
3. **Receiver history depth** — default `730` days.
4. **IP allowlist** — comma-separated CIDRs (e.g. `203.0.113.10/32`); Enter = disabled. The list is checked before the token.
5. **"Receiver behind nginx (trust X-Forwarded-For)?"** — answer "yes" only if you really put nginx in front; this sets `SB_TRUST_PROXY=1`.

## What the installer does (both roles)

- copies the project to `/opt/solarbridge` (existing `data/` and `.env` are untouched; re-running = updating the code);
- creates the system user `sbridge`, adds it to the `dialout` group (USB-serial access);
- creates a venv and installs `pyserial` from `requirements.txt`;
- creates `data/` and `data/seeds/`;
- writes `.env` (backs up the old one as `.env.bak`), sets `0640` on `.env` and `receivers.list`, `0750` on `data/`;
- installs `/etc/systemd/system/solarbridge.service`, `daemon-reload`, `enable`, `restart`;
- waits for `http://127.0.0.1:<port>/healthz`.

## Management menu (re-running install.py)

On the master:

1. Forwarding status (per receiver: enabled, state, watermark, failures, sent/acked)
2. Add receiver
3. Manage receivers (enable/disable, rotate token, delete)
4. Create seed
5. Active seed links (and revocation)
6. Restore master data from a receiver database (dead master SD card)
7. Database maintenance: delete data before a date (with VACUUM)
8. Diagnostics
9. Service (start/stop/restart/status/logs)
10. Reconfigure role and parameters

On the receiver: status (master alive / bus error / offline, master version, heartbeat age, last frame, events) · download seed via link · configure `.env` · diagnostics · service · reconfigure.

Menu rules: numbered choice, `Enter` = safe default, dangerous actions require confirmation (default "no").

## Master recovery from a receiver database

Scenario: the master's SD card died. The data is not lost — every receiver keeps a full mirror.

1. Install SolarBridge on the new card as usual (the "Master" role; a new `master_id` is generated with a random suffix).
2. Copy the receiver's database to the master:
   ```bash
   scp user@receiver:/opt/solarbridge/data/solarbridge.sqlite3 /tmp/rx.sqlite3
   ```
3. `install.py` → **"Restore master data from a receiver database"** → the file path → transfer mode:
   - **"Everything"** — the receiver's whole history;
   - **"Date range"** — from/to dates inclusive;
   - **"From a date to the end"** — frames from the chosen date and newer.
4. The installer backs up the current database, imports frames and battery rows with deduplication (re-running is safe) and restarts the service.

The loss is limited to the tail of data from before the new master started writing (minutes). See the "Master recovery from scratch" section of README.en.md for details.

## Serial ports: by-id and by-path

Two adapters (inverter + batteries) can swap as `ttyUSB0/1` after reconnects. Use stable paths:

```bash
ls -l /dev/serial/by-id/     # the adapter's serial number — most stable
ls -l /dev/serial/by-path/   # the physical USB port
```

The systemd unit from `deploy/solarbridge.service` keeps `DevicePolicy=closed` with `DeviceAllow=char-ttyUSB rw` — every `ttyUSB*` stays accessible; if an adapter enumerates as ttyACM (CDC-ACM driver), add `DeviceAllow=char-ttyACM rw`.

## nginx (receiver behind HTTPS)

Scenario: a receiver on a VPS, the dashboard served over HTTPS, the master's ingest traffic arrives through the same address. In the receiver's `.env`: `SB_DASH_HOST=127.0.0.1`, `SB_TRUST_PROXY=1`.

```nginx
server {
    listen 443 ssl http2;
    server_name vps1.example.com;

    ssl_certificate     /etc/letsencrypt/live/vps1.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vps1.example.com/privkey.pem;

    location / {
        proxy_pass         http://127.0.0.1:8090;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        # IMPORTANT: overwrite rather than append — otherwise a client can
        # spoof the first X-Forwarded-For entry and defeat the allowlist
        proxy_set_header   X-Forwarded-For $remote_addr;
        # SSE (/api/events): disable buffering
        proxy_buffering    off;
        proxy_read_timeout 65s;
    }
}

server {
    listen 80;
    server_name vps1.example.com;
    return 301 https://$host$request_uri;
}
```

The receiver URL in the master's `receivers.list` — `https://vps1.example.com` (no port, no trailing slash).

If only you should see the dashboard, add basic auth in nginx:

```nginx
auth_basic "SolarBridge";
auth_basic_user_file /etc/nginx/solarbridge.htpasswd;
```

## nftables: open ports deliberately

The receiver port is set once in the receiver's `.env` — `SB_DASH_PORT` (default `8090`). The master POSTs to three endpoints on that port:

```
POST {url}/api/ingest/hello       # handshake: schema exchange + last-sample stamp
POST {url}/api/ingest/frames      # telemetry frames (gzip)
POST {url}/api/ingest/heartbeat   # heartbeat every 15 s
```

### Option 1: direct receiver (no nginx)

The service listens on `0.0.0.0:8090`. Open the port **only for the master's IP** — this also protects the dashboard, which in this option has no authentication of its own:

```nft
# /etc/nftables.conf (input chain fragment)
table inet filter {
    chain input {
        type filter hook input priority filter; policy drop;

        iifname "lo" accept
        ct state established,related accept

        # your SSH — keep whatever you already have
        tcp dport 22 accept

        # SolarBridge: ingest + dashboard, from the master's IP only
        ip saddr 203.0.113.10 tcp dport 8090 accept
        # if the master is reachable over IPv6:
        # ip6 saddr 2001:db8:1::10 tcp dport 8090 accept
    }
}
```

Applying and enabling at boot:

```bash
sudo nft -f /etc/nftables.conf
sudo systemctl enable nftables
```

If the master sits behind NAT/a dynamic address — additionally use the app-level allowlist `SB_INGEST_ALLOWLIST` (CIDRs) on the receiver, but remember: the dashboard GET routes remain public for everyone else.

### Option 2: receiver behind nginx (recommended for a VPS)

Only `80/443` are open; the service stays on `127.0.0.1:8090`:

```nft
table inet filter {
    chain input {
        type filter hook input priority filter; policy drop;
        iifname "lo" accept
        ct state established,related accept
        tcp dport 22 accept
        tcp dport 80 accept   # redirect to HTTPS
        tcp dport 443 accept  # dashboard + ingest through nginx
        # tcp dport 8090 — do NOT open to anyone
    }
}
```

Master-IP filtering is then done at the application level (`SB_INGEST_ALLOWLIST`) or by nginx basic auth.

### Master

The master dashboard listens on `127.0.0.1` by default — nothing to expose. To view it from another device, put nginx in front or use an SSH tunnel (`ssh -L 8090:127.0.0.1:8090 master-host`) rather than `SB_DASH_HOST=0.0.0.0`: GET routes on the master are unauthenticated.

## Deploying a new receiver

**Option A — without history (the common case).** The master backfills up to 60 days of history on first contact.

1. On the master: `install.py` → **"Add receiver"**: a name (e.g. `vps1`) → URL (`https://vps1.example.com` or `http://203.0.113.10:8090`). The token is generated automatically, the line is appended to `receivers.list`, and a ready `.env` block is saved to `data/seeds/env-<name>.txt` (mode 0600). You can test the link right away (a `hello` probe; if the receiver is not installed yet — fine, the master retries).
2. On the VPS: unpack the zip, `sudo python3 install.py`, role "Receiver", paste the token from `env-<name>.txt`.
3. Done: the master backfills the window automatically (~10 minutes for a full 60 days).

**Option B — deeper history (network seed).**

1. On the master: `install.py` → **"Create seed"** → compact (~190 MB per 60 days) or full. The installer prints a one-time link like `http://…/api/seed/download/<id>?t=…` (valid 24 h, up to 10 downloads, resumable).
2. On the receiver: `install.py` → **"Download seed via link"** → paste the link. The receiver verifies sha256, freshness (`SB_SEED_MAX_AGE_DAYS`) and schema, backs up, deploys the snapshot and restarts.
3. The master forwards the frames accumulated during the transfer.

Active links and revocation — the "Active seed links" menu item.

**Option C — moving an existing receiver.** Copy only its `data/solarbridge.sqlite3` (data, not secrets) and write your own `.env`. Never copy to a receiver: the master's `receivers.list` (it holds tokens) or the master's `.env`.

## Updating SolarBridge

**Option 1 — `update.py` (recommended).** The script is included in the package (and stays at `/opt/solarbridge/update.py` after installation):

```bash
sudo python3 update.py --check                 # compare versions (installed vs available)
sudo python3 update.py                         # fetch the release (SB_UPDATE_URL or --url), verify the sha256,
                                               # back up, apply, restart, healthz; rollback on failure
sudo python3 update.py --from solarbridge-1.1.0.zip   # offline, from a local file
```

The release source is `SB_UPDATE_URL` in `.env` (a GitHub repository or a direct zip URL). `.env`, `data/`, `receivers.list` and `.venv` are never overwritten; backups live in `backups/` (the last 2 are kept). Downgrades require `--force`. If the service does not answer `/healthz` within 60 s, `update.py` restores the backup and restarts the service on its own.

**Option 2 — manual.** Unpack the new zip over (or next to) the old one and run the installer:

1. Unpack the new zip next to (or over) the old one — the installer updates the files in `/opt/solarbridge` without touching `data/` and `.env`.
2. `sudo python3 install.py` — it finds the existing `.env`, updates the code and restarts the service.
3. Database schema mismatch: a master newer than the receiver gets `409` responses and the receiver keeps its data; after the receiver is updated, backfilling resumes.

In both cases keep the master and receiver versions identical: on a mismatch the dashboard shows a warning banner (the master version arrives with heartbeats).

## Troubleshooting

- **Service logs**: `journalctl -u solarbridge -n 100 -f`.
- **Quick check**: `curl http://127.0.0.1:8090/healthz` → `{"status":"ok"}`.
- **Master state as seen by the receiver**: `curl http://127.0.0.1:8090/api/master` (on the receiver) — state, master version, recent events (`master_events`, kept 30 days): `master_alive`, `master_offline`, `bus_error`, `bus_ok`, `schema_mismatch`.
- **Forwarding status** (master, menu item 1): the watermark = the newest sample the receiver acked; failures and the last error.
- **RS485 bus error** on the dashboard — check the cable/termination; the master keeps polling and recovers on its own.
- A receiver fell behind the backfill window — it needs a seed (Option B).
- Port busy: change `SB_DASH_PORT` in `.env` and restart the service.

## Uninstalling

```bash
sudo systemctl disable --now solarbridge
sudo rm /etc/systemd/system/solarbridge.service
sudo userdel sbridge
sudo rm -rf /opt/solarbridge
```
