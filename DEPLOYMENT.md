# 🚀 Deployment Guide for Render.com

## Overview
This disaster relief management system is configured for easy deployment on Render.com using a single web service with Honcho process manager.

## Files Created for Deployment

### 1. `Procfile`
Defines the two processes that run simultaneously:
- **backend**: AI agent server (port 8001)
- **frontend**: Flask web interface (port from Render's PORT env var)

### 2. `render.yaml`
Render Blueprint configuration that automates deployment setup.

### 3. Updated Code
- `frontend_app.py`: Now uses Render's PORT environment variable
- `manager_server.py`: Configurable port and production mode

## Prerequisites

1. **GitHub/GitLab Account** - Your code must be in a Git repository
2. **Render Account** - Sign up at https://render.com (free)
3. **Google API Key** - For Gemini AI models

## Deployment Steps

### Step 1: Prepare Your Repository

```bash
# Make sure all files are committed
git add .
git commit -m "Configure for Render deployment"
git push origin main
```

### Step 2: Deploy on Render

#### Option A: Using Blueprint (Recommended - Automatic)

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Blueprint"**
3. Connect your GitHub/GitLab repository
4. Render will detect `render.yaml` and configure automatically
5. **IMPORTANT**: Add environment variable:
   - Navigate to the created service
   - Go to **Environment** tab
   - Add variable:
     - Key: `GOOGLE_API_KEY`
     - Value: `your_actual_google_api_key_here`
6. Click **"Manual Deploy"** → **"Deploy latest commit"**

#### Option B: Manual Setup

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Web Service"**
3. Connect your repository
4. Configure:
   - **Name**: `disaster-relief-app`
   - **Runtime**: Python 3
   - **Region**: Oregon (or closest to you)
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `honcho start`
5. Add Environment Variables:
   - `GOOGLE_API_KEY` = `your_api_key`
   - `PYTHON_VERSION` = `3.11`
6. Click **"Create Web Service"**

### Step 3: Monitor Deployment

- Watch the deployment logs in real-time
- Look for:
  ```
  🚀 Starting Hierarchical Multi-Agent Backend Server...
  ✅ Client Proxies Ready. Starting on port...
  ```
- First deployment takes 5-10 minutes

### Step 4: Access Your Application

Once deployed, Render provides a URL like:
```
https://disaster-relief-app.onrender.com
```

Access the interfaces:
- **Victim Interface**: https://disaster-relief-app.onrender.com/
- **Supervisor Dashboard**: https://disaster-relief-app.onrender.com/supervisor

## Important Notes

### ⚠️ Free Tier Limitations

1. **Cold Starts**: Service spins down after 15 minutes of inactivity
   - First request after sleeping takes ~60 seconds to wake up
   - Subsequent requests are fast

2. **Resource Limits**:
   - 512 MB RAM per service
   - 750 free hours/month

3. **Database Persistence**:
   - SQLite database (`relief_logistics.db`) is ephemeral
   - Data resets on each deployment
   - For production, migrate to PostgreSQL

4. **Activity Logs**:
   - In-memory logs (`SUPERVISOR_ACTIVITY_LOG`) clear on restart
   - This is by design for session-based activity monitoring

### 🔒 Security Best Practices

1. **Never commit `.env` file** - It's in `.gitignore`
2. **Set secrets in Render dashboard** - Use Environment Variables
3. **Use HTTPS** - Render provides automatic SSL certificates

### 📊 Monitoring

Monitor your application health:
1. **Render Dashboard**: View logs, metrics, deployment history
2. **Health Check**: Configured at `/` (homepage)
3. **Logs**: Real-time logs available in Render dashboard

### 🔄 Auto-Deploy

Render automatically deploys when you push to your main branch:
```bash
git add .
git commit -m "Update feature"
git push origin main
# Render automatically detects and deploys
```

## Troubleshooting

### Issue: Services not starting
**Solution**: Check logs in Render dashboard for errors

### Issue: "GOOGLE_API_KEY not found"
**Solution**: Add the environment variable in Render dashboard

### Issue: Cold start takes too long
**Solution**: 
- Free tier limitation
- Consider upgrading to paid plan
- Or use a cron job to ping your app every 10 minutes

### Issue: Database resets on deploy
**Solution**: 
- Expected behavior with SQLite on ephemeral storage
- Migrate to Render PostgreSQL for persistence
- Or use external database (Supabase, PlanetScale)

## Local Testing

Test the production configuration locally:

```bash
# Set environment variables
export GOOGLE_API_KEY=your_key
export FLASK_ENV=production

# Install honcho
pip install honcho

# Run with Procfile
honcho start

# Access at http://localhost:5000
```

## Upgrading to Production

For a production-ready deployment, consider:

1. **PostgreSQL Database**:
   - Add Render PostgreSQL service (free tier available)
   - Migrate from SQLite to PostgreSQL
   - Persistent data across deployments

2. **Separate Services**:
   - Deploy backend and frontend as separate services
   - Better scalability and isolation

3. **Custom Domain**:
   - Connect your own domain name
   - Available on all Render plans

4. **Paid Plan Benefits**:
   - No cold starts
   - More RAM and CPU
   - Better performance

## Support

- **Render Docs**: https://render.com/docs
- **Project Issues**: Create an issue in your repository
- **Render Support**: https://render.com/support

---

**Deployment configured successfully! 🎉**
