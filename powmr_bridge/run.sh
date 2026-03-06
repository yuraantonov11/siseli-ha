#!/usr/bin/with-contenv bashio

echo "--- PowMr Bridge 1.8.0 (Full Autonomous L2 Bridge) ---"

# 1. Експорт налаштувань
export MQTT_HOST=$(bashio::config 'mqtt_host' 'core-mosquitto')
export MQTT_PORT=$(bashio::config 'mqtt_port' '1883')
export MQTT_USER=$(bashio::config 'mqtt_user' '')
export MQTT_PASSWORD=$(bashio::config 'mqtt_password' '')
export TARGET_HOST=$(bashio::config 'TARGET_HOST' '8.212.18.157')
export INVERTER_IP=$(bashio::config 'INVERTER_IP' '192.168.1.139')
export ROUTER_IP=$(bashio::config 'ROUTER_IP' '192.168.1.1')

# 2. Очищення мережевих правил
iptables -t nat -F PREROUTING 2>/dev/null
iptables -F INPUT 2>/dev/null
iptables -F FORWARD 2>/dev/null

# 3. Блокуємо ядро від обробки пакетів інвертора (Python зробить це сам)
iptables -I INPUT -s $INVERTER_IP -j DROP
iptables -I FORWARD -s $INVERTER_IP -j DROP

echo "Launching Python L2 Bridge..."
python3 -u /app/powmr_bridge.py
