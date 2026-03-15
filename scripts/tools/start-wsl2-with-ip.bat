@echo off
:: start-wsl2-with-ip.bat
set DISTRO=%1
set IP=%2
wsl -d %DISTRO% -e sudo sh -c "echo 'nameserver 8.8.8.8' > /etc/resolv.conf"
wsl -d %DISTRO% -e sudo ip addr add %IP%/24 dev eth0
