#!/usr/bin/with-contenv bashio

echo "--- PowMr Bridge 1.6.0 (Transparent Proxy Mode) ---"

# Експорт налаштувань
export MQTT_HOST=$(bashio::config 'mqtt_host' 'core-mosquitto')
export MQTT_PORT=$(bashio::config 'mqtt_port' '1883')
export MQTT_USER=$(bashio::config 'mqtt_user' '')
export MQTT_PASSWORD=$(bashio::config 'mqtt_password' '')
export TARGET_HOST=$(bashio::config 'TARGET_HOST' '8.212.18.157')
export INVERTER_IP=$(bashio::config 'INVERTER_IP' '')
export ROUTER_IP=$(bashio::config 'ROUTER_IP' '')

# Перенаправляємо транзитний трафік у наш скрипт-дублікатор
iptables -t nat -A PREROUTING -p tcp --dport 1883 -j REDIRECT --to-port 18899 || echo "WARNING: iptables failed"

echo "Launching Universal Python Bridge..."
python3 -u /app/powmr_bridge.py
