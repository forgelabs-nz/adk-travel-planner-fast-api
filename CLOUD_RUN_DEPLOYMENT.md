# Cloud Run Deployment Guide

Complete guide to deploy the Google ADK Multi-Agent System to Google Cloud Run.

## Prerequisites

1. **Google Cloud CLI** installed and configured:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

2. **Enable Required APIs**:
   ```bash
   gcloud services enable \
     run.googleapis.com \
     cloudbuild.googleapis.com \
     aiplatform.googleapis.com \
     artifactregistry.googleapis.com
   ```

3. **Set Environment Variables**:
   ```bash
   export PROJECT_ID=$(gcloud config get-value project)
   export REGION=us-central1
   export SERVICE_NAME=adk-movie-pitch
   ```

---

## Option 1: Quick Deploy (Recommended)

### Deploy Directly from Source

```bash
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --port 8010 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --set-env-vars ENVIRONMENT=production,MODEL=gemini-2.5-flash,GOOGLE_CLOUD_LOCATION=$REGION \
  --service-account $PROJECT_ID@appspot.gserviceaccount.com
```

This will:
- Build the container automatically using Cloud Build
- Deploy to Cloud Run
- Provide a public URL

**Note:** Cloud Run provides Application Default Credentials automatically via the service account.

---

## Option 2: Build and Deploy Separately

### Step 1: Build Container Image

```bash
# Build image with Cloud Build
gcloud builds submit \
  --tag gcr.io/$PROJECT_ID/$SERVICE_NAME:latest

# Or use Docker locally
docker build -t gcr.io/$PROJECT_ID/$SERVICE_NAME:latest .
docker push gcr.io/$PROJECT_ID/$SERVICE_NAME:latest
```

### Step 2: Deploy to Cloud Run

```bash
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME:latest \
  --region $REGION \
  --allow-unauthenticated \
  --port 8010 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --set-env-vars ENVIRONMENT=production,MODEL=gemini-2.5-flash
```

---

## Configuration Options

### Environment Variables

Set via `--set-env-vars` or `--env-vars-file`:

```bash
# Production configuration
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --set-env-vars \
    ENVIRONMENT=production,\
    MODEL=gemini-2.5-flash,\
    GOOGLE_CLOUD_LOCATION=us-central1,\
    ENABLE_CLOUD_LOGGING=true,\
    ALLOWED_ORIGINS=https://yourfrontend.com
```

Or use an env file:

```bash
# Create env.yaml
cat > env.yaml <<EOF
ENVIRONMENT: production
MODEL: gemini-2.5-flash
GOOGLE_CLOUD_LOCATION: us-central1
ENABLE_CLOUD_LOGGING: true
EOF

# Deploy with env file
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --env-vars-file env.yaml
```

### Resource Limits

Adjust based on your needs:

```bash
# For higher load
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --memory 4Gi \
  --cpu 4 \
  --max-instances 50 \
  --min-instances 1

# For cost optimization (cold starts acceptable)
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 5 \
  --min-instances 0
```

---

## Database Configuration (Production)

For production, use Cloud SQL instead of SQLite:

### Step 1: Create Cloud SQL Instance

```bash
# Create PostgreSQL instance
gcloud sql instances create adk-sessions-db \
  --database-version=POSTGRES_15 \
  --region=$REGION \
  --tier=db-f1-micro \
  --root-password=YOUR_SECURE_PASSWORD

# Create database
gcloud sql databases create adk_sessions \
  --instance=adk-sessions-db
```

### Step 2: Connect Cloud Run to Cloud SQL

```bash
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --add-cloudsql-instances $PROJECT_ID:$REGION:adk-sessions-db \
  --set-env-vars SESSION_DB_URL="postgresql://postgres:PASSWORD@/adk_sessions?host=/cloudsql/$PROJECT_ID:$REGION:adk-sessions-db"
```

---

## Permissions & Service Account

### Grant Vertex AI Permissions

```bash
# Get the service account email
SERVICE_ACCOUNT=$(gcloud run services describe $SERVICE_NAME \
  --region $REGION \
  --format="value(spec.template.spec.serviceAccountName)")

# Grant Vertex AI User role
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/aiplatform.user"
```

### Custom Service Account (Recommended for Production)

```bash
# Create service account
gcloud iam service-accounts create adk-agent-sa \
  --display-name="ADK Agent Service Account"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:adk-agent-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# Use in Cloud Run
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --service-account adk-agent-sa@$PROJECT_ID.iam.gserviceaccount.com
```

---

## Verify Deployment

### Test the Deployment

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --region $REGION \
  --format="value(status.url)")

echo "Service URL: $SERVICE_URL"

# Test health endpoint
curl $SERVICE_URL/health

# Test info endpoint
curl $SERVICE_URL/info

