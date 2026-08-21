# Production Deployment Guide

Complete guide for deploying Shop Chatbot Socket Server to production.

---

## 📋 Pre-Deployment Checklist

### **1. Security**
- [ ] Generate and set `API_KEY` in .env
- [ ] Restrict `CORS_ORIGINS` to your domain
- [ ] Enable rate limiting (`RATE_LIMIT_ENABLED=True`)
- [ ] Review and adjust rate limits
- [ ] Ensure `.env` is in `.gitignore`
- [ ] Remove any hardcoded credentials

### **2. Configuration**
- [ ] Set `SOCKET_DEBUG=False`
- [ ] Configure `LOG_LEVEL=INFO` or `WARNING`
- [ ] Set up log rotation for `logs/socket_server.log`
- [ ] Configure Redis for checkpointer
- [ ] Configure PostgreSQL for conversation data

### **3. Infrastructure**
- [ ] Set up Redis (persistent, not just cache)
- [ ] Set up PostgreSQL database
- [ ] Set up Langfuse (optional but recommended)
- [ ] Configure firewall rules
- [ ] Set up SSL/TLS certificates (if external)
- [ ] Set up monitoring and alerting

### **4. Testing**
- [ ] Test all socket events
- [ ] Load test with expected concurrent users
- [ ] Test rate limiting
- [ ] Test API key authentication
- [ ] Test error scenarios
- [ ] Verify logs are being written

---

## 🔐 Security Configuration

### **Step 1: Generate API Key**

```bash
python generate_api_key.py
```

Copy output to `.env`:
```env
API_KEY=your-generated-key-here
```

### **Step 2: Restrict CORS**

Edit `.env`:
```env
# Development
CORS_ORIGINS=*

# Production - restrict to your domains
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

### **Step 3: Configure Rate Limits**

Edit `.env`:
```env
# Rate limiting (adjust based on your needs)
RATE_LIMIT_ENABLED=True
RATE_LIMIT_DEFAULT=100 per minute
RATE_LIMIT_CHAT=20 per minute
```

**Guidelines:**
- `RATE_LIMIT_DEFAULT`: For general HTTP endpoints (health, stats, metrics)
- `RATE_LIMIT_CHAT`: For chat messages (adjust based on expected usage)
- Start conservative, increase if needed
- Monitor rate limit hits in logs

---

## 🚀 Deployment Options

### **Option 1: Direct Python (Simple)**

**Pros:** Simple, good for small deployments  
**Cons:** Single process, manual management

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set production environment variables
export SOCKET_DEBUG=False
export LOG_LEVEL=INFO

# 3. Start server
python -m app.socket_server
```

**Process Management with systemd:**

Create `/etc/systemd/system/shop-chatbot-socket.service`:

```ini
[Unit]
Description=Shop Chatbot Socket Server
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/shop-langgraph
Environment="PATH=/var/www/shop-langgraph/.venv/bin"
EnvironmentFile=/var/www/shop-langgraph/.env
ExecStart=/var/www/shop-langgraph/.venv/bin/python -m app.socket_server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable shop-chatbot-socket
sudo systemctl start shop-chatbot-socket
sudo systemctl status shop-chatbot-socket
```

---

### **Option 2: Docker (Recommended)**

**Pros:** Isolated, reproducible, easy to scale  
**Cons:** More complex setup

**Create `Dockerfile`:**

```dockerfile
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY .env .env

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:5000/health')"

# Run server
CMD ["python", "-m", "app.socket_server"]
```

**Create `docker-compose.yml`:**

```yaml
version: '3.8'

services:
  socket-server:
    build: .
    ports:
      - "5000:5000"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - DATABASE_URL=postgresql://user:pass@postgres:5432/shopdb
      - REDIS_URL=redis://redis:6379
      - LANGFUSE_HOST=http://langfuse:3000
      - LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}
      - LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY}
      - SOCKET_HOST=0.0.0.0
      - SOCKET_PORT=5000
      - SOCKET_DEBUG=False
      - CORS_ORIGINS=${CORS_ORIGINS}
      - RATE_LIMIT_ENABLED=True
      - API_KEY=${API_KEY}
      - LOG_LEVEL=INFO
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: shopdb
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  redis_data:
  postgres_data:
```

**Deploy:**

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f socket-server

