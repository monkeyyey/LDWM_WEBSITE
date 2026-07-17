# LDWM AWS Setup And Maintenance Guide

This document describes how to run and maintain the LDWM website on an Ubuntu AWS GPU instance.

The current production-style setup is:

```text
Browser
  -> https://ldwm.anyhow.sbs
  -> Nginx on ports 80/443
  -> Vite frontend on 127.0.0.1:5173
  -> Python backend on 127.0.0.1:8000
  -> SFWMark + Stable Diffusion on the AWS GPU
```

## 1. AWS Instance

Recommended instance family:

```text
g4dn.xlarge or another NVIDIA GPU instance
```

The current tested GPU was:

```text
Tesla T4
```

Recommended AMI:

```text
Deep Learning OSS Nvidia Driver AMI GPU PyTorch, Ubuntu 24.04
```

Recommended storage:

```text
At least 100 GB EBS
```

Stable Diffusion, SFWMark, Python packages, model caches, and generated images can use a lot of disk space.

## 2. Security Group

Inbound rules:

```text
22    TCP    your IP, or 0.0.0.0/0 while testing
80    TCP    0.0.0.0/0
443   TCP    0.0.0.0/0
5173  TCP    optional, only needed if directly testing Vite without Nginx
8000  TCP    optional, only needed if directly testing backend without Nginx
```

For the Nginx setup, the public website should only need:

```text
80
443
22
```

Keep `5173` and `8000` closed later if you want a cleaner production security posture, because Nginx proxies to those ports locally.

## 3. Elastic IP And DNS

Allocate an Elastic IP in EC2:

```text
EC2 -> Network & Security -> Elastic IPs -> Allocate Elastic IP address
```

Associate it to the GPU instance.

Then create a DNS A record:

```text
Type: A
Host: ldwm
Value: <Elastic IP>
TTL: 300 or 600
```

For the current domain:

```text
ldwm.anyhow.sbs -> 47.130.234.128
```

Check DNS from your Mac:

```bash
dig ldwm.anyhow.sbs +short
```

Expected output:

```text
47.130.234.128
```

## 4. SSH

From your Mac:

```bash
ssh -i /path/to/your-key.pem ubuntu@47.130.234.128
```

Or, if DNS is working:

```bash
ssh -i /path/to/your-key.pem ubuntu@ldwm.anyhow.sbs
```

If macOS complains about key permissions:

```bash
chmod 400 /path/to/your-key.pem
```

## 5. Repository Location

The AWS instance expects the project at:

```bash
/home/ubuntu/LDWM_WEBSITE
```

Normal update:

```bash
cd ~/LDWM_WEBSITE
git pull
```

## 6. Python Virtual Environment

Create the venv once:

```bash
cd ~/LDWM_WEBSITE
sudo apt update
sudo apt install -y python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
```

Install backend dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.gpu.txt
```

Run SFWMark setup:

```bash
bash backend/integrations/sfwmark/setup_sfwmark.sh
```

This clones the official SFWMark repo into:

```bash
external/SFWMark
```

It also installs missing SFWMark dependencies and keeps the CUDA PyTorch already provided by the AWS Deep Learning AMI.

## 7. Hugging Face Model Access

SFWMark uses Stable Diffusion model weights from Hugging Face.

If model download fails, log in:

```bash
source ~/LDWM_WEBSITE/.venv/bin/activate
python -m pip install --force-reinstall "huggingface_hub[cli]>=0.24.0,<1.0"
hf auth login
```

Important: keep `huggingface_hub` below `1.0`, because the current SFWMark dependency stack uses `transformers==4.48.1`.

Check versions:

```bash
python - <<'PY'
import huggingface_hub
import transformers
import diffusers
print("huggingface_hub:", huggingface_hub.__version__)
print("transformers:", transformers.__version__)
print("diffusers:", diffusers.__version__)
PY
```

## 8. Node And Frontend Setup

Install Node with `nvm`:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
source ~/.bashrc
nvm install 22
nvm use 22
```

Install frontend dependencies:

```bash
cd ~/LDWM_WEBSITE/watermark-lab
npm install
```

## 9. Manual Run Commands

Backend:

```bash
cd ~/LDWM_WEBSITE
source .venv/bin/activate
python backend/server.py --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd ~/LDWM_WEBSITE/watermark-lab
npm run dev -- --host 127.0.0.1
```

With Nginx, access:

```text
https://ldwm.anyhow.sbs
```

## 10. Nginx Reverse Proxy

Install Nginx:

```bash
sudo apt update
sudo apt install -y nginx
```

Create:

```bash
sudo nano /etc/nginx/sites-available/ldwm
```

Use this config:

```nginx
server {
    listen 80;
    server_name ldwm.anyhow.sbs;

    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /api/ {
        rewrite ^/api/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    location /files/ {
        proxy_pass http://127.0.0.1:8000/files/;
        proxy_set_header Host $host;
    }
}
```

Enable it:

