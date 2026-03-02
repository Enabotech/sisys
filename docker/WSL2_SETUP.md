# sisys - WSL 2 Setup Guide

This guide provides detailed instructions for setting up sisys development environment on WSL 2 with Ubuntu 22.04.

## Why WSL 2?

**Advantages over Docker Desktop:**

- Better performance for file I/O operations (when working in WSL filesystem)
- Native Linux environment for development
- No Docker Desktop license restrictions for enterprises
- Lower resource overhead
- Better integration with Linux tools

**Considerations:**

- Requires manual Docker Engine setup
- Some GUI features may require additional configuration
- Windows-Docker Desktop integration features not available

## Prerequisites

### Windows 11 Requirements

- Windows 11 version 21H2 or later
- Virtualization enabled in BIOS/UEFI
- WSL 2 enabled

### Enable WSL 2

From PowerShell (Administrator):

```powershell
# Enable WSL
wsl --install

# Set WSL 2 as default
wsl --set-default-version 2

# Install Ubuntu 22.04
wsl --install -d Ubuntu-22.04

# Check WSL version
wsl --list --verbose
```

Restart your computer if prompted.

## Docker Engine Setup

### Step 1: Update Ubuntu

```bash
sudo apt update
sudo apt upgrade -y
```

### Step 2: Install Docker Engine

```bash
# Download Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

### Step 3: Configure Non-Root Access

```bash
# Add your user to docker group
sudo usermod -aG docker $USER

# Apply group changes
newgrp docker

# Verify (should work without sudo)
docker ps
```

### Step 4: Start Docker Service

```bash
# Start Docker daemon
sudo systemctl start docker

# Enable Docker to start on boot
sudo systemctl enable docker

# Check status
sudo systemctl status docker
```

## Project Setup

### Step 1: Clone Repository

**IMPORTANT:** Always clone to WSL filesystem, NOT to `/mnt/c/`

```bash
# Navigate to home directory
cd ~

# Clone repository
git clone <repository-url>
cd sisys
```

### Step 2: Verify Docker Compose

```bash
# Navigate to docker directory
cd docker

# Verify docker-compose.yml
docker-compose config

# Start services
docker-compose up -d

# Check service status
docker-compose ps
```

### Step 3: Install Python Dependencies

```bash
# Return to project root
cd ..

# Install Poetry (if not installed)
curl -sSL https://install.python-poetry.org | python3 -

# Add Poetry to PATH
export PATH="$HOME/.local/bin:$PATH"

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

### Step 4: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your values
nano .env
```

### Step 5: Verify Setup

```bash
# Run health check
python scripts/monitoring/health_check.py

# Or run Story 0.1 acceptance test
python tests/e2e/test_story_01.py
```

## Performance Tips

### File System Performance

**DO:** Work in WSL filesystem (`~/sisys`, `/home/user/sisys`)
**DON'T:** Work in mounted Windows filesystem (`/mnt/c/sisys`)

```bash
# Good - Fast I/O
cd ~/sisys

# Bad - Slow I/O, avoid for development
cd /mnt/c/sisys
```

### Accessing Services

From WSL 2:
```bash
# Access via localhost
curl http://localhost:5432  # PostgreSQL
curl http://localhost:6379  # Redis
```

From Windows:
```powershell
# Access via localhost (WSL 2 networking)
curl http://localhost:5432  # PostgreSQL
curl http://localhost:6379  # Redis
```

### VSCode Integration

Install these extensions in VSCode:

- **WSL** (Microsoft)
- **Remote - WSL** (Microsoft)
- **Docker** (Microsoft)
- **Python** (Microsoft)

Open project in WSL:
```bash
# From WSL terminal
code .
```

## Troubleshooting

### Docker Daemon Not Running

```bash
# Start Docker daemon
sudo systemctl start docker

# Check status
sudo systemctl status docker
```

### Permission Denied Errors

```bash
# Re-add user to docker group
sudo usermod -aG docker $USER

# Log out and log back in
exit
# Then reconnect to WSL
```

### Port Already in Use

```bash
# Find process using port (from PowerShell)
netstat -ano | findstr :5432

# Stop conflicting service or change port in docker-compose.yml
```

### WSL 2 Networking Issues

```powershell
# From PowerShell (Administrator)
wsl --shutdown
wsl

# Restart Docker in WSL
sudo systemctl restart docker
```

### Disk Space Issues

```bash
# Clean up Docker resources
docker system prune -a

# Clean up WSL disk
wsl --shutdown
diskpart
# Select and compact VHD (advanced users only)
```

## Comparison: Docker Desktop vs WSL 2

| Feature | Docker Desktop | WSL 2 + Docker Engine |
|---------|---------------|----------------------|
| Setup Complexity | Easy | Medium |
| Performance | Good | Better (in WSL fs) |
| License | Free for personal, paid for enterprise | Free (GPL) |
| GUI Support | Built-in | Requires setup |
| Windows Integration | Excellent | Good |
| Resource Usage | Higher | Lower |
| File I/O (WSL fs) | Good | Excellent |
| File I/O (Windows fs) | Excellent | Poor |

## Next Steps

After setup:

1. ✅ Story 0.1: Development Environment Setup (Complete)
2. ⏳ Story 0.2: CI/CD Pipeline
3. ⏳ Story 0.3: Test Framework Setup

---

**Last Updated:** 2026-02-28
**WSL 2 Version:** 2
**Ubuntu Version:** 22.04 LTS
