# Quick Start Guide

Get Docker Update Orchestrator running in 5 minutes!

## Prerequisites

- Docker and Docker Compose installed
- SSH access to your Docker servers
- LLM API key (Anthropic/OpenAI/Gemini) OR Ollama installed locally

## Step 1: Clone and Setup

```bash
git clone https://github.com/yourusername/docker-update-orchestrator.git
cd docker-update-orchestrator
./setup.sh
```

The setup script will:
- Create your `.env` file
- Check for SSH keys
- Build and start all services
- Provide next steps

## Step 2: Configure LLM

Edit `.env` and add your API key:

```bash
# For Claude (recommended)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# OR for ChatGPT
OPENAI_API_KEY=sk-your-key-here

# OR install Ollama (free, local)
# Download from https://ollama.ai/
# Then: ollama pull llama2
```

## Step 3: Add Your Servers

1. Open http://localhost:3000
2. Go to "Servers" page
3. Click "Add Server"
4. Enter details:
   ```
   Name: workhorse1
   Hostname: 192.168.1.100 (or hostname)
   Port: 22
   Username: root
   ```
5. Click "Connect"

Repeat for all your servers!

## Step 4: Discover Containers

Click **"Scan All Servers"** on the dashboard.

This will:
- Connect to each server via SSH
- List all Docker containers
- Store them in the database

## Step 5: Check for Updates

Click **"Check for Updates"**.

This will:
- Query Docker Hub/GHCR for new versions
- Retrieve changelogs from GitHub
- Analyze with AI for breaking changes
- Generate risk assessments

This may take a few minutes for the first run.

## Step 6: Review Updates

1. Go to "Updates" page
2. See all pending updates with:
   - Version changes
   - Risk levels
   - Breaking changes
   - AI summaries
3. Click "Details" to see full changelog analysis

## Step 7: Approve and Execute

For each update:

1. Review the changelog summary
2. Check for breaking changes
3. Note any config changes needed
4. Click **"Approve"**
5. Click **"Execute"** to run the update

Or enable auto-update for low-risk services!

## Common Use Cases

### Scenario 1: I want to see what needs updating

```
Dashboard → Check for Updates → View pending updates
```

### Scenario 2: I want to safely update a critical service

```
Updates → Find service → Review changelog → Check breaking changes → Approve → Execute
```

### Scenario 3: I want to auto-update non-critical services

```
Settings → Configure auto-update for:
- Risk level: low or medium
- Require approval: No
- Auto-rollback: Yes
```

### Scenario 4: An update failed

Don't panic! The system:
1. Automatically rolls back to previous version
2. Sends you a notification
3. Logs the error for review

View the logs in the UI or:
```bash
docker-compose logs celery-worker
```

## Configuration Tips

### For Your Homelab

```bash
# .env
UPDATE_CHECK_INTERVAL_HOURS=6
MAX_CONCURRENT_UPDATES=2
NTFY_ENABLED=true
```

### For Production

```bash
# .env
UPDATE_CHECK_INTERVAL_HOURS=24
MAX_CONCURRENT_UPDATES=1
ROLLBACK_ON_FAILURE=true
BACKUP_RETENTION_DAYS=30
```

## Monitoring

### View Task Queue

http://localhost:5555 (Flower - Celery monitoring)

### Check Logs

```bash
# All services
docker-compose logs -f

# Just workers
docker-compose logs -f celery-worker

# Just API
docker-compose logs -f api
```

## Notifications

### NTFY (Free Push Notifications)

1. Install NTFY app on your phone
2. Subscribe to your topic (default: `docker-updates`)
3. Get notifications for:
   - Updates available
   - Updates completed
   - Updates failed
   - Rollbacks executed

### Email

Edit `.env`:
```bash
EMAIL_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_TO=admin@example.com
```

For Gmail, generate an app password: https://myaccount.google.com/apppasswords

## Troubleshooting

### Can't connect to server

```bash
# Test SSH manually
ssh root@your-server

# Check SSH key
ls -la ~/.ssh/id_rsa

# View logs
docker-compose logs api
```

### LLM not working

```bash
# Check API key in .env
cat .env | grep API_KEY

# View worker logs
docker-compose logs celery-worker

# Try Ollama instead (free!)
ollama pull llama2
# Then set LLM_PROVIDER=ollama in .env
```

### Updates not showing

```bash
# Manually trigger check
curl -X POST http://localhost:8000/api/v1/containers/scan

# Check worker logs
docker-compose logs celery-worker
```

## Advanced Features

### Per-Service Configuration

Each container can have custom settings:
- Auto-update enabled/disabled
- Update approval requirements
- Health check configuration
- Custom update scripts
- Rollback policy

### Update Scheduling

Schedule updates for off-peak hours:
```
Settings → Service Config → Update Windows
```

### Custom Health Checks

Define custom health checks per service:
- HTTP endpoints
- TCP connections
- Custom scripts
- Log analysis

## Getting Help

- Read the full [README.md](README.md)
- Check [docs/](docs/) for detailed guides
- Open an issue on GitHub
- Join discussions

## What's Next?

Once you're comfortable:

1. **Enable auto-updates** for low-risk services
2. **Set up update windows** for critical services
3. **Configure custom health checks** for important apps
4. **Create update groups** for related services
5. **Integrate with your monitoring** (Prometheus/Grafana)

Enjoy safer, smarter Docker updates! 🚀
