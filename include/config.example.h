#pragma once

// Copy this file to include/config.h and adjust the values.

#define WIFI_SSID "your-wifi"
#define WIFI_PASSWORD "your-wifi-password"

#define MQTT_HOST "192.168.1.10"
#define MQTT_PORT 1883
#define MQTT_USER ""
#define MQTT_PASSWORD ""

// Used for MQTT topics and Home Assistant device identifiers.
#define DEVICE_ID "bookoo_bridge"
#define DEVICE_NAME "Bookoo Bridge"

// Optional static BLE addresses. Leave empty to scan by advertised name/service.
#define BOOKOO_SCALE_ADDRESS ""
#define BOOKOO_EM_ADDRESS ""

// Optional name-prefix fallback. Prefer static BLE addresses or service UUID discovery
// because both devices may advertise similar BOOKOO names.
#define BOOKOO_SCALE_NAME_PREFIX ""
#define BOOKOO_EM_NAME_PREFIX ""

// MQTT topic root. The bridge publishes:
// bookoo/bridge/status
// bookoo/scale/state
// bookoo/em/state
#define MQTT_BASE_TOPIC "bookoo"

// Reconnect/scan behavior.
#define BLE_SCAN_SECONDS 5
#define MQTT_RECONNECT_MS 5000
#define BLE_RECONNECT_MS 5000
