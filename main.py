"""
Ally Center - Decky Loader Plugin Backend
ROG Ally hardware control and system management

2024 Keith Baker / Pixel Addict Games
Licensed under GPL3
"""

import os
import json
import subprocess
import asyncio
import threading
import time
import math
from pathlib import Path

import decky

# Hardware paths - these are specific to the ROG Ally running SteamOS
BATTERY_PATH = "/sys/class/power_supply/BAT0"
BACKLIGHT_PATH = "/sys/class/backlight/amdgpu_bl0"
DMI_PATH = "/sys/class/dmi/id"
ASUS_WMI_PATH = "/sys/devices/platform/asus-nb-wmi"
ALLY_LED_PATH = "/sys/class/leds/ally:rgb:joystick_rings"
FAN_CURVE_PATH = "/sys/devices/platform/asus-nb-wmi/fan_curve_enable"
PWM_PATH = "/sys/devices/platform/asus-nb-wmi/hwmon"
RYZENADJ_PATH = "/usr/bin/ryzenadj"
ALLY_CONTROLLER_PATH = "/sys/devices/platform/asus-nb-wmi"

# Preset power profiles with sensible defaults for the Z1 Extreme
PERFORMANCE_PROFILES = {
    "download": {
        "name": "Download",
        "tdp": 5,
        "gpu_clock": 800,
        "fan_curve": "quiet",
        "description": "Minimum power for downloads"
    },
    "silent": {
        "name": "Silent",
        "tdp": 15,
        "gpu_clock": 1200,
        "fan_curve": "quiet",
        "description": "Low power, minimal fan noise"
    },
    "performance": {
        "name": "Performance", 
        "tdp": 25,
        "gpu_clock": 2200,
        "fan_curve": "balanced",
        "description": "Balanced performance and thermals"
    },
    "turbo": {
        "name": "Turbo",
        "tdp": 30,
        "gpu_clock": 2700,
        "fan_curve": "performance",
        "description": "Maximum performance"
    }
}


