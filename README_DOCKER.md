# Docker Deployment Guide

This guide explains how to deploy the AlgoTrading system on Render using Docker.

## Files Created

1. **Dockerfile** - Multi-stage Docker configuration for the application
2. **requirements.txt** - Python dependencies for the application
3. **render.yaml** - Render deployment configuration
4. **configs/config.template.yml** - Configuration template with environment variables
5. **.dockerignore** - Files to exclude from Docker build

## Environment Variables

Before deploying, set these environment variables in your Render dashboard:

### Required Environment Variables
- `DELTA_API_KEY` - Your Delta Exchange API key
- `DELTA_API_SECRET` - Your Delta Exchange API secret

### Optional Environment Variables
- `PYTHONUNBUFFERED=1` - Ensures Python output is not buffered
- `PYTHONDONTWRITEBYTECODE=1` - Prevents Python from writing .pyc files

## Deployment Steps

### 1. Push to GitHub
Ensure all files are committed to your GitHub repository:
```bash
git add .
git commit -m "Add Docker configuration for Render deployment"
git push origin main
```

### 2. Configure Render
1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Render will automatically detect the `render.yaml` file
5. Set the required environment variables:
   - `DELTA_API_KEY`: Your Delta Exchange API key
   - `DELTA_API_SECRET`: Your Delta Exchange API secret

### 3. Deploy
Render will automatically build and deploy your Docker container.

## Configuration Management

The application now supports environment variable substitution in configuration files:

- Use `configs/config.template.yml` as a template
- Replace sensitive values with `${VARIABLE_NAME}` syntax
- The `config_loader.py` automatically substitutes environment variables at runtime

Example:
```yaml
exchange:
  api_key: ${DELTA_API_KEY}
  api_secret: ${DELTA_API_SECRET}
```

## Local Development

To test the Docker setup locally:

```bash
# Build the Docker image
docker build -t algo-trading .

# Run with environment variables
docker run --rm \
  -e DELTA_API_KEY="your_api_key" \
  -e DELTA_API_SECRET="your_api_secret" \
  algo-trading
```

## Health Checks

The Dockerfile includes a basic health check. Render will monitor the service and restart if it fails.

## Monitoring

- Check Render logs for application logs
- Monitor resource usage in Render dashboard
- Set up alerts for service failures

## Security Notes

- Never commit API keys to version control
- Use Render's environment variables for sensitive data
- The `.dockerignore` file excludes sensitive files from the Docker build
- Consider using Render's private repositories for additional security

## Troubleshooting

### Common Issues

1. **Build Failures**: Check that all dependencies are in `requirements.txt`
2. **Runtime Errors**: Verify environment variables are set correctly
3. **Connection Issues**: Ensure API keys are valid and have proper permissions

### Logs

Access logs through:
- Render Dashboard → Logs tab
- `docker logs <container_id>` (for local testing)

## Scaling

The `render.yaml` is configured for a single instance. To scale:
1. Update `instances` in `render.yaml`
2. Consider adding a message queue for multiple instances
3. Implement proper state management for distributed trading
