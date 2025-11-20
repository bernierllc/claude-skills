# Production Deployment Guide

## Overview

This guide covers deploying the Google Slides skill in production environments including server deployment, security hardening, performance optimization, monitoring, and operational procedures.

## Prerequisites

### Required

- Python 3.8+ production environment
- Google Cloud Project with Slides API enabled
- OAuth 2.0 credentials or Service Account
- SSL/TLS certificates for secure communication
- Monitoring infrastructure
- Backup system

### Optional

- ~~Anthropic API key~~ **No longer needed!** AI features work through Claude skill invocation
- Load balancer (for high availability)
- CDN (for static assets)
- Database (for usage tracking)

## Environment Setup

### Production Environment Configuration

#### 1. Create Production Directory Structure

```bash
/opt/gslides-production/
├── app/
│   ├── scripts/               # Application code
│   ├── templates/             # Brand templates
│   ├── auth/                  # Auth credentials (secure)
│   └── logs/                  # Application logs
├── config/
│   ├── production.env         # Environment variables
│   └── nginx.conf             # Web server config
├── backups/                   # Backup storage
└── monitoring/                # Monitoring configs
```

#### 2. Install Dependencies

```bash
cd /opt/gslides-production/app/

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install production dependencies
pip install -r requirements.txt

# Install production-only packages
pip install gunicorn supervisor redis celery
```

#### 3. Set File Permissions

```bash
# Application files: read-only for app user
chmod -R 755 /opt/gslides-production/app/scripts/
chmod -R 755 /opt/gslides-production/app/templates/

# Auth directory: restricted access
chmod 700 /opt/gslides-production/app/auth/
chmod 600 /opt/gslides-production/app/auth/*.json

# Logs: writable by app user
chmod 755 /opt/gslides-production/app/logs/
chown -R appuser:appuser /opt/gslides-production/app/logs/

# Config files: restricted
chmod 600 /opt/gslides-production/config/production.env
```

#### 4. Configure Environment Variables

Create `/opt/gslides-production/config/production.env`:

```bash
# Application
APP_ENV=production
APP_NAME=gslides-production
LOG_LEVEL=INFO

# Google Slides API
GOOGLE_CREDENTIALS_PATH=/opt/gslides-production/app/auth/credentials.json
GOOGLE_TOKEN_PATH=/opt/gslides-production/app/auth/token.json

# Anthropic API - NO LONGER NEEDED!
# Phase 5 AI features work through Claude skill invocation
# ANTHROPIC_API_KEY=not-required-anymore

# Database (if using)
DATABASE_URL=postgresql://user:pass@localhost/gslides_prod

# Redis (for caching/queuing)
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=generate-secure-random-key-here
ALLOWED_HOSTS=your-domain.com,api.your-domain.com

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60

# Monitoring
SENTRY_DSN=https://your-sentry-dsn
DATADOG_API_KEY=your-datadog-key
```

Load environment in application:

```python
# scripts/config.py
import os
from dotenv import load_dotenv

# Load production environment
if os.environ.get('APP_ENV') == 'production':
    load_dotenv('/opt/gslides-production/config/production.env')
else:
    load_dotenv()  # Development .env
```

## Security Considerations

### API Key Management

#### Never Store Keys in Code

**~~Wrong~~ (NO LONGER NEEDED!):**
```python
# Old way - no longer required
editor = GoogleSlidesEditor(anthropic_api_key='sk-ant-...')
```

**✅ New Way (Phase 5):**
```python
# Phase 5 works through Claude skill invocation
# No API key configuration needed!
editor = GoogleSlidesEditor()
# AI features work automatically through Claude
```

#### ~~Use Secret Management Service~~ (NO LONGER NEEDED FOR PHASE 5!)

**Phase 5 AI features no longer require secret management:**

```python
# Simply use the skill through Claude Code
editor = GoogleSlidesEditor()

# AI features work automatically - no secrets needed!
result = editor.generate_from_notes(notes, purpose, audience)
```

