#!/usr/bin/with-contenv bashio

echo "--- PowMr Bridge Diagnostic Start ---"
echo "Current user: $(id)"
echo "Capabilities: $(capsh --print 2>/dev/null || echo 'capsh not found')"
echo "Network Interface Info:"
ip addr show | grep -E 'eth0|wlan0|end0' || ip addr show

echo "Checking iptables availability..."
which iptables-legacy || echo "iptables-legacy not found"
which iptables || echo "iptables not found"

# Спроба налаштувати REDIRECT
echo "Setting up port redirection (1883 -> 18899)..."
iptables-legacy -t nat -A PREROUTING -p tcp --dport 1883 -j REDIRECT --to-port 18899 2>/tmp/ipt_err || \
iptables -t nat -A PREROUTING -p tcp --dport 1883 -j REDIRECT --to-port 18899 2>>/tmp/ipt_err || \
echo "CRITICAL: iptables failed. Error: $(cat /tmp/ipt_err)"

echo "--- Diagnostic End ---"

# Export HA MQTT settings
export MQTT_HOST=$(bashio::config 'mqtt_host' 'core-mosquitto')
export MQTT_PORT=$(bashio::config 'mqtt_port' '1883')
export MQTT_USER=$(bashio::config 'mqtt_user' '')
export MQTT_PASSWORD=$(bashio::config 'mqtt_password' '')

# Export user options
export TARGET_HOST=$(bashio::config 'TARGET_HOST' '8.212.18.157')
export TARGET_PORT=$(bashio::config 'TARGET_PORT' '1883')
export LISTEN_PORT=$(bashio::config 'LISTEN_PORT' '18899')
export INVERTER_IP=$(bashio::config 'INVERTER_IP' '')
export ROUTER_IP=$(bashio::config 'ROUTER_IP' '')

echo "Starting PowMr HA Bridge..."
python3 -u /app/powmr_bridge.py
