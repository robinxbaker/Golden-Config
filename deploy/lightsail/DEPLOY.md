# Deploying Golden Config to AWS Lightsail

A step-by-step guide to put the app behind a public HTTPS link an interviewer can
click. Uses a single Lightsail VM running the whole stack with `docker compose`,
fronted by Caddy for automatic Let's Encrypt certificates.

Result: `https://demo.yourdomain.com` → the running app.

---

## 0. What you'll create

- 1 Lightsail instance (Ubuntu 22.04, **2 GB RAM** plan) — ~$12/mo, first months often free.
- 1 static IP (free while attached).
- 1 DNS `A` record pointing your domain at the static IP.
- Firewall open on **80** and **443** only.

> No domain? Two options: buy a cheap one (Namecheap/Cloudflare/Porkbun), or use a
> free subdomain from [DuckDNS](https://www.duckdns.org). Caddy needs a real
> hostname to issue a TLS certificate — a bare IP won't get HTTPS.

---

## 1. Create the Lightsail instance

1. AWS Console → **Lightsail** → **Create instance**.
2. Platform: **Linux/Unix** → Blueprint: **OS Only → Ubuntu 22.04 LTS**.
3. Plan: pick at least the **2 GB RAM / 2 vCPU** tier (the stack has ~6 containers).
4. Name it `golden-config`, click **Create instance**.

## 2. Give it a stable IP + open the firewall

1. Lightsail → **Networking** → **Create static IP** → attach to the instance.
2. On the instance's **Networking** tab, under **IPv4 Firewall**, ensure:
   - **HTTP** (TCP 80) — allowed
   - **HTTPS** (TCP 443) — allowed
   - keep **SSH** (TCP 22)
   - remove anything else (do NOT open 5432/6379/8000).

## 3. Point DNS at the IP

At your DNS provider, add an `A` record:

```
demo.yourdomain.com  →  <your Lightsail static IP>
```

Wait a few minutes, then verify from your laptop:

```bash
nslookup demo.yourdomain.com
```

## 4. Connect and install Docker

Use the Lightsail browser SSH (or your own SSH key), then:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker   # run docker without sudo
docker --version
```

## 5. Get the code

```bash
git clone https://github.com/robinxbaker/Golden-Config.git
cd Golden-Config
```

## 6. Create the production `.env`

```bash
cp .env.prod.example .env

# generate real secrets:
python3 -c "import secrets;print('SECRET_KEY='+secrets.token_urlsafe(48))"
python3 -c "from cryptography.fernet import Fernet;print('CREDENTIAL_ENCRYPTION_KEY='+Fernet.generate_key().decode())"

nano .env
```

Fill in, at minimum:
- `DOMAIN=demo.yourdomain.com`
- `ACME_EMAIL=you@example.com`
- `BACKEND_CORS_ORIGINS=["https://demo.yourdomain.com"]` (JSON array)
- `SECRET_KEY=...` and `CREDENTIAL_ENCRYPTION_KEY=...` (generated above)
- a strong `POSTGRES_PASSWORD`
- a demo `FIRST_ADMIN_PASSWORD` (this is the interviewer's login)

## 7. Launch

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

First run builds images and pulls a TLS certificate (takes a minute). Check it:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f caddy      # watch cert issuance
```

Open **https://demo.yourdomain.com** — that's the link you send.

## 8. Give the interviewer access

Log in with `FIRST_ADMIN_USERNAME` / `FIRST_ADMIN_PASSWORD` from your `.env`.
The stack seeds an admin on startup (`python -m app.initial_data`). Optionally
create a read-only `viewer` account in the app for them.

---

## Operations cheat-sheet

```bash
# View logs
docker compose -f docker-compose.prod.yml logs -f backend worker

# Update to latest code
git pull && docker compose -f docker-compose.prod.yml up -d --build

# Stop everything (keeps data volumes)
docker compose -f docker-compose.prod.yml down

# Stop AND wipe data (fresh demo)
docker compose -f docker-compose.prod.yml down -v
```

To save money between interviews, **Stop** the instance in Lightsail (you keep the
static IP if attached). **Start** it again a few minutes before the demo.

---

## Troubleshooting

- **No HTTPS / cert error:** DNS `A` record must resolve to the instance IP before
  Caddy can validate. Confirm with `nslookup`, then `docker compose -f
  docker-compose.prod.yml restart caddy`.
- **Login/API fails, 404 on `/api/v1`:** the frontend was built with the wrong API
  URL. It must be built with `VITE_API_BASE_URL=/api/v1` (already set in
  `docker-compose.prod.yml`). Rebuild: `docker compose -f docker-compose.prod.yml
  build --no-cache frontend && docker compose -f docker-compose.prod.yml up -d`.
- **Out of memory / containers killed:** use the 2 GB plan, or drop the optional
  observability stack (Prometheus/Grafana/OTel are not included in the prod compose).
- **502 Bad Gateway:** backend still starting (running migrations). Wait and check
  `docker compose -f docker-compose.prod.yml logs backend`.