**Note**: Secret management still applies to:
- Google OAuth credentials (`credentials.json`)
- Google API tokens (`token.json`)
- Database passwords
- Other service credentials

But Anthropic API keys are no longer needed for Phase 5.

### OAuth in Production

#### Service Account (Recommended)

For server environments without browser access:

1. **Create Service Account** in Google Cloud Console:
   - Go to IAM & Admin → Service Accounts
   - Create service account with descriptive name
   - Download JSON key file

2. **Grant Access to Presentations**:
   - Share presentations with service account email
   - Grant "Editor" permissions

3. **Configure Application**:

```python
# scripts/auth_manager.py
from google.oauth2 import service_account

class ServiceAccountAuthManager:
    """Authenticate using service account."""

    SCOPES = [
        'https://www.googleapis.com/auth/presentations',
        'https://www.googleapis.com/auth/drive.file'
    ]

    def __init__(self, service_account_file):
        self.service_account_file = service_account_file

    def get_credentials(self):
        """Get credentials from service account."""
        credentials = service_account.Credentials.from_service_account_file(
            self.service_account_file,
            scopes=self.SCOPES
        )
        return credentials
```

Usage:
```python
from scripts.auth_manager import ServiceAccountAuthManager
from googleapiclient.discovery import build

auth = ServiceAccountAuthManager('/opt/gslides-production/app/auth/service-account.json')
creds = auth.get_credentials()
slides_service = build('slides', 'v1', credentials=creds)
```

#### OAuth with Token Management

For user-based access:

```python
# scripts/production_auth.py
import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

class ProductionAuthManager:
    """Manage OAuth tokens in production."""

    def __init__(self, token_path, credentials_path):
        self.token_path = token_path
        self.credentials_path = credentials_path

    def get_credentials(self):
        """Get valid credentials, refreshing if needed."""
        creds = None

        # Load existing token
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(
                self.token_path, SCOPES
            )

        # Refresh if expired
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Save refreshed token
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                # Log error and alert operations
                logger.error(f"Token refresh failed: {e}")
                # Trigger alert
                send_alert("OAuth token refresh failed")
                raise

        return creds
```

### Input Validation

Validate all inputs before processing:

```python
def validate_presentation_id(pres_id: str) -> str:
    """Validate presentation ID format."""
    import re

    # Google presentation IDs are alphanumeric with hyphens/underscores
    pattern = r'^[a-zA-Z0-9_-]+$'

    if not re.match(pattern, pres_id):
        raise ValueError(f"Invalid presentation ID: {pres_id}")

    if len(pres_id) < 20 or len(pres_id) > 100:
        raise ValueError(f"Presentation ID length invalid: {len(pres_id)}")

    return pres_id

def validate_color(color: str) -> str:
    """Validate hex color format."""
    import re

    pattern = r'^#[0-9A-Fa-f]{6}$'

    if not re.match(pattern, color):
        raise ValueError(f"Invalid hex color: {color}")

    return color
```

### Data Sanitization

Sanitize user-provided content:

```python
import html

def sanitize_text(text: str) -> str:
    """Sanitize text content for presentation."""
    # Escape HTML entities
    sanitized = html.escape(text)

    # Remove control characters
    sanitized = ''.join(char for char in sanitized if ord(char) >= 32 or char == '\n')

    # Limit length
    if len(sanitized) > 10000:
        raise ValueError("Text content too long")

    return sanitized
```

## Performance Optimization

### Caching Strategy

#### In-Memory Cache

```python
from functools import lru_cache
from datetime import datetime, timedelta

class CachedSlidesEditor:
    """Slides editor with caching."""

    def __init__(self):
        self.editor = GoogleSlidesEditor()
        self._presentation_cache = {}
        self._cache_ttl = timedelta(minutes=5)

    def get_presentation(self, pres_id: str):
        """Get presentation with caching."""
        cache_key = f"pres_{pres_id}"

        # Check cache
        if cache_key in self._presentation_cache:
            cached_data, cached_time = self._presentation_cache[cache_key]
            if datetime.now() - cached_time < self._cache_ttl:
                return cached_data

        # Fetch from API
        presentation = self.editor.get_presentation(pres_id)

        # Store in cache
        self._presentation_cache[cache_key] = (presentation, datetime.now())

        return presentation

    @lru_cache(maxsize=100)
    def load_brand_guidelines(self, filepath: str):
        """Cache brand guidelines."""
        return self.editor.load_brand_guidelines(filepath)
```

#### Redis Cache

```python
import redis
import json
from datetime import timedelta

class RedisCachedEditor:
    """Slides editor with Redis caching."""

    def __init__(self, redis_url='redis://localhost:6379/0'):
        self.editor = GoogleSlidesEditor()
        self.redis_client = redis.from_url(redis_url)
        self.cache_ttl = 300  # 5 minutes

    def get_presentation(self, pres_id: str):
        """Get presentation with Redis cache."""
        cache_key = f"presentation:{pres_id}"

        # Try cache first
        cached = self.redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        # Fetch from API
        presentation = self.editor.get_presentation(pres_id)

        # Cache result
        self.redis_client.setex(
            cache_key,
            self.cache_ttl,
            json.dumps(presentation)
        )

        return presentation
```

### Batch Operations

Optimize API calls by batching:

```python
def create_slides_batch(pres_id: str, slide_configs: List[Dict]):
    """Create multiple slides in single batch."""
    editor = GoogleSlidesEditor()

    requests = []
    for config in slide_configs:
        request = {
            'createSlide': {
                'slideLayoutReference': {
                    'layoutId': config.get('layout_id')
                },
                'insertionIndex': config.get('index')
            }
        }
        requests.append(request)

    # Single API call for all slides
    response = editor.batch_update(pres_id, requests)

    return response
```

### Connection Pooling

Reuse API connections:

```python
from googleapiclient.discovery import build
from googleapiclient.http import HttpRequest
import httplib2

class PooledSlidesService:
    """Slides service with connection pooling."""

    def __init__(self, credentials):
        # Create HTTP client with connection pooling
        http = httplib2.Http(
            timeout=30,
            # Enable connection reuse
            disable_ssl_certificate_validation=False
        )

        # Build service with pooled connections
        self.service = build(
            'slides', 'v1',
            credentials=credentials,
            http=http,
            cache_discovery=False  # Disable for production
        )

    def get_service(self):
        """Get pooled service instance."""
        return self.service
```

### Rate Limiting

Implement client-side rate limiting:

```python
import time
from collections import deque
from threading import Lock

class RateLimiter:
    """Rate limiter for API calls."""

    def __init__(self, max_requests=60, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self.lock = Lock()

    def acquire(self):
        """Acquire permission to make API call."""
        with self.lock:
            now = time.time()

            # Remove old requests outside time window
            while self.requests and self.requests[0] < now - self.time_window:
                self.requests.popleft()

            # Check if under limit
            if len(self.requests) >= self.max_requests:
                # Calculate wait time
                wait_time = self.requests[0] + self.time_window - now
                time.sleep(wait_time)

            # Record this request
            self.requests.append(now)

# Usage
rate_limiter = RateLimiter(max_requests=60, time_window=60)

def create_presentation_rate_limited(title):
    rate_limiter.acquire()
    return editor.create_presentation(title)
```

## Error Handling

### Production Error Handler

