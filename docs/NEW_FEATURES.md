# New Features - Advanced Update Capabilities

This document covers the advanced features recently added to Docker Update Orchestrator.

## 🔍 Dependency Analysis

### Overview

The system now automatically detects dependencies between your containers and uses this information to:
- Determine the correct update order
- Assess the impact of updates
- Prevent breaking dependent services

### How It Works

The dependency analyzer uses multiple detection methods:

1. **Environment Variable Analysis**: Detects connection strings pointing to other containers
2. **Shared Network Analysis**: Identifies containers on the same Docker networks
3. **Shared Volume Analysis**: Finds containers sharing data volumes
4. **Docker Compose Analysis**: Reads explicit `depends_on` declarations
5. **Pattern Matching**: Recognizes common service patterns (database, cache, proxy, etc.)

### API Endpoints

#### Analyze Dependencies
```bash
POST /api/v1/dependencies/analyze
```

Triggers dependency analysis for all containers or a specific server.

**Parameters:**
- `server_id` (optional): Limit analysis to specific server

**Response:**
```json
{
  "success": true,
  "dependencies_found": 25,
  "message": "Found 25 dependencies"
}
```

#### Get Container Dependencies
```bash
GET /api/v1/dependencies/container/{container_id}
```

Get all dependencies for a specific container.

**Response:**
```json
{
  "outgoing": [
    {
      "to_container_name": "postgres",
      "type": "database",
      "is_critical": true,
      "confidence": 90,
      "description": "References postgres in DATABASE_URL"
    }
  ],
  "incoming": [
    {
      "from_container_name": "api",
      "type": "api",
      "is_critical": false,
      "confidence": 70
    }
  ]
}
```

#### Get Dependency Graph
```bash
GET /api/v1/dependencies/graph
```

Get the complete dependency graph for visualization.

**Response:**
```json
{
  "nodes": [
    {
      "id": "container-123",
      "name": "api",
      "type": "application",
      "is_critical": true
    }
  ],
  "edges": [
    {
      "from": "api-id",
      "to": "postgres-id",
      "type": "database",
      "is_critical": true
    }
  ]
}
```

#### Get Update Order
```bash
GET /api/v1/dependencies/update-order?container_ids=id1,id2,id3
```

Calculate the optimal update order for multiple containers.

**Response:**
```json
{
  "update_order": [
    {
      "level": 1,
      "containers": [
        {"id": "postgres-id", "name": "postgres"},
        {"id": "redis-id", "name": "redis"}
      ],
      "can_update_in_parallel": true
    },
    {
      "level": 2,
      "containers": [
        {"id": "api-id", "name": "api"}
      ],
      "can_update_in_parallel": true
    }
  ],
  "message": "Containers in the same level can be updated in parallel"
}
```

### Example Use Case

**Scenario**: You want to update your entire stack (database, cache, API, frontend)

1. Request update order: `GET /api/v1/dependencies/update-order?container_ids=...`
2. System calculates:
   - Level 1: Update postgres and redis first (no dependencies)
   - Level 2: Update API (depends on postgres and redis)
   - Level 3: Update frontend (depends on API)
3. Execute updates in order, or in parallel within each level

---

## ⚡ Complete Update Orchestration

### Overview

Full end-to-end update execution with safety checks at every step.

### Update Process

The orchestrator executes updates in 9 carefully controlled steps:

#### Step 1: Pre-Update Validation
- Verify server connectivity
- Confirm container exists
- Check prerequisites

#### Step 2: Create Backup
- Save current container configuration
- Create volume snapshots (if configured)
- Store rollback information

#### Step 3: Pull New Image
- Download the new Docker image
- Verify image integrity
- Track download progress

#### Step 4: Stop Old Container
- Gracefully stop current container
- Wait for clean shutdown
- Force stop if timeout reached

#### Step 5: Remove Old Container
- Remove stopped container
- Preserve named volumes
- Clean up temporary resources

#### Step 6: Create New Container
- Create container with same configuration
- Use new image version
- Apply any configuration changes

#### Step 7: Start New Container
- Start the new container
- Wait for initialization
- Monitor startup logs

#### Step 8: Health Checks
- Run comprehensive health checks
- Multiple attempts with backoff
- Automatic rollback on failure

#### Step 9: Complete
- Mark update as successful
- Update container record
- Send success notification
- Enable rollback option

### Example

