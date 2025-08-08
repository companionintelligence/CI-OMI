#!/bin/bash
# Deployment script for Omi Companion API
# This script sets up nginx reverse proxy and deploys the application

set -e

echo "🚀 Deploying Omi Companion API..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root (use sudo)"
    exit 1
fi

# Configuration
DOMAIN="dev.companionintelligence.com"
APP_DIR="/opt/omi-companion"
NGINX_CONF="/etc/nginx/sites-available/companion"
NGINX_ENABLED="/etc/nginx/sites-enabled/companion"

# Create application directory
echo "📁 Creating application directory..."
mkdir -p $APP_DIR
mkdir -p /var/www/companion/static
mkdir -p /var/log/nginx

# Copy application files
echo "📋 Copying application files..."
cp -r . $APP_DIR/
chown -R www-data:www-data $APP_DIR
chmod -R 755 $APP_DIR

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
cd $APP_DIR
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# Create systemd service
echo "🔧 Creating systemd service..."
cat > /etc/systemd/system/omi-companion.service << EOF
[Unit]
Description=Omi Companion API
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
ExecStart=$APP_DIR/venv/bin/python backend/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Copy nginx configuration
echo "🌐 Setting up nginx configuration..."
cp nginx/companion.conf $NGINX_CONF

# Enable nginx site
if [ -L $NGINX_ENABLED ]; then
    rm $NGINX_ENABLED
fi
ln -s $NGINX_CONF $NGINX_ENABLED

# Test nginx configuration
echo "🧪 Testing nginx configuration..."
nginx -t

# Reload nginx
echo "🔄 Reloading nginx..."
systemctl reload nginx

# Enable and start service
echo "🚀 Starting Omi Companion service..."
systemctl daemon-reload
systemctl enable omi-companion
systemctl start omi-companion

# Check service status
echo "📊 Checking service status..."
systemctl status omi-companion --no-pager

echo "✅ Deployment complete!"
echo ""
echo "🌐 Your API is now available at:"
echo "   https://$DOMAIN"
echo ""
echo "📋 Useful commands:"
echo "   sudo systemctl status omi-companion"
echo "   sudo systemctl restart omi-companion"
echo "   sudo nginx -t"
echo "   sudo systemctl reload nginx"
echo ""
echo "📁 Application directory: $APP_DIR"
echo "📄 Nginx config: $NGINX_CONF"
echo "📊 Logs: /var/log/nginx/companion_*.log"