```python
import logging
import traceback
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class ProductionErrorHandler:
    """Handle errors in production."""

    def __init__(self, alert_service=None):
        self.alert_service = alert_service

    def handle_api_error(self, error: Exception, context: Dict[str, Any]) -> Optional[Dict]:
        """Handle Google API errors."""
        from googleapiclient.errors import HttpError

        if isinstance(error, HttpError):
            status = error.resp.status

            # Log error with context
            logger.error(
                f"API Error {status}: {error}",
                extra={
                    'status_code': status,
                    'context': context,
                    'traceback': traceback.format_exc()
                }
            )

            # Handle specific errors
            if status == 403:
                # Permission denied
                logger.critical("Permission denied - check OAuth scopes")
                if self.alert_service:
                    self.alert_service.send_critical("OAuth permission error")
                return {'error': 'permission_denied', 'retry': False}

            elif status == 429:
                # Rate limit
                logger.warning("Rate limit exceeded - implementing backoff")
                return {'error': 'rate_limit', 'retry': True, 'backoff': 60}

            elif status == 500 or status == 503:
                # Server error - retry
                logger.warning(f"Server error {status} - will retry")
                return {'error': 'server_error', 'retry': True, 'backoff': 30}

            else:
                # Unknown error
                logger.error(f"Unknown API error: {status}")
                return {'error': 'unknown', 'retry': False}

        # Non-API error
        logger.exception("Unexpected error", extra={'context': context})
        return {'error': 'unexpected', 'retry': False}

# Usage
error_handler = ProductionErrorHandler(alert_service=AlertService())

try:
    result = editor.create_presentation('Test')
except Exception as e:
    error_info = error_handler.handle_api_error(e, {'operation': 'create_presentation'})
    if error_info.get('retry'):
        # Implement retry logic
        time.sleep(error_info.get('backoff', 10))
        # Retry operation
```

### Retry Logic with Exponential Backoff

```python
import time
from functools import wraps

def retry_with_backoff(max_retries=3, base_delay=1, max_delay=60):
    """Decorator for retry logic with exponential backoff."""

    def decorator(func):
        @wraps(func):
        def wrapper(*args, **kwargs):
            retries = 0

            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1

                    if retries >= max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}")
                        raise

                    # Calculate backoff with jitter
                    delay = min(base_delay * (2 ** retries), max_delay)
                    jitter = delay * 0.1 * (2 * (time.time() % 1) - 1)  # ±10%
                    wait_time = delay + jitter

                    logger.warning(
                        f"Retry {retries}/{max_retries} for {func.__name__} "
                        f"after {wait_time:.1f}s (error: {e})"
                    )

                    time.sleep(wait_time)

        return wrapper
    return decorator

# Usage
@retry_with_backoff(max_retries=3, base_delay=2)
def create_presentation_with_retry(title):
    return editor.create_presentation(title)
```

## Monitoring

### Logging Configuration

```python
# scripts/logging_config.py
import logging
import logging.handlers
import sys

def setup_production_logging(log_dir='/opt/gslides-production/app/logs'):
    """Configure production logging."""

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s - '
        '[%(filename)s:%(lineno)d]'
    )

    json_formatter = logging.Formatter(
        '{"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", '
        '"message": "%(message)s", "file": "%(filename)s", "line": %(lineno)d}'
    )

    # Console handler (errors only)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.ERROR)
    console_handler.setFormatter(detailed_formatter)

    # File handler (all logs)
    file_handler = logging.handlers.RotatingFileHandler(
        f'{log_dir}/app.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=10
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(detailed_formatter)

    # JSON handler (for log aggregation)
    json_handler = logging.handlers.RotatingFileHandler(
        f'{log_dir}/app.json.log',
        maxBytes=10*1024*1024,
        backupCount=10
    )
    json_handler.setLevel(logging.INFO)
    json_handler.setFormatter(json_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(json_handler)

    return root_logger
```

### Application Metrics

```python
# scripts/metrics.py
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

@dataclass
class Metrics:
    """Track application metrics."""

    api_calls: int = 0
    presentations_created: int = 0
    errors: int = 0
    response_times: List[float] = field(default_factory=list)
    last_reset: datetime = field(default_factory=datetime.now)

    def record_api_call(self, duration: float):
        """Record API call metrics."""
        self.api_calls += 1
        self.response_times.append(duration)

    def record_error(self):
        """Record error occurrence."""
        self.errors += 1

    def get_stats(self) -> Dict:
        """Get current statistics."""
        avg_response = sum(self.response_times) / len(self.response_times) if self.response_times else 0

        return {
            'api_calls': self.api_calls,
            'presentations_created': self.presentations_created,
            'errors': self.errors,
            'error_rate': self.errors / self.api_calls if self.api_calls > 0 else 0,
            'avg_response_time': avg_response,
            'uptime_seconds': (datetime.now() - self.last_reset).total_seconds()
        }

# Usage
metrics = Metrics()

def create_presentation_with_metrics(title):
    start = time.time()
    try:
        result = editor.create_presentation(title)
        metrics.presentations_created += 1
        return result
    except Exception as e:
        metrics.record_error()
        raise
    finally:
        duration = time.time() - start
        metrics.record_api_call(duration)
```