```bash
sudo ln -s /etc/nginx/sites-available/ldwm /etc/nginx/sites-enabled/ldwm
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

## 11. HTTPS With Certbot

Install Certbot:

```bash
sudo apt install -y certbot python3-certbot-nginx
```

Issue/install certificate:

```bash
sudo certbot --nginx -d ldwm.anyhow.sbs
```

If Certbot says an existing certificate exists, choose:

```text
1: Attempt to reinstall this existing certificate
```

Check:

```bash
sudo nginx -t
sudo systemctl reload nginx
curl -I https://ldwm.anyhow.sbs
```

## 12. systemd Services

Use two services:

```text
ldwm-backend.service
ldwm-frontend.service
```

### Backend Service

Create:

```bash
sudo nano /etc/systemd/system/ldwm-backend.service
```

Paste:

```ini
[Unit]
Description=LDWM backend API
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/LDWM_WEBSITE
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/ubuntu/LDWM_WEBSITE/.venv/bin/python backend/server.py --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Frontend Service

Find your Node path:

```bash
which node
which npm
```

For the current Node version, create:

```bash
sudo nano /etc/systemd/system/ldwm-frontend.service
```

Paste:

```ini
[Unit]
Description=LDWM Vite frontend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/LDWM_WEBSITE/watermark-lab
Environment=PATH=/home/ubuntu/.nvm/versions/node/v22.23.1/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/home/ubuntu/.nvm/versions/node/v22.23.1/bin/npm run dev -- --host 127.0.0.1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ldwm-backend ldwm-frontend
sudo systemctl restart ldwm-backend ldwm-frontend
```

Check status:

```bash
sudo systemctl status ldwm-backend --no-pager
sudo systemctl status ldwm-frontend --no-pager
```

## 13. Normal Maintenance Workflow

After pushing code from local machine:

```bash
ssh -i /path/to/key.pem ubuntu@ldwm.anyhow.sbs
cd ~/LDWM_WEBSITE
git pull
sudo systemctl restart ldwm-backend ldwm-frontend
```

If only frontend changed:

```bash
sudo systemctl restart ldwm-frontend
```

If only backend changed:

```bash
sudo systemctl restart ldwm-backend
```

If service files changed:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ldwm-backend ldwm-frontend
```

## 14. Logs

Backend logs:

```bash
journalctl -u ldwm-backend -f
```

Frontend logs:

```bash
journalctl -u ldwm-frontend -f
```

Nginx logs:

```bash
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

Certbot logs:

```bash
sudo tail -f /var/log/letsencrypt/letsencrypt.log
```

## 15. Validation Commands

Health check:

```bash
curl http://127.0.0.1:8000/health
curl https://ldwm.anyhow.sbs/api/health
```

Frontend through Nginx:

```bash
curl -I https://ldwm.anyhow.sbs
```

Port check:

```bash
sudo ss -tlnp | grep -E ':80|:443|:5173|:8000'
```

Expected:

```text
nginx listening on 80/443
node/Vite listening on 127.0.0.1:5173
python backend listening on 127.0.0.1:8000
```

## 16. SFWMark Validation

Generate one SFWMark image:

```bash
cd ~/LDWM_WEBSITE
source .venv/bin/activate
bash backend/integrations/sfwmark/smoke_official_generate.sh HSQR
```

Detect it:

```bash
bash backend/integrations/sfwmark/smoke_official_detect.sh HSQR
```

Validate all four SFWMark modes:

```bash
bash backend/integrations/sfwmark/smoke_all_wm_types.sh 2>&1 | tee sfwmark-all-types.log
```

The four modes are:

```text
HSQR
HSTR
Tree-Ring
RingID
```

Generated website jobs are stored in:

```bash
~/LDWM_WEBSITE/backend/storage/outputs/<job-id>/
```

Each generation job should contain:

```text
watermarked.png
clean.png
metadata.json
pattern_list-2048.pt
identify_gt_indices_1.npy
```

## 17. Common Problems

### Website Shows Nginx Default Page

Nginx is installed but the LDWM config is not enabled.

Check:

```bash
ls -l /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Domain Returns 403 But IP Works

Vite may reject the domain host. The project now allows:

```text
ldwm.anyhow.sbs
```

If changing domains, set `VITE_ALLOWED_HOSTS` or update `watermark-lab/vite.config.ts`.

### Backend Not Reachable From HTTPS Site

The frontend should call:

```text
/api
```

not:

```text
:8000
```

Check Nginx has the `/api/` proxy block.

### Certbot NXDOMAIN

DNS is not public yet.

Check:

```bash
dig ldwm.anyhow.sbs +short
```

### Certbot Already Running

Check:

```bash
ps aux | grep certbot
```

Kill if stuck:

```bash
sudo pkill -f certbot
```

### Python Says No pip Or Externally Managed Environment

Use the venv:

```bash
cd ~/LDWM_WEBSITE
source .venv/bin/activate
python -m pip install ...
```

### Hugging Face Version Conflict

If you see:

```text
huggingface-hub>=0.24.0,<1.0 is required
```

Run:

```bash
source ~/LDWM_WEBSITE/.venv/bin/activate
python -m pip uninstall -y huggingface_hub huggingface-hub
python -m pip install --no-cache-dir "huggingface_hub[cli]>=0.24.0,<1.0"
```

### GPU Not Detected

Check:

```bash
nvidia-smi
python - <<'PY'
import torch
print(torch.__version__)
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "no cuda")
PY
```

## 18. Disk Maintenance

Check disk:

```bash
df -h
du -sh ~/LDWM_WEBSITE/backend/storage/outputs
du -sh ~/.cache/huggingface
du -sh ~/.cache/torch
```

Generated images and model caches can grow large.

To remove old generated jobs:

```bash
rm -rf ~/LDWM_WEBSITE/backend/storage/outputs/<job-id>
```

Do not delete `~/.cache/huggingface` unless you are willing to redownload model weights.

