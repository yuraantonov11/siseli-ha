#!/usr/bin/with-contenv bashio

echo "--- PowMr Bridge 1.2.4 START ---"

# 1. Спершу експортуємо ВСІ змінні
export MQTT_HOST=$(bashio::config 'mqtt_host' 'core-mosquitto')
export MQTT_PORT=$(bashio::config 'mqtt_port' '1883')
export MQTT_USER=$(bashio::config 'mqtt_user' '')
export MQTT_PASSWORD=$(bashio::config 'mqtt_password' '')
export TARGET_HOST=$(bashio::config 'TARGET_HOST' '8.212.18.157')
export TARGET_PORT=$(bashio::config 'TARGET_PORT' '1883')
export LISTEN_PORT=$(bashio::config 'LISTEN_PORT' '18899')
export INVERTER_IP=$(bashio::config 'INVERTER_IP' '')
export ROUTER_IP=$(bashio::config 'ROUTER_IP' '')
export INVERTER_MAC=$(bashio::config 'INVERTER_MAC' '')
export ROUTER_MAC=$(bashio::config 'ROUTER_MAC' '')

# 2. Діагностика (тиха)
echo "Interface: $(ip route | grep default | awk '{print $5}')"
echo "IP Forwarding: $(cat /proc/sys/net/ipv4/ip_forward)"

# 3. Налаштування iptables
echo "Configuring Port Redirection (1883 -> $LISTEN_PORT)..."
iptables-legacy -t nat -A PREROUTING -p tcp --dport 1883 -j REDIRECT --to-port $LISTEN_PORT 2>/tmp/ipt_err || \
iptables -t nat -A PREROUTING -p tcp --dport 1883 -j REDIRECT --to-port $LISTEN_PORT 2>>/tmp/ipt_err

if [ -s /tmp/ipt_err ]; then
    echo "NOTICE: iptables issues (check Protection Mode): $(cat /tmp/ipt_err)"
fi

echo "Launching Python Bridge..."
python3 -u /app/powmr_bridge.py
