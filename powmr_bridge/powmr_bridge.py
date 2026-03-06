import asyncio
import json
import base64
import threading
import time
import os
import logging
import warnings
import paho.mqtt.client as mqtt
from datetime import datetime
from scapy.all import sniff, ARP, Ether, sendp, getmacbyip, IP, TCP, Raw, UDP

# Silence warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

# === CONFIG ===
INVERTER_IP = os.getenv('INVERTER_IP', '192.168.1.139')
ROUTER_IP = os.getenv('ROUTER_IP', '192.168.1.1')
TARGET_HOST = os.getenv('TARGET_HOST', '8.212.18.157')

HA_BROKER = os.getenv('MQTT_HOST', 'core-mosquitto')
HA_PORT = int(os.getenv('MQTT_PORT', 1883))
HA_USER = os.getenv('MQTT_USER', '')
HA_PASS = os.getenv('MQTT_PASSWORD', '')

DEVICE_ID = "powmr_rwb1"
STATE_TOPIC = f"powmr/{DEVICE_ID}/state"

INV_MAC = None
ROUTER_MAC = None

# --- MQTT ---
ha_client = mqtt.Client()
if HA_USER and HA_PASS: ha_client.username_pw_set(HA_USER, HA_PASS)

def connect_ha_mqtt():
    try:
        ha_client.connect(HA_BROKER, HA_PORT, 60)
        ha_client.loop_start()
        print("[HA MQTT] Connected to Mosquitto")
        publish_discovery()
    except Exception as e: print(f"[HA MQTT ERROR] {e}")

def publish_discovery():
    sensors = {
        "grid_v": ["Grid Voltage", "V", "voltage", "mdi:transmission-tower"],
        "grid_hz": ["Grid Frequency", "Hz", "frequency", "mdi:current-ac"],
        "out_v": ["Output Voltage", "V", "voltage", "mdi:power-plug"],
        "out_hz": ["Output Frequency", "Hz", "frequency", "mdi:current-ac"],
        "load_w": ["Active Load", "W", "power", "mdi:home-lightning-bolt"],
        "apparent_va": ["Apparent Load", "VA", "apparent_power", "mdi:flash"],
        "load_pct": ["Load Percentage", "%", "power_factor", "mdi:gauge"],
        "bat_v": ["Battery Voltage", "V", "voltage", "mdi:battery"],
        "bat_cap": ["Battery Capacity", "%", "battery", "mdi:battery-high"],
        "dischg_current": ["Battery Discharge Current", "A", "current", "mdi:battery-minus"],
        "bat_temp": ["Inverter Temperature", "°C", "temperature", "mdi:thermometer"],
        "pv_w": ["PV Power", "W", "power", "mdi:solar-power"],
        "pv_v": ["PV Voltage", "V", "voltage", "mdi:solar-panel"],
        "max_chg": ["Max Charge Current", "A", "current", "mdi:current-dc"],
        "util_chg": ["Utility Charge Current", "A", "current", "mdi:current-dc"],
        "bulk_v": ["Bulk Charging Voltage", "V", "voltage", "mdi:battery-charging-high"],
        "float_v": ["Float Charging Voltage", "V", "voltage", "mdi:battery-charging-medium"],
        "cut_v": ["Low Battery Cut-off", "V", "voltage", "mdi:battery-off-outline"]
    }
    for key, data in sensors.items():
        topic = f"homeassistant/sensor/{DEVICE_ID}/{key}/config"
        payload = {
            "name": f"PowMr {data[0]}", "state_topic": STATE_TOPIC,
            "value_template": f"{{{{ value_json.{key} }}}}", "unit_of_measurement": data[1],
            "device_class": data[2], "icon": data[3], "unique_id": f"{DEVICE_ID}_{key}",
            "device": {"identifiers": [DEVICE_ID], "name": "PowMr 6.2kW Inverter", "manufacturer": "PowMr"}
        }
        ha_client.publish(topic, json.dumps(payload), retain=True)

