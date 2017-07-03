#!/bin/bash
# This script changes the NGINX configuration to be able to
# renew the Let's Encrypt certificates. Then restores the normal NGINX config.
# (In addition, it's required to open the port 80 to make the renewal)

# Set renewal config
systemctl stop nginx.service
ln -s /etc/nginx/sites-available/renew /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/hass_kodi
systemctl start nginx.service

# Run renewal
/home/pi/certbot-auto renew

# Restore config
systemctl stop nginx.service
ln -s /etc/nginx/sites-available/hass_kodi /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/renew
systemctl start nginx.service

exit 0
