#!/bin/bash
# sisys - Docker Engine Setup for WSL 2 (Ubuntu 22.04)
# Run this script inside WSL 2 Ubuntu terminal after initial setup

set -e

echo "============================================================"
echo "  sisys - Docker Engine Setup for WSL 2"
echo "============================================================"
echo ""

# Check if running in WSL
if grep -qi microsoft /proc/version; then
    echo "[OK] Running in WSL"
else
    echo "[WARN] Not running in WSL, but continuing anyway..."
fi

# Step 1: Update system
echo "[STEP 1/6] Updating system..."
sudo apt update
sudo apt upgrade -y
echo "[OK] System updated"
echo ""

# Step 2: Install prerequisites
echo "[STEP 2/6] Installing prerequisites..."
sudo apt install -y ca-certificates curl gnupg lsb-release
echo "[OK] Prerequisites installed"
echo ""

# Step 3: Add Docker's official GPG key
echo "[STEP 3/6] Adding Docker GPG key..."
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "[OK] Docker GPG key added"
echo ""

# Step 4: Add Docker repository
echo "[STEP 4/6] Adding Docker repository..."
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
echo "[OK] Docker repository added"
echo ""

# Step 5: Install Docker Engine
echo "[STEP 5/6] Installing Docker Engine..."
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
echo "[OK] Docker Engine installed"
echo ""

# Step 6: Configure non-root access
echo "[STEP 6/6] Configuring non-root access..."
sudo usermod -aG docker $USER
echo "[OK] User added to docker group"
echo "[INFO] Please log out and log back in for group changes to take effect"
echo ""

# Verify installation
echo "============================================================"
echo "  Verifying Installation"
echo "============================================================"
echo ""

echo "Docker version:"
docker --version

echo ""
echo "Docker Compose version:"
docker compose version

echo ""
echo "============================================================"
echo "  Setup Complete!" -green
echo "============================================================"
echo ""
echo "Next steps:"
echo "1. Log out and log back in (or run: newgrp docker)"
echo "2. Verify Docker works: docker ps"
echo "3. Start Docker daemon: sudo systemctl start docker"
echo "4. Navigate to sisys project: cd ~/sisys"
echo "5. Start services: cd docker && docker-compose up -d"
echo ""
