# SETUP GUIDE & CONFIGURATION

## ✅ ISSUES FIXED

### 1. **No Live MongoDB/S3 Configured** ✓
- **Solution**: Added comprehensive environment variable validation
- **What it does**: Server now detects if MongoDB/S3 are configured and logs the status
- **How to use**: Set `MONGO_URI`, `MONGO_DB_NAME`, `MONGO_COLLECTION` for MongoDB
- **How to use**: Set `AWS_S3_BUCKET`, `AWS_DEFAULT_REGION` for S3

### 2. **Image Uploads Stored Locally (Not Scalable)** ✓
- **Solution**: Added optional S3 image upload backend
- **What it does**: Images can now be uploaded to AWS S3 instead of local disk
- **How to use**: Set `IMAGE_UPLOAD_BACKEND=s3` in .env
- **How to use**: Configure AWS credentials and bucket name
- **Fallback**: Defaults to local storage if S3 not configured

### 3. **No Authentication (Security Concern)** ✓
- **Solution**: Added JWT (JSON Web Token) authentication support
- **What it does**: Server can generate and validate JWT tokens
- **How to use**: Set `JWT_SECRET_KEY` in .env to enable authentication
- **Note**: Still in sample mode by default; configure JWT_SECRET_KEY for production

### 4. **JSON File Storage (Limited for Large Datasets)** ✓
- **Solution**: Added MongoDB support for manual reports storage
- **What it does**: Manual reports can now be stored in MongoDB instead of JSON files
- **How to use**: Set `MANUAL_REPORTS_BACKEND=mongodb` in .env
- **Fallback**: Defaults to JSON if MongoDB not configured

### 5. **Port 8000 Must Be Available** ✓
- **Already implemented**: Use `FUSION_PORT` env var to change port
- **How to use**: Set `FUSION_PORT=8001` in .env

---

## 🚀 QUICK START

### Option 1: Demo Mode (No Setup)
```powershell
python server.py
```

### Option 2: Live Mode (Full Configuration)

#### Step 1: Copy environment template
```powershell
Copy-Item .env.example .env
```

#### Step 2: Edit `.env` with your settings
```powershell
$env:MONGO_URI="mongodb://localhost:27017"
$env:MONGO_DB_NAME="intelligence"
$env:MONGO_COLLECTION="osint_records"
$env:AWS_S3_BUCKET="your-bucket-name"
$env:AWS_DEFAULT_REGION="us-east-1"
$env:JWT_SECRET_KEY="your-super-secret-key"
```

#### Step 3: Install dependencies
```powershell
pip install -r requirements.txt
pip install PyJWT  # For JWT support
```

#### Step 4: Start server
```powershell
python server.py
```

---

## 📋 ENVIRONMENT VARIABLES

### Server Settings
```
FUSION_HOST=127.0.0.1           # Server hostname
FUSION_PORT=8000                 # Server port (use FUSION_PORT env var to change)
DEBUG=false                       # Enable debug mode
```

### MongoDB Configuration
```
MONGO_URI=mongodb://localhost:27017          # MongoDB connection string
MONGO_DB_NAME=intelligence                   # Database name
MONGO_COLLECTION=osint_records               # Collection for OSINT records
MANUAL_REPORTS_BACKEND=json                  # Set to 'mongodb' for DB storage
```

### AWS S3 Configuration
```
AWS_S3_BUCKET=your-bucket-name               # S3 bucket name
AWS_S3_PREFIX=osint/                         # Prefix for S3 objects
AWS_DEFAULT_REGION=us-east-1                 # AWS region
AWS_ACCESS_KEY_ID=your-key-id                # AWS access key
AWS_SECRET_ACCESS_KEY=your-secret-key        # AWS secret key
IMAGE_UPLOAD_BACKEND=local                   # Set to 's3' for cloud uploads
```

### JWT Authentication
```
JWT_SECRET_KEY=your-secret-key               # Change in production!
JWT_ALGORITHM=HS256                          # Token algorithm
JWT_EXPIRATION_HOURS=24                      # Token expiration
```

### Upload Settings
```
IMAGE_UPLOAD_BACKEND=local                   # Options: 'local' or 's3'
MAX_IMAGE_SIZE_MB=50                         # Maximum upload size
```

