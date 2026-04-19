# PRODUCTION DEPLOYMENT GUIDE

This guide walks you through deploying the Fusion Dashboard to production with full security, scalability, and reliability.

## Pre-Deployment Checklist

- [ ] All environment variables configured
- [ ] MongoDB instance running and accessible
- [ ] AWS S3 bucket created with proper permissions
- [ ] JWT secret key generated and stored securely
- [ ] SSL/TLS certificates obtained
- [ ] Reverse proxy (nginx) configured
- [ ] Monitoring and logging setup
- [ ] Database backups automated

---

## 1. CONFIGURE PRODUCTION ENVIRONMENT

### Create .env.production

```bash
# Server
FUSION_HOST=0.0.0.0
FUSION_PORT=8080
DEBUG=false

# MongoDB (Production Instance)
MONGO_URI=mongodb+srv://user:password@cluster.mongodb.net/?retryWrites=true&w=majority
MONGO_DB_NAME=intelligence_prod
MONGO_COLLECTION=osint_records

# AWS S3 (Production Bucket)
AWS_S3_BUCKET=intelligence-fusion-prod
AWS_S3_PREFIX=osint/
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-prod-access-key
AWS_SECRET_ACCESS_KEY=your-prod-secret-key

# Authentication
JWT_SECRET_KEY=generate-strong-random-key-min-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Image Upload
IMAGE_UPLOAD_BACKEND=s3
MAX_IMAGE_SIZE_MB=50

# Data Storage
MANUAL_REPORTS_BACKEND=mongodb
```

### Generate Strong JWT Secret

```python
import secrets
import base64

# Generate 32-byte random key
secret = base64.b64encode(secrets.token_bytes(32)).decode()
print(f"JWT_SECRET_KEY={secret}")
```

---

## 2. INSTALL DEPENDENCIES

```bash
pip install -r requirements.txt
```

---

## 3. CONFIGURE REVERSE PROXY (Nginx)

### /etc/nginx/sites-available/fusion-dashboard

```nginx
upstream fusion_dashboard {
    server 127.0.0.1:8080;
    keepalive 32;
}

server {
    listen 80;
    server_name intelligence-dashboard.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name intelligence-dashboard.example.com;

    ssl_certificate /etc/letsencrypt/live/intelligence-dashboard.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/intelligence-dashboard.example.com/privkey.pem;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=upload_limit:10m rate=5r/m;

    location / {
        proxy_pass http://fusion_dashboard;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_buffering off;
    }

    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://fusion_dashboard;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/upload/ {
        limit_req zone=upload_limit burst=5 nodelay;
        client_max_body_size 50M;
        proxy_pass http://fusion_dashboard;
    }

    location /uploads/ {
        # Disable uploads on public instance
        return 403;
    }
}
```

### Enable Nginx Site

```bash
sudo ln -s /etc/nginx/sites-available/fusion-dashboard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 4. SETUP SYSTEMD SERVICE

### /etc/systemd/system/fusion-dashboard.service

```ini
[Unit]
Description=Strategic Fusion Dashboard
After=network.target mongodb.service

[Service]
Type=simple
User=fusionapp
WorkingDirectory=/opt/fusion-dashboard
EnvironmentFile=/opt/fusion-dashboard/.env.production
ExecStart=/usr/bin/python3 server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Enable Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable fusion-dashboard.service
sudo systemctl start fusion-dashboard.service
sudo systemctl status fusion-dashboard.service
```

---

## 5. SETUP MONGODB FOR PRODUCTION

### Create MongoDB User with Minimal Permissions

```javascript
use intelligence_prod;

db.createUser({
  user: "fusion_app",
  pwd: "strong-password-here",
  roles: [
    { role: "readWrite", db: "intelligence_prod" }
  ]
});

db.createCollection("osint_records");
db.createCollection("manual_reports");
db.createCollection("simulated_feed");

// Create indexes for performance
db.osint_records.createIndex({ "lat": 1, "lon": 1 });
db.osint_records.createIndex({ "sourceName": 1 });
db.manual_reports.createIndex({ "timestamp": -1 });
```

### Enable MongoDB Security

```yaml
# /etc/mongod.conf
security:
  authorization: enabled
  
net:
  bindIp: 127.0.0.1  # Only local connections
  ssl:
    mode: requireSSL
    certFile: /path/to/cert.pem
```

---

## 6. SETUP AWS S3 FOR PRODUCTION

### Create S3 Bucket

```bash
aws s3 mb s3://intelligence-fusion-prod --region us-east-1
```

### Configure Bucket Policy (Minimal Permissions)

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::ACCOUNT-ID:user/fusion-app"
            },
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::intelligence-fusion-prod/*"
        },
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::ACCOUNT-ID:user/fusion-app"
            },
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::intelligence-fusion-prod"
        }
    ]
}
```

