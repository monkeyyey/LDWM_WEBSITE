# AWS Deployment and Maintenance

Use an Ubuntu x86_64 NVIDIA GPU instance with a working driver. Confirm
`nvidia-smi` works. The application does not install GPU drivers or provision
AWS resources. The [root setup guide](../README.md) lists OS prerequisites and
the complete installer workflow.

## Install as the application user

Run setup as `ubuntu`, not `root`. Use the same account for installation,
Hugging Face authentication and the backend service. This keeps virtualenv links,
model caches, repositories and checkpoint permissions consistent.

```bash
cd /home/ubuntu/LDWM_WEBSITE
bash setup.sh --artifacts /home/ubuntu/ldwm-artifacts --download-models
bash setup.sh --check
```

On an existing installation, export trained artifacts before migration. Setup
preserves configured paths and refuses to overwrite changed upstream checkouts.
The nine newer methods require clean pinned sources; the installer also pins the
original five. Review any reported revision differences before changing paths.

The installer writes a local `.env.gpu`, installs method runtimes under
`.venvs/`, and builds static frontend files under `watermark-lab/dist/`.
Existing external `*_PYTHON` overrides are reused without package installation
into those environments. Verify generation and all available analysis actions
on this GPU before publishing the site.

## Run the backend with systemd

Create `/etc/systemd/system/ldwm-backend.service`, adjusting paths and account
for the machine. Use `LDWM_BACKEND_PYTHON` from `.env.gpu` if an existing
backend executable was preserved instead of the default below.

```ini
[Unit]
Description=Watermark Lab backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/LDWM_WEBSITE
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
EnvironmentFile=/home/ubuntu/LDWM_WEBSITE/.env.gpu
ExecStart=/home/ubuntu/LDWM_WEBSITE/.venvs/backend/bin/python backend/server.py --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ldwm-backend
sudo systemctl status ldwm-backend --no-pager
```

The service starts after reboot. Changing `.env.gpu` requires a backend restart.
The gateway also reads that file automatically for manual launches; an exported
environment value takes precedence over its value in the file.

## Serve the built frontend

Use Nginx for the static build rather than the Vite development server:

```bash
sudo apt-get install -y nginx
sudo mkdir -p /var/www/ldwm
sudo cp -R watermark-lab/dist/. /var/www/ldwm/
```

Example Nginx site configuration; replace `your-domain.example`:

```nginx
server {
    listen 80;
    server_name your-domain.example;
    root /var/www/ldwm;
    index index.html;
    client_max_body_size 20m;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_read_timeout 7200s;
    }

    location /files/ {
        proxy_pass http://127.0.0.1:8000/files/;
    }
}
```

Enable the site, validate with `sudo nginx -t`, then reload Nginx. Configure
HTTPS for the domain using your certificate manager. Place the site behind
authenticated access: the API does not include user accounts or per-user limits.
Only expose the web ports required by your deployment; keep backend port 8000
and development port 5173 private. Limit SSH access to your administration IPs.

A local development session can instead use `bash start.sh` in tmux, with SSH
port forwarding for ports 5173 and 8000. The launcher stays in the foreground;
a systemd service is what restarts a process after an instance reboot.

## Update

```bash
cd /home/ubuntu/LDWM_WEBSITE
git pull --ff-only
bash setup.sh --check
sudo systemctl restart ldwm-backend
```

For changed Python requirements, rerun setup for the affected methods. For UI
changes, rebuild using the installed Node/npm and copy the new `dist/` contents
to `/var/www/ldwm/`. Rebuilding does not require retraining watermark components.

```bash
npm --prefix watermark-lab run build
sudo cp -R watermark-lab/dist/. /var/www/ldwm/
curl http://127.0.0.1:8000/health
journalctl -u ldwm-backend -n 100 --no-pager
```

Run one GPU job at a time. Keep model caches and the supplied artifact bundle
available to the service user. Back up `backend/storage/outputs/` because linked
analysis needs private generation state. Runtime freezes are saved in
`work/setup/*.freeze.txt`; monitor both disk usage and GPU memory.
