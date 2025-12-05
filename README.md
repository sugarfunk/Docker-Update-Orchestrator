# Docker Update Orchestrator

An intelligent system that discovers updates across all your Docker containers, analyzes changelogs for breaking changes using AI, orchestrates safe updates with dependency awareness, and provides automatic rollback capabilities.

## 🎯 Key Features

### Update Discovery
- **Automatic Container Scanning**: Discovers all containers across multiple servers
- **Multi-Registry Support**: Docker Hub, ghcr.io, and custom registries
- **Version Detection**: Semantic versioning awareness (major/minor/patch)
- **Update Tracking**: Monitors update frequency and identifies abandoned images

### AI-Powered Changelog Analysis
- **Automatic Changelog Retrieval**: Fetches from GitHub releases, Docker Hub, and project documentation
- **Breaking Change Detection**: Uses LLMs (Claude, GPT, Gemini, Ollama) to identify breaking changes
- **Multi-LLM Support**: Fallback between models with cost optimization
- **Risk Assessment**: Categorizes updates by risk level with detailed analysis

### Dependency & Impact Analysis
- **Service Relationship Mapping**: Identifies dependencies between containers
- **Impact Assessment**: "What will break if I update this?"
- **Update Ordering**: Respects dependencies (databases before apps)

### Safe Update Orchestration
- **Smart Update Planning**: Generates execution plans with dependency awareness
- **Multiple Execution Modes**: Manual, semi-automatic, and fully automatic
- **Health Checking**: HTTP endpoints, container logs, resource usage validation
- **Automatic Rollback**: Reverts to previous version on health check failure

### Dashboard & Monitoring
- **Web Dashboard**: Modern React UI for monitoring and control
- **Real-time Status**: See all updates at a glance
- **Detailed Analytics**: Success rates, downtime tracking, time saved

### Notifications
- **NTFY Integration**: Push notifications to your devices
- **Email Support**: Digest notifications and critical alerts
- **Webhook Support**: Integrate with your existing tools

## 🏗️ Architecture

```
┌─────────────────┐
│  React Frontend │
│   Dashboard     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────┐
│  FastAPI Backend│◄─────┤ PostgreSQL   │
│   REST API      │      │  Database    │
└────────┬────────┘      └──────────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────┐
│  Celery Workers │◄─────┤    Redis     │
│  Async Tasks    │      │  Task Queue  │
└────────┬────────┘      └──────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│   Docker Services (via SSH)             │
│   ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  │
│   │ S1  │  │ S2  │  │ S3  │  │ S4  │  │
│   └─────┘  └─────┘  └─────┘  └─────┘  │
└─────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- SSH access to your Docker servers
- API keys for LLM providers (Anthropic/OpenAI/Gemini) or Ollama for local

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/docker-update-orchestrator.git
cd docker-update-orchestrator
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```bash
# LLM Configuration
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...

# Notifications
NTFY_ENABLED=true
NTFY_TOPIC=docker-updates
NTFY_SERVER=https://ntfy.sh

# Email (Optional)
EMAIL_ENABLED=false
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=your-email@gmail.com
EMAIL_TO=admin@example.com

# Security
SECRET_KEY=change-this-to-a-secure-random-key
```

### 3. Set Up SSH Keys

Ensure your SSH keys are available for connecting to Docker servers:

```bash
# Copy your SSH key to the default location
cp ~/.ssh/id_rsa ~/.ssh/id_rsa
chmod 600 ~/.ssh/id_rsa

