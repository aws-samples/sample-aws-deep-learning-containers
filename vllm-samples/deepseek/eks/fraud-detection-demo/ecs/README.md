# ECS Deployment Guide - Financial Fraud Detection System

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                  Internet Gateway                        │
│                         │                                │
│                    ┌────▼────┐                          │
│                    │   ALB   │ (Public subnets)         │
│                    │         │ (Your IP only)           │
│                    └────┬────┘                          │
│                         │                                │
│              ┌──────────┴──────────┐                    │
│              │                     │                    │
│         ┌────▼────┐         ┌─────▼────┐              │
│         │ ECS Task│         │ ECS Task │              │
│         │   UI    │         │ MCP Srvs │              │
│         │(Private)│         │(Private) │              │
│         └─────────┘         └──────────┘              │
│                                                          │
│      Private Subnets (us-west-2a, us-west-2b)          │
│      Service Discovery (Cloud Map)                      │
└─────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **VPC Setup**
   - VPC with public and private subnets in 2 AZs
   - NAT Gateway in public subnets
   - Internet Gateway attached

2. **AWS Resources**
   - ECS Cluster
   - ECR repositories for all containers
   - Application Load Balancer
   - AWS Cloud Map namespace for service discovery

3. **IAM Roles**
   - ECS Task Execution Role (for pulling images, secrets)
   - ECS Task Role (for Bedrock, SES, CloudWatch)

4. **Security Requirements**
   - **CRITICAL**: NO 0.0.0.0/0 rules allowed
   - ALB security group: Allow YOUR IP only
   - ECS security groups: Allow from ALB/other ECS tasks only

## Deployment Steps

### 1. Create ECR Repositories

```bash
# Create ECR repos for all MCP servers
for service in transaction-risk identity-verifier email-alerts fraud-logger geolocation-checker report-generator ui; do
  aws ecr create-repository \
    --repository-name fraud-detection/$service \
    --region us-west-2 \
    --profile non-prod-profile
done
```

### 2. Build and Push Docker Images

```bash
# Set your account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile non-prod-profile)
REGION=us-west-2
REGISTRY=$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

# Login to ECR
aws ecr get-login-password --region $REGION --profile non-prod-profile | \
  docker login --username AWS --password-stdin $REGISTRY

# Build and push MCP servers
cd mcp-servers
for service in transaction-risk identity-verifier email-alerts fraud-logger geolocation-checker report-generator; do
  echo "Building $service..."
  docker build -t fraud-detection/$service:latest \
    --build-arg SERVICE_DIR=$service \
    -f Dockerfile \
    --build-context server=./$service \
    .
  
  docker tag fraud-detection/$service:latest $REGISTRY/fraud-detection/$service:latest
  docker push $REGISTRY/fraud-detection/$service:latest
done

# Build and push UI
cd ../ui
docker build -t fraud-detection/ui:latest .
docker tag fraud-detection/ui:latest $REGISTRY/fraud-detection/ui:latest
docker push $REGISTRY/fraud-detection/ui:latest
```

### 3. Create Service Discovery Namespace

```bash
aws servicediscovery create-private-dns-namespace \
  --name fraud-detection.local \
  --vpc vpc-xxxxx \
  --region us-west-2 \
  --profile non-prod-profile
```

### 4. Deploy ECS Resources

See the `deploy.sh` script for automated deployment.

## Security Groups Configuration

### ALB Security Group
```
Inbound:
- Port 80: YOUR_IP/32 ONLY (no 0.0.0.0/0!)
Outbound:
- Port 8501: ECS UI security group
```

### ECS UI Security Group
```
Inbound:
- Port 8501: From ALB security group
Outbound:
- Port 8080: To MCP servers security group
- Port 443: To AWS services (Bedrock, SES)
```

### MCP Servers Security Group
```
Inbound:
- Port 8080: From ECS UI security group
Outbound:
- Port 443: To AWS services
```

## Environment Variables

### UI Task
- `MCP_TRANSACTION_RISK_URL`: http://transaction-risk.fraud-detection.local:8080/sse
- `MCP_IDENTITY_VERIFIER_URL`: http://identity-verifier.fraud-detection.local:8080/sse
- `MCP_EMAIL_ALERTS_URL`: http://email-alerts.fraud-detection.local:8080/sse
- `MCP_FRAUD_LOGGER_URL`: http://fraud-logger.fraud-detection.local:8080/sse
- `MCP_GEOLOCATION_URL`: http://geolocation-checker.fraud-detection.local:8080/sse
- `MCP_REPORT_GENERATOR_URL`: http://report-generator.fraud-detection.local:8080/sse
- `AWS_REGION`: us-west-2

### Email Alerts Task
- `SENDER_EMAIL`: fraud-alerts@yourdomain.com
- `ALERT_RECIPIENTS`: security-team@yourdomain.com
- `AWS_REGION`: us-west-2

## Cost Optimization

- Use Fargate Spot for MCP servers (cheaper)
- Use regular Fargate for UI (reliability)
- Set appropriate task sizes:
  - MCP servers: 0.5 vCPU, 1 GB RAM
  - UI: 1 vCPU, 2 GB RAM

## Monitoring

- CloudWatch Container Insights enabled
- ALB access logs to S3
- ECS task logs to CloudWatch Logs

## Troubleshooting

### MCP Servers Not Reachable
1. Check service discovery: `dig transaction-risk.fraud-detection.local`
2. Verify security groups allow port 8080
3. Check ECS task logs

### UI Can't Connect to MCP Servers
1. Verify environment variables
2. Check network connectivity from UI task
3. Verify Cloud Map namespace

### ALB Returns 503
1. Check target health in ALB console
2. Verify UI task is running
3. Check security groups

## Next Steps

After deployment:
1. Access UI via ALB DNS name
2. Test with sample transactions
3. When DeepSeek EKS is ready, update UI env var
4. Monitor CloudWatch metrics
