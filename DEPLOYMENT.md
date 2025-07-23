# 股票信号分析系统 - Linux服务器部署指南

## 部署方案对比

### 方案一：Docker容器化部署 ⭐⭐⭐⭐⭐ (推荐)
- **优点**: 环境隔离、易于管理、支持一键部署、可扩展性强
- **适用**: 所有生产环境，特别适合云服务器

### 方案二：传统部署 + Nginx + Gunicorn ⭐⭐⭐
- **优点**: 性能更高、资源占用少
- **适用**: 对性能要求较高的环境

### 方案三：PM2/Supervisor进程管理 ⭐⭐⭐
- **优点**: 简单直接、便于调试
- **适用**: 小型项目或开发环境

---

## 方案一：Docker容器化部署（推荐）

### 前置条件
- Linux服务器 (Ubuntu 18.04+, CentOS 7+)
- Docker 20.10+
- Docker Compose 1.27+

### 步骤1: 服务器准备
```bash
# Ubuntu/Debian系统
sudo apt update
sudo apt install -y curl git

# CentOS/RHEL系统  
sudo yum update
sudo yum install -y curl git

# 安装Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 重新登录或执行
newgrp docker
```

### 步骤2: 部署项目
```bash
# 上传项目文件到服务器
# 可使用scp, rsync, git clone等方式

# 进入项目目录
cd /path/to/stock-picking

# 赋予部署脚本执行权限
chmod +x deploy.sh

# 一键部署
./deploy.sh
```

### 步骤3: 验证部署
```bash
# 检查容器状态
docker-compose ps

# 查看应用日志
docker-compose logs -f stock-app

# 查看Nginx日志
docker-compose logs -f nginx
```

### 步骤4: 访问应用
- 主页: `http://你的服务器IP`
- 历史信号: `http://你的服务器IP/history`

### 常用管理命令
```bash
# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 更新代码后重新部署
docker-compose down
docker-compose up -d --build

# 查看实时日志
docker-compose logs -f

# 进入容器
docker-compose exec stock-app bash
```

---

## 方案二：传统部署 + Nginx + Gunicorn

### 步骤1: 环境准备
```bash
# 安装Python和pip
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx

# 创建用户
sudo useradd -m -s /bin/bash stockapp
sudo su - stockapp
```

### 步骤2: 项目配置
```bash
# 克隆代码
git clone <your-repo> /home/stockapp/stock-picking
cd /home/stockapp/stock-picking

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install gunicorn

# 创建Gunicorn配置
cat > gunicorn.conf.py << 'EOF'
bind = "127.0.0.1:8000"
workers = 2
worker_class = "sync"
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
user = "stockapp"
group = "stockapp"
daemon = False
pidfile = "/tmp/gunicorn.pid"
accesslog = "/home/stockapp/stock-picking/log/gunicorn_access.log"
errorlog = "/home/stockapp/stock-picking/log/gunicorn_error.log"
loglevel = "info"
EOF
```

### 步骤3: Systemd服务配置
```bash
# 退出到root用户
exit

# 创建systemd服务文件
sudo cat > /etc/systemd/system/stockapp.service << 'EOF'
[Unit]
Description=Stock Signal Analysis App
After=network.target

[Service]
User=stockapp
Group=stockapp
WorkingDirectory=/home/stockapp/stock-picking
Environment=FLASK_ENV=production
ExecStart=/home/stockapp/stock-picking/venv/bin/gunicorn -c gunicorn.conf.py app:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 启用并启动服务
sudo systemctl daemon-reload
sudo systemctl enable stockapp
sudo systemctl start stockapp
sudo systemctl status stockapp
```

### 步骤4: Nginx配置
```bash
sudo cat > /etc/nginx/sites-available/stockapp << 'EOF'
server {
    listen 80;
    server_name 你的域名或IP;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /home/stockapp/stock-picking/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# 启用站点
sudo ln -s /etc/nginx/sites-available/stockapp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 方案三：PM2进程管理

### 步骤1: 安装Node.js和PM2
```bash
# 安装Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# 安装PM2
sudo npm install -g pm2
```

### 步骤2: PM2配置
```bash
# 创建PM2配置文件
cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [{
    name: 'stock-app',
    script: 'app.py',
    interpreter: 'python3',
    cwd: '/path/to/stock-picking',
    env: {
      FLASK_ENV: 'production'
    },
    instances: 1,
    exec_mode: 'fork',
    watch: false,
    max_memory_restart: '1G',
    error_file: './log/pm2_error.log',
    out_file: './log/pm2_out.log',
    log_file: './log/pm2_combined.log',
    time: true
  }]
};
EOF

# 启动应用
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

---

## 安全配置建议

### 1. 防火墙配置
```bash
# Ubuntu UFW
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable

# CentOS Firewalld
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### 2. SSL证书配置 (可选)
```bash
# 使用Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d 你的域名
```

### 3. 日志轮转
```bash
# 配置logrotate
sudo cat > /etc/logrotate.d/stockapp << 'EOF'
/home/stockapp/stock-picking/log/*.log {
    daily
    missingok
    rotate 30
    compress
    notifempty
    create 644 stockapp stockapp
    postrotate
        sudo systemctl reload stockapp
    endscript
}
EOF
```

---

## 监控和维护

### 1. 健康检查脚本
```bash
cat > health_check.sh << 'EOF'
#!/bin/bash
URL="http://localhost/api/signals"
if curl -f -s $URL > /dev/null; then
    echo "$(date): Service is healthy"
else
    echo "$(date): Service is down, restarting..."
    docker-compose restart stock-app
fi
EOF

chmod +x health_check.sh

# 添加到crontab (每5分钟检查一次)
echo "*/5 * * * * /path/to/health_check.sh >> /var/log/health_check.log 2>&1" | crontab -
```

### 2. 备份脚本
```bash
cat > backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backup/stockapp"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# 备份数据
tar -czf $BACKUP_DIR/data_$DATE.tar.gz history/ log/ datas/

# 保留最近7天的备份
find $BACKUP_DIR -name "data_*.tar.gz" -mtime +7 -delete
EOF

chmod +x backup.sh

# 添加到crontab (每天凌晨2点备份)
echo "0 2 * * * /path/to/backup.sh" | crontab -
```

---

## 故障排除

### 常见问题

1. **容器无法启动**
   ```bash
   docker-compose logs stock-app
   # 检查端口占用
   sudo netstat -tlnp | grep :5000
   ```

2. **数据获取失败**
   ```bash
   # 检查网络连接
   docker-compose exec stock-app ping www.baidu.com
   # 检查akshare模块
   docker-compose exec stock-app python -c "import akshare as ak; print(ak.__version__)"
   ```

3. **内存不足**
   ```bash
   # 增加Docker内存限制
   # 在docker-compose.yml中添加:
   # deploy:
   #   resources:
   #     limits:
   #       memory: 2G
   ```

### 性能优化
- 调整Gunicorn worker数量 (通常为 CPU核心数 × 2 + 1)
- 启用Nginx gzip压缩
- 配置Redis缓存 (如需要)
- 使用CDN加速静态资源

---

## 部署完成检查清单

- [ ] 服务器环境准备完成
- [ ] Docker/依赖安装完成  
- [ ] 项目代码上传完成
- [ ] 容器/服务正常启动
- [ ] 网络访问正常
- [ ] 数据获取功能正常
- [ ] 日志记录正常
- [ ] 防火墙配置完成
- [ ] 监控脚本配置完成
- [ ] 备份策略配置完成

部署成功后，你的股票信号分析系统就可以7×24小时稳定运行了！ 