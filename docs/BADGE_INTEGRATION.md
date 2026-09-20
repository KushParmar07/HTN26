# Hacker Badge (ESP32-C3) Mobile RF Scanner Integration

## 1. Hardware Identification & Specifications
- **Hardware**: 2026 Hacker Badge
- **Module**: ESP32-C3-MINI-1-N4
- **Processor**: RISC-V Single Core @ 160MHz
- **Flash Size**: 4 MB (Embedded XMC SPI Flash)
- **USB Interface**: Native USB Serial/JTAG (VID `0x303A`, PID `0x1001`)
- **Hardware MAC Address**: `28:84:85:E8:F0:E0`
- **Assigned COM Port**: `COM6`

---

## 2. Sensor Role: MOBILE Sensor Node
- **Sensor Identifier**: `badge_01`
- **Node Classification**: `node_type = MOBILE`
- **Architectural Role**:
  - The badge functions as a roaming mobile sensor carried through physical space.
  - It passively scans 2.4 GHz channels and transmits observations (`BSSID`, `SSID`, `RSSI`, `channel`, `authmode`) to the backend via `POST /api/ingest`.
  - **Exclusion from Trilateration**: Unlike the 3 fixed anchor pods (`pod_a`, `pod_b`, `pod_c`), `badge_01` is strictly excluded from `MultilaterationSolver2D`. Its dynamic position does not serve as a fixed distance reference and cannot corrupt fixed-pod spatial localization.
  - **Corroborating Evidence**: Its observations contribute to threat visibility, multi-sensor detection flags (`MULTIPLE_SENSORS`), signal strength monitoring (`STRONG_SIGNAL`), and live Unity/Quest VR streaming.

---

## 3. Firmware Build & Upload Commands

### 3.1 Build Command
```powershell
& "C:\Program Files\Arduino CLI\arduino-cli.exe" compile -b esp32:esp32:esp32c3:CDCOnBoot=cdc,FlashSize=4M firmware/hacker_badge_scanner
```

### 3.2 Upload Command (Authorized Flashing)
```powershell
& "C:\Program Files\Arduino CLI\arduino-cli.exe" upload -p COM6 -b esp32:esp32:esp32c3:CDCOnBoot=cdc,FlashSize=4M firmware/hacker_badge_scanner
```

### 3.3 Serial Monitor Command (115200 Baud)
```powershell
& "C:\Program Files\Arduino CLI\arduino-cli.exe" monitor -p COM6 --config baudrate=115200
```

---

## 4. Disaster Recovery & Original Backup

### 4.1 Immutable Recovery Image
- **Path**: `backups/badge_original_full_flash.bin`
- **Size**: 4,194,304 bytes (Exact 4 MB dump)
- **SHA-256**: `8895e9b2ed2ec8478e7370d4061ba304c6ac6c68aa1b6d6c97e34fff62518522`
- **Audit Documentation**: `backups/README.txt`

### 4.2 Exact Recovery Restoration Command
To restore the badge back to its factory state:
```powershell
& "C:\Users\KushP\AppData\Local\Arduino15\packages\esp32\tools\esptool_py\5.3.1\esptool.exe" --chip esp32c3 --port COM6 --baud 460800 write_flash 0x0 backups/badge_original_full_flash.bin
```
*(No flash encryption or secure boot is enabled on this chip, guaranteeing 100% reversible byte-for-byte restoration).*

---

## 5. Distinguishing the Badge from the Fixed Pods

| Attribute | Fixed Pods (`pod_a`, `pod_b`, `pod_c`) | Mobile Badge (`badge_01`) |
| :--- | :--- | :--- |
| **Hardware** | ESP32-WROOM-32D / ESP32-U (Xtensa Dual-Core) | ESP32-C3-MINI-1-N4 (RISC-V Single-Core) |
| **USB Interface** | External USB-UART Bridge (CP2102) | Native On-Chip USB Serial/JTAG |
| **FQBN** | `esp32:esp32:esp32` | `esp32:esp32:esp32c3` |
| **Firmware Path** | `firmware/esp32_scanner/esp32_scanner.ino` | `firmware/hacker_badge_scanner/hacker_badge_scanner.ino` |
| **Spatial Anchor** | Yes (Fixed calibrated coordinates $x, y$) | No (Excluded from solver; mobile coordinates) |
| **Node Type** | `fixed` | `mobile` |
| **COM Ports** | Pod A / B / C ports | `COM6` |
