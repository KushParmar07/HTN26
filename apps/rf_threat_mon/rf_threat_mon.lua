--[==[badge-app
slug=rf_threat_mon
name=RF Threat Mon
icon=RF
api=2
heap_kb=48
wake_lock=1
]==]

-- =============================================================================
-- RF Threat Detection System — Badge Companion & Status Monitor
-- Framework: Hack the North 2026 Hacker Badge (Lua 5.x / LVGL 9 API 2)
-- Architecture: Standalone RF Threat Monitor Companion
-- Features:
--   - Real-time visualization of RF Threat Detection pipeline states
--   - Multi-state demo switcher (Secure -> Rogue Detected -> Tracking -> Mobile Alert)
--   - 6-channel perimeter RGB LED cues matching system threat level
--   - Accelerometer shake detection (physical proximity alarm trigger)
--   - Compliant with official badge app sandboxing (0 flash modifications)
-- =============================================================================

-- State definitions
local STATE_SECURE = 1
local STATE_THREAT = 2
local STATE_TRACKING = 3
local STATE_PROXIMITY = 4
local NUM_STATES = 4

local currentState = STATE_SECURE
local lastLedUpdateMs = 0
local lastStateChangeMs = 0
local animStep = 0

-- UI widget references
local headerBox = nil
local statusBadgeBox = nil
local statusBadgeText = nil
local cardBox = nil
local titleLabel = nil
local row1Label = nil
local row2Label = nil
local row3Label = nil
local row4Label = nil
local footerLabel = nil

-- Colors (0xRRGGBB)
local COLOR_BG = 0x0a0e17
local COLOR_CARD = 0x141b2d
local COLOR_BORDER = 0x22304e
local COLOR_TEXT = 0xf1f5f9
local COLOR_MUTED = 0x94a3b8

local COLOR_SECURE = 0x10b981      -- Green
local COLOR_THREAT = 0xef4444      -- Red
local COLOR_TRACKING = 0xf59e0b    -- Amber/Orange
local COLOR_PROXIMITY = 0xa855f7   -- Purple

-- Helper to update text safely
local function setLabel(widget, text)
  if widget then
    widget:set_text(text)
  end
end

-- Refresh UI content according to currentState
local function refreshView()
  lastStateChangeMs = badge.sys.ms()

  if currentState == STATE_SECURE then
    statusBadgeBox:style({ bg_color = COLOR_SECURE, border_color = 0x059669 })
    setLabel(statusBadgeText, "SYSTEM SECURE  [NOMINAL]")
    statusBadgeBox:align("top_mid", 0, 36)

    setLabel(row1Label, "Baseline: HTN-Secure  (Ch 6, WPA2)")
    setLabel(row2Label, "Active Pods: pod_a, pod_b, pod_c [ONLINE]")
    setLabel(row3Label, "RF Transmitters: 1 Legit, 0 Rogue")
    setLabel(row4Label, "Threat Risk Score: 0.0%  [NO ALARMS]")

  elseif currentState == STATE_THREAT then
    statusBadgeBox:style({ bg_color = COLOR_THREAT, border_color = 0xdc2626 })
    setLabel(statusBadgeText, "! ROGUE AP DETECTED ! [ALERT]")
    statusBadgeBox:align("top_mid", 0, 36)

    setLabel(row1Label, "Threat SSID: HTN-Secure (Evil Twin Clone)")
    setLabel(row2Label, "Rogue BSSID: DE:AD:BE:EF:00:01 (Ch 1)")
    setLabel(row3Label, "Security: OPEN  |  RSSI: -45 dBm (Strong)")
    setLabel(row4Label, "Risk Score: 95.0% [CRITICAL ROGUE AP]")

  elseif currentState == STATE_TRACKING then
    statusBadgeBox:style({ bg_color = COLOR_TRACKING, border_color = 0xd97706 })
    setLabel(statusBadgeText, "MULTILATERATION ACTIVE [3D]")
    statusBadgeBox:align("top_mid", 0, 36)

    setLabel(row1Label, "2D Position: X: 2.14 m , Y: 1.68 m")
    setLabel(row2Label, "Uncertainty Radius: +/- 0.45 m (1-sigma)")
    setLabel(row3Label, "Velocity: 0.35 m/s  Heading: 52 deg")
    setLabel(row4Label, "Movement Classification: MOVING ROGUE")

  elseif currentState == STATE_PROXIMITY then
    statusBadgeBox:style({ bg_color = COLOR_PROXIMITY, border_color = 0x9333ea })
    setLabel(statusBadgeText, "! MOBILE PROXIMITY WARNING !")
    statusBadgeBox:align("top_mid", 0, 36)

    setLabel(row1Label, "Badge Node: badge_01 (Mobile Node)")
    setLabel(row2Label, "Proximity Signal: -36 dBm [VERY CLOSE]")
    setLabel(row3Label, "Corroboration: Multi-Sensor Triggered")
    setLabel(row4Label, "Action: Inspect Rogue Vicinity")
  end
