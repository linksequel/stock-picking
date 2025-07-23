#!/bin/bash

echo "开始部署股票信号分析系统..."

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "Docker未安装，请先安装Docker"
    exit 1
fi

# 检查Docker Compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose未安装，请先安装Docker Compose"
    exit 1
fi

# 停止已存在的容器
echo "停止现有容器..."
docker-compose down

# 构建并启动容器
echo "构建并启动容器..."
docker-compose up -d --build

# 检查容器状态
echo "检查容器状态..."
docker-compose ps

echo "部署完成！"
echo "访问地址: http://你的服务器IP"
echo "查看日志: docker-compose logs -f" 