# Access Web UI
open $SERVICE_URL
```

### Check Logs

```bash
# View logs
gcloud run services logs read $SERVICE_NAME \
  --region $REGION \
  --limit 50

# Stream logs
gcloud run services logs tail $SERVICE_NAME \
  --region $REGION
```

---

## CI/CD with GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches:
      - main

env:
  PROJECT_ID: your-project-id
  SERVICE_NAME: adk-movie-pitch
  REGION: us-central1

jobs:
  deploy:
    runs-on: ubuntu-latest

    permissions:
      contents: read
      id-token: write

    steps:
      - uses: actions/checkout@v4

      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: 'projects/PROJECT_NUM/locations/global/workloadIdentityPools/POOL/providers/PROVIDER'
          service_account: 'github-actions@${{ env.PROJECT_ID }}.iam.gserviceaccount.com'

      - name: Deploy to Cloud Run
        uses: google-github-actions/deploy-cloudrun@v2
        with:
          service: ${{ env.SERVICE_NAME }}
          region: ${{ env.REGION }}
          source: ./
          env_vars: |
            ENVIRONMENT=production
            MODEL=gemini-2.5-flash
```

---

## Monitoring & Observability

### Enable Cloud Logging

```bash
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --set-env-vars ENABLE_CLOUD_LOGGING=true
```

### View in Cloud Console

1. Navigate to https://console.cloud.google.com/run
2. Click on your service
3. View **Logs**, **Metrics**, and **Revisions**

### Set Up Alerts

```bash
# Create uptime check
gcloud monitoring uptime create adk-health-check \
  --display-name="ADK Agent Health Check" \
  --resource-type=uptime-url \
  --host=$SERVICE_URL \
  --path=/health
```

---

## Troubleshooting

### Common Issues

#### 1. **Permission Denied for Vertex AI**

```bash
# Solution: Grant AI Platform User role
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/aiplatform.user"
```

#### 2. **Container Fails to Start**

```bash
# Check logs
gcloud run services logs read $SERVICE_NAME --region $REGION

# Common causes:
# - PORT environment variable not set (should be 8010)
# - Missing dependencies in Dockerfile
# - Health check failing
```

#### 3. **Cold Start Timeout**

```bash
# Increase timeout and use min instances
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --timeout 300 \
  --min-instances 1
```

#### 4. **SQLite Database Issues**

SQLite doesn't work well in Cloud Run (ephemeral storage). Use Cloud SQL:

```bash
# Quick fix: Use in-memory SQLite (data lost on restart)
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --set-env-vars SESSION_DB_URL="sqlite:///:memory:"

# Production fix: Use Cloud SQL (see Database Configuration section)
```

---

## Cost Optimization

### Reduce Costs

```bash
# Minimum configuration
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --memory 512Mi \
  --cpu 1 \
  --max-instances 5 \
  --min-instances 0 \
  --concurrency 80

# Use us-central1 (cheapest region)
# Set max-instances to limit spend
# Use min-instances=0 to avoid idle charges
```

### Estimate Costs

- **Cloud Run**: ~$0.00002400 per vCPU-second, ~$0.00000250 per GiB-second
- **Request**: ~$0.40 per million requests
- **Networking**: Egress varies by region

Example: 1 instance, 2 CPU, 2 GiB, 100 requests/day:
- Compute: ~$15/month
- Requests: Negligible
- **Total: ~$15-20/month**

---

## Production Checklist

Before going to production:

- [ ] Use Cloud SQL instead of SQLite
- [ ] Set `ENVIRONMENT=production`
- [ ] Enable Cloud Logging (`ENABLE_CLOUD_LOGGING=true`)
- [ ] Configure proper CORS origins (not `*`)
- [ ] Set up monitoring and alerts
- [ ] Use custom service account with least privilege
- [ ] Set appropriate resource limits
- [ ] Test with production traffic patterns
- [ ] Set up CI/CD pipeline
- [ ] Document runbooks for common issues
- [ ] Set up backup strategy for sessions

---

## Rollback

If deployment fails:

```bash
# List revisions
gcloud run revisions list \
  --service $SERVICE_NAME \
  --region $REGION

# Rollback to previous revision
gcloud run services update-traffic $SERVICE_NAME \
  --region $REGION \
  --to-revisions PREVIOUS_REVISION=100
```

---

## Cleanup

To delete the service:

```bash
gcloud run services delete $SERVICE_NAME \
  --region $REGION
```

---

## Next Steps

1. Deploy with the quick command above
2. Test the `/health` and `/info` endpoints
3. Configure Cloud SQL for production
4. Set up monitoring
5. Integrate with frontend (Reflex or other)

**Service will be available at:** `https://adk-movie-pitch-HASH-uc.a.run.app`