end

-- Update the 6 RGB perimeter LEDs based on current threat mode
local function updateLeds(nowMs)
  animStep = animStep + 1

  if currentState == STATE_SECURE then
    -- Calm breathing green on all 6 LEDs
    local phase = math.floor(nowMs / 80) % 20
    local brightness = (phase < 10) and (phase * 6 + 10) or ((20 - phase) * 6 + 10)
    badge.led.set_all(0, brightness, math.floor(brightness / 3))
    badge.led.show()

  elseif currentState == STATE_THREAT then
    -- Urgent flashing red perimeter alert
    local flash = math.floor(nowMs / 140) % 2
    if flash == 0 then
      badge.led.set_all(255, 0, 0)
    else
      badge.led.set_all(30, 0, 0)
    end
    badge.led.show()

  elseif currentState == STATE_TRACKING then
    -- Amber rotating chase sequence indicating direction
    badge.led.clear()
    local lead = (math.floor(nowMs / 120) % 6) + 1
    local trail = ((lead + 4) % 6) + 1
    badge.led.set(lead, 255, 140, 0)
    badge.led.set(trail, 90, 40, 0)
    badge.led.show()

  elseif currentState == STATE_PROXIMITY then
    -- Alternating purple and red strobe
    local strobe = math.floor(nowMs / 100) % 2
    if strobe == 0 then
      badge.led.set(1, 180, 0, 255)
      badge.led.set(3, 180, 0, 255)
      badge.led.set(5, 180, 0, 255)
      badge.led.set(2, 255, 0, 40)
      badge.led.set(4, 255, 0, 40)
      badge.led.set(6, 255, 0, 40)
    else
      badge.led.set(1, 255, 0, 40)
      badge.led.set(3, 255, 0, 40)
      badge.led.set(5, 255, 0, 40)
      badge.led.set(2, 180, 0, 255)
      badge.led.set(4, 180, 0, 255)
      badge.led.set(6, 180, 0, 255)
    end
    badge.led.show()
  end
end

-- =============================================================================
-- Global App Lifecycle Callbacks
-- =============================================================================