# Test SSH access to your servers
ssh root@workhorse1
ssh root@workhorse2
# etc...
```

### 4. Start the System

```bash
docker-compose up -d
```

This will start:
- PostgreSQL database (port 5432)
- Redis (port 6379)
- FastAPI backend (port 8000)
- Celery workers
- Celery beat scheduler
- Flower monitoring (port 5555)
- React frontend (port 3000)

### 5. Access the Dashboard

Open your browser to: http://localhost:3000

### 6. Add Your Servers

1. Go to the "Servers" page
2. Click "Add Server"
3. Enter server details:
   - Name: e.g., "workhorse1"
   - Hostname: e.g., "workhorse1" or IP address
   - Port: 22 (default SSH port)
   - Username: root (or your SSH user)
4. Click "Connect" to test the connection

### 7. Discover Containers

1. Click "Scan All Servers" on the dashboard
2. Wait for the scan to complete
3. View discovered containers on the "Containers" page

### 8. Check for Updates

1. Click "Check for Updates"
2. The system will:
   - Query registries for new versions
   - Retrieve changelogs
   - Analyze with AI for breaking changes
   - Generate update recommendations

### 9. Review and Approve Updates

1. Go to the "Updates" page
2. Review pending updates
3. Check changelog summaries and risk assessments
4. Approve low-risk updates or review breaking changes
5. Execute updates manually or enable auto-update

## 📚 Documentation

### Configuration

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for detailed configuration options.

### API Documentation

Once running, visit: http://localhost:8000/docs for interactive API documentation.

### Architecture Details

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design and component details.

### Development Guide

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for contributing and development setup.

## 🔒 Security Considerations

- **SSH Key Management**: Store SSH keys securely, use read-only mounts
- **API Key Storage**: Use environment variables, never commit keys to git
- **Database Access**: Use strong passwords, limit network access
- **HTTPS**: Use reverse proxy (nginx/traefik) for production
- **Audit Logging**: All actions are logged for review
- **Rate Limiting**: Automatic updates are rate-limited

## 🎛️ Configuration Options

### Per-Service Settings

Each container can be configured individually:

- Auto-update enabled/disabled
- Update approval requirements
- Preferred update windows
- Health check configuration
- Rollback policy
- Custom pre/post update scripts

### Global Settings

System-wide configuration:

- Default update policy
- Concurrent update limit
- LLM provider selection
- Notification preferences
- Backup retention policy

## 📊 Monitoring

### Flower (Celery)

Monitor background tasks: http://localhost:5555

### Logs

```bash
# Backend logs
docker-compose logs -f api

# Worker logs
docker-compose logs -f celery-worker

# Database logs
docker-compose logs -f postgres
```

## 🛠️ Troubleshooting

### Connection Issues

If you can't connect to a server:

1. Verify SSH access: `ssh root@server-hostname`
2. Check SSH key permissions: `ls -la ~/.ssh/id_rsa`
3. Verify Tailscale/network connectivity
4. Check server logs: `docker-compose logs api`

### Update Failures

If an update fails:

1. Check the update logs in the dashboard
2. Review health check results
3. Rollback is automatic by default
4. Manual rollback available in UI

### LLM Issues

If changelog analysis fails:

1. Verify API keys in `.env`
2. Check LLM provider status
3. Review worker logs: `docker-compose logs celery-worker`
4. Try fallback model or local Ollama

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

## 📈 Performance

### Scaling

- **Horizontal Scaling**: Add more Celery workers
- **Database**: Increase connection pool size
- **Redis**: Use Redis Cluster for high availability

### Optimization

- Use local Ollama for sensitive data (no API costs)
- Batch update checks during off-peak hours
- Configure appropriate check intervals

## 🤝 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with FastAPI, React, Celery, and PostgreSQL
- LLM integration via LiteLLM
- Inspired by Watchtower, but smarter and safer

## 📞 Support

- GitHub Issues: Report bugs and request features
- Discussions: Ask questions and share ideas

## ✅ Completed Features

- [x] **Dependency Analysis Service** - Automatic detection of service dependencies
- [x] **Full Update Orchestration** - Complete update execution with health checks
- [x] **Comprehensive Health Checks** - HTTP, TCP, Docker, log analysis, resource monitoring
- [x] **Rollback System** - Automatic rollback on failure with backup restoration
- [x] **Backup & Restore** - Container configuration and volume backups

## 🚧 Future Roadmap

- [ ] GitOps integration (commit changes to git)
- [ ] Blue-green deployment support
- [ ] A/B testing capabilities
- [ ] Prometheus/Grafana integration
- [ ] Volume snapshot integration
- [ ] Mobile app
- [ ] Multi-tenant support
- [ ] Kubernetes support

---

**Built with ❤️ to make Docker updates safer and easier**