```python
# The update is fully automated:
POST /api/v1/updates/{update_id}/execute

# Orchestrator handles everything:
# ✓ Backup created
# ✓ New image pulled
# ✓ Container replaced
# ✓ Health checks passed
# ✓ Ready for rollback if needed
```

---

## 🏥 Comprehensive Health Checks

### Health Check Types

#### 1. HTTP Health Checks
- Connects to container HTTP endpoint
- Validates response status code
- Measures response time
- Checks response content (optional)

**Auto-detection**: Finds containers with ports 80, 443, 8080, 3000, 5000, 8000

**Example Config:**
```json
{
  "health_check_type": "http",
  "health_check_url": "http://service:8080/health",
  "health_check_method": "GET",
  "health_check_expected_status": 200
}
```

#### 2. TCP Port Checks
- Attempts TCP connection to container port
- Measures connection time
- Validates port accessibility

**Example:**
```json
{
  "health_check_type": "tcp",
  "health_check_port": 5432
}
```

#### 3. Docker Native Checks
- Uses Docker's own health status
- Checks container state (running/stopped)
- Monitors exit codes
- Validates container hasn't crashed

**Always performed as baseline check**

#### 4. Custom Script Checks
- Execute custom health check scripts
- Support for complex validation logic
- Integration with external monitoring

```json
{
  "health_check_type": "custom",
  "custom_health_check_script": "curl localhost:8080/deep-health && check-db-connection"
}
```

### Resource Monitoring

Health checks also monitor resource usage:

- **CPU Usage**: Alerts if over threshold (default: 90%)
- **Memory Usage**: Tracks memory consumption
- **Network I/O**: Monitors traffic
- **Disk I/O**: Watches for bottlenecks

### Log Analysis

Automatically scans container logs for:
- Error patterns (`ERROR`, `Exception`, `Failed`)
- Warning patterns (`WARNING`, `WARN`)
- Critical issues (`FATAL`, `CRITICAL`)

**Critical errors trigger health check failure**

### Health Check API

```bash
# Manual health check
POST /api/v1/containers/{container_id}/health-check

# Get health check history
GET /api/v1/health-checks/{container_id}
```

---

## 🔄 Automatic Rollback

### Overview

When an update fails, the system automatically reverts to the previous version.

### Rollback Triggers

1. **Health Check Failure**: Container fails health checks after update
2. **Container Crashed**: New container won't start or immediately crashes
3. **High Error Rate**: Excessive errors in logs
4. **Resource Exhaustion**: CPU or memory maxed out
5. **Dependency Failure**: Required services unavailable
6. **Timeout**: Update takes too long
7. **Manual**: User-initiated rollback

### Rollback Process

#### Step 1: Stop Failed Container
- Stop the new (failing) container
- Force stop if necessary
- Remove failed container

#### Step 2: Restore Configuration
- Load previous container configuration
- Restore from backup if available
- Prepare rollback environment

#### Step 3: Pull Previous Image
- Ensure old image is available
- Re-download if needed

#### Step 4: Create Previous Container
- Recreate container with old image
- Use saved configuration
- Restore environment variables

#### Step 5: Start Previous Container
- Start the rolled-back container
- Monitor startup process

#### Step 6: Health Check
- Verify rolled-back container is healthy
- Confirm services restored

#### Step 7: Complete
- Mark rollback as successful
- Send notification
- Log rollback details

### Rollback API

#### Execute Rollback
```bash
POST /api/v1/rollback/{update_id}
{
  "reason": "manual",
  "notes": "Customer reported issues"
}
```

#### Check if Rollback Available
```bash
GET /api/v1/rollback/{update_id}/can-rollback
```

**Response:**
```json
{
  "can_rollback": true,
  "message": "Rollback available",
  "update_id": "update-123"
}
```

#### Get Rollback Details
```bash
GET /api/v1/rollback/{update_id}
```

**Response:**
```json
{
  "id": "rollback-123",
  "update_id": "update-123",
  "reason": "health_check_failed",
  "status": "completed",
  "successful": true,
  "rolled_back_from": "2.1.0",
  "rolled_back_to": "2.0.5",
  "duration_seconds": 45
}
```

### Rollback Guarantees

- ✓ **Configuration Preserved**: Previous settings restored exactly
- ✓ **Automatic Execution**: No manual intervention required
- ✓ **Health Verified**: Rollback verified before completion
- ✓ **Notification Sent**: Alerts sent on rollback
- ✓ **Fully Logged**: Complete audit trail