### Health Checks

```python
# scripts/health_check.py
from flask import Flask, jsonify
import logging

app = Flask(__name__)
logger = logging.getLogger(__name__)

@app.route('/health')
def health_check():
    """Basic health check endpoint."""
    return jsonify({'status': 'healthy', 'service': 'gslides-skill'})

@app.route('/health/detailed')
def detailed_health_check():
    """Detailed health check with dependencies."""
    health = {
        'status': 'healthy',
        'checks': {}
    }

    # Check Google API connectivity
    try:
        editor = GoogleSlidesEditor()
        # Simple API call to verify connectivity
        health['checks']['google_api'] = 'healthy'
    except Exception as e:
        logger.error(f"Google API health check failed: {e}")
        health['checks']['google_api'] = 'unhealthy'
        health['status'] = 'degraded'

    # Check Anthropic API (if configured)
    if os.environ.get('ANTHROPIC_API_KEY'):
        try:
            # Could make test API call here
            health['checks']['anthropic_api'] = 'healthy'
        except Exception as e:
            logger.error(f"Anthropic API health check failed: {e}")
            health['checks']['anthropic_api'] = 'unhealthy'
            health['status'] = 'degraded'

    # Check Redis (if configured)
    if os.environ.get('REDIS_URL'):
        try:
            redis_client.ping()
            health['checks']['redis'] = 'healthy'
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            health['checks']['redis'] = 'unhealthy'

    return jsonify(health)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

## Scaling Considerations

### Horizontal Scaling

Deploy multiple instances behind load balancer:

```nginx
# /opt/gslides-production/config/nginx.conf
upstream gslides_backend {
    least_conn;
    server 10.0.1.10:8000 weight=1 max_fails=3 fail_timeout=30s;
    server 10.0.1.11:8000 weight=1 max_fails=3 fail_timeout=30s;
    server 10.0.1.12:8000 weight=1 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name api.your-domain.com;

    location / {
        proxy_pass http://gslides_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /health {
        proxy_pass http://gslides_backend/health;
        access_log off;
    }
}
```

### Async Processing

Use Celery for background tasks:

```python
# scripts/tasks.py
from celery import Celery

app = Celery('gslides_tasks', broker='redis://localhost:6379/0')

@app.task
def generate_presentation_async(notes, purpose, audience):
    """Generate presentation in background."""
    editor = GoogleSlidesEditor()

    result = editor.generate_from_notes(
        notes=notes,
        purpose=purpose,
        audience=audience
    )

    return result

# Usage
from scripts.tasks import generate_presentation_async

# Queue task
task = generate_presentation_async.delay(notes, purpose, audience)

# Check status
if task.ready():
    result = task.get()
```

## Cost Management

### Track API Usage

```python
# scripts/usage_tracker.py
import logging
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)

class UsageTracker:
    """Track API usage and costs."""

    def __init__(self):
        self.usage = {
            'google_api_calls': 0,
            'presentations_created': 0,
            'phase5_ai_calls': 0  # FREE through Claude!
        }

    def record_google_api_call(self):
        """Record Google API call."""
        self.usage['google_api_calls'] += 1

    def record_phase5_usage(self):
        """Record Phase 5 AI usage (FREE through Claude)."""
        self.usage['phase5_ai_calls'] += 1

    def get_costs(self) -> Dict:
        """Calculate current costs."""
        return {
            'google_api_calls': self.usage['google_api_calls'],
            'google_api_cost': 0,  # Free tier
            'phase5_ai_calls': self.usage['phase5_ai_calls'],
            'phase5_cost_usd': 0,  # FREE through Claude!
            'total_cost_usd': 0,  # Only Google API (free tier)
            'presentations_created': self.usage['presentations_created']
        }

    def log_costs(self):
        """Log current costs."""
        costs = self.get_costs()
        logger.info(
            f"API Usage - Google: {costs['google_api_calls']} calls, "
            f"Phase 5 AI: {costs['phase5_ai_calls']} calls (FREE through Claude)"
        )

