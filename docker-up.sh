#!/bin/bash
# 便捷脚本 - 启动Docker容器

echo "Starting Lantern Hedge Bot with Docker..."
docker-compose -f config/docker-compose.yml up -d

echo ""
echo "Container started! Use these commands:"
echo "  View logs:    docker-compose -f config/docker-compose.yml logs -f"
echo "  Stop:         docker-compose -f config/docker-compose.yml down"
echo "  Restart:      docker-compose -f config/docker-compose.yml restart"