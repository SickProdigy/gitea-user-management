# Gitea User Management

A small private admin panel for bulk-managing Gitea users through the official Gitea API.

This is intended to run beside a self-hosted Gitea container on the same Docker network. Keep it private: bind it to localhost or a trusted LAN/VPN, not the public internet.

## What it does

The first version can list Gitea users and apply bulk cleanup actions:

- set users as restricted
- disable organization creation
- clear profile website
- clear profile location
- set visibility to private
- prohibit login
- set max repository creation to `0`
- dry-run changes before applying them

The Gitea admin API does not consistently expose the exact existing-user "Keep email private" checkbox across versions. This panel uses `visibility = private` for existing users and expects `DEFAULT_KEEP_EMAIL_PRIVATE = true` in Gitea for future signups.

## Requirements

- Docker / Docker Compose
- A Gitea admin access token
- Network access from this container to Gitea, usually `http://gitea:3000` on the same Docker network

## Install Beside Gitea

Clone this repo inside or beside your Gitea compose folder. Example:

```text
docker-containers/
  gitea/
    docker-compose.yml
    gitea-user-management/
```

Copy the example environment file and fill it in:

```bash
cp .env.example .env
```

Use long random values for `GITEA_TOKEN`, `PANEL_AUTH_TOKEN`, and `PANEL_SECRET_KEY`.

Add a service like this to your Gitea compose file:

```yaml
services:
  gitea-user-management:
    build: ./gitea-user-management
    container_name: gitea-user-management
    restart: unless-stopped
    env_file:
      - ./gitea-user-management/.env
    ports:
      - "127.0.0.1:4099:8080"
    networks:
      homelab:

networks:
  homelab:
    external: true
```

Start it:

```bash
docker compose up -d --build gitea-user-management
```

If the server is remote, use an SSH tunnel:

```bash
ssh -L 4099:127.0.0.1:4099 user@server
```

Then open:

```text
http://127.0.0.1:4099
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `GITEA_BASE_URL` | `http://gitea:3000` | Internal URL for the Gitea container |
| `GITEA_TOKEN` | empty | Gitea admin API token |
| `PANEL_AUTH_TOKEN` | empty | Password/token for logging into this panel |
| `PANEL_SECRET_KEY` | `change-me-before-use` | Secret used to sign browser sessions |
| `ALLOW_INSECURE_NO_AUTH` | `false` | Set to `true` only for local development |

## Notes

- Keep the panel localhost-only unless you add additional authentication at your reverse proxy.
- Use Dry Run before applying bulk actions.
- The app calls Gitea's API; it does not modify the database directly.
- For public/open registration instances, pair this with Gitea settings like `DEFAULT_USER_IS_RESTRICTED = true`, `DEFAULT_ALLOW_CREATE_ORGANIZATION = false`, and `DEFAULT_KEEP_EMAIL_PRIVATE = true`.