### Enable Versioning and Encryption

```bash
aws s3api put-bucket-versioning \
  --bucket intelligence-fusion-prod \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket intelligence-fusion-prod \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

---

## 7. SETUP MONITORING & LOGGING

### Systemd Journal Logging

```bash
# View logs
sudo journalctl -u fusion-dashboard.service -f

# Export logs
sudo journalctl -u fusion-dashboard.service --since today > dashboard.log
```

### Setup Log Rotation

Create `/etc/logrotate.d/fusion-dashboard`:

```
/var/log/fusion-dashboard/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 fusionapp fusionapp
    sharedscripts
}
```

---

## 8. SETUP AUTOMATED BACKUPS

### MongoDB Backup Script

```bash
#!/bin/bash
# /opt/fusion-dashboard/backup-mongodb.sh

BACKUP_DIR="/backups/mongodb"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/intelligence_prod_$TIMESTAMP.gz"

mkdir -p "$BACKUP_DIR"

mongodump \
  --uri "mongodb+srv://fusion_app:password@cluster.mongodb.net/intelligence_prod" \
  --archive="$BACKUP_FILE" \
  --gzip

# Upload to S3
aws s3 cp "$BACKUP_FILE" "s3://intelligence-backups/mongodb/$TIMESTAMP.gz"

# Keep only last 30 days locally
find "$BACKUP_DIR" -mtime +30 -delete
```

### Schedule with Cron

```bash
# Backup every day at 2 AM
0 2 * * * /opt/fusion-dashboard/backup-mongodb.sh
```

---

## 9. HEALTH CHECK ENDPOINT

Add to `server.py`:

```python
def handle_health_check(self):
    """Health check endpoint for monitoring."""
    health = {
        "status": "ok",
        "timestamp": iso_now(),
        "services": {
            "mongodb": "unknown",
            "s3": "unknown",
        }
    }
    
    # Check MongoDB
    if MongoClient and MONGO_URI:
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
            client.server_info()
            health["services"]["mongodb"] = "ok"
        except:
            health["services"]["mongodb"] = "error"
    
    # Check S3
    if boto3 and S3_BUCKET:
        try:
            client = boto3.client("s3", region_name=AWS_REGION)
            client.head_bucket(Bucket=S3_BUCKET)
            health["services"]["s3"] = "ok"
        except:
            health["services"]["s3"] = "error"
    
    self.send_json(health)
```

### Monitor with curl

```bash
curl https://intelligence-dashboard.example.com/health
```

---

## 10. SECURITY HARDENING

### API Rate Limiting (Already in Nginx)
- General API: 10 requests/second
- Upload endpoints: 5 requests/minute

### CORS Headers

Add to `server.py`:

```python
self.send_header("Access-Control-Allow-Origin", "https://intelligence-dashboard.example.com")
self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
self.send_header("Access-Control-Max-Age", "3600")
```

### JWT Validation on All Protected Endpoints

```python
def require_jwt(self):
    """Decorator-like function for JWT validation."""
    auth = self.headers.get("Authorization", "").replace("Bearer ", "")
    token_data = verify_jwt_token(auth)
    if not token_data:
        self.send_json({"error": "Unauthorized"}, 401)
        return None
    return token_data
```

---

## 11. DEPLOYMENT COMMANDS

```bash
# Deploy
cd /opt/fusion-dashboard
git pull origin main
pip install -r requirements.txt
sudo systemctl restart fusion-dashboard.service

# Check status
sudo systemctl status fusion-dashboard.service
journalctl -u fusion-dashboard.service -n 50

# Rollback
git revert HEAD
sudo systemctl restart fusion-dashboard.service
```

---

## 12. PERFORMANCE TUNING

### MongoDB Indexes

Already set up in the MongoDB script above.

### Python Performance

```python
# Use workers for concurrent requests
# Consider using gunicorn or uwsgi instead of HTTPServer

# gunicorn -w 4 -b 0.0.0.0:8080 server:app
```

### Caching Headers

```python
self.send_header("Cache-Control", "public, max-age=300")  # 5 minutes
```

---

## 13. DISASTER RECOVERY

### Backup Restore

```bash
mongorestore \
  --uri "mongodb+srv://fusion_app:password@cluster.mongodb.net" \
  --archive="/backups/mongodb/intelligence_prod_20240101_020000.gz" \
  --gzip
```

### S3 Disaster Recovery

All images stored in S3 with versioning enabled. Restore from S3 version history.

---

## Monitoring Dashboard Recommendations

- **Datadog**: Monitor application metrics
- **PagerDuty**: Alert on service failures
- **CloudTrail**: Audit S3 access
- **MongoDB Atlas**: Built-in monitoring

