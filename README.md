# AWS Python DevOps Solution — Step-by-step Guide

## Overview
This repository demonstrates a complete **Python + AWS** DevOps solution:
- FastAPI CRUD app backed by PostgreSQL
- Docker + Docker Compose for local development
- GitHub Actions CI to build & push Docker images
- Terraform for provisioning AWS (VPC, EKS, RDS)
- Helm charts to deploy on EKS
- Prometheus monitoring and alert rules

> This README contains **explicit step-by-step commands** for each stage (local dev, CI, AWS infra, deployment, monitoring, and cleanup). Replace placeholders (like `<DOCKERHUB_USERNAME>`, `<RDS_ENDPOINT>`, and `<AWS_REGION>`) with your values.

---

## Prerequisites (install tools)

### Ubuntu / Debian
```bash
# update & install essentials
sudo apt-get update && sudo apt-get install -y   python3 python3-venv python3-pip   docker.io docker-compose unzip wget curl   apt-transport-https ca-certificates gnupg lsb-release   software-properties-common

# Install Terraform (example)
wget https://releases.hashicorp.com/terraform/1.5.7/terraform_1.5.7_linux_amd64.zip
unzip terraform_1.5.7_linux_amd64.zip && sudo mv terraform /usr/local/bin/

# Install AWS CLI v2 (example)
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install

# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

### macOS (Homebrew)
```bash
brew update
brew install python docker docker-compose terraform awscli kubectl helm
```

### Docker (start & enable)
```bash
# Linux (systemd)
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER   # log out/in for group change to take effect
```

---

## 1) Clone repository
```bash
git clone <REPO_URL> aws-python-solution
cd aws-python-solution
ls -la
```

---

## 2) Local development — Docker Compose (quick start)
This runs Postgres + the FastAPI app locally.

```bash
# Build and start containers
sudo docker-compose up --build

# In another terminal, check logs
sudo docker-compose logs -f web

# API endpoints
# Create item (POST)
curl -s -X POST "http://localhost:8000/items" -H "Content-Type: application/json"   -d '{ "name": "Book", "description": "A novel" }' | jq

# List items (GET)
curl -s http://localhost:8000/items | jq

# Swagger UI
# Open: http://localhost:8000/docs
```

### Alternative: Run the app without Docker (virtualenv)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
export DATABASE_URL=postgresql://dev:dev@localhost:5432/itemsdb  # run local Postgres
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 3) Build & push Docker image (local)
Replace `<DOCKERHUB_USERNAME>` with your Docker Hub username.

```bash
# Build image locally
docker build -t <DOCKERHUB_USERNAME>/items-api:latest .

# Login to Docker Hub
docker login

# Push image
docker push <DOCKERHUB_USERNAME>/items-api:latest
```

---

## 4) GitHub Actions — connect secrets (if using the provided CI)
Set these in your GitHub repo settings → Settings → Secrets → Actions.

Required secrets:
- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN` (Docker Hub access token)

Optionally, use the GitHub CLI (`gh`) to set them:
```bash
# Install GitHub CLI and authenticate first: gh auth login
gh secret set DOCKERHUB_USERNAME --body "<DOCKERHUB_USERNAME>" -R <owner>/<repo>
gh secret set DOCKERHUB_TOKEN --body "<DOCKERHUB_TOKEN>" -R <owner>/<repo>
```

Once you push to `main`, the workflow `.github/workflows/ci.yml` will build & push the image.

---

## 5) Terraform — provision AWS (EKS + RDS)
> Ensure AWS CLI is configured: `aws configure` or export `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_REGION` env vars.

```bash
cd terraform

# Initialize terraform provider plugins
terraform init

# Plan (replace DB password placeholder)
terraform plan -var="db_password=SuperSecret123" -out=tfplan

# Apply the plan (creates VPC, EKS cluster nodes, RDS)
terraform apply -var="db_password=SuperSecret123" -auto-approve

# Get outputs (RDS endpoint)
terraform output db_endpoint
# Example output usage (store in shell variable)
export RDS_ENDPOINT=$(terraform output -raw db_endpoint)
echo "RDS endpoint: $RDS_ENDPOINT"
```

**Important notes:**
- For production, use remote state (S3 + DynamoDB locking).
- Use strong DB password or use AWS Secrets Manager and inject via Terraform.

---

## 6) Configure kubectl to use EKS cluster
After Terraform creates EKS, run:

```bash
aws eks update-kubeconfig --region <AWS_REGION> --name devops-eks
kubectl get nodes
```

If Terraform provides kubeconfig, you can write it to file:
```bash
terraform output -raw kubeconfig > kubeconfig.yaml
export KUBECONFIG=$(pwd)/kubeconfig.yaml
kubectl get nodes
```

---