# Stop
docker-compose down
```

---

### **Option 3: Kubernetes (Enterprise)**

**Pros:** Auto-scaling, high availability, cloud-native  
**Cons:** Complex, overkill for small deployments

**See `k8s/` directory for manifests** (not included in this guide)

---

## 📊 Monitoring

### **1. Health Check**

```bash
# Basic health check
curl -H "X-API-Key: your-api-key" http://localhost:5000/health

# Expected response:
{
  "status": "ok",
  "service": "shop-chatbot-socket",
  "version": "1.0.0",
  "langfuse_enabled": true,
  "rate_limiting": true
}
```

### **2. Stats Endpoint**

```bash
curl -H "X-API-Key: your-api-key" http://localhost:5000/stats

# Response:
{
  "active_threads": 5,
  "total_clients": 12,
  "rate_limiting": {
    "enabled": true,
    "default": "100 per minute",
    "chat": "20 per minute"
  },
  "threads": { ... }
}
```

### **3. Metrics Endpoint (Prometheus)**

```bash
curl -H "X-API-Key: your-api-key" http://localhost:5000/metrics

# Response (Prometheus format):
# HELP socket_active_threads Number of active conversation threads
# TYPE socket_active_threads gauge
socket_active_threads 5
...
```

**Prometheus Configuration:**

```yaml
scrape_configs:
  - job_name: 'shop-chatbot-socket'
    scrape_interval: 30s
    static_configs:
      - targets: ['localhost:5000']
    params:
      api_key: ['your-api-key']
```

### **4. Log Monitoring**

**View logs:**
```bash
tail -f logs/socket_server.log
```

**Log format:**
```
2026-08-20 10:30:15 [INFO] app.socket_server: Client abc123 joined thread: shop-001
2026-08-20 10:30:20 [INFO] app.socket_server: Processing message for thread shop-001 from abc123: Top 5...
2026-08-20 10:30:25 [INFO] app.socket_server: Sent response for thread shop-001
```

**Log levels:**
- `DEBUG`: Detailed info for debugging (not recommended in production)
- `INFO`: General operational messages (recommended)
- `WARNING`: Warnings and potential issues
- `ERROR`: Errors that need attention

**Set up log rotation** (Linux):

Create `/etc/logrotate.d/shop-chatbot-socket`:
```
/var/www/shop-langgraph/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload shop-chatbot-socket
    endscript
}
```

---

## 🔍 Testing Production Setup

### **1. Connectivity Test**

```bash
# Test WebSocket connection
python -c "
from socketio import SimpleClient

client = SimpleClient()
client.connect('http://localhost:5000')
print('✅ Connected')
client.disconnect()
"
```

### **2. Load Test**

**Using `locust` (install: `pip install locust`):**

Create `locustfile.py`:
```python
from locust import User, task, between
from socketio import SimpleClient

class ChatUser(User):
    wait_time = between(1, 3)
    
    def on_start(self):
        self.client = SimpleClient()
        self.client.connect('http://localhost:5000')
        self.client.emit('join_thread', {'thread_id': 'load-test-001'})
    
    @task
    def send_message(self):
        self.client.emit('chat_message', {
            'message': 'Test message',
            'thread_id': 'load-test-001',
            'tool_enabled': False
        })
    
    def on_stop(self):
        self.client.disconnect()
```

Run load test:
```bash
locust -f locustfile.py --host=http://localhost:5000
```

Open http://localhost:8089 and configure:
- Number of users: 50
- Spawn rate: 10/sec
- Run test and monitor

### **3. Rate Limiting Test**

```bash
# Rapid requests (should hit rate limit)
for i in {1..50}; do
  curl -H "X-API-Key: your-key" http://localhost:5000/health &
done
wait

