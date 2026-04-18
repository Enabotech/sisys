#!/bin/bash

# 移除可能已存在的同名源
poetry source remove tsinghua 2>/dev/null
poetry source remove aliyun 2>/dev/null
poetry source remove ustc 2>/dev/null
poetry source remove tencent 2>/dev/null
poetry source remove pypi 2>/dev/null

# 按个人偏好顺序添加多个国内镜像作为主要源（越靠前优先级越高）
poetry source add --priority=primary tsinghua https://pypi.tuna.tsinghua.edu.cn/simple/
poetry source add --priority=primary aliyun https://mirrors.aliyun.com/pypi/simple/
poetry source add --priority=primary ustc https://mirrors.ustc.edu.cn/pypi/simple/
poetry source add --priority=primary tencent https://mirrors.cloud.tencent.com/pypi/simple/

# 官方 PyPI 作为补充源（所有主要源都找不到时才用）
poetry source add --priority=supplemental pypi

# 查看配置结果
poetry source show

# 更新锁文件并安装依赖
poetry lock
poetry install