## 7) Helm — deploy app to EKS
1. Edit `helm/items-api/values.yaml`:
   - Set `image.repository` → `<DOCKERHUB_USERNAME>/items-api`
   - Set `env.DATABASE_URL` → `postgresql://<DB_USER>:<DB_PASS>@<RDS_ENDPOINT>:5432/itemsdb`

Example (in shell):
```bash
# quick edit (replace values)
RDS_ENDPOINT=$(terraform output -raw db_endpoint)
sed -i "s|<DOCKERHUB_USERNAME>|<your-dockerhub-username>|g" helm/items-api/values.yaml
sed -i "s|<RDS_ENDPOINT>|${RDS_ENDPOINT}|g" helm/items-api/values.yaml
```

2. Install the app via Helm:
```bash
helm repo add bitnami https://charts.bitnami.com/bitnami  # optional; for useful charts
helm install items-api ./helm/items-api -n default --create-namespace
```

3. Check pods and services:
```bash
kubectl get pods -l app=items-api -o wide
kubectl get svc -l app=items-api
# Check logs
kubectl logs -f deploy/items-api
```

If you need to update image or DB config, change `values.yaml` and run:
```bash
helm upgrade items-api ./helm/items-api -n default
```

---

## 8) Provide DB credentials securely (Kubernetes Secrets)
Instead of putting DB URL in `values.yaml`, create a Kubernetes secret and modify the Helm chart to read it from env.

Create secret example:
```bash
cat <<EOF > .env
DATABASE_URL=postgresql://items_user:SuperSecret123@${RDS_ENDPOINT}:5432/itemsdb
EOF

kubectl create secret generic items-db-secret --from-env-file=.env -n default

# Make sure helm chart uses envFrom secretKeyRef or envFrom secret
```

Example with kubectl to patch deployment env (one-time demonstration):
```bash
kubectl set env deployment/items-api --from=secret/items-db-secret -n default
```

---

## 9) Monitoring — Prometheus & ServiceMonitor
Install kube-prometheus-stack (Prometheus + Grafana + Alertmanager):
```bash
kubectl create namespace monitoring
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring
```

Apply ServiceMonitor & alert rules:
```bash
kubectl apply -f monitoring/servicemonitor.yaml -n monitoring
kubectl apply -f monitoring/alerts.yaml -n monitoring
```

Check Prometheus targets:
```bash
# Port-forward Prometheus or access Grafana
kubectl get pods -n monitoring
kubectl port-forward svc/kube-prometheus-stack-prometheus -n monitoring 9090:9090 &
# Then open http://localhost:9090/targets
```

Grafana: find service and port-forward to access dashboards:
```bash
kubectl port-forward svc/kube-prometheus-stack-grafana -n monitoring 3000:80 &
# Open http://localhost:3000  (default admin credentials in Helm notes)
```

---

## 10) Test end-to-end (example)
1. Confirm image is pushed to Docker Hub:
```bash
docker pull <DOCKERHUB_USERNAME>/items-api:latest
```
2. Ensure Helm deployed pods are running:
```bash
kubectl rollout status deployment/items-api -n default
kubectl get pods -l app=items-api -n default
```
3. Get LoadBalancer external IP or port-forward:
```bash
kubectl get svc items-api -o wide
# or port-forward to test locally
kubectl port-forward svc/items-api 8000:80 -n default
curl -s http://localhost:8000/items | jq
```

---

## 11) Cleanup commands
### Local Docker cleanup
```bash
docker-compose down -v
docker system prune -f
docker rmi <DOCKERHUB_USERNAME>/items-api:latest || true
```

### Helm / Kubernetes cleanup
```bash
helm uninstall items-api -n default || true
helm uninstall kube-prometheus-stack -n monitoring || true
kubectl delete namespace monitoring || true
kubectl delete secret items-db-secret -n default || true
```

### Terraform destroy (AWS infra)
```bash
cd terraform
terraform destroy -var="db_password=SuperSecret123" -auto-approve
```

---

## 12) Helpful troubleshooting commands
```bash
# Kubernetes debugging
kubectl describe pod <pod-name> -n default
kubectl logs -f deployment/items-api -n default

# Terraform diagnostics
terraform plan
terraform show

# AWS: check EKS cluster status
aws eks describe-cluster --name devops-eks --region <AWS_REGION>
```

---

## 13) Security & production notes
- Use **AWS Secrets Manager** or **SSM Parameter Store** for credentials in production.
- Use **IRSA** to grant AWS permissions to pods securely.
- Use private ECR for images and configure EKS node role to pull images using IAM roles.
- Use TLS (cert-manager + ingress) for secure endpoints.
- Protect Terraform state with S3 + DynamoDB state locking.

---

## 14) Support / Next steps
If you'd like, I can:
- create a ready-to-run CloudFormation / Terraform that uses Secrets Manager for DB credentials,
- add GitHub Actions to run `terraform plan` and `terraform apply` in a controlled fashion,
- or produce a PDF guide with diagrams for architecture and networking details.

---
