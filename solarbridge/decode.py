"""Decoders: raw Modbus registers -> named, typed snapshot fields.

Register maps and bit flags follow the official HIDEN protocol 1.4.15
(HS20 / HPS30 / HS50). Read-only: nothing here builds write commands.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Bit maps from the official HIDEN protocol 1.4.15 (HS20 / HPS30 / HS50):
#   * Inverter error message 1  -> 25261, error message 2 -> 25262
#     (error message 3 -> 25263 has no documented bits; raw code is exposed)
#   * Inverter warning message 1 -> 25265, warning message 2 -> 25266
#   * Charger error message      -> 15213, warning message -> 15214
# Translation keys are resolved on the frontend; the server only emits
# stable bit coordinates and codes.
# ---------------------------------------------------------------------------

INVERTER_ERROR_REGISTERS = ((1, 60), (2, 61))  # (message index, offset in block 25201)
INVERTER_WARNING_REGISTERS = ((1, 64), (2, 65))

INVERTER_WORK_STATES = (0, 1, 2, 3, 4, 5, 6)  # 25201: PowerOn..Grid charging
CHARGER_WORK_STATES = (0, 1, 2, 3)  # 15201: Initialization/Selftest/Work/Stop
CHARGER_MPPT_STATES = (0, 1, 2)  # 15202: Stop/MPPT/Current limiting
CHARGER_CHARGING_STATES = (0, 1, 2, 3)  # 15203: Stop/Absorb/Float/EQ


def signed16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def value(registers: list[int] | None, index: int, *, signed: bool = True) -> int | None:
    if registers is None or index >= len(registers):
        return None
    raw = registers[index]
    if raw is None:  # legacy identity fallback keeps an empty slot for 20000
        return None
    return signed16(raw) if signed else raw


def scaled(registers: list[int] | None, index: int, factor: float) -> float | None:
    raw = value(registers, index)
    return None if raw is None else round(raw * factor, 3)


def version(registers: list[int] | None, index: int) -> str | None:
    raw = value(registers, index, signed=False)
    if raw is None:
        return None
    if raw == 0:
        return "1.00.00"
    return f"{raw // 10000}.{(raw // 100) % 100:02}.{raw % 100:02}"


def _model_from(machine_type: int | None, software_raw: int | None) -> str | None:
    if machine_type == 1600:
        return "PC1600"
    if machine_type == 1800:
        return "PV1800" if (software_raw or 0) > 20000 else "PH1800"
    if machine_type == 3000:
        return "PH3000"
    if machine_type == 3500:
        return "PV3500"
    return f"HIDEN ({machine_type})" if machine_type is not None else None


def _relay(registers: list[int] | None, index: int) -> bool | None:
    """Relay registers (25237-25242, 15211, 15212): 0 = disconnect, 1 = connect."""
    raw = value(registers, index, signed=False)
    if raw is None:
        return None
    return raw == 1


def packed_energy_kwh(registers: list[int] | None, index: int) -> float | None:
    """Accumulated energy counters per protocol 1.4.15.

    The high register counts 1000 KWH steps, the low register 0.1 KWH steps
    with decimal packing, so total KWH = (high * 10000 + low) * 0.1.
    """
    if registers is None or index + 1 >= len(registers):
        return None
    return round((registers[index] * 10000 + registers[index + 1]) * 0.1, 1)


def _power_factor(registers: list[int] | None, p_index: int, s_index: int) -> float | None:
    """cos phi = P / S built from the register pairs (W over VA)."""
    p = value(registers, p_index)
    s = value(registers, s_index)
    if p is None or s is None or s <= 0:
        return None
    return round(max(-1.0, min(1.0, p / s)), 2)


def _uptime(registers: list[int] | None, index: int) -> dict[str, int] | None:
    """15219/15220/15221: accumulated day / hour / minute."""
    if registers is None or index + 2 >= len(registers):
        return None
    return {
        "days": registers[index],
        "hours": registers[index + 1],
        "minutes": registers[index + 2],
    }


def _arrow_flag(registers: list[int] | None, index: int) -> dict[str, Any] | None:
    """25279 Arrow Flag (see protocol frame "Arrow Flag bit").

    bit0 PVFlag, bit1 LoadFlag, bit2 BattFlag, bit3 GridFlag (existence),
    bit4 PV-to-Machine, bit5 Machine-to-Load,
    bits6-7 Machine-Batt (0 disconnect, 1 machine->batt, 2 batt->machine, 3 connected),
    bits8-9 Machine-Grid (0 disconnect, 1 machine->grid, 2 grid->machine, 3 connected).
    """
    raw = value(registers, index, signed=False)
    if raw is None:
        return None
    return {
        "pv_present": bool(raw & (1 << 0)),
        "load_present": bool(raw & (1 << 1)),
        "battery_present": bool(raw & (1 << 2)),
        "grid_present": bool(raw & (1 << 3)),
        "pv_to_machine": bool(raw & (1 << 4)),
        "machine_to_load": bool(raw & (1 << 5)),
        "machine_battery": (raw >> 6) & 0b11,
        "machine_grid": (raw >> 8) & 0b11,
        "raw": raw,
    }


def _flag_list(
    registers: list[int] | None,
    index: int,
    *,
    code_prefix: str,
    key_prefix: str,
    message: int | None = None,
) -> list[dict[str, Any]]:
    raw = value(registers, index, signed=False)
    if raw is None:
        return []
    flags: list[dict[str, Any]] = []
    for bit in range(16):
        if raw & (1 << bit):
            flag: dict[str, Any] = {
                "bit": bit,
                "code": f"{code_prefix}{message if message is not None else ''}-{bit:02d}",
                "key": f"fault.{key_prefix}.{bit}" if message is None else f"fault.{key_prefix}{message}.{bit}",
            }
            if message is not None:
                flag["message"] = message
            flags.append(flag)
    return flags


def decode_inverter_error_flags(registers: list[int] | None) -> list[dict[str, Any]]:
    """Active bits of inverter error messages 1 and 2 (25261, 25262)."""
    flags: list[dict[str, Any]] = []
    for message, offset in INVERTER_ERROR_REGISTERS:
        flags.extend(_flag_list(registers, offset, code_prefix="E", key_prefix="inv.e", message=message))
    return flags


def decode_inverter_warning_flags(registers: list[int] | None) -> list[dict[str, Any]]:
    """Active bits of inverter warning messages 1 and 2 (25265, 25266)."""
    flags: list[dict[str, Any]] = []
    for message, offset in INVERTER_WARNING_REGISTERS:
        flags.extend(_flag_list(registers, offset, code_prefix="W", key_prefix="inv.w", message=message))
    return flags


def decode_charger_error_flags(registers: list[int] | None) -> list[dict[str, Any]]:
    """Active bits of the charger error message (15213)."""
    return _flag_list(registers, 12, code_prefix="CE", key_prefix="chg.e")


def decode_charger_warning_flags(registers: list[int] | None) -> list[dict[str, Any]]:
    """Active bits of the charger warning message (15214)."""
    return _flag_list(registers, 13, code_prefix="CW", key_prefix="chg.w")


def decode_identity(registers: list[int] | None) -> dict[str, Any] | None:
    """Identity block 20000..20016 (protocol 1.4.15).

    20000 machine type high (PV/PH/EP series), 20001 machine type low,
    20002-20003 serial, 20004/20005 versions, 20006 protocol edition,
    20009-20016 measurement calibration coefficients (16384 nominal).
    """
    if not registers:
        return None
    serial_number = None
    if len(registers) > 3 and registers[2] is not None and registers[3] is not None:
        serial_number = f"{registers[2]:04X}{registers[3]:04X}"
    machine_type = value(registers, 1, signed=False)
    software_raw = value(registers, 5, signed=False)
    return {
        "machine_type_high_code": value(registers, 0, signed=False),
        "model": _model_from(machine_type, software_raw),
        "machine_type_code": machine_type,
        "serial_number": serial_number,
        "hardware_version": version(registers, 4),
        "software_version": version(registers, 5),
        "communication_protocol_version": version(registers, 6),
        "battery_voltage_calibration": value(registers, 9),
        "inverter_voltage_calibration": value(registers, 10),
        "grid_voltage_calibration": value(registers, 11),
        "bus_voltage_calibration": value(registers, 12),
        "control_current_calibration": value(registers, 13),
        "inverter_current_calibration": value(registers, 14),
        "grid_current_calibration": value(registers, 15),
        "load_current_calibration": value(registers, 16),
    }


def decode_charger_identity(registers: list[int] | None) -> dict[str, Any] | None:
    """Charger identity block 10001..10005 (machine type, serial, versions)."""
    if not registers:
        return None
    serial_number = None
    if len(registers) > 2:
        serial_number = f"{registers[1]:04X}{registers[2]:04X}"
    machine_type = value(registers, 0, signed=False)
    return {
        "model": _model_from(machine_type, None),
        "machine_type_code": machine_type,
        "serial_number": serial_number,
        "hardware_version": version(registers, 3),
        "software_version": version(registers, 4),
    }


def decode_charger_status(registers: list[int] | None) -> dict[str, Any] | None:
    if not registers:
        return None
    return {
        "work_state_code": value(registers, 0, signed=False),  # 15201
        "mppt_state_code": value(registers, 1, signed=False),  # 15202
        "charging_state_code": value(registers, 2, signed=False),  # 15203
        "pv_voltage_v": scaled(registers, 4, 0.1),
        "battery_voltage_v": scaled(registers, 5, 0.1),
        "charger_current_a": scaled(registers, 6, 0.1),
        "charger_power_w": value(registers, 7),
        "radiator_temperature_c": value(registers, 8),
        "external_temperature_c": value(registers, 9),
        "battery_relay_connected": _relay(registers, 10),  # 15211
        "pv_relay_connected": _relay(registers, 11),  # 15212
        "error_code": value(registers, 12, signed=False),  # 15213
        "warning_code": value(registers, 13, signed=False),  # 15214
        "error_flags": decode_charger_error_flags(registers),
        "warning_flags": decode_charger_warning_flags(registers),
        "battery_voltage_grade_code": value(registers, 14, signed=False),
        "rated_current_a": scaled(registers, 15, 0.1),
        "accumulated_pv_power_kwh": packed_energy_kwh(registers, 16),  # 15217-15218
        "uptime": _uptime(registers, 18),  # 15219-15221 days/hours/minutes
    }


def decode_inverter_status(registers: list[int] | None) -> dict[str, Any] | None:
    if not registers:
        return None
    return {
        "work_state_code": value(registers, 0, signed=False),  # 25201
        "ac_voltage_grade_code": value(registers, 1, signed=False),
        "rated_power_va": value(registers, 2),  # 25203 (VA, not W)
        "battery_voltage_v": scaled(registers, 4, 0.1),
        "inverter_voltage_v": scaled(registers, 5, 0.1),
        "grid_voltage_v": scaled(registers, 6, 0.1),
        "bus_voltage_v": scaled(registers, 7, 0.1),
        "control_current_a": scaled(registers, 8, 0.1),
        "inverter_current_a": scaled(registers, 9, 0.1),
        "grid_current_a": scaled(registers, 10, 0.1),
        "load_current_a": scaled(registers, 11, 0.1),
        "inverter_power_w": value(registers, 12),  # 25213
        "grid_power_w": value(registers, 13),
        "load_power_w": value(registers, 14),
        "load_percent": value(registers, 15),
        "inverter_apparent_power_va": value(registers, 16),  # 25217
        "grid_apparent_power_va": value(registers, 17),
        "load_apparent_power_va": value(registers, 18),
        "inverter_reactive_power_var": value(registers, 20),
        "grid_reactive_power_var": value(registers, 21),
        "load_reactive_power_var": value(registers, 22),
        "inverter_frequency_hz": scaled(registers, 24, 0.01),
        "grid_frequency_hz": scaled(registers, 25, 0.01),
        "inverter_max_number": value(registers, 28, signed=False),
        "combine_type_code": value(registers, 29, signed=False),
        "inverter_number": value(registers, 30, signed=False),
        "ac_radiator_temperature_c": value(registers, 32),
        "transformer_temperature_c": value(registers, 33),
        "dc_radiator_temperature_c": value(registers, 34),
        "inverter_relay_connected": _relay(registers, 36),  # 25237
        "grid_relay_connected": _relay(registers, 37),  # 25238
        "load_relay_connected": _relay(registers, 38),  # 25239
        "n_line_relay_connected": _relay(registers, 39),  # 25240
        "dc_relay_connected": _relay(registers, 40),  # 25241
        "earth_relay_connected": _relay(registers, 41),  # 25242
        "accumulated_charger_power_kwh": packed_energy_kwh(registers, 44),  # 25245-25246
        "accumulated_discharger_power_kwh": packed_energy_kwh(registers, 46),
        "accumulated_buy_power_kwh": packed_energy_kwh(registers, 48),
        "accumulated_sell_power_kwh": packed_energy_kwh(registers, 50),
        "accumulated_load_power_kwh": packed_energy_kwh(registers, 52),
        "accumulated_self_use_power_kwh": packed_energy_kwh(registers, 54),
        "accumulated_pv_sell_power_kwh": packed_energy_kwh(registers, 56),
        "accumulated_grid_charger_power_kwh": packed_energy_kwh(registers, 58),
        "error_code_1": value(registers, 60, signed=False),  # 25261
        "error_code_2": value(registers, 61, signed=False),  # 25262
        "error_code_3": value(registers, 62, signed=False),  # 25263 (undocumented bits)
        "error_flags": decode_inverter_error_flags(registers),
        "warning_code_1": value(registers, 64, signed=False),  # 25265
        "warning_code_2": value(registers, 65, signed=False),  # 25266
        "warning_flags": decode_inverter_warning_flags(registers),
        "serial_number": _register_pair_hex(registers, 68),  # 25269-25270
        "hardware_version": version(registers, 70),  # 25271
        "software_version": version(registers, 71),  # 25272
        "battery_power_w": value(registers, 72),  # 25273
        "battery_current_a": value(registers, 73),  # 25274 (A per protocol)
        "battery_voltage_grade_code": value(registers, 74, signed=False),
        "rated_power_w": value(registers, 76),  # 25277
        "communication_protocol_version": version(registers, 77),  # 25278
        "arrow": _arrow_flag(registers, 78),  # 25279
        "power_factor": _power_factor(registers, 12, 16),  # Pinverter / SInverter
        "load_power_factor": _power_factor(registers, 14, 18),  # PLoad / Sload
    }


def decode_charger_config(registers: list[int] | None) -> dict[str, Any] | None:
    if not registers:
        return None
    return {
        "charger_work_enabled": bool(value(registers, 0)),
        "absorb_voltage_v": scaled(registers, 1, 0.1),
        "float_voltage_v": scaled(registers, 2, 0.1),
        "absorption_voltage_v": scaled(registers, 3, 0.1),
        "battery_low_voltage_v": scaled(registers, 4, 0.1),
        "battery_high_voltage_v": scaled(registers, 6, 0.1),
        "max_charger_current_a": scaled(registers, 7, 0.1),
        "absorb_charger_current_a": scaled(registers, 8, 0.1),
        "battery_type_code": value(registers, 9, signed=False),  # 10110
        "battery_capacity_ah": value(registers, 10, signed=False),
        "remove_accumulated_data_code": value(registers, 11),
        "equalization_enabled": bool(value(registers, 17)),
        "equalization_voltage_v": scaled(registers, 18, 0.1),
        "equalization_time_min": value(registers, 20),
        "equalization_timeout_min": value(registers, 21),
        "equalization_interval_days": value(registers, 22),
        "equalization_immediate_code": value(registers, 23),
    }


def decode_inverter_config(registers: list[int] | None) -> dict[str, Any] | None:
    if not registers:
        return None
    return {
        "offgrid_work_enabled": bool(value(registers, 0)),
        "output_voltage_v": scaled(registers, 1, 0.1),
        "output_frequency_hz": scaled(registers, 2, 0.01),
        "search_mode_enabled": bool(value(registers, 3)),
        "discharge_to_grid_enabled": bool(value(registers, 7)),
        "energy_use_mode_code": value(registers, 8, signed=False),  # 20109
        "grid_protect_standard_code": value(registers, 10, signed=False),  # 20111
        "solar_use_aim_code": value(registers, 11, signed=False),  # 20112
        "max_discharger_current_a": scaled(registers, 12, 0.1),
        "normal_voltage_point_v": scaled(registers, 17, 0.1),
        "start_sell_voltage_point_v": scaled(registers, 18, 0.1),
        "grid_max_charger_current_a": scaled(registers, 24, 0.1),
        "battery_low_voltage_v": scaled(registers, 26, 0.1),  # 20127
        "battery_high_voltage_v": scaled(registers, 27, 0.1),  # 20128
        "max_combine_charger_current_a": scaled(registers, 31, 0.1),
        "system_setting_code": value(registers, 41, signed=False),  # 20142
        # Display-only expansion of the 20142 "System setting" bit frame
        # (protocol sheet "System setting bit"); bits 7-15 are reserved.
        "system_setting_flags": _system_setting_flags(value(registers, 41, signed=False)),
        "charger_source_priority_code": value(registers, 42, signed=False),  # 20143
        "solar_power_balance_code": value(registers, 43, signed=False),  # 20144
        "raw_register_count": len(registers),
    }


def _system_setting_flags(code: int | None) -> dict[str, bool] | None:
    """Bit frame of register 20142, named per the protocol xlsx.

    0 OverLoadRestartForbid, 1 OverTempRestartForbid, 2 OverLoadBypassForbid,
    3 AutoTurnPageFlagForbid, 4 GridBuzzEnable (PV1800 only), 5 BuzzForbide
    (PV1800 only), 6 LcdLightEnable, 7-15 reserved.
    """
    if not isinstance(code, int):
        return None
    return {
        "overload_restart_forbid": bool(code & 0x0001),
        "overtemp_restart_forbid": bool(code & 0x0002),
        "overload_bypass_forbid": bool(code & 0x0004),
        "auto_turn_page_forbid": bool(code & 0x0008),
        "grid_buzzer_enable": bool(code & 0x0010),
        "buzzer_forbid": bool(code & 0x0020),
        "lcd_light_enable": bool(code & 0x0040),
    }


def decode_snapshot(
    *,
    sections: dict[str, list[int]],
    captured_at: str,
    source: dict[str, Any],
    errors: dict[str, str],
    latency_ms: float,
) -> dict[str, Any]:
    identity = decode_identity(sections.get("identity"))
    charger_identity = decode_charger_identity(sections.get("charger_identity"))
    charger = decode_charger_status(sections.get("charger_status"))
    inverter = decode_inverter_status(sections.get("inverter_status"))
    charger_config = decode_charger_config(sections.get("charger_config"))
    inverter_config = decode_inverter_config(sections.get("inverter_config"))

    def first(*values: Any) -> Any:
        return next((item for item in values if item is not None), None)

    metrics = {
        "battery_voltage_v": first(
            inverter and inverter.get("battery_voltage_v"),
            charger and charger.get("battery_voltage_v"),
        ),
        "pv_voltage_v": charger and charger.get("pv_voltage_v"),
        "pv_current_a": charger and charger.get("charger_current_a"),
        "pv_power_w": charger and charger.get("charger_power_w"),
        "inverter_voltage_v": inverter and inverter.get("inverter_voltage_v"),
        "grid_voltage_v": inverter and inverter.get("grid_voltage_v"),
        "bus_voltage_v": inverter and inverter.get("bus_voltage_v"),
        "inverter_current_a": inverter and inverter.get("inverter_current_a"),
        "grid_current_a": inverter and inverter.get("grid_current_a"),
        "load_current_a": inverter and inverter.get("load_current_a"),
        "inverter_power_w": inverter and inverter.get("inverter_power_w"),
        "grid_power_w": inverter and inverter.get("grid_power_w"),
        "load_power_w": inverter and inverter.get("load_power_w"),
        "load_percent": inverter and inverter.get("load_percent"),
        "inverter_frequency_hz": inverter and inverter.get("inverter_frequency_hz"),
        "grid_frequency_hz": inverter and inverter.get("grid_frequency_hz"),
        "battery_power_w": inverter and inverter.get("battery_power_w"),
        "ac_radiator_temperature_c": inverter and inverter.get("ac_radiator_temperature_c"),
        "transformer_temperature_c": inverter and inverter.get("transformer_temperature_c"),
        "dc_radiator_temperature_c": inverter and inverter.get("dc_radiator_temperature_c"),
        "rated_power_w": inverter and inverter.get("rated_power_w"),  # 25277
        "rated_power_va": inverter and inverter.get("rated_power_va"),  # 25203
        "power_factor": inverter and inverter.get("power_factor"),
    }

    return {
        "captured_at": captured_at,
        "source": source,
        "connection": {
            "status": "degraded" if errors else "online",
            "latency_ms": latency_ms,
            "section_errors": errors,
        },
        "identity": identity,
        "charger_identity": charger_identity,
        "status": {
            "charger": charger,
            "inverter": inverter,
        },
        "metrics": metrics,
        "configuration": {
            "charger": charger_config,
            "inverter": inverter_config,
        } if charger_config is not None or inverter_config is not None else None,
        "raw": sections,
    }


def _register_pair_hex(registers: list[int] | None, index: int) -> str | None:
    if registers is None or index + 1 >= len(registers):
        return None
    return f"{registers[index]:04X}{registers[index + 1]:04X}"
