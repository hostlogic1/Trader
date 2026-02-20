# OpenClaw Memory Stack (Redis + Qdrant)

This folder contains a local-only Docker Compose stack for:
- **Redis** (short-term memory buffer)
- **Qdrant** (vector DB for long-term semantic memory)

Both are bound to **localhost (127.0.0.1)** for safety.

## Prereqs on the Hostinger VPS
Install Docker + Compose plugin:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# Docker repo
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# allow your user to run docker without sudo (optional)
sudo usermod -aG docker $USER
newgrp docker
```

## Start the stack
From the repo root on the VPS:

```bash
cd /data/.openclaw/workspace/Trader/memory_system
docker compose up -d
```

## Verify
```bash
docker ps
curl -s http://127.0.0.1:6333/ | head
redis-cli -h 127.0.0.1 ping
```

## Security
- Ports are bound to `127.0.0.1` only.
- Do **not** expose Redis/Qdrant to the public internet without auth/TLS and firewall rules.

## Next
Once these services are up, we will:
- point memory scripts to `REDIS_HOST=127.0.0.1` and `QDRANT_URL=http://127.0.0.1:6333`
- add an OpenClaw cron capture job (token-free) + nightly flush into Qdrant
