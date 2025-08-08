#!/bin/bash
# Nginx reset script for macOS
# This script sets up nginx for the Omi Companion API

set -e

echo "🍎 Setting up nginx for macOS..."

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew is not installed. Please install it first:"
    echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi

# Install nginx if not already installed
if ! command -v nginx &> /dev/null; then
    echo "📦 Installing nginx..."
    brew install nginx
else
    echo "✅ nginx is already installed"
fi

# Get the nginx configuration directory based on architecture
if [[ $(uname -m) == "arm64" ]]; then
    # Apple Silicon
    NGINX_CONF_DIR="/opt/homebrew/etc/nginx"
    NGINX_VAR_DIR="/opt/homebrew/var"
else
    # Intel
    NGINX_CONF_DIR="/usr/local/etc/nginx"
    NGINX_VAR_DIR="/usr/local/var"
fi

echo "📁 Using nginx config directory: $NGINX_CONF_DIR"
echo "📁 Using nginx var directory: $NGINX_VAR_DIR"

# Create necessary directories
echo "📁 Creating nginx directories..."
sudo mkdir -p $NGINX_VAR_DIR/log/nginx
sudo mkdir -p $NGINX_VAR_DIR/run
sudo mkdir -p $NGINX_CONF_DIR/sites-available
sudo mkdir -p $NGINX_CONF_DIR/sites-enabled

# Copy the nginx configuration
echo "📋 Copying nginx configuration..."
sudo cp nginx/companion.conf $NGINX_CONF_DIR/sites-available/companion

# Create symlink for the site
echo "🔗 Creating site symlink..."
if [ -L "$NGINX_CONF_DIR/sites-enabled/companion" ]; then
    sudo rm $NGINX_CONF_DIR/sites-enabled/companion
fi
sudo ln -s $NGINX_CONF_DIR/sites-available/companion $NGINX_CONF_DIR/sites-enabled/

# Update the main nginx.conf to include sites-enabled
echo "🔧 Updating main nginx configuration..."
if [ ! -f "$NGINX_CONF_DIR/nginx.conf.backup" ]; then
    sudo cp $NGINX_CONF_DIR/nginx.conf $NGINX_CONF_DIR/nginx.conf.backup
fi

# Create a new nginx.conf that includes our sites
sudo tee $NGINX_CONF_DIR/nginx.conf > /dev/null << EOF
worker_processes  1;

events {
    worker_connections  1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;

    sendfile        on;
    keepalive_timeout  65;

    # Include sites-enabled
    include $NGINX_CONF_DIR/sites-enabled/*;

    # Default server block (fallback)
    server {
        listen       8080;
        server_name  localhost;

        location / {
            root   html;
            index  index.html index.htm;
        }

        error_page   500 502 503 504  /50x.html;
        location = /50x.html {
            root   html;
        }
    }
}
EOF

# Test nginx configuration
echo "🧪 Testing nginx configuration..."
if sudo nginx -t; then
    echo "✅ nginx configuration is valid"
else
    echo "❌ nginx configuration test failed"
    exit 1
fi

# Start nginx if not running
if ! pgrep -x "nginx" > /dev/null; then
    echo "🚀 Starting nginx..."
    sudo nginx
else
    echo "🔄 Reloading nginx..."
    sudo nginx -s reload
fi

echo ""
echo "✅ nginx setup complete!"
echo ""
echo "🌐 Your API will be available at:"
echo "   http://localhost:8080 (HTTP)"
echo "   https://dev.companionintelligence.com (HTTPS - when SSL is configured)"
echo ""
echo "📋 Useful commands:"
echo "   sudo nginx -t                    # Test configuration"
echo "   sudo nginx -s reload            # Reload configuration"
echo "   sudo nginx -s stop              # Stop nginx"
echo "   sudo nginx                      # Start nginx"
echo ""
echo "📁 Configuration files:"
echo "   Main config: $NGINX_CONF_DIR/nginx.conf"
echo "   Site config: $NGINX_CONF_DIR/sites-available/companion"
echo "   Logs: $NGINX_VAR_DIR/log/nginx/"
echo ""
echo "🔒 For HTTPS setup, you'll need to:"
echo "   1. Get an SSL certificate for dev.companionintelligence.com"
echo "   2. Update the SSL paths in nginx/companion.conf"
echo "   3. Reload nginx: sudo nginx -s reload"