# Global tracker
usage_tracker = UsageTracker()
```

### ~~Cost Optimization~~ (NO LONGER NEEDED FOR PHASE 5!)

**Phase 5 AI features are FREE** through Claude skill invocation:

```python
# Simply use Phase 5 features - no cost management needed!
result = editor.generate_from_notes(notes, purpose, audience)

# Track usage for metrics only (not costs)
usage_tracker.record_phase5_usage()
```

**Note**: Only Google Slides API has quotas. Phase 5 AI features have no external costs!

## Maintenance

### Backup Procedures

```bash
#!/bin/bash
# /opt/gslides-production/scripts/backup.sh

BACKUP_DIR="/opt/gslides-production/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup auth credentials
tar -czf "$BACKUP_DIR/auth_$DATE.tar.gz" /opt/gslides-production/app/auth/

# Backup configuration
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" /opt/gslides-production/config/

# Backup templates
tar -czf "$BACKUP_DIR/templates_$DATE.tar.gz" /opt/gslides-production/app/templates/

# Clean up old backups (keep 30 days)
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

### Update Procedures

```bash
#!/bin/bash
# /opt/gslides-production/scripts/update.sh

# Activate virtual environment
source /opt/gslides-production/app/venv/bin/activate

# Pull latest code
cd /opt/gslides-production/app/
git pull origin main

# Update dependencies
pip install -r requirements.txt --upgrade

# Run tests
python -m pytest tests/

# Restart services
sudo supervisorctl restart gslides-app

echo "Update completed"
```

## Support

### Operational Runbook

Located in: `/opt/gslides-production/docs/runbook.md`

#### Common Issues

**Issue: OAuth Token Expired**
- Symptom: 401 errors on API calls
- Resolution: Refresh token or re-authenticate
- Command: `python scripts/refresh_token.py`

**Issue: Rate Limit Exceeded**
- Symptom: 429 errors
- Resolution: Implement backoff, check rate limiting
- Command: Check `usage_tracker.get_stats()`

**~~Issue: High API Costs~~ (NO LONGER APPLICABLE!)**
- Phase 5 AI features are FREE through Claude skill invocation
- No Anthropic costs to manage
- Only Google Slides API quotas apply (free tier)

### Monitoring Dashboards

Set up in monitoring tool (Datadog, Grafana, etc.):

- API call rate
- Error rate
- Response times
- Cost per presentation
- Active users
- Health check status

### Alerting

Configure alerts for:

- **Critical**: Service down, OAuth failure, cost limit exceeded
- **Warning**: High error rate (>5%), slow response times (>5s)
- **Info**: Daily usage reports, cost reports

## Deployment Checklist

### Pre-Deployment

- [ ] All tests passing
- [ ] Dependencies updated
- [ ] Security review completed
- [ ] OAuth credentials configured
- [ ] Environment variables set
- [ ] Monitoring configured
- [ ] Backup procedures tested
- [ ] Load testing completed
- [ ] Documentation updated

### Deployment

- [ ] Backup current production
- [ ] Deploy new code
- [ ] Restart services
- [ ] Run health checks
- [ ] Monitor error rates
- [ ] Verify functionality
- [ ] Check logs for issues

### Post-Deployment

- [ ] Monitor for 24 hours
- [ ] Validate metrics normal
- [ ] Verify alerts working
- [ ] Document any issues
- [ ] Update runbook if needed

## Conclusion

This guide provides a foundation for production deployment. Adapt procedures to your specific infrastructure and requirements. Always prioritize security, monitoring, and cost management in production environments.

For additional support:
- Review `SKILL.md` for feature documentation
- Check `TESTING.md` for quality procedures
- Consult Google Slides API documentation
- Monitor application logs and metrics
