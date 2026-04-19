# Setup script for Fusion Dashboard
# Run this to configure environment variables

param(
    [string]$Mode = "demo",  # demo, live, or production
    [string]$MongoUri = "mongodb://localhost:27017",
    [string]$S3Bucket = "",
    [string]$S3Region = "us-east-1",
    [string]$JwtSecret = ""
)

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Fusion Dashboard Setup" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Mode selection
if ($Mode -eq "demo") {
    Write-Host "Setting up DEMO MODE (no external services required)" -ForegroundColor Green
    $env:FUSION_HOST = "127.0.0.1"
    $env:FUSION_PORT = "8000"
    $env:DEBUG = "false"
    Write-Host "✓ Demo mode configured" -ForegroundColor Green
}
elseif ($Mode -eq "live") {
    Write-Host "Setting up LIVE MODE (with MongoDB and S3)" -ForegroundColor Green
    
    if ($MongoUri) {
        $env:MONGO_URI = $MongoUri
        $env:MONGO_DB_NAME = "intelligence"
        $env:MONGO_COLLECTION = "osint_records"
        Write-Host "✓ MongoDB configured: $MongoUri" -ForegroundColor Green
    }
    
    if ($S3Bucket) {
        $env:AWS_S3_BUCKET = $S3Bucket
        $env:AWS_S3_PREFIX = "osint/"
        $env:AWS_DEFAULT_REGION = $S3Region
        $env:IMAGE_UPLOAD_BACKEND = "s3"
        Write-Host "✓ S3 configured: s3://$S3Bucket/" -ForegroundColor Green
    }
    
    if ($JwtSecret) {
        $env:JWT_SECRET_KEY = $JwtSecret
        Write-Host "✓ JWT configured" -ForegroundColor Green
    }
}
elseif ($Mode -eq "production") {
    Write-Host "Setting up PRODUCTION MODE" -ForegroundColor Yellow
    
    if (-not $JwtSecret) {
        Write-Host "⚠ JWT_SECRET_KEY not provided. Use: .\setup.ps1 -Mode production -JwtSecret 'your-secret'" -ForegroundColor Yellow
        exit 1
    }
    
    $env:MONGO_URI = $MongoUri
    $env:MONGO_DB_NAME = "intelligence"
    $env:MONGO_COLLECTION = "osint_records"
    $env:MANUAL_REPORTS_BACKEND = "mongodb"
    
    if ($S3Bucket) {
        $env:AWS_S3_BUCKET = $S3Bucket
        $env:IMAGE_UPLOAD_BACKEND = "s3"
    }
    
    $env:JWT_SECRET_KEY = $JwtSecret
    $env:DEBUG = "false"
    
    Write-Host "✓ Production mode configured" -ForegroundColor Green
}

Write-Host ""
Write-Host "Current Environment Variables:" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "FUSION_HOST: $($env:FUSION_HOST)" 
Write-Host "FUSION_PORT: $($env:FUSION_PORT)"
Write-Host "MONGO_URI: $($env:MONGO_URI)"
Write-Host "AWS_S3_BUCKET: $($env:AWS_S3_BUCKET)"
Write-Host "DEBUG: $($env:DEBUG)"
Write-Host ""

Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. pip install -r requirements.txt"
Write-Host "2. python server.py"
Write-Host ""
Write-Host "Open browser to: http://127.0.0.1:8000" -ForegroundColor Green
