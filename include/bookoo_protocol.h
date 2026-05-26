#pragma once

#include <Arduino.h>

struct ScaleReading {
  bool valid = false;
  float weightG = 0.0f;
  float timerS = 0.0f;
  float flowGs = 0.0f;
  uint8_t batteryPct = 0;
  uint16_t standbyMin = 0;
  uint8_t buzzerGear = 0;
  bool flowSmoothing = false;
};

struct EmReading {
  bool valid = false;
  float pressureBar = 0.0f;
  uint8_t batteryPct = 0;
};

constexpr uint8_t SCALE_CMD_TARE[] = {0x03, 0x0A, 0x01, 0x00, 0x00, 0x08};
constexpr uint8_t SCALE_CMD_START_TIMER[] = {0x03, 0x0A, 0x04, 0x00, 0x00, 0x0A};
constexpr uint8_t SCALE_CMD_STOP_TIMER[] = {0x03, 0x0A, 0x05, 0x00, 0x00, 0x0D};
constexpr uint8_t SCALE_CMD_RESET_TIMER[] = {0x03, 0x0A, 0x06, 0x00, 0x00, 0x0C};
constexpr uint8_t SCALE_CMD_TARE_AND_START[] = {0x03, 0x0A, 0x07, 0x00, 0x00, 0x00};

constexpr uint8_t EM_CMD_STOP_EXTRACTION[] = {0x02, 0x0C, 0x00, 0x00, 0x00, 0x00, 0x0E};
constexpr uint8_t EM_CMD_START_EXTRACTION[] = {0x02, 0x0C, 0x01, 0x00, 0x00, 0x00, 0x0F};

inline bool bookooChecksumOk(const uint8_t *data, size_t len) {
  if (len < 2) {
    return false;
  }

  uint8_t checksum = 0;
  for (size_t i = 0; i < len - 1; i++) {
    checksum ^= data[i];
  }
  return checksum == data[len - 1];
}

inline uint32_t readU24(const uint8_t high, const uint8_t mid, const uint8_t low) {
  return (static_cast<uint32_t>(high) << 16) |
         (static_cast<uint32_t>(mid) << 8) |
         static_cast<uint32_t>(low);
}

inline int32_t applySign(uint32_t value, uint8_t signByte) {
  return signByte == 1 ? -static_cast<int32_t>(value) : static_cast<int32_t>(value);
}

inline ScaleReading decodeScalePacket(const uint8_t *data, size_t len) {
  ScaleReading reading;
  if (len != 20 || data[0] != 0x03 || data[1] != 0x0B || !bookooChecksumOk(data, len)) {
    return reading;
  }

  const uint32_t ms = readU24(data[2], data[3], data[4]);
  const uint32_t weightRaw = readU24(data[7], data[8], data[9]);
  const uint16_t flowRaw = (static_cast<uint16_t>(data[11]) << 8) | data[12];
  const uint16_t standby = (static_cast<uint16_t>(data[14]) << 8) | data[15];

  reading.valid = true;
  reading.timerS = static_cast<float>(ms) / 1000.0f;
  reading.weightG = static_cast<float>(applySign(weightRaw, data[6])) / 100.0f;
  reading.flowGs = static_cast<float>(applySign(flowRaw, data[10])) / 100.0f;
  reading.batteryPct = data[13];
  reading.standbyMin = standby;
  reading.buzzerGear = data[16];
  reading.flowSmoothing = data[17] == 1;
  return reading;
}

inline EmReading decodeEmPacket(const uint8_t *data, size_t len) {
  EmReading reading;
  if (len < 10 || data[0] != 0x02 || data[1] != 0x1B) {
    return reading;
  }

  const uint16_t pressureRaw = (static_cast<uint16_t>(data[4]) << 8) | data[5];
  reading.valid = true;
  reading.pressureBar = static_cast<float>(pressureRaw) / 100.0f;
  reading.batteryPct = data[6];
  return reading;
}