function on_enter(root)
  badge.sys.log("RF Threat Monitor companion app launched")

  -- Full screen container background
  local bg = badge.ui.box{
    parent = root,
    w = 320,
    h = 240,
    bg_color = COLOR_BG,
    border_width = 0,
    radius = 0,
  }
  bg:align("center", 0, 0)

  -- Top title bar
  headerBox = badge.ui.box{
    parent = bg,
    w = 304,
    h = 26,
    bg_color = COLOR_CARD,
    border_width = 1,
    border_color = COLOR_BORDER,
    radius = 4,
  }
  headerBox:align("top_mid", 0, 6)

  titleLabel = badge.ui.label(headerBox, "RF THREAT MONITOR :: HTN26")
  titleLabel:style({ text_color = 0x38bdf8, text_font = "small" })
  titleLabel:align("center", 0, 0)

  -- Prominent state banner badge
  statusBadgeBox = badge.ui.box{
    parent = bg,
    w = 296,
    h = 24,
    bg_color = COLOR_SECURE,
    border_width = 1,
    border_color = 0x059669,
    radius = 4,
  }
  statusBadgeBox:align("top_mid", 0, 36)

  statusBadgeText = badge.ui.label(statusBadgeBox, "SYSTEM SECURE  [NOMINAL]")
  statusBadgeText:style({ text_color = 0xffffff, text_font = "small" })
  statusBadgeText:align("center", 0, 0)

  -- Main telemetry details card
  cardBox = badge.ui.box{
    parent = bg,
    w = 304,
    h = 138,
    bg_color = COLOR_CARD,
    border_width = 1,
    border_color = COLOR_BORDER,
    radius = 6,
  }
  cardBox:align("top_mid", 0, 66)

  row1Label = badge.ui.label(cardBox, "Initializing pipeline...")
  row1Label:style({ text_color = COLOR_TEXT, text_font = "small" })
  row1Label:align("top_left", 10, 8)

  row2Label = badge.ui.label(cardBox, "Connecting sensors...")
  row2Label:style({ text_color = COLOR_TEXT, text_font = "small" })
  row2Label:align("top_left", 10, 38)

  row3Label = badge.ui.label(cardBox, "Calibrating 2D multilateration...")
  row3Label:style({ text_color = COLOR_MUTED, text_font = "small" })
  row3Label:align("top_left", 10, 68)

  row4Label = badge.ui.label(cardBox, "Status: Nominal")
  row4Label:style({ text_color = 0x38bdf8, text_font = "small" })
  row4Label:align("top_left", 10, 98)

  -- Bottom navigation instructions
  footerLabel = badge.ui.label(bg, "[A] Next Mode   [B] Alarm   [Shake] Proximity   [HOME] Exit")
  footerLabel:style({ text_color = COLOR_MUTED, text_font = "small" })
  footerLabel:align("bottom_mid", 0, -4)

  -- Initialize view
  refreshView()
end

function on_tick()
  local nowMs = badge.sys.ms()

  -- Check accelerometer shake for mobile proximity simulation
  if badge.sensor and badge.sensor.shake and badge.sensor.shake() then
    currentState = STATE_PROXIMITY
    badge.sys.log("Badge shaken: Triggered Mobile Proximity State")
    refreshView()
  end

  -- Update perimeter LEDs at ~30 Hz (every 33 ms)
  if nowMs - lastLedUpdateMs >= 33 then
    lastLedUpdateMs = nowMs
    updateLeds(nowMs)
  end
end

function on_button(button, kind)
  -- Only process button press events
  if kind == badge.input.KIND.PRESSED then
    if button == badge.input.BUTTON.A then
      -- Cycle through demo states
      currentState = (currentState % NUM_STATES) + 1
      badge.sys.log("Button A pressed: Switched to mode " .. tostring(currentState))
      refreshView()

    elseif button == badge.input.BUTTON.B then
      -- Instant toggle between Secure and Rogue Alert
      if currentState == STATE_THREAT then
        currentState = STATE_SECURE
      else
        currentState = STATE_THREAT
      end
      badge.sys.log("Button B pressed: Toggled alert state to " .. tostring(currentState))
      refreshView()

    elseif button == badge.input.BUTTON.UP or button == badge.input.BUTTON.RIGHT then
      currentState = STATE_TRACKING
      badge.sys.log("DPad pressed: Showing 2D Tracking")
      refreshView()

    elseif button == badge.input.BUTTON.DOWN or button == badge.input.BUTTON.LEFT then
      currentState = STATE_PROXIMITY
      badge.sys.log("DPad pressed: Showing Mobile Proximity")
      refreshView()
    end
  end
end

function on_exit()
  badge.sys.log("RF Threat Monitor companion app exiting")
  -- Safely clear RGB LEDs
  badge.led.clear()
  badge.led.show()
end
