#include <Arduino.h>
#include <NimBLEDevice.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <cstring>

#include "bookoo_protocol.h"

#if __has_include("config.h")
#include "config.h"
#else
#include "config.example.h"
#warning "Using config.example.h. Copy it to include/config.h and set real credentials."
#endif

namespace {

constexpr const char *SCALE_SERVICE_UUID = "00000ffe-0000-1000-8000-00805f9b34fb";
constexpr const char *SCALE_WEIGHT_UUID = "0000ff11-0000-1000-8000-00805f9b34fb";
constexpr const char *SCALE_COMMAND_UUID = "0000ff12-0000-1000-8000-00805f9b34fb";

constexpr const char *EM_SERVICE_UUID = "00000fff-0000-1000-8000-00805f9b34fb";
constexpr const char *EM_DATA_UUID = "0000ff02-0000-1000-8000-00805f9b34fb";
constexpr const char *EM_COMMAND_UUID = "0000ff01-0000-1000-8000-00805f9b34fb";

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

NimBLEAdvertisedDevice *scaleDevice = nullptr;
NimBLEAdvertisedDevice *emDevice = nullptr;
NimBLEClient *scaleClient = nullptr;
NimBLEClient *emClient = nullptr;
class ScanCallbacks;
ScanCallbacks *scanCallbacks = nullptr;

bool scaleConnected = false;
bool emConnected = false;
int scaleRssi = 0;
int emRssi = 0;
unsigned long lastMqttAttempt = 0;
unsigned long lastBleAttempt = 0;
bool discoveryPublished = false;

String topic(const char *suffix) {
  return String(MQTT_BASE_TOPIC) + "/" + suffix;
}

void publishAvailability() {
  mqtt.publish(topic("bridge/status").c_str(), "online", true);
}

void publishHaDiscoverySensor(
    const char *objectId,
    const char *name,
    const char *stateTopic,
    const char *valueTemplate,
    const char *unit,
    const char *deviceClass,
    const char *stateClass) {
  const String configTopic = String("homeassistant/sensor/") + DEVICE_ID + "/" + objectId + "/config";
  String payload = "{";
  payload += "\"name\":\"";
  payload += name;
  payload += "\",\"unique_id\":\"";
  payload += DEVICE_ID;
  payload += "_";
  payload += objectId;
  payload += "\",\"state_topic\":\"";
  payload += stateTopic;
  payload += "\",\"value_template\":\"";
  payload += valueTemplate;
  payload += "\",\"availability_topic\":\"";
  payload += topic("bridge/status");
  payload += "\",\"device\":{\"identifiers\":[\"";
  payload += DEVICE_ID;
  payload += "\"],\"name\":\"";
  payload += DEVICE_NAME;
  payload += "\",\"manufacturer\":\"Bookoo/DIY\",\"model\":\"ESP32 MQTT Bridge\"}";
  if (unit && strlen(unit) > 0) {
    payload += ",\"unit_of_measurement\":\"";
    payload += unit;
    payload += "\"";
  }
  if (deviceClass && strlen(deviceClass) > 0) {
    payload += ",\"device_class\":\"";
    payload += deviceClass;
    payload += "\"";
  }
  if (stateClass && strlen(stateClass) > 0) {
    payload += ",\"state_class\":\"";
    payload += stateClass;
    payload += "\"";
  }
  payload += "}";
  mqtt.publish(configTopic.c_str(), payload.c_str(), true);
}

void publishHaDiscoveryButton(
    const char *objectId,
    const char *name,
    const char *commandTopic,
    const char *payloadPress) {
  const String configTopic = String("homeassistant/button/") + DEVICE_ID + "/" + objectId + "/config";
  String payload = "{";
  payload += "\"name\":\"";
  payload += name;
  payload += "\",\"unique_id\":\"";
  payload += DEVICE_ID;
  payload += "_";
  payload += objectId;
  payload += "\",\"command_topic\":\"";
  payload += commandTopic;
  payload += "\",\"payload_press\":\"";
  payload += payloadPress;
  payload += "\",\"availability_topic\":\"";
  payload += topic("bridge/status");
  payload += "\",\"device\":{\"identifiers\":[\"";
  payload += DEVICE_ID;
  payload += "\"],\"name\":\"";
  payload += DEVICE_NAME;
  payload += "\",\"manufacturer\":\"Bookoo/DIY\",\"model\":\"ESP32 MQTT Bridge\"}}";
  mqtt.publish(configTopic.c_str(), payload.c_str(), true);
}

void publishDiscovery() {
  const String scaleState = topic("scale/state");
  const String emState = topic("em/state");
  const String scaleCommand = topic("scale/command");
  const String emCommand = topic("em/command");

  publishHaDiscoverySensor("scale_weight", "Bookoo Scale Weight", scaleState.c_str(), "{{ value_json.weight_g }}", "g", "weight", "measurement");
  publishHaDiscoverySensor("scale_timer", "Bookoo Scale Timer", scaleState.c_str(), "{{ value_json.timer_s }}", "s", "duration", "measurement");
  publishHaDiscoverySensor("scale_flow", "Bookoo Scale Flow", scaleState.c_str(), "{{ value_json.flow_g_s }}", "g/s", "", "measurement");
  publishHaDiscoverySensor("scale_battery", "Bookoo Scale Battery", scaleState.c_str(), "{{ value_json.battery_pct }}", "%", "battery", "measurement");
  publishHaDiscoverySensor("scale_rssi", "Bookoo Scale RSSI", scaleState.c_str(), "{{ value_json.rssi }}", "dBm", "signal_strength", "measurement");

  publishHaDiscoverySensor("em_pressure", "Bookoo EM Pressure", emState.c_str(), "{{ value_json.pressure_bar }}", "bar", "pressure", "measurement");
  publishHaDiscoverySensor("em_battery", "Bookoo EM Battery", emState.c_str(), "{{ value_json.battery_pct }}", "%", "battery", "measurement");
  publishHaDiscoverySensor("em_rssi", "Bookoo EM RSSI", emState.c_str(), "{{ value_json.rssi }}", "dBm", "signal_strength", "measurement");

  publishHaDiscoveryButton("scale_tare", "Bookoo Scale Tare", scaleCommand.c_str(), "tare");
  publishHaDiscoveryButton("scale_start_timer", "Bookoo Scale Start Timer", scaleCommand.c_str(), "start_timer");
  publishHaDiscoveryButton("scale_stop_timer", "Bookoo Scale Stop Timer", scaleCommand.c_str(), "stop_timer");
  publishHaDiscoveryButton("scale_reset_timer", "Bookoo Scale Reset Timer", scaleCommand.c_str(), "reset_timer");
  publishHaDiscoveryButton("scale_tare_and_start", "Bookoo Scale Tare And Start", scaleCommand.c_str(), "tare_and_start");
  publishHaDiscoveryButton("em_start_extraction", "Bookoo EM Start Extraction", emCommand.c_str(), "start");
  publishHaDiscoveryButton("em_stop_extraction", "Bookoo EM Stop Extraction", emCommand.c_str(), "stop");

  discoveryPublished = true;
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\nWiFi connected: %s\n", WiFi.localIP().toString().c_str());
}

bool writeBleCommand(
    NimBLEClient *client,
    const char *serviceUuid,
    const char *commandUuid,
    const uint8_t *payload,
    size_t payloadLen,
    const char *label) {
  if (client == nullptr || !client->isConnected()) {
    Serial.printf("%s command ignored: device not connected\n", label);
    return false;
  }

  NimBLERemoteService *service = client->getService(serviceUuid);
  if (service == nullptr) {
    Serial.printf("%s command ignored: service unavailable\n", label);
    return false;
  }

  NimBLERemoteCharacteristic *commandChar = service->getCharacteristic(commandUuid);
  if (commandChar == nullptr || (!commandChar->canWrite() && !commandChar->canWriteNoResponse())) {
    Serial.printf("%s command ignored: command characteristic unavailable\n", label);
    return false;
  }

  return commandChar->writeValue(const_cast<uint8_t *>(payload), payloadLen, false);
}

void handleScaleCommand(const String &command) {
  if (command == "tare") {
    writeBleCommand(scaleClient, SCALE_SERVICE_UUID, SCALE_COMMAND_UUID, SCALE_CMD_TARE, sizeof(SCALE_CMD_TARE), "scale");
  } else if (command == "start_timer") {
    writeBleCommand(scaleClient, SCALE_SERVICE_UUID, SCALE_COMMAND_UUID, SCALE_CMD_START_TIMER, sizeof(SCALE_CMD_START_TIMER), "scale");
  } else if (command == "stop_timer") {
    writeBleCommand(scaleClient, SCALE_SERVICE_UUID, SCALE_COMMAND_UUID, SCALE_CMD_STOP_TIMER, sizeof(SCALE_CMD_STOP_TIMER), "scale");
  } else if (command == "reset_timer") {
    writeBleCommand(scaleClient, SCALE_SERVICE_UUID, SCALE_COMMAND_UUID, SCALE_CMD_RESET_TIMER, sizeof(SCALE_CMD_RESET_TIMER), "scale");
  } else if (command == "tare_and_start") {
    writeBleCommand(scaleClient, SCALE_SERVICE_UUID, SCALE_COMMAND_UUID, SCALE_CMD_TARE_AND_START, sizeof(SCALE_CMD_TARE_AND_START), "scale");
  } else {
    Serial.printf("Unknown scale command: %s\n", command.c_str());
  }
}

void handleEmCommand(const String &command) {
  if (command == "start") {
    writeBleCommand(emClient, EM_SERVICE_UUID, EM_COMMAND_UUID, EM_CMD_START_EXTRACTION, sizeof(EM_CMD_START_EXTRACTION), "EM");
  } else if (command == "stop") {
    writeBleCommand(emClient, EM_SERVICE_UUID, EM_COMMAND_UUID, EM_CMD_STOP_EXTRACTION, sizeof(EM_CMD_STOP_EXTRACTION), "EM");
  } else {
    Serial.printf("Unknown EM command: %s\n", command.c_str());
  }
}

void mqttCallback(char *rawTopic, byte *payload, unsigned int length) {
  String command;
  command.reserve(length);
  for (unsigned int i = 0; i < length; i++) {
    command += static_cast<char>(payload[i]);
  }
  command.trim();

  const String incomingTopic(rawTopic);
  if (incomingTopic == topic("scale/command")) {
    handleScaleCommand(command);
  } else if (incomingTopic == topic("em/command")) {
    handleEmCommand(command);
  }
}

void connectMqtt() {
  if (mqtt.connected() || millis() - lastMqttAttempt < MQTT_RECONNECT_MS) {
    return;
  }
  lastMqttAttempt = millis();

  Serial.println("Connecting MQTT");
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(mqttCallback);
  mqtt.setBufferSize(1024);
  mqtt.setKeepAlive(30);

  const bool ok = strlen(MQTT_USER) > 0
                      ? mqtt.connect(DEVICE_ID, MQTT_USER, MQTT_PASSWORD, topic("bridge/status").c_str(), 1, true, "offline")
                      : mqtt.connect(DEVICE_ID, topic("bridge/status").c_str(), 1, true, "offline");
  if (!ok) {
    Serial.printf("MQTT failed: %d\n", mqtt.state());
    return;
  }

  publishAvailability();
  if (!discoveryPublished) {
    publishDiscovery();
  }
  mqtt.subscribe(topic("scale/command").c_str());
  mqtt.subscribe(topic("em/command").c_str());
  Serial.println("MQTT connected");
}

bool hasService(NimBLEAdvertisedDevice *device, const char *uuid) {
  return device->haveServiceUUID() && device->isAdvertisingService(NimBLEUUID(uuid));
}

bool nameStartsWith(NimBLEAdvertisedDevice *device, const char *prefix) {
  if (strlen(prefix) == 0 || !device->haveName()) {
    return false;
  }
  return String(device->getName().c_str()).startsWith(prefix);
}

bool matchesAddress(NimBLEAdvertisedDevice *device, const char *address) {
  return strlen(address) > 0 && String(device->getAddress().toString().c_str()).equalsIgnoreCase(address);
}

class ScanCallbacks : public NimBLEAdvertisedDeviceCallbacks {
  void onResult(NimBLEAdvertisedDevice *advertisedDevice) override {
    if (scaleDevice == nullptr &&
        (matchesAddress(advertisedDevice, BOOKOO_SCALE_ADDRESS) ||
         hasService(advertisedDevice, SCALE_SERVICE_UUID) ||
         nameStartsWith(advertisedDevice, BOOKOO_SCALE_NAME_PREFIX))) {
      scaleDevice = new NimBLEAdvertisedDevice(*advertisedDevice);
      Serial.printf("Found scale: %s\n", advertisedDevice->toString().c_str());
    }

    if (emDevice == nullptr &&
        (matchesAddress(advertisedDevice, BOOKOO_EM_ADDRESS) ||
         hasService(advertisedDevice, EM_SERVICE_UUID))) {
      emDevice = new NimBLEAdvertisedDevice(*advertisedDevice);
      Serial.printf("Found EM: %s\n", advertisedDevice->toString().c_str());
    }
  }
};

void publishScaleReading(const ScaleReading &reading) {
  String payload = "{";
  payload += "\"connected\":true";
  payload += ",\"weight_g\":";
  payload += String(reading.weightG, 2);
  payload += ",\"timer_s\":";
  payload += String(reading.timerS, 3);
  payload += ",\"flow_g_s\":";
  payload += String(reading.flowGs, 2);
  payload += ",\"battery_pct\":";
  payload += String(static_cast<unsigned int>(reading.batteryPct));
  payload += ",\"standby_min\":";
  payload += String(static_cast<unsigned int>(reading.standbyMin));
  payload += ",\"buzzer_gear\":";
  payload += String(static_cast<unsigned int>(reading.buzzerGear));
  payload += ",\"flow_smoothing\":";
  payload += reading.flowSmoothing ? "true" : "false";
  payload += ",\"rssi\":";
  payload += String(scaleRssi);
  payload += "}";
  mqtt.publish(topic("scale/state").c_str(), payload.c_str(), false);
}

void publishEmReading(const EmReading &reading) {
  String payload = "{";
  payload += "\"connected\":true";
  payload += ",\"pressure_bar\":";
  payload += String(reading.pressureBar, 2);
  payload += ",\"battery_pct\":";
  payload += String(static_cast<unsigned int>(reading.batteryPct));
  payload += ",\"rssi\":";
  payload += String(emRssi);
  payload += "}";
  mqtt.publish(topic("em/state").c_str(), payload.c_str(), false);
}

void scaleNotify(NimBLERemoteCharacteristic *, uint8_t *data, size_t length, bool) {
  const ScaleReading reading = decodeScalePacket(data, length);
  if (!reading.valid) {
    Serial.printf("Invalid scale packet length=%u\n", static_cast<unsigned>(length));
    return;
  }
  if (scaleClient != nullptr && scaleClient->isConnected()) {
    scaleRssi = scaleClient->getRssi();
  }
  publishScaleReading(reading);
}

void emNotify(NimBLERemoteCharacteristic *, uint8_t *data, size_t length, bool) {
  const EmReading reading = decodeEmPacket(data, length);
  if (!reading.valid) {
    Serial.printf("Invalid EM packet length=%u\n", static_cast<unsigned>(length));
    return;
  }
  if (emClient != nullptr && emClient->isConnected()) {
    emRssi = emClient->getRssi();
  }
  publishEmReading(reading);
}

void scanForDevices() {
  if (scaleDevice != nullptr && emDevice != nullptr) {
    return;
  }

  NimBLEScan *scan = NimBLEDevice::getScan();
  if (scanCallbacks == nullptr) {
    scanCallbacks = new ScanCallbacks();
    scan->setAdvertisedDeviceCallbacks(scanCallbacks, false);
  }
  scan->setActiveScan(true);
  scan->setInterval(45);
  scan->setWindow(15);
  Serial.println("Scanning for Bookoo devices");
  scan->start(BLE_SCAN_SECONDS, false);
  scan->clearResults();
}

bool connectBleDevice(
    NimBLEAdvertisedDevice *device,
    NimBLEClient *&client,
    const char *serviceUuid,
    const char *notifyUuid,
    void (*notifyCallback)(NimBLERemoteCharacteristic *, uint8_t *, size_t, bool),
    bool &connectedFlag,
    const char *label) {
  if (device == nullptr || connectedFlag) {
    return connectedFlag;
  }

  if (client == nullptr) {
    client = NimBLEDevice::createClient();
  }

  Serial.printf("Connecting %s: %s\n", label, device->getAddress().toString().c_str());
  if (!client->connect(device)) {
    Serial.printf("%s BLE connect failed\n", label);
    NimBLEDevice::deleteClient(client);
    client = nullptr;
    connectedFlag = false;
    return false;
  }

  NimBLERemoteService *service = client->getService(serviceUuid);
  if (service == nullptr) {
    Serial.printf("%s service not found\n", label);
    client->disconnect();
    connectedFlag = false;
    return false;
  }

  NimBLERemoteCharacteristic *notifyChar = service->getCharacteristic(notifyUuid);
  if (notifyChar == nullptr || !notifyChar->canNotify()) {
    Serial.printf("%s notify characteristic not found\n", label);
    client->disconnect();
    connectedFlag = false;
    return false;
  }

  if (!notifyChar->subscribe(true, notifyCallback)) {
    Serial.printf("%s subscribe failed\n", label);
    client->disconnect();
    connectedFlag = false;
    return false;
  }

  connectedFlag = true;
  Serial.printf("%s connected\n", label);
  return true;
}

void maintainBle() {
  if (millis() - lastBleAttempt < BLE_RECONNECT_MS) {
    return;
  }
  lastBleAttempt = millis();

  if (scaleClient != nullptr && !scaleClient->isConnected()) {
    scaleConnected = false;
    mqtt.publish(topic("scale/state").c_str(), "{\"connected\":false}", false);
  }
  if (emClient != nullptr && !emClient->isConnected()) {
    emConnected = false;
    mqtt.publish(topic("em/state").c_str(), "{\"connected\":false}", false);
  }

  scanForDevices();
  connectBleDevice(scaleDevice, scaleClient, SCALE_SERVICE_UUID, SCALE_WEIGHT_UUID, scaleNotify, scaleConnected, "scale");
  connectBleDevice(emDevice, emClient, EM_SERVICE_UUID, EM_DATA_UUID, emNotify, emConnected, "EM");
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(500);

  connectWifi();
  NimBLEDevice::init(DEVICE_NAME);
  NimBLEDevice::setPower(ESP_PWR_LVL_P9);

  connectMqtt();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWifi();
  }

  connectMqtt();
  mqtt.loop();
  maintainBle();
  delay(20);
}