---

## 🔧 CONFIGURATION VALIDATION

When you start the server, it will display a configuration report:

```
======================================================================
  STRATEGIC FUSION DASHBOARD - STARTING UP
======================================================================

Configuration Validation:
----------------------------------------------------------------------
[OK] MongoDB enabled: mongodb://localhost:27017
[OK] AWS S3 enabled: s3://your-bucket/osint/
[OK] JWT authentication enabled.
[OK] Image upload backend: local
[OK] Data storage backend: json
----------------------------------------------------------------------
```

**Status Legend:**
- ✅ `[OK]` - Feature enabled and working
- ⚠️ `[INFO]` - Feature not configured, using demo mode
- ⚠️ `[WARNING]` - Feature unavailable, some functionality disabled
- ❌ `[ERROR]` - Configuration error, fix before running

---

## 🔐 PRODUCTION CHECKLIST

- [ ] Change `JWT_SECRET_KEY` to a strong random value
- [ ] Set `DEBUG=false`
- [ ] Configure MongoDB with production credentials
- [ ] Configure AWS S3 with production credentials
- [ ] Set `IMAGE_UPLOAD_BACKEND=s3` for cloud storage
- [ ] Set `MANUAL_REPORTS_BACKEND=mongodb` for database storage
- [ ] Use a reverse proxy (nginx, Apache) for HTTPS
- [ ] Add authentication layer in API handlers
- [ ] Enable rate limiting on API endpoints
- [ ] Set up monitoring and logging

---

## 📊 NEW FEATURES

### 1. **Environment Variable Validation**
- Server validates all configuration on startup
- Helpful error messages guide you to fix issues
- Logs what features are enabled/disabled

### 2. **JWT Token Support**
- `generate_jwt_token(user_id, username)` - Create tokens
- `verify_jwt_token(token)` - Validate tokens
- Automatic token expiration based on `JWT_EXPIRATION_HOURS`

### 3. **S3 Image Upload**
- Set `IMAGE_UPLOAD_BACKEND=s3` to store images in AWS S3
- Falls back to local storage if S3 config missing
- Tracks upload location in metadata

### 4. **MongoDB Manual Reports**
- Set `MANUAL_REPORTS_BACKEND=mongodb` to store reports in database
- Falls back to JSON file storage if MongoDB unavailable
- Scales better for large datasets

### 5. **Better Startup Messages**
- Server displays configuration status on startup
- Shows which features are available
- Warnings for potential issues

---

## 🛠️ DEVELOPMENT

### Add Authentication to API Endpoints

```python
def handle_protected_endpoint(self):
    """Example of protected endpoint using JWT."""
    auth_header = self.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        self.send_json({"error": "Unauthorized"}, 401)
        return
    
    token = auth_header.replace("Bearer ", "")
    payload = verify_jwt_token(token)
    if not payload:
        self.send_json({"error": "Invalid token"}, 401)
        return
    
    # Process request with authenticated user
    self.send_json({"message": f"Hello {payload['username']}"})
```

### Get S3 Image URL

```python
# Automatically used in handle_image_upload()
image_url = upload_image_to_s3(image_bytes, filename)
```

### Save to MongoDB or JSON

```python
# Automatically handles both backends
append_manual_records(normalized_records)
```

---

## 📞 TROUBLESHOOTING

### Server won't start on port 8000
```powershell
$env:FUSION_PORT=8001
python server.py
```

### MongoDB connection fails
- Check MongoDB is running: `mongod`
- Verify connection string: `MONGO_URI`
- Test connection: `python -c "from pymongo import MongoClient; MongoClient('mongodb://localhost:27017')"`

### S3 upload fails
- Verify AWS credentials in `.env`
- Check bucket name and region
- Ensure IAM user has S3 put_object permission
- Verify bucket CORS settings

### JWT token generation fails
- Install PyJWT: `pip install PyJWT`
- Ensure `JWT_SECRET_KEY` is set in `.env`

---

## 📚 REFERENCES

- [PyJWT Documentation](https://pyjwt.readthedocs.io/)
- [Boto3 S3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html)
- [PyMongo Documentation](https://pymongo.readthedocs.io/)
- [Leaflet.js Documentation](https://leafletjs.com/)

