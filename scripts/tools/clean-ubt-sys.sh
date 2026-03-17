#!/bin/bash

sudo apt clean                 # 删除所有缓存的包
sudo apt autoclean             # 只删除已无法下载的过时包（可选）
sudo journalctl --vacuum-time=1s
sudo find /var/log -type f -name "*.log" -mtime +1 -delete   # 删除 7 天前的 .log 文件
sudo rm -rf /tmp/*
sudo rm -rf /var/tmp/*
rm -rf ~/.local/share/Trash/*          # 回收站（如果 WSL 启用了回收站）
rm -f ~/.bash_history                  # 清除历史命令（可选）
history -c                             # 清空当前会话历史
# rm -rf ~/.cache/*                     # 用户级缓存