---

## 💾 Backup & Restore

### Backup Creation

Backups are created automatically before each update (if configured):

1. **Container Configuration**: All settings, environment vars, labels
2. **Volume List**: Names and mount points of all volumes
3. **Network Configuration**: Network attachments
4. **Port Mappings**: All published ports
5. **Metadata**: Creation time, version info

### Backup Storage

```
/var/lib/docker-orchestrator/backups/
├── server1/
│   ├── container1/
│   │   ├── container1_20240115_120000.tar.gz
│   │   ├── container1_20240114_120000.tar.gz
│   │   └── container1_20240113_120000.tar.gz
│   └── container2/
│       └── container2_20240115_120000.tar.gz
└── server2/
    └── ...
```

### Retention Policy

- Configurable retention period (default: 30 days)
- Automatic cleanup of old backups
- Keeps minimum number of backups per container

### Manual Backup/Restore

```bash
# Create backup
POST /api/v1/backups/create/{container_id}

# List backups
GET /api/v1/backups/{container_id}

# Restore from backup
POST /api/v1/backups/restore/{container_id}
{
  "backup_path": "/path/to/backup.tar.gz"
}
```

---

## 🎯 Putting It All Together

### Complete Update Workflow

1. **Discovery**: System scans servers and finds containers
2. **Dependency Analysis**: Builds dependency graph
3. **Update Detection**: Checks registries for new versions
4. **Changelog Analysis**: AI analyzes breaking changes
5. **User Review**: Dashboard shows pending updates with risk assessment
6. **Approval**: User approves update (or auto-approved if configured)
7. **Dependency Ordering**: System calculates update order
8. **Backup**: Creates backup of current state
9. **Orchestration**: Executes update with health checks
10. **Validation**: Comprehensive health checks
11. **Rollback** (if needed): Automatic rollback on failure
12. **Notification**: User notified of result

### Example Scenario

**You have a web app stack: nginx → api → postgres**

1. All three have updates available
2. System detects dependencies: `nginx depends on api depends on postgres`
3. Calculates update order:
   - Level 1: Update postgres first
   - Level 2: Update api
   - Level 3: Update nginx
4. For each update:
   - ✓ Backup created
   - ✓ New image pulled
   - ✓ Container replaced
   - ✓ Health checks run
   - ✓ If failure: automatic rollback
   - ✓ If success: continue to next
5. Result: All services updated safely with zero breaking changes

---

## 🔧 Configuration

### Enable Features

In `.env`:
```bash
# Enable automatic dependency analysis
DEPENDENCY_ANALYSIS_ENABLED=true

# Enable automatic rollback
ROLLBACK_ON_FAILURE=true

# Enable backups before updates
BACKUP_BEFORE_UPDATE=true
BACKUP_RETENTION_DAYS=30

# Health check settings
HEALTH_CHECK_TIMEOUT_SECONDS=300
HEALTH_CHECK_RETRIES=3
```

### Per-Service Configuration

Each service can override global settings:

```json
{
  "auto_update_enabled": true,
  "backup_before_update": true,
  "auto_rollback_enabled": true,
  "health_check_enabled": true,
  "health_check_type": "http",
  "health_check_url": "http://localhost:8080/health"
}
```

---

## 📊 Monitoring

### Celery Tasks

Monitor background tasks with Flower: `http://localhost:5555`

New tasks:
- `app.tasks.dependencies.analyze_all_dependencies`
- `app.tasks.updates.execute_update` (now uses orchestrator)
- Health check tasks (automatic)
- Rollback tasks (automatic)

### API Endpoints

New endpoints available at `http://localhost:8000/docs`:
- `/api/v1/dependencies/*`
- `/api/v1/rollback/*`
- `/api/v1/health-checks/*` (coming soon)
- `/api/v1/backups/*` (coming soon)

---

## 🎉 Benefits

With these new features, you get:

✅ **Zero Breaking Changes**: AI + dependency awareness prevents issues
✅ **Automatic Recovery**: Rollback on failure means no manual intervention
✅ **Complete Visibility**: Know exactly what depends on what
✅ **Safe Automation**: Health checks ensure updates succeed
✅ **Audit Trail**: Complete history of all updates and rollbacks
✅ **Time Savings**: Even more automated than before

**You can now confidently enable auto-updates for most services!**
