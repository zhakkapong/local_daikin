# Local Daikin Integration
This is a full integration for Daikin air conditioners using local network access. It includes UI-based setup and supports climate control, switches, selects, and sensors.
Built quick and dirty as a bridge until we have a better solution available, this custom integration allows you to connect Daikin air conditioners, specifically those running firmware version 2.8.0, to Home Assistant. It serves as a temporary solution to ensure compatibility until the official Home Assistant team can address the issue.

## 🔧 Installation

1. Copy the `local_daikin` folder into your Home Assistant `custom_components` directory:
   ```
   <config>/custom_components/local_daikin/
   ```

2. Restart Home Assistant.

3. Go to:
   **Settings → Devices & Services → Add Integration → Local Daikin**

4. Enter the IP address of your Daikin air conditioner.

## Features

- Full climate control (temperature, HVAC mode, fan, swing)
- Extra entities:
  - Switches: Power, Quiet Fan, Powerful (see below)
  - Select: HVAC Mode Fan Speed, Swing Mode

  - Sensors: Outdoor temperature, energy today, runtime today indoor temp, humidity
  - Sensor: Target temperature (Not programming only, not in UI, Null if not applicable due to HVAC Mode)
  - Sensors: Compressor frequency (Hz), compressor load (% of a nominal 100 Hz, can exceed 100%), power (W), indoor fan speed (rpm)
  - Diagnostic sensors: Current (A), supply voltage (V), outdoor fan speed (rpm), indoor/outdoor coil temperature, control target temperature, EEV position (disabled by default)
    - Fan speed sensors carry `max_rpm` and `percent` attributes
  - Binary sensor: Compressor running
  - Diagnostic entities show as unavailable on models that don't report that value.

### Powerful switch
Reading and writing Powerful (`p_44`) have been confirmed on a firmware 2.8.0 unit: the unit accepts the command (`rsc` 2004), `p_44` follows, and the indoor fan speeds up while it is on. Each command and the unit's response are logged at `info` level. The command is not sent while the unit is off. The unit cancels Powerful on its own after about 20 minutes, and it can't be combined with Econo / Comfort / Outdoor Quiet (the unit handles that itself).

## Protocol notes (for contributors)
All values come from the single poll of `/dsiot/multireq`; see `custom_components/local_daikin/dsiot.py` (`DIAGNOSTIC_PARAMS`) for the full path table.

- `pv` is a little-endian, signed hex string: `"4100"` = 65, `"C0FF"` = -64.
- `md.st` is a one-byte step multiplier. The high nibble is a signed 4-bit power of ten (`0x0`–`0x7` = 10^0…10^7, `0x8`–`0xF` = 10^-8…10^-1) and the low nibble is the mantissa. Examples: `245` (0xF5) = ×0.5, `241` = ×0.1, `225` = ×0.01, `17` = ×10, `2` = ×2, `1` = ×1. `st = 0` means a non-numeric value (enum, bitmask, ASCII) and must not be scaled.
- `md.mx` / `md.mi` are the model's supported range, encoded the same way as `pv` (used for the fan `max_rpm`).

| Value | Resource | Path |
|---|---|---|
| Compressor frequency | `adr_0200` | `e_1003/e_2006/p_04` |
| Compressor running | `adr_0200` | `e_1003/e_2006/p_01` |
| Power (×10 W) | `adr_0200` | `e_1003/e_A005/p_01` |
| Current | `adr_0200` | `e_1003/e_A005/p_02` |
| Supply voltage | `adr_0200` | `e_1003/e_A005/p_09` |
| Indoor fan speed | `adr_0100` | `e_1002/e_2028/p_04` |
| Outdoor fan speed | `adr_0200` | `e_1003/e_2008/p_01` |
| Indoor coil temp | `adr_0100` | `e_1002/e_2029/p_02` |
| Outdoor coil temp | `adr_0200` | `e_1003/e_2009/p_02` |
| Control target temp | `adr_0100` | `e_1002/e_3003/p_0C` |
| EEV position | `adr_0200` | `e_1003/e_2005/p_01` |
| Powerful | `adr_0200` | `e_1003/e_3002/p_44` |

Run the decoder tests (no Home Assistant install needed) with `pytest tests`.

## Notes
- If upgrading from v0.0.5 (or earlier), you will need to delete the manual configuration in your `configuration.yaml` and reconfigure via the Home Assistant devices panel.
- Ensure your Daikin unit is on the same network as Home Assistant.
- Communicates with the `/dsiot/multireq` endpoint on your device.


# Compatibility
This integration has been tested and confirmed to work with the following Daikin models:
  - FTKM20YVMA with firmware version 2.8.0.
  - FTXM46WVMA with firmware version 2.8.0.

Compatibility with other models or firmware versions is not guaranteed. I keep my own units on firmware 2.8.0 and haven’t upgraded because I don’t want to risk breaking anything.

# Feedback and Contributions
This integration is a quick and dirty fix, and any suggestions for improvements or expansions are welcome. If you encounter issues or have ideas for enhancements, please open an issue in the GitHub repository for this project.

# Disclaimer
This integration is not officially supported by Home Assistant or Daikin. Use it at your own risk. The creators of this integration are not responsible for any issues that may arise from its use.
This README template should help users understand how to install, configure, and use the integration, as well as set the right expectations regarding its temporary nature and supported models. If there are any other specifics or additional sections you'd like to include, feel free to let me know!