# --- PARSER ---
class SolarParser:
    @staticmethod
    def parse_payload(payload_bytes):
        try:
            idx = payload_bytes.find(b'{"b":')
            if idx == -1: return
            raw_json = json.loads(payload_bytes[idx:].decode('utf-8', errors='ignore'))
            state = {}
            if "b" in raw_json and "ct" in raw_json["b"]:
                blocks = {item["cn"]: base64.b64decode(item["co"]) for item in raw_json["b"]["ct"]}
                if "PS4Z" in blocks:
                    r = blocks["PS4Z"]
                    if len(r) >= 44:
                        state["grid_v"] = int.from_bytes(r[5:7], 'little') / 10.0
                        state["bat_v"] = int.from_bytes(r[13:15], 'little') / 10.0
                        state["load_w"] = int.from_bytes(r[27:29], 'little')
                        state["pv_v"] = int.from_bytes(r[39:41], 'little') / 10.0
                        pv_w = int.from_bytes(r[41:43], 'little')
                        state["pv_w"] = pv_w if pv_w < 6500 else 0
                        state["grid_hz"] = int.from_bytes(r[7:9], 'little') / 10.0
                        state["bat_cap"] = int.from_bytes(r[15:17], 'little')
                        state["out_v"] = int.from_bytes(r[21:23], 'little') / 10.0
                        state["out_hz"] = int.from_bytes(r[23:25], 'little') / 10.0
                        state["apparent_va"] = int.from_bytes(r[25:27], 'little')
                        state["load_pct"] = int.from_bytes(r[29:31], 'little')
                        state["dischg_current"] = round((state["load_w"] / state["bat_v"]), 1) if (state["grid_v"] < 100 and state["load_w"] > 0) else 0
                if "Sgx0" in blocks:
                    r = blocks["Sgx0"]
                    if len(r) >= 42:
                        state["max_chg"] = int.from_bytes(r[13:15], 'little')
                        state["util_chg"] = int.from_bytes(r[17:19], 'little')
                        state["float_v"] = int.from_bytes(r[21:23], 'little') / 10.0
                        state["bulk_v"] = int.from_bytes(r[23:25], 'little') / 10.0
                        state["cut_v"] = int.from_bytes(r[27:29], 'little') / 10.0
                        state["bat_temp"] = r[41]
            if state:
                ha_client.publish(STATE_TOPIC, json.dumps(state))
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ➡️ Data duplicated to HA: {len(state)} params.")
        except: pass

# --- ARP SPOOFER ---
class ArpSpoofer:
    def run(self):
        global INV_MAC, ROUTER_MAC
        while not INV_MAC or not ROUTER_MAC:
            INV_MAC = getmacbyip(INVERTER_IP)
            ROUTER_MAC = getmacbyip(ROUTER_IP)
            time.sleep(1)
        print(f"[ARP] Interception ACTIVE: {INVERTER_IP} <-> {ROUTER_IP}")
        while True:
            sendp(Ether(dst=INV_MAC)/ARP(op=2, pdst=INVERTER_IP, psrc=ROUTER_IP, hwdst=INV_MAC), verbose=False)
            sendp(Ether(dst=ROUTER_MAC)/ARP(op=2, pdst=ROUTER_IP, psrc=INVERTER_IP, hwdst=ROUTER_MAC), verbose=False)
            time.sleep(2)

# --- ПРОГРАМНИЙ L2-МАРШРУТИЗАТОР ---
def packet_callback(pkt):
    if not IP in pkt or not Ether in pkt: return
    
    src_mac = pkt[Ether].src
    src_ip = pkt[IP].src
    dst_ip = pkt[IP].dst

    # --- РЕНТГЕН: Логуємо абсолютно весь трафік інвертора ---
    if src_ip == INVERTER_IP or dst_ip == INVERTER_IP:
        proto = "TCP" if TCP in pkt else ("UDP" if UDP in pkt else "OTHER")
        port = f":{pkt[TCP].dport}" if TCP in pkt else ""
        print(f"🔍 [X-RAY] {src_ip} ({src_mac}) ---> {dst_ip}{port} [{proto}]")

    # 1. Пакет йде ВІД Інвертора
    if src_ip == INVERTER_IP and src_mac == INV_MAC:
        # Якщо це наш цільовий MQTT пакет - парсимо для Home Assistant
        if TCP in pkt and pkt[TCP].dport == 1883 and dst_ip == TARGET_HOST:
            if Raw in pkt:
                payload = pkt[Raw].load
                if len(payload) > 0 and (payload[0] & 0xF0) == 0x30:
                    SolarParser.parse_payload(payload)
                    
        # ПРОПУСКАЄМО пакет на справжній роутер
        fwd_pkt = Ether(dst=ROUTER_MAC) / pkt[IP]
        sendp(fwd_pkt, verbose=False)
        
    # 2. Відповідь повертається ДО Інвертора (від роутера або хмари)
    elif dst_ip == INVERTER_IP and src_mac == ROUTER_MAC:
        # Віддаємо пакет інвертору
        fwd_pkt = Ether(dst=INV_MAC) / pkt[IP]
        sendp(fwd_pkt, verbose=False)

if __name__ == "__main__":
    connect_ha_mqtt()
    threading.Thread(target=ArpSpoofer().run, daemon=True).start()
    while not INV_MAC or not ROUTER_MAC: time.sleep(1)
    print(f"--- PowMr Full L2 Bridge 1.8.0 ACTIVE ---")
    sniff(filter=f"ip host {INVERTER_IP}", prn=packet_callback, store=0)