# Check for 429 (Too Many Requests) responses
```

---

## 🚨 Troubleshooting

### **Issue: Server won't start**

**Check logs:**
```bash
tail -n 50 logs/socket_server.log
```

**Common causes:**
- Port 5000 already in use → Change `SOCKET_PORT`
- Redis not running → Start Redis
- PostgreSQL not running → Start PostgreSQL
- Missing `.env` file → Copy from `.env.example`

### **Issue: Clients can't connect**

**Check:**
1. Firewall allows port 5000
2. CORS_ORIGINS includes client domain
3. WebSocket not blocked by proxy/firewall
4. Client using correct URL

**Test:**
```bash
curl http://localhost:5000/health
```

### **Issue: Rate limiting too strict**

**Adjust in `.env`:**
```env
RATE_LIMIT_CHAT=50 per minute  # Increase from 20
```

**Monitor rate limit hits:**
```bash
grep "rate limit" logs/socket_server.log
```

### **Issue: High memory usage**

**Check active threads:**
```bash
curl -H "X-API-Key: your-key" http://localhost:5000/stats | jq '.active_threads'
```

**Cleanup inactive threads:**
- Threads auto-cleanup after 24 hours
- Force cleanup by calling `/stats` endpoint

### **Issue: Slow responses**

**Check:**
1. Gemini API latency (most common)
2. Redis connection latency
3. PostgreSQL connection latency
4. Server CPU/memory

**Monitor:**
```bash
# Check response time
time curl -H "X-API-Key: your-key" http://localhost:5000/health
```

---

## 📈 Performance Tuning

### **1. Redis Optimization**

**Use Redis for limiter storage** (instead of memory):

Update `app/socket_server.py`:
```python
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[RATE_LIMIT_DEFAULT] if RATE_LIMIT_ENABLED else [],
    storage_uri="redis://localhost:6379"  # Change from memory://
)
```

**Benefits:**
- Shared across multiple server instances
- Persistent rate limits
- Better performance at scale

### **2. Connection Pooling**

Redis and PostgreSQL already use connection pooling via their respective libraries.

### **3. Horizontal Scaling**

**For multiple server instances**, use Redis adapter for Socket.IO:

```bash
pip install redis
```

Update `app/socket_server.py`:
```python
from socketio import RedisManager

socketio = SocketIO(
    app,
    cors_allowed_origins=CORS_ORIGINS,
    async_mode='eventlet',
    client_manager=RedisManager('redis://localhost:6379')
)
```

**Deploy multiple instances:**
```bash
# Instance 1
SOCKET_PORT=5000 python -m app.socket_server &

# Instance 2
SOCKET_PORT=5001 python -m app.socket_server &

# Load balancer in front (nginx, HAProxy, etc.)
```

---

## 🔒 Security Best Practices

1. **Never commit `.env`** - Use `.env.example` as template
2. **Rotate API keys** regularly (every 90 days)
3. **Use HTTPS** in production (add SSL termination at reverse proxy)
4. **Restrict CORS** to specific domains
5. **Monitor for abuse** (check rate limit logs)
6. **Keep dependencies updated** (`pip list --outdated`)
7. **Use secrets management** (AWS Secrets Manager, HashiCorp Vault)
8. **Enable firewall** rules (allow only necessary ports)
9. **Regular backups** of Redis and PostgreSQL
10. **Audit logs** regularly for suspicious activity

---

## 📞 Support & Maintenance

### **Regular Tasks:**

**Daily:**
- Check error logs: `grep ERROR logs/socket_server.log`
- Monitor health endpoint: `curl http://localhost:5000/health`

**Weekly:**
- Review stats: `curl http://localhost:5000/stats`
- Check disk usage: `du -sh logs/`
- Update dependencies if needed

**Monthly:**
- Rotate API keys
- Review rate limits
- Analyze usage patterns
- Performance optimization

### **Emergency Contacts:**

- Server admin: [Your contact]
- Database admin: [Your contact]
- On-call: [Your contact]

---

## ✅ Production Readiness Checklist

**Security:**
- [ ] API_KEY configured
- [ ] CORS restricted
- [ ] Rate limiting enabled
- [ ] HTTPS/TLS enabled
- [ ] Firewall configured

**Configuration:**
- [ ] SOCKET_DEBUG=False
- [ ] LOG_LEVEL appropriate
- [ ] All services configured
- [ ] Environment variables set

**Infrastructure:**
- [ ] Redis running and persistent
- [ ] PostgreSQL running and backed up
- [ ] Langfuse running (if used)
- [ ] Monitoring set up
- [ ] Alerting configured

**Testing:**
- [ ] Health check works
- [ ] Stats endpoint works
- [ ] WebSocket connects
- [ ] Rate limiting works
- [ ] Load test passed

**Documentation:**
- [ ] Deployment documented
- [ ] Runbook created
- [ ] Team trained
- [ ] Contacts updated

---

**Ready for production!** 🚀

For questions or issues, refer to logs or contact the development team.