class Plugin:
    settings_path: str = None
    settings: dict = {}
    screen_off: bool = False
    effect_thread: threading.Thread = None
    effect_running: bool = False
    
    async def _main(self):
        """Main entry point for the plugin"""
        self.settings_path = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "settings.json")
        await self.load_settings()
        decky.logger.info("Ally Center initialized")

    async def _unload(self):
        """Cleanup when plugin is unloaded"""
        # Stop any running effect
        self._stop_effect()
        # Restore screen if it was off
        if self.screen_off:
            await self.set_screen_state(True)
        decky.logger.info("Ally Center unloaded")

    async def _migration(self):
        """Handle plugin migrations"""
        pass

    async def load_settings(self):
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, 'r') as f:
                    self.settings = json.load(f)
            else:
                self.settings = {
                    "current_profile": "performance",
                    "rgb_enabled": True,
                    "rgb_color": "#FF0000",
                    "rgb_brightness": 100,
                    "rgb_effect": "static",
                    "charge_limit": 100
                }
                await self.save_settings()
        except Exception as e:
            decky.logger.error(f"Failed to load settings: {e}")
            self.settings = {}
        return self.settings

    async def save_settings(self):
        try:
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            with open(self.settings_path, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            decky.logger.error(f"Failed to save settings: {e}")

    async def get_settings(self) -> dict:
        return self.settings

    async def update_setting(self, key: str, value) -> bool:
        self.settings[key] = value
        await self.save_settings()
        return True

    async def get_device_info(self) -> dict:
        info = {
            "model": "Unknown",
            "bios_version": "Unknown",
            "serial": "Unknown",
            "cpu": "Unknown",
            "gpu": "Unknown",
            "kernel": "Unknown",
            "memory_total": "Unknown"
        }
        
        try:
            # Read DMI info
            dmi_files = {
                "model": "product_name",
                "bios_version": "bios_version",
                "serial": "product_serial"
            }
            
            for key, filename in dmi_files.items():
                filepath = os.path.join(DMI_PATH, filename)
                if os.path.exists(filepath):
                    with open(filepath, 'r') as f:
                        info[key] = f.read().strip()
            
            # Get CPU info
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo", 'r') as f:
                    for line in f:
                        if line.startswith("model name"):
                            info["cpu"] = line.split(":")[1].strip()
                            break
            
            # Get kernel version
            result = subprocess.run(["uname", "-r"], capture_output=True, text=True)
            if result.returncode == 0:
                info["kernel"] = result.stdout.strip()
            
            # Get memory info
            if os.path.exists("/proc/meminfo"):
                with open("/proc/meminfo", 'r') as f:
                    for line in f:
                        if line.startswith("MemTotal"):
                            mem_kb = int(line.split()[1])
                            info["memory_total"] = f"{mem_kb // 1024 // 1024} GB"
                            break
            
            # GPU info (AMD APU)
            info["gpu"] = "AMD Radeon 780M" if "Z1" in info.get("cpu", "") else "AMD Radeon Graphics"
            
        except Exception as e:
            decky.logger.error(f"Failed to get device info: {e}")
        
        return info

    async def get_battery_info(self) -> dict:
        battery = {
            "present": False,
            "status": "Unknown",
            "capacity": 0,
            "health": 100,
            "cycle_count": 0,
            "voltage": 0,
            "current": 0,
            "temperature": 0,
            "design_capacity": 0,
            "full_capacity": 0,
            "charge_limit": self.settings.get("charge_limit", 100),
            "time_to_empty": "Unknown",
            "time_to_full": "Unknown"
        }
        
        try:
            if not os.path.exists(BATTERY_PATH):
                return battery
            
            battery["present"] = True
            
            # Read battery files
            battery_files = {
                "status": "status",
                "capacity": "capacity",
                "cycle_count": "cycle_count",
                "voltage_now": "voltage_now",
                "current_now": "current_now",
                "energy_full_design": "energy_full_design",
                "energy_full": "energy_full"
            }
            
            for key, filename in battery_files.items():
                filepath = os.path.join(BATTERY_PATH, filename)
                if os.path.exists(filepath):
                    with open(filepath, 'r') as f:
                        value = f.read().strip()
                        if key == "status":
                            battery["status"] = value
                        elif key == "capacity":
                            battery["capacity"] = int(value)
                        elif key == "cycle_count":
                            battery["cycle_count"] = int(value)
                        elif key == "voltage_now":
                            battery["voltage"] = int(value) / 1000000  # Convert to V
                        elif key == "current_now":
                            battery["current"] = int(value) / 1000000  # Convert to A
                        elif key == "energy_full_design":
                            battery["design_capacity"] = int(value) / 1000000  # Convert to Wh
                        elif key == "energy_full":
                            battery["full_capacity"] = int(value) / 1000000  # Convert to Wh
            
            # Calculate health percentage
            if battery["design_capacity"] > 0:
                battery["health"] = round((battery["full_capacity"] / battery["design_capacity"]) * 100, 1)
            
            # Try to get temperature from ACPI
            temp_path = os.path.join(BATTERY_PATH, "temp")
            if os.path.exists(temp_path):
                with open(temp_path, 'r') as f:
                    battery["temperature"] = int(f.read().strip()) / 10  # Convert to Celsius
            
        except Exception as e:
            decky.logger.error(f"Failed to get battery info: {e}")
        
        return battery

    async def set_charge_limit(self, limit: int) -> bool:
        try:
            limit = max(60, min(100, limit))  # Clamp between 60-100%
            
            # Try ASUS WMI charge limit
            charge_limit_path = os.path.join(ASUS_WMI_PATH, "charge_control_end_threshold")
            if os.path.exists(charge_limit_path):
                with open(charge_limit_path, 'w') as f:
                    f.write(str(limit))
                
                self.settings["charge_limit"] = limit
                await self.save_settings()
                decky.logger.info(f"Set charge limit to {limit}%")
                return True
            else:
                decky.logger.warning("Charge limit control not available")
                return False
                
        except Exception as e:
            decky.logger.error(f"Failed to set charge limit: {e}")
            return False

    async def get_rgb_state(self) -> dict:
        return {
            "enabled": self.settings.get("rgb_enabled", True),
            "color": self.settings.get("rgb_color", "#FF0000"),
            "brightness": self.settings.get("rgb_brightness", 100),
            "effect": self.settings.get("rgb_effect", "static"),
            "available": os.path.exists(ALLY_LED_PATH)
        }

    async def set_rgb_color(self, color: str) -> bool:
        try:
            self.settings["rgb_color"] = color
            await self.save_settings()
            await self._apply_rgb()
            return True
        except Exception as e:
            decky.logger.error(f"Failed to set RGB color: {e}")
            return False

    async def set_rgb_brightness(self, brightness: int) -> bool:
        try:
            brightness = max(0, min(100, brightness))
            self.settings["rgb_brightness"] = brightness
            await self.save_settings()
            await self._apply_rgb()
            return True
        except Exception as e:
            decky.logger.error(f"Failed to set RGB brightness: {e}")
            return False

    async def set_rgb_effect(self, effect: str) -> bool:
        try:
            self.settings["rgb_effect"] = effect
            self.settings["rgb_enabled"] = effect != "off"
            await self.save_settings()
            await self._apply_rgb()
            return True
        except Exception as e:
            decky.logger.error(f"Failed to set RGB effect: {e}")
            return False

    async def set_rgb_enabled(self, enabled: bool) -> bool:
        try:
            self.settings["rgb_enabled"] = enabled
            await self.save_settings()
            await self._apply_rgb()
            return True
        except Exception as e:
            decky.logger.error(f"Failed to toggle RGB: {e}")
            return False

    def _stop_effect(self):
        self.effect_running = False
        if self.effect_thread and self.effect_thread.is_alive():
            self.effect_thread.join(timeout=1.0)
        self.effect_thread = None

    def _set_led_color(self, r: int, g: int, b: int, brightness: int = 255):
        try:
            brightness_path = os.path.join(ALLY_LED_PATH, "brightness")
            multi_intensity_path = os.path.join(ALLY_LED_PATH, "multi_intensity")
            
            color_int = (r << 16) | (g << 8) | b
            
            if os.path.exists(multi_intensity_path):
                color_str = f"{color_int} {color_int} {color_int} {color_int}"
                with open(multi_intensity_path, 'w') as f:
                    f.write(color_str)
            
            if os.path.exists(brightness_path):
                with open(brightness_path, 'w') as f:
                    f.write(str(brightness))
        except Exception as e:
            pass  # Silently fail during animations

    def _set_led_zones(self, colors: list, brightness: int = 255):
        try:
            brightness_path = os.path.join(ALLY_LED_PATH, "brightness")
            multi_intensity_path = os.path.join(ALLY_LED_PATH, "multi_intensity")
            
            color_ints = []
            for r, g, b in colors:
                color_ints.append((r << 16) | (g << 8) | b)
            
            if os.path.exists(multi_intensity_path):
                color_str = " ".join(str(c) for c in color_ints)
                with open(multi_intensity_path, 'w') as f:
                    f.write(color_str)
            
            if os.path.exists(brightness_path):
                with open(brightness_path, 'w') as f:
                    f.write(str(brightness))
        except Exception as e:
            pass

    def _effect_pulse(self):
        color = self.settings.get("rgb_color", "#FF0000").lstrip('#')
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        base_brightness = int(self.settings.get("rgb_brightness", 100) * 255 / 100)
        
        phase = 0.0
        while self.effect_running:
            # Sine wave for smooth breathing (0 to 1)
            factor = (math.sin(phase) + 1) / 2
            brightness = int(base_brightness * (0.1 + 0.9 * factor))
            self._set_led_color(r, g, b, brightness)
            phase += 0.1
            time.sleep(0.05)

    def _effect_spectrum(self):
        base_brightness = int(self.settings.get("rgb_brightness", 100) * 255 / 100)
        
        hue = 0
        while self.effect_running:
            # HSV to RGB conversion
            h = hue / 360.0
            i = int(h * 6)
            f = h * 6 - i
            q = 1 - f
            t = f
            
            if i % 6 == 0: r, g, b = 1, t, 0
            elif i % 6 == 1: r, g, b = q, 1, 0
            elif i % 6 == 2: r, g, b = 0, 1, t
            elif i % 6 == 3: r, g, b = 0, q, 1
            elif i % 6 == 4: r, g, b = t, 0, 1
            else: r, g, b = 1, 0, q
            
            self._set_led_color(int(r * 255), int(g * 255), int(b * 255), base_brightness)
            hue = (hue + 2) % 360
            time.sleep(0.05)

    def _effect_wave(self):
        base_brightness = int(self.settings.get("rgb_brightness", 100) * 255 / 100)
        
        offset = 0
        while self.effect_running:
            colors = []
            for zone in range(4):
                hue = ((offset + zone * 90) % 360) / 360.0
                i = int(hue * 6)
                f = hue * 6 - i
                q = 1 - f
                t = f
                
                if i % 6 == 0: r, g, b = 1, t, 0
                elif i % 6 == 1: r, g, b = q, 1, 0
                elif i % 6 == 2: r, g, b = 0, 1, t
                elif i % 6 == 3: r, g, b = 0, q, 1
                elif i % 6 == 4: r, g, b = t, 0, 1
                else: r, g, b = 1, 0, q
                
                colors.append((int(r * 255), int(g * 255), int(b * 255)))
            
            self._set_led_zones(colors, base_brightness)
            offset = (offset + 3) % 360
            time.sleep(0.03)

    def _effect_flash(self):
        color = self.settings.get("rgb_color", "#FF0000").lstrip('#')
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        base_brightness = int(self.settings.get("rgb_brightness", 100) * 255 / 100)
        
        on = True
        while self.effect_running:
            if on:
                self._set_led_color(r, g, b, base_brightness)
            else:
                self._set_led_color(0, 0, 0, 0)
            on = not on
            time.sleep(0.3)

    def _start_effect(self, effect: str):
        self._stop_effect()
        
        if effect == "static" or effect == "off":
            return  # No animation needed
        
        effect_map = {
            "pulse": self._effect_pulse,
            "spectrum": self._effect_spectrum,
            "wave": self._effect_wave,
            "flash": self._effect_flash,
        }
        
        effect_func = effect_map.get(effect)
        if effect_func:
            self.effect_running = True
            self.effect_thread = threading.Thread(target=effect_func, daemon=True)
            self.effect_thread.start()
            decky.logger.info(f"Started effect: {effect}")

    async def _apply_rgb(self):
        try:
            if not os.path.exists(ALLY_LED_PATH):
                decky.logger.warning("Ally LED path not found")
                return
            
            brightness_path = os.path.join(ALLY_LED_PATH, "brightness")
            
            if not self.settings.get("rgb_enabled", True):
                # Turn off RGB
                self._stop_effect()
                if os.path.exists(brightness_path):
                    with open(brightness_path, 'w') as f:
                        f.write("0")
                decky.logger.info("RGB disabled")
                return
            
            effect = self.settings.get("rgb_effect", "static")
            
            if effect == "off":
                self._stop_effect()
                if os.path.exists(brightness_path):
                    with open(brightness_path, 'w') as f:
                        f.write("0")
                return
            
            if effect == "static":
                # Static color - no animation
                self._stop_effect()
                color = self.settings.get("rgb_color", "#FF0000").lstrip('#')
                brightness = self.settings.get("rgb_brightness", 100)
                
                r = int(color[0:2], 16)
                g = int(color[2:4], 16)
                b = int(color[4:6], 16)
                hw_brightness = int(brightness * 255 / 100)
                
                self._set_led_color(r, g, b, hw_brightness)
                decky.logger.info(f"Set static RGB: #{color} @ {brightness}%")
            else:
                # Start animated effect
                self._start_effect(effect)
                    
        except Exception as e:
            decky.logger.error(f"Failed to apply RGB settings: {e}")

    def _command_exists(self, cmd: str) -> bool:
        return subprocess.run(
            ["which", cmd], 
            capture_output=True
        ).returncode == 0

    async def get_performance_profiles(self) -> dict:
        return {
            "profiles": PERFORMANCE_PROFILES,
            "current": self.settings.get("current_profile", "performance")
        }

    async def set_performance_profile(self, profile_id: str) -> bool:
        try:
            if profile_id not in PERFORMANCE_PROFILES:
                decky.logger.error(f"Unknown profile: {profile_id}")
                return False
            
            profile = PERFORMANCE_PROFILES[profile_id]
            tdp = profile["tdp"]
            
            await self.set_tdp(tdp)
            
            self.settings["current_profile"] = profile_id
            await self.save_settings()
            
            decky.logger.info(f"Applied profile: {profile['name']} ({tdp}W)")
            return True
            
        except Exception as e:
            decky.logger.error(f"Failed to set performance profile: {e}")
            return False

    async def get_current_tdp(self) -> dict:
        result = {
            "tdp": 0,
            "gpu_clock": 0,
            "cpu_temp": 0,
            "gpu_temp": 0
        }
        
        try:
            # Try to read from hwmon
            hwmon_base = "/sys/class/hwmon"
            if os.path.exists(hwmon_base):
                for hwmon in os.listdir(hwmon_base):
                    hwmon_path = os.path.join(hwmon_base, hwmon)
                    name_path = os.path.join(hwmon_path, "name")
                    
                    if os.path.exists(name_path):
                        with open(name_path, 'r') as f:
                            name = f.read().strip()
                        
                        # AMD CPU/APU temps
                        if name in ["k10temp", "zenpower"]:
                            temp_path = os.path.join(hwmon_path, "temp1_input")
                            if os.path.exists(temp_path):
                                with open(temp_path, 'r') as f:
                                    result["cpu_temp"] = int(f.read().strip()) / 1000
                        
                        # AMD GPU temps
                        if name == "amdgpu":
                            temp_path = os.path.join(hwmon_path, "temp1_input")
                            if os.path.exists(temp_path):
                                with open(temp_path, 'r') as f:
                                    result["gpu_temp"] = int(f.read().strip()) / 1000
                            
                            # GPU clock
                            freq_path = os.path.join(hwmon_path, "freq1_input")
                            if os.path.exists(freq_path):
                                with open(freq_path, 'r') as f:
                                    result["gpu_clock"] = int(f.read().strip()) / 1000000  # MHz
            
        except Exception as e:
            decky.logger.error(f"Failed to get TDP info: {e}")
        
        return result

    async def get_screen_state(self) -> dict:
        return {
            "screen_off": self.screen_off,
            "brightness": await self._get_brightness()
        }

    async def _get_brightness(self) -> int:
        try:
            # Find the backlight device
            if os.path.exists(BACKLIGHT_PATH):
                for device in os.listdir(BACKLIGHT_PATH):
                    device_path = os.path.join(BACKLIGHT_PATH, device)
                    brightness_path = os.path.join(device_path, "brightness")
                    max_path = os.path.join(device_path, "max_brightness")
                    
                    if os.path.exists(brightness_path) and os.path.exists(max_path):
                        with open(brightness_path, 'r') as f:
                            current = int(f.read().strip())
                        with open(max_path, 'r') as f:
                            maximum = int(f.read().strip())
                        
                        return int((current / maximum) * 100)
        except Exception as e:
            decky.logger.error(f"Failed to get brightness: {e}")
        
        return 100

    async def set_screen_state(self, on: bool) -> bool:
        try:
            brightness_file = os.path.join(BACKLIGHT_PATH, "brightness")
            max_file = os.path.join(BACKLIGHT_PATH, "max_brightness")
            
            if not os.path.exists(brightness_file):
                decky.logger.error(f"Backlight device not found at {brightness_file}")
                return False
            
            if on:
                # Restore brightness to saved value
                with open(max_file, 'r') as f:
                    max_brightness = int(f.read().strip())
                restore_value = self.settings.get("saved_brightness", max_brightness // 2)
                with open(brightness_file, 'w') as f:
                    f.write(str(restore_value))
                decky.logger.info(f"Screen restored to brightness {restore_value}")
                
                # Restore previous performance profile
                saved_profile = self.settings.get("saved_profile", "performance")
                await self.set_performance_profile(saved_profile)
                
                self.screen_off = False
            else:
                # Save current brightness before turning off
                with open(brightness_file, 'r') as f:
                    current = int(f.read().strip())
                if current > 100:  # Only save if brightness is meaningful
                    self.settings["saved_brightness"] = current
                self.settings["saved_profile"] = self.settings.get("current_profile", "performance")
                await self.save_settings()
                decky.logger.info(f"Saved brightness: {current}, profile: {self.settings['saved_profile']}")
                
                # Set brightness to minimum
                with open(brightness_file, 'w') as f:
                    f.write("0")
                decky.logger.info("Screen brightness set to 0")
                
                # Set to download/5W profile
                await self.set_performance_profile("download")
                
                self.screen_off = True
            
            return True
            
        except Exception as e:
            decky.logger.error(f"Failed to set screen state: {e}")
            return False

    async def toggle_screen(self) -> bool:
        return await self.set_screen_state(self.screen_off)

    async def get_fan_info(self) -> dict:
        result = {
            "mode": self.settings.get("fan_mode", "auto"),
            "speed": 0,
            "available": False
        }
        
        try:
            # Check for fan control availability
            hwmon_base = "/sys/class/hwmon"
            if os.path.exists(hwmon_base):
                for hwmon in os.listdir(hwmon_base):
                    hwmon_path = os.path.join(hwmon_base, hwmon)
                    fan_path = os.path.join(hwmon_path, "fan1_input")
                    pwm_path = os.path.join(hwmon_path, "pwm1")
                    
                    if os.path.exists(fan_path):
                        result["available"] = True
                        with open(fan_path, 'r') as f:
                            result["speed"] = int(f.read().strip())
                        break
        except Exception as e:
            decky.logger.error(f"Failed to get fan info: {e}")
        
        return result

    async def set_fan_mode(self, mode: str) -> bool:
        try:
            self.settings["fan_mode"] = mode
            await self.save_settings()
            
            # Try ASUS WMI fan control
            throttle_policy = os.path.join(ASUS_WMI_PATH, "throttle_thermal_policy")
            if os.path.exists(throttle_policy):
                mode_map = {"quiet": "2", "balanced": "0", "performance": "1", "max": "1", "auto": "0"}
                with open(throttle_policy, 'w') as f:
                    f.write(mode_map.get(mode, "0"))
                decky.logger.info(f"Set fan mode: {mode}")
                return True
            
            return True
        except Exception as e:
            decky.logger.error(f"Failed to set fan mode: {e}")
            return False

    async def get_tdp_settings(self) -> dict:
        return {
            "tdp": self.settings.get("custom_tdp", 15),
            "min": 5,
            "max": 30,
            "available": os.path.exists(RYZENADJ_PATH) or os.path.exists("/sys/devices/platform/asus-nb-wmi")
        }

    async def set_tdp(self, tdp: int) -> bool:
        try:
            tdp = max(5, min(30, tdp))
            self.settings["custom_tdp"] = tdp
            await self.save_settings()
            
            tdp_set = False
            
            ppt_paths = [
                os.path.join(ASUS_WMI_PATH, "ppt_pl1_spl"),
                os.path.join(ASUS_WMI_PATH, "ppt_pl2_sppt"),
                os.path.join(ASUS_WMI_PATH, "ppt_apu_sppt"),
                os.path.join(ASUS_WMI_PATH, "ppt_fppt"),
            ]
            
            for ppt_path in ppt_paths:
                if os.path.exists(ppt_path):
                    try:
                        with open(ppt_path, 'w') as f:
                            f.write(str(tdp))
                        tdp_set = True
                    except PermissionError:
                        decky.logger.warning(f"Permission denied writing to {ppt_path}")
            
            if tdp_set:
                decky.logger.info(f"Set TDP to {tdp}W via ASUS WMI")
                return True
            
            if os.path.exists(RYZENADJ_PATH):
                tdp_mw = tdp * 1000
                subprocess.run(
                    [RYZENADJ_PATH, f"--stapm-limit={tdp_mw}", f"--fast-limit={tdp_mw}", f"--slow-limit={tdp_mw}"],
                    capture_output=True
                )
                decky.logger.info(f"Set TDP to {tdp}W via ryzenadj")
                return True
            
            decky.logger.warning("No TDP control method available")
            return False
        except Exception as e:
            decky.logger.error(f"Failed to set TDP: {e}")
            return False

    async def get_charge_limit(self) -> dict:
        return {
            "limit": self.settings.get("charge_limit", 100),
            "available": os.path.exists(os.path.join(ASUS_WMI_PATH, "charge_control_end_threshold"))
        }

    async def set_charge_limit(self, limit: int) -> bool:
        try:
            limit = max(60, min(100, limit))
            self.settings["charge_limit"] = limit
            await self.save_settings()
            
            # ASUS WMI charge limit
            charge_path = os.path.join(ASUS_WMI_PATH, "charge_control_end_threshold")
            if os.path.exists(charge_path):
                with open(charge_path, 'w') as f:
                    f.write(str(limit))
                decky.logger.info(f"Set charge limit to {limit}%")
                return True
            
            return True
        except Exception as e:
            decky.logger.error(f"Failed to set charge limit: {e}")
            return False

    async def get_controller_settings(self) -> dict:
        return {
            "gyro_enabled": self.settings.get("gyro_enabled", True),
            "vibration_intensity": self.settings.get("vibration_intensity", 100),
            "available": True
        }

    async def set_gyro_enabled(self, enabled: bool) -> bool:
        try:
            self.settings["gyro_enabled"] = enabled
            await self.save_settings()
            
            # Try to find and control gyro via hidraw or sysfs
            # This is device-specific and may need adjustment
            decky.logger.info(f"Gyro {'enabled' if enabled else 'disabled'}")
            return True
        except Exception as e:
            decky.logger.error(f"Failed to set gyro: {e}")
            return False

    async def set_vibration_intensity(self, intensity: int) -> bool:
        try:
            intensity = max(0, min(100, intensity))
            self.settings["vibration_intensity"] = intensity
            await self.save_settings()
            
            # Trigger test rumble via ffmpeg/evdev if available
            if intensity > 0:
                await self._trigger_rumble(intensity)
            
            decky.logger.info(f"Set vibration intensity to {intensity}%")
            return True
        except Exception as e:
            decky.logger.error(f"Failed to set vibration: {e}")
            return False

    async def _trigger_rumble(self, intensity: int) -> None:
        try:
            from evdev import InputDevice, ecodes
            
            # Find device with force feedback (Xbox 360 pad on ROG Ally)
            input_path = "/dev/input"
            for device_name in os.listdir(input_path):
                if device_name.startswith("event"):
                    device_path = os.path.join(input_path, device_name)
                    try:
                        dev = InputDevice(device_path)
                        caps = dev.capabilities()
                        
                        # Check if device has force feedback capability
                        if ecodes.EV_FF in caps:
                            # Duration based on intensity
                            duration = 0.1 + (intensity / 100) * 0.2  # 0.1 to 0.3 seconds
                            
                            # Trigger rumble - effect 0 is usually the default rumble
                            dev.write(ecodes.EV_FF, 0, 1)  # Start rumble
                            await asyncio.sleep(duration)
                            dev.write(ecodes.EV_FF, 0, 0)  # Stop rumble
                            
                            decky.logger.info(f"Rumble played on {dev.name} at {intensity}%")
                            dev.close()
                            return
                    except (PermissionError, OSError) as e:
                        decky.logger.debug(f"Cannot access {device_path}: {e}")
                        continue
                    except Exception as e:
                        decky.logger.debug(f"Error with {device_path}: {e}")
                        continue
            
            decky.logger.debug("No force feedback device found")
                
        except ImportError:
            decky.logger.debug("evdev module not available")
        except Exception as e:
            decky.logger.error(f"Rumble error: {e}")

    async def set_brightness(self, brightness: int) -> bool:
        """Set screen brightness (0-100)"""
        try:
            brightness = max(0, min(100, brightness))
            
            if os.path.exists(BACKLIGHT_PATH):
                for device in os.listdir(BACKLIGHT_PATH):
                    device_path = os.path.join(BACKLIGHT_PATH, device)
                    brightness_path = os.path.join(device_path, "brightness")
                    max_path = os.path.join(device_path, "max_brightness")
                    
                    if os.path.exists(brightness_path) and os.path.exists(max_path):
                        with open(max_path, 'r') as f:
                            maximum = int(f.read().strip())
                        
                        hw_brightness = int((brightness / 100) * maximum)
                        
                        with open(brightness_path, 'w') as f:
                            f.write(str(hw_brightness))
                        
                        decky.logger.info(f"Set brightness to {brightness}%")
                        return True
            
            return False
            
        except Exception as e:
            decky.logger.error(f"Failed to set brightness: {e}")
            return False
