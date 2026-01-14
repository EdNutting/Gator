# Configuration and Deployment Improvements

**Priority Level:** MEDIUM
**Estimated Effort:** 1-2 weeks
**Action:** Improve deployment and operational readiness

---

## Table of Contents

1. [Configuration Management](#1-configuration-management)
2. [Environment Configuration](#2-environment-configuration)
3. [Deployment Options](#3-deployment-options)
4. [CI/CD Pipeline](#4-cicd-pipeline)
5. [Monitoring and Observability](#5-monitoring-and-observability)
6. [Production Readiness](#6-production-readiness)

---

## 1. Configuration Management

### Issue 1.1: No Configuration File Support
**Priority:** Medium | **Effort:** Small | **Value:** High

**Current Limitation:**
All configuration is via CLI arguments or environment variables, making complex setups difficult.

**Recommended Implementation:**

```python
# gator/config.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any
import yaml

@dataclass
class GatorConfig:
    """Gator configuration"""

    # Execution
    concurrency: int = field(default_factory=lambda: os.cpu_count() or 4)
    tracking_dir: Path = Path(".gator")

    # Logging
    log_level: str = "INFO"
    log_max_warnings: int = 100
    log_max_errors: int = 100

    # Scheduling
    scheduler: str = "local"
    scheduler_opts: Dict[str, Any] = field(default_factory=dict)

    # Hub
    hub_url: Optional[str] = None
    hub_token: Optional[str] = None

    # Monitoring
    heartbeat_interval: float = 1.0
    monitor_interval: float = 1.0

    @classmethod
    def from_file(cls, path: Path) -> 'GatorConfig':
        """Load configuration from YAML file"""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def from_env(cls) -> 'GatorConfig':
        """Load configuration from environment variables"""
        return cls(
            concurrency=int(os.getenv('GATOR_CONCURRENCY', os.cpu_count() or 4)),
            tracking_dir=Path(os.getenv('GATOR_TRACKING_DIR', '.gator')),
            log_level=os.getenv('GATOR_LOG_LEVEL', 'INFO'),
            scheduler=os.getenv('GATOR_SCHEDULER', 'local'),
            hub_url=os.getenv('GATOR_HUB_URL'),
            hub_token=os.getenv('GATOR_HUB_TOKEN'),
        )

    def save(self, path: Path) -> None:
        """Save configuration to YAML file"""
        with open(path, 'w') as f:
            yaml.dump(asdict(self), f, default_flow_style=False)
```

**Usage:**
```yaml
# .gatorrc.yaml
concurrency: 8
tracking_dir: /var/gator/tracking
log_level: DEBUG

scheduler: slurm
scheduler_opts:
  url: http://slurm-rest:8080
  username: gator
  token_file: /secrets/slurm-token

hub_url: http://hub:8080
hub_token_file: /secrets/hub-token

monitoring:
  heartbeat_interval: 2.0
  monitor_interval: 5.0
```

```bash
# CLI usage
gator run job.yaml --config .gatorrc.yaml

# Or use default location
gator run job.yaml  # Loads .gatorrc.yaml if present
```

---

### Issue 1.2: Configuration Hierarchy
**Priority:** Medium | **Effort:** Small | **Value:** Medium

**Recommended Priority:**
1. CLI arguments (highest priority)
2. Environment variables
3. Configuration file (~/.gatorrc.yaml)
4. Project config (./gatorrc.yaml)
5. System defaults (lowest priority)

**Implementation:**
```python
def load_config(cli_args: Dict[str, Any]) -> GatorConfig:
    """Load configuration with proper precedence"""
    # Start with defaults
    config = GatorConfig()

    # Load system config if exists
    system_config = Path("/etc/gator/config.yaml")
    if system_config.exists():
        config = GatorConfig.from_file(system_config)

    # Load user config if exists
    user_config = Path.home() / ".gatorrc.yaml"
    if user_config.exists():
        config.update(GatorConfig.from_file(user_config))

    # Load project config if exists
    project_config = Path(".gatorrc.yaml")
    if project_config.exists():
        config.update(GatorConfig.from_file(project_config))

    # Load from environment
    config.update(GatorConfig.from_env())

    # CLI arguments override everything
    config.update(cli_args)

    return config
```

---

## 2. Environment Configuration

### Issue 2.1: Environment Variable Documentation
**Priority:** Medium | **Effort:** Small | **Value:** High

**Create comprehensive documentation:**

```markdown
# Environment Variables

## Execution
- `GATOR_CONCURRENCY`: Max concurrent jobs (default: CPU count)
- `GATOR_TRACKING_DIR`: Job tracking directory (default: .gator)

## Logging
- `GATOR_LOG_LEVEL`: Log level DEBUG|INFO|WARNING|ERROR (default: INFO)
- `GATOR_LOG_FILE`: Optional log file path
- `GATOR_VERBOSE`: Enable verbose logging (default: false)

## Scheduling
- `GATOR_SCHEDULER`: Scheduler type local|slurm (default: local)
- `GATOR_SLURM_URL`: Slurm REST API URL
- `GATOR_SLURM_USER`: Slurm username
- `GATOR_SLURM_TOKEN`: Slurm API token

## Hub
- `GATOR_HUB_URL`: Hub URL for job registration
- `GATOR_HUB_TOKEN`: Authentication token for Hub

## Internal (set by Gator)
- `GATOR_PARENT`: Parent WebSocket address
- `GATOR_ARRAY_INDEX`: Array job iteration index
- `GATOR_SEED`: Random seed for reproducibility

## Database (Hub)
- `GATOR_DB_HOST`: PostgreSQL host
- `GATOR_DB_PORT`: PostgreSQL port
- `GATOR_DB_NAME`: Database name
- `GATOR_DB_USER`: Database user
- `GATOR_DB_PASSWORD`: Database password

## Security
- `GATOR_AUTH_ENABLED`: Enable authentication (default: false)
- `GATOR_API_KEY`: API key for Hub access
- `GATOR_JWT_SECRET`: JWT secret for token generation
```

### Issue 2.2: .env File Support
**Priority:** Low-Medium | **Effort:** Small | **Value:** Medium

**Implementation:**
```python
# Use python-dotenv
from dotenv import load_dotenv

def setup_environment():
    """Load environment from .env file"""
    # Load from .env if present
    env_file = Path(".env")
    if env_file.exists():
        load_dotenv(env_file)

    # Validate required variables
    required = ['GATOR_DB_PASSWORD'] if hub_enabled else []
    for var in required:
        if not os.getenv(var):
            raise RuntimeError(f"Required environment variable {var} not set")
```

**Example .env:**
```bash
# .env
GATOR_LOG_LEVEL=DEBUG
GATOR_TRACKING_DIR=/var/gator
GATOR_HUB_URL=http://localhost:8080
GATOR_DB_PASSWORD=secure_password_here
```

---

## 3. Deployment Options

### Option 3.1: Docker Containerization
**Priority:** Medium | **Effort:** Medium | **Value:** High

**Create Dockerfile:**
```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create gator user
RUN useradd -m -s /bin/bash gator

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install Poetry
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction --no-ansi

# Copy application
COPY gator ./gator
COPY examples ./examples

# Set ownership
RUN chown -R gator:gator /app

# Switch to gator user
USER gator

# Default command
ENTRYPOINT ["python", "-m", "gator"]
CMD ["--help"]
```

**Docker Compose for Hub:**
```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: gator
      POSTGRES_PASSWORD: ${GATOR_DB_PASSWORD}
      POSTGRES_DB: gator
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  hub:
    build: .
    command: poetry run poe hub
    environment:
      GATOR_DB_HOST: postgres
      GATOR_DB_PORT: 5432
      GATOR_DB_USER: gator
      GATOR_DB_PASSWORD: ${GATOR_DB_PASSWORD}
      GATOR_DB_NAME: gator
    ports:
      - "8080:8080"
    depends_on:
      - postgres
    volumes:
      - hub_data:/var/gator

  gator-worker:
    build: .
    command: python -m gator /jobs/spec.yaml --hub hub:8080
    environment:
      GATOR_HUB_URL: http://hub:8080
    volumes:
      - ./jobs:/jobs
      - worker_data:/var/gator
    depends_on:
      - hub

volumes:
  postgres_data:
  hub_data:
  worker_data:
```

**Build and run:**
```bash
# Build image
docker build -t gator:latest .

# Run single job
docker run -v $(pwd)/examples:/examples gator:latest /examples/job.yaml

# Run with Hub
docker-compose up -d
```

---

### Option 3.2: Kubernetes Deployment
**Priority:** Low-Medium | **Effort:** Large | **Value:** High for enterprise

**Create Kubernetes manifests:**

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: gator

---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: gator-config
  namespace: gator
data:
  config.yaml: |
    log_level: INFO
    concurrency: 4
    scheduler: local

---
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: gator-secrets
  namespace: gator
type: Opaque
stringData:
  db-password: your-secure-password
  hub-token: your-hub-token

---
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gator-hub
  namespace: gator
spec:
  replicas: 1
  selector:
    matchLabels:
      app: gator-hub
  template:
    metadata:
      labels:
        app: gator-hub
    spec:
      containers:
      - name: hub
        image: gator:latest
        command: ["poetry", "run", "poe", "hub"]
        ports:
        - containerPort: 8080
        env:
        - name: GATOR_DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: gator-secrets
              key: db-password
        volumeMounts:
        - name: config
          mountPath: /etc/gator
        - name: data
          mountPath: /var/gator
      volumes:
      - name: config
        configMap:
          name: gator-config
      - name: data
        persistentVolumeClaim:
          claimName: gator-data-pvc

---
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: gator-hub
  namespace: gator
spec:
  selector:
    app: gator-hub
  ports:
  - port: 8080
    targetPort: 8080
  type: LoadBalancer
```

**Deploy:**
```bash
kubectl apply -f k8s/
kubectl get pods -n gator
kubectl logs -f -n gator deployment/gator-hub
```

---

### Option 3.3: Systemd Service
**Priority:** Medium | **Effort:** Small | **Value:** Medium for servers

**Create service file:**
```ini
# /etc/systemd/system/gator-hub.service
[Unit]
Description=Gator Hub Service
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=gator
Group=gator
WorkingDirectory=/opt/gator
Environment="PATH=/opt/gator/.venv/bin:/usr/local/bin:/usr/bin"
EnvironmentFile=/etc/gator/environment
ExecStart=/opt/gator/.venv/bin/python -m gator.hub.app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Environment file:**
```bash
# /etc/gator/environment
GATOR_DB_HOST=localhost
GATOR_DB_PORT=5432
GATOR_DB_USER=gator
GATOR_DB_PASSWORD=secure_password
GATOR_DB_NAME=gator
GATOR_LOG_LEVEL=INFO
```

**Install and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable gator-hub
sudo systemctl start gator-hub
sudo systemctl status gator-hub
```

---

## 4. CI/CD Pipeline

### Issue 4.1: Comprehensive CI Pipeline
**Priority:** High | **Effort:** Medium | **Value:** High

**Already covered in [06-testing-improvements.md](06-testing-improvements.md#51-github-actions-workflow)**

Additional recommendations:
- Add deployment jobs
- Add release automation
- Add changelog generation

**Release Workflow:**
```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build package
        run: |
          poetry build

      - name: Publish to PyPI
        env:
          POETRY_PYPI_TOKEN_PYPI: ${{ secrets.PYPI_TOKEN }}
        run: poetry publish

      - name: Create GitHub Release
        uses: actions/create-release@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          tag_name: ${{ github.ref }}
          release_name: Release ${{ github.ref }}
          draft: false
          prerelease: false

      - name: Build Docker image
        run: |
          docker build -t gator:${{ github.ref_name }} .
          docker tag gator:${{ github.ref_name }} gator:latest

      - name: Push to Docker Hub
        env:
          DOCKER_USERNAME: ${{ secrets.DOCKER_USERNAME }}
          DOCKER_PASSWORD: ${{ secrets.DOCKER_PASSWORD }}
        run: |
          echo $DOCKER_PASSWORD | docker login -u $DOCKER_USERNAME --password-stdin
          docker push gator:${{ github.ref_name }}
          docker push gator:latest
```

---

## 5. Monitoring and Observability

### Issue 5.1: Health Check Endpoints
**Priority:** Medium | **Effort:** Small | **Value:** High

**Add to Hub:**
```python
# gator/hub/app.py
@app.route('/health')
async def health_check():
    """Health check endpoint for load balancers"""
    try:
        # Check database connection
        await db.execute("SELECT 1")

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 503

@app.route('/ready')
async def readiness_check():
    """Readiness check for Kubernetes"""
    # Check if fully initialized
    if not app_initialized:
        return jsonify({'status': 'not ready'}), 503
    return jsonify({'status': 'ready'}), 200

@app.route('/metrics')
async def metrics():
    """Prometheus metrics endpoint"""
    return generate_prometheus_metrics()
```

### Issue 5.2: Structured Logging
**Priority:** Low-Medium | **Effort:** Medium | **Value:** Medium

**Add structured logging option:**
```python
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Usage
log = structlog.get_logger()
log.info("job_started", job_id="job123", command="python script.py")
```

---

## 6. Production Readiness

### Checklist 6.1: Production Deployment Readiness

#### Security
- [ ] Remove hardcoded credentials
- [ ] Implement authentication
- [ ] Use secrets management (Vault, K8s secrets)
- [ ] Enable HTTPS/TLS
- [ ] Set up firewall rules
- [ ] Regular security audits

#### Monitoring
- [ ] Health check endpoints
- [ ] Prometheus metrics export
- [ ] Error alerting (PagerDuty, etc.)
- [ ] Log aggregation (ELK, Splunk)
- [ ] Performance dashboards

#### Reliability
- [ ] Database backups automated
- [ ] Disaster recovery plan
- [ ] High availability setup
- [ ] Load balancing configured
- [ ] Rate limiting enabled

#### Operations
- [ ] Deployment automation
- [ ] Rollback procedures
- [ ] Runbooks for common issues
- [ ] On-call rotation setup
- [ ] Incident response plan

#### Documentation
- [ ] Deployment guide
- [ ] Operations manual
- [ ] Troubleshooting guide
- [ ] Architecture documentation
- [ ] API documentation

---

## Summary Table

| Area | Priority | Effort | Value | Status |
|------|----------|--------|-------|--------|
| Config file support | Medium | Small | High | TODO |
| Env var docs | Medium | Small | High | TODO |
| Docker setup | Medium | Medium | High | TODO |
| K8s deployment | Low-Medium | Large | High | TODO |
| CI/CD pipeline | High | Medium | High | Partial |
| Health checks | Medium | Small | High | TODO |
| Production checklist | High | Ongoing | Critical | TODO |

**Total Effort:** 1-2 weeks for basic deployment setup

**Priority Order:**
1. Configuration file support
2. Environment variable documentation
3. Docker containerization
4. CI/CD enhancement
5. Health check endpoints
6. Production hardening
7. Kubernetes deployment (if needed)

---

*Production readiness is a journey, not a destination. Implement incrementally.*
