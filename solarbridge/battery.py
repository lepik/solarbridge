"""Battery monitoring adapters (MNB LPR-51.2-100 class, PACE BMS).

Experimental: disabled by default (SB_BATTERY_MODE=off). Two transports are provided:

- ASCII: the verified PACE "paceic" protocol (reference implementation in
  debug/mnb_pace_poll.py, checked against live MNB dumps on 2026-11), plus the
  official Pylontech low-voltage variant from
  doc/RS485-protocol-pylon-low-voltage-V3.3-20180821.pdf:

      v25 (native PACE, what the live hardware answers):
          frame: ~ VER=25 ADR CID1=46 CID2 LENGTH INFO CHKSUM CR
          reads 0x42/0x44 carry INFO = pack address (01..0F)
      pylon (official Pylontech V3.3, ch. 3.3/3.5; the live MNB accepts these
          request frames too - the doc example ~20024642E00202FD33 is exactly
          what the old monitor sent):
          frame: ~ VER=20 ADR CID1=46 CID2 LENGTH INFO CHKSUM CR
          reads 0x42/0x44 carry INFO = command byte = pack address
      v20 (paceic "PYLON"-compatible fallback):
          frame: ~ VER=20 ADR CID1=4A CID2 0000 CHKSUM CR (no INFO)

  CIDs (read-only): 0x90 BMS count, 0x42 analog (cells/temps/current/U/
  capacity), 0x44 status (protection/MOS/system/warnings/balance), 0x47
  system parameters (protection thresholds), 0x92 charge/discharge
  management info (limits + request flags), 0x93 module SN number,
  0xC2 product info (fallback). Write commands 0x94/0x95 from the Pylon
  document are deliberately NOT implemented: the service is read-only.

  Live-hardware facts (two MNB modules at DIP addresses 2 and 3):
  - The BMS answers VER=25/CID1=46 even to VER=20 requests (Pylon and v20
    shapes), so variants are probed with a strict version check and then
    locked per address.
  - Response layouts follow the PACE (paceic) variant, not Pylon V3.3:
    the 0x44 tail is prot1/prot2/sys/ctl/fault/bal/w1/w2, and 0x42 ends
    with define_p/full/cycles/design + ~13 undocumented bytes.
  - Temperatures are 0.1 K. PACE variants use the -2730 offset of the
    reference parser (matches the live dump: 0x0B47 -> 15.7 C); the pylon
    variant uses the -2731 offset from Pylon V3.3 ch. 3.3 (2986 -> 25.5 C).
    Raw values are kept in the payload JSON.

- Modbus RTU: the documented PACE-BMS-Modbus-Protocol-for-RS485 V1.3 map
  (registers 0..36: current, voltage, SOC/SOH, capacities, cycles, flags,
  16 cell voltages, 4 pack temps + MOS + environment).

Module addresses are always taken from the explicit SB_BATTERY_ADDRESSES
list (e.g. "2,3"); nothing is auto-discovered on the bus. Addresses start
from 2 per both protocol documents (2 = master battery, 3.. slaves).

Both adapters are strictly read-only. Parsers never crash the poller: a
parse failure is reported through health and the battery section is simply
omitted from the frame.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from .modbus import crc16

try:
    import serial
except ImportError:  # pragma: no cover
    serial = None  # type: ignore[assignment]


LOGGER = logging.getLogger(__name__)

# CID2 command codes. 0x42/0x44/0x90/0xC2 are paceic commands; 0x47/0x92/0x93
# come from the Pylon low-voltage V3.3 document (ch. 3.4/3.6/3.7). Write
# commands 0x94/0x95 from that document are deliberately not implemented.
CID_BMS_COUNT = 0x90       # number of packs / link check
CID_ANALOG = 0x42          # cell voltages, temperatures, current, U, capacity, cycles
CID_STATUS = 0x44          # protection, MOSFET, system flags, warnings, balance
CID_SYSTEM_PARAMS = 0x47   # protection thresholds (Pylon V3.3 ch. 3.4)
CID_CHARGE_LIMITS = 0x92   # charge/discharge limits + request flags (ch. 3.6)
CID_MODULE_SN = 0x93       # 16-byte ASCII module serial number (ch. 3.7)
CID_PRODUCT_INFO = 0xC2    # product/serial info (optional, unverified on live HW)

RTN_CODES = {
    "00": "ok",
    "01": "VER error",
    "02": "frame checksum error",
    "03": "length checksum error",
    "04": "unknown CID2",
    "05": "command format error",
    "06": "invalid INFO data",
    "09": "operation error",
    "90": "address error",
    "91": "internal communication error",
}

# Frame shapes per protocol variant: (VER, CID1) of request and reply.
VARIANT_FRAMES = {
    "v25": (0x25, 0x46),    # PACE native (what the live MNB hardware answers)
    "pylon": (0x20, 0x46),  # Pylontech low voltage V3.3
    "v20": (0x20, 0x4A),    # PACE "PYLON"-compatible fallback
}

# Protocol name stored in the per-module payload JSON.
ASCII_PROTOCOL_NAMES = {
    "v25": "paceic-ascii/v25",
    "v20": "paceic-ascii/v20",
    "pylon": "pylon-lv-ascii/v3.3",
}

# 0x44 status bit tables (Pace A.17/A.18; English labels for the stored JSON).
PROTECTION1_BITS = [
    (0, "cell overvoltage protection"), (1, "cell undervoltage protection"),
    (2, "pack overvoltage protection"), (3, "pack undervoltage protection"),
    (4, "charge overcurrent protection"), (5, "discharge overcurrent protection"),
    (6, "short circuit protection"),
]
PROTECTION2_BITS = [
    (0, "charge overtemperature protection"), (1, "discharge overtemperature protection"),
    (2, "charge undertemperature protection"), (3, "discharge undertemperature protection"),
    (4, "MOSFET overheating protection"), (5, "ambient overtemperature protection"),
    (6, "ambient undertemperature protection"), (7, "full charge protection"),
]
SYSTEM_BITS = [
    (0, "current limiting active"), (1, "charge MOSFET on"), (2, "discharge MOSFET on"),
    (3, "pack present"), (4, "polarity reversed"), (5, "AC present"), (7, "heartbeat"),
]
FAULT_BITS = [
    (0, "charge MOSFET fault"), (1, "discharge MOSFET fault"), (2, "NTC fault"),
    (4, "cell fault"), (5, "measurement fault"),
]
WARNING1_BITS = [
    (0, "cell overvoltage warning"), (1, "cell undervoltage warning"),
    (2, "pack overvoltage warning"), (3, "pack undervoltage warning"),
    (4, "charge overcurrent warning"), (5, "discharge overcurrent warning"),
]
WARNING2_BITS = [
    (0, "charge overtemperature warning"), (1, "discharge overtemperature warning"),
    (2, "charge undertemperature warning"), (3, "discharge undertemperature warning"),
    (4, "ambient overtemperature warning"), (5, "ambient undertemperature warning"),
    (6, "MOSFET overheating warning"), (7, "low state of charge warning"),
]
LEVEL_CODES = {0: "normal", 1: "below limit", 2: "above limit", 0xF0: "other fault"}

# 0x44 status tables for the pylon variant (Pylon V3.3 ch. 3.5, Status 1-3).
# Status 4/5 carry one bit per cell (1-8 / 9-16): 1 = cell voltage fault.
PYLON_STATUS1_BITS = [
    (0, "pack overvoltage"), (1, "cell undervoltage"),
    (2, "charge overcurrent"), (4, "discharge overcurrent"),
    (5, "discharge overtemperature"), (6, "charge overtemperature"),
    (7, "pack undervoltage"),
]
PYLON_STATUS2_BITS = [
    (0, "pre-charge MOSFET on"), (1, "charge MOSFET on"),
    (2, "discharge MOSFET on"), (3, "load supplied by battery"),
]
PYLON_STATUS3_BITS = [
    (0, "buzzer on"), (3, "fully charged"), (5, "heater on"),
    (6, "effective discharge current"), (7, "effective charge current"),
]


class BatteryError(RuntimeError):
    pass


class ForeignFrameError(BatteryError):
    """A syntactically valid frame addressed to another module on the bus."""


# --------------------------------------------------------------------- framing


def calc_lchksum(lenid: int) -> str:
    """LENGTH = LCHKSUM(4 bits) + LENID(12 bits), ASCII-hex.
    LCHKSUM = (~(D11..8 + D7..4 + D3..0) + 1) & 0x0F; LENID = INFO char count."""
    if lenid == 0:
        return "0000"
    n1 = (lenid >> 8) & 0x0F
    n2 = (lenid >> 4) & 0x0F
    n3 = lenid & 0x0F
    lchk = (16 - ((n1 + n2 + n3) % 16)) % 16
    return f"{lchk:01X}{lenid:03X}"


def frame_checksum(body: bytes) -> int:
    """CHKSUM: sum of the body's ASCII codes, two's complement modulo 65536."""
    total = 0
    for byte in body:
        total += byte
    return ((~total) % 0x10000 + 1) & 0xFFFF


def build_ascii_request(addr: int, cid2: int, info: bytes = b"", variant: str = "v25") -> bytes:
    """Full ASCII request frame. v25/pylon carry CID1=46 and INFO (the command
    byte = module address); v20 uses 4A without INFO.
    LENID counts the ASCII-hex characters of INFO (2 per byte)."""
    if variant == "v25":
        info_hex = info.hex().upper()
        body = f"25{addr:02X}46{cid2:02X}{calc_lchksum(len(info_hex))}{info_hex}"
    elif variant == "pylon":
        # Pylon V3.3: VER=20, CID1=46. For 0x42/0x44/0x92/0x93 the INFO is the
        # 1-byte command (== ADR, ch. 3.3/3.5/3.6/3.7); 0x47 sends no INFO.
        info_hex = info.hex().upper()
        body = f"20{addr:02X}46{cid2:02X}{calc_lchksum(len(info_hex))}{info_hex}"
    elif variant == "v20":
        body = f"20{addr:02X}4A{cid2:02X}0000"
    else:
        raise BatteryError(f"unknown protocol variant: {variant!r}")
    encoded = body.encode("ascii")
    return b"~" + encoded + f"{frame_checksum(encoded):04X}".encode("ascii") + b"\r"


def parse_ascii_response(
    raw: bytes,
    expect_addr: int | None = None,
    expect_version: int | None = None,
    expect_cid1: int | None = None,
) -> dict[str, Any]:
    """Validate and split a response frame:
    ~ VER(2) ADR(2) CID1(2) RTN(2) LENGTH(4) INFO... CHKSUM(4) CR."""
    if len(raw) < 18 or raw[0] != 0x7E or raw[-1] != 0x0D:
        raise BatteryError("invalid frame boundaries")
    body, checksum = raw[1:-5], raw[-5:-1]
    try:
        received = int(checksum, 16)
    except ValueError as exc:
        raise BatteryError("checksum field is not hex") from exc
    if frame_checksum(body) != received:
        raise BatteryError(f"frame checksum mismatch (received {checksum.decode('ascii', 'replace')})")
    try:
        text = body.decode("ascii")
        version = int(text[0:2], 16)
        addr = int(text[2:4], 16)
        cid1 = int(text[4:6], 16)
        len_field = int(text[8:12], 16)
        info_hex = text[12:]
        info = bytes.fromhex(info_hex)
    except (UnicodeDecodeError, ValueError) as exc:
        raise BatteryError(f"malformed frame body: {exc}") from exc
    # LENID counts INFO's ASCII-hex characters (2 per payload byte).
    expected_len = len_field & 0x0FFF
    if expected_len != len(info_hex):
        raise BatteryError(f"info length mismatch: field {expected_len}, info chars {len(info_hex)}")
    if calc_lchksum(expected_len) != text[8:12]:
        raise BatteryError(f"length checksum mismatch (field {text[8:12]})")
    if expect_addr is not None and addr != expect_addr:
        raise ForeignFrameError(f"frame addressed to 0x{addr:02X}, expected 0x{expect_addr:02X}")
    if expect_version is not None and version != expect_version:
        raise BatteryError(f"unexpected protocol version 0x{version:02X} (expected 0x{expect_version:02X})")
    if expect_cid1 is not None and cid1 != expect_cid1:
        raise BatteryError(f"unexpected CID1 0x{cid1:02X} (expected 0x{expect_cid1:02X})")
    rtn = text[6:8]
    if rtn != "00":
        raise BatteryError(f"device returned RTN={rtn} ({RTN_CODES.get(rtn, 'unknown')})")
    return {"version": version, "addr": addr, "cid1": cid1, "rtn": rtn, "info": info}


# --------------------------------------------------------------------- parsers


def parse_analog_v25(payload: bytes) -> dict[str, Any]:
    """0x42 analog reply, v25 layout (Pace A.13/A.14, verified on live dumps):
    [flag][pack][cellCount][cells 2B mV][tempCount][temps 2B 0.1K][current 2B 10mA]
    [U 2B mV][remain 2B 10mAh][P=3][full 2B 10mAh][cycles 2B][design 2B 10mAh] + tail."""
    try:
        idx = 2  # flag + pack echo
        cell_count = payload[idx]; idx += 1
        cells_mv = []
        for _ in range(cell_count):
            cells_mv.append(int.from_bytes(payload[idx:idx + 2], "big")); idx += 2
        temp_count = payload[idx]; idx += 1
        temps_c = []
        for _ in range(temp_count):
            raw_t = int.from_bytes(payload[idx:idx + 2], "big")
            temps_c.append(round((raw_t - 2730) / 10.0, 1)); idx += 2
        current_a = _signed16(int.from_bytes(payload[idx:idx + 2], "big")) / 100.0; idx += 2
        voltage_v = int.from_bytes(payload[idx:idx + 2], "big") / 1000.0; idx += 2
        remain_ah = int.from_bytes(payload[idx:idx + 2], "big") / 100.0; idx += 2
        define_p = payload[idx]; idx += 1
        full_ah = int.from_bytes(payload[idx:idx + 2], "big") / 100.0; idx += 2
        cycles = int.from_bytes(payload[idx:idx + 2], "big"); idx += 2
        design_ah = int.from_bytes(payload[idx:idx + 2], "big") / 100.0
    except (IndexError, ValueError):
        return {"error": "unexpected INFO length while parsing 0x42"}
    return {
        "voltage_v": voltage_v, "current_a": current_a,
        "power_w": round(voltage_v * current_a, 1),
        "soc_percent": round(remain_ah / full_ah * 100.0, 1) if full_ah else 0.0,
        "remain_ah": remain_ah, "full_ah": full_ah,
        "design_ah": design_ah,
        "soh_percent": round(full_ah / design_ah * 100.0, 1) if design_ah else 0.0,
        "cycles": cycles, "cells_mv": cells_mv,
        "min_mv": min(cells_mv) if cells_mv else 0,
        "max_mv": max(cells_mv) if cells_mv else 0,
        "delta_mv": (max(cells_mv) - min(cells_mv)) if cells_mv else 0,
        "temps_c": temps_c, "define_p": define_p,
    }


def parse_analog_v20(payload: bytes) -> dict[str, Any]:
    """0x42 analog reply, v20 (PYLON) layout: U in 0.01 V, constant 2, no design capacity."""
    try:
        idx = 2
        cell_count = payload[idx]; idx += 1
        cells_mv = []
        for _ in range(cell_count):
            cells_mv.append(int.from_bytes(payload[idx:idx + 2], "big")); idx += 2
        temp_count = payload[idx]; idx += 1
        temps_c = []
        for _ in range(temp_count):
            raw_t = int.from_bytes(payload[idx:idx + 2], "big")
            temps_c.append(round((raw_t - 2730) / 10.0, 1)); idx += 2
        current_a = _signed16(int.from_bytes(payload[idx:idx + 2], "big")) / 100.0; idx += 2
        voltage_v = int.from_bytes(payload[idx:idx + 2], "big") / 100.0; idx += 2
        remain_ah = int.from_bytes(payload[idx:idx + 2], "big") / 100.0; idx += 2
        idx += 1  # constant 2
        full_ah = int.from_bytes(payload[idx:idx + 2], "big") / 100.0; idx += 2
        cycles = int.from_bytes(payload[idx:idx + 2], "big")
    except (IndexError, ValueError):
        return {"error": "unexpected INFO length while parsing 0x42 (v20)"}
    return {
        "voltage_v": voltage_v, "current_a": current_a,
        "power_w": round(voltage_v * current_a, 1),
        "soc_percent": round(remain_ah / full_ah * 100.0, 1) if full_ah else 0.0,
        "remain_ah": remain_ah, "full_ah": full_ah,
        "design_ah": 0.0, "soh_percent": 0.0, "cycles": cycles,
        "cells_mv": cells_mv, "min_mv": min(cells_mv) if cells_mv else 0,
        "max_mv": max(cells_mv) if cells_mv else 0,
        "delta_mv": (max(cells_mv) - min(cells_mv)) if cells_mv else 0,
        "temps_c": temps_c, "define_p": 2,
    }


def parse_analog_pylon(payload: bytes) -> dict[str, Any]:
    """0x42 analog reply, Pylon V3.3 ch. 3.3 layout:
    [flag][cmd][cellCount][cells 2B mV][tempCount][temps 2B 0.1K-2731]
    [current 2B signed 0.01A][U 2B mV][remain1 2B 0.001Ah][userdef 1B]
    [total1 2B 0.001Ah][cycles 2B] and, when userdef >= 4 (packs > 65 Ah),
    [remain2][total2]. The doc example (74 Ah pack) carries remain2/total2
    as 3-byte values (00CA58 -> 51.800 Ah) because 74 000 mAh does not fit
    into two bytes; 2-byte replies are handled as well. remain1/total1 = 0xFFFF
    means "use remain2/total2"."""
    try:
        idx = 2  # INFO flag + command echo
        cell_count = payload[idx]; idx += 1
        cells_mv = []
        for _ in range(cell_count):
            cells_mv.append(int.from_bytes(payload[idx:idx + 2], "big")); idx += 2
        temp_count = payload[idx]; idx += 1
        temps_c = []
        for _ in range(temp_count):
            raw_t = int.from_bytes(payload[idx:idx + 2], "big")
            temps_c.append(round((raw_t - 2731) / 10.0, 1)); idx += 2
        current_a = _signed16(int.from_bytes(payload[idx:idx + 2], "big")) / 100.0; idx += 2
        voltage_v = int.from_bytes(payload[idx:idx + 2], "big") / 1000.0; idx += 2
        remain_raw = int.from_bytes(payload[idx:idx + 2], "big"); idx += 2
        userdef = payload[idx]; idx += 1
        total_raw = int.from_bytes(payload[idx:idx + 2], "big"); idx += 2
        cycles = int.from_bytes(payload[idx:idx + 2], "big"); idx += 2
    except (IndexError, ValueError):
        return {"error": "unexpected INFO length while parsing 0x42 (pylon)"}
    tail = payload[idx:]
    remain2_raw = total2_raw = None
    leftover = tail if userdef < 4 else b""
    if userdef >= 4 and len(tail) >= 4:
        if len(tail) >= 6:
            remain2_raw = int.from_bytes(tail[0:3], "big")
            total2_raw = int.from_bytes(tail[3:6], "big")
            leftover = tail[6:]
        else:
            remain2_raw = int.from_bytes(tail[0:2], "big")
            total2_raw = int.from_bytes(tail[2:4], "big")
            leftover = tail[4:]
    elif userdef >= 4:
        leftover = tail
    remain_ah = remain2_raw / 1000.0 if remain_raw == 0xFFFF and remain2_raw is not None else remain_raw / 1000.0
    full_ah = total2_raw / 1000.0 if total_raw == 0xFFFF and total2_raw is not None else total_raw / 1000.0
    out: dict[str, Any] = {
        "voltage_v": voltage_v, "current_a": current_a,
        "power_w": round(voltage_v * current_a, 1),
        "soc_percent": round(remain_ah / full_ah * 100.0, 1) if full_ah else 0.0,
        "remain_ah": round(remain_ah, 3), "full_ah": round(full_ah, 3),
        "design_ah": 0.0, "soh_percent": 0.0,  # no design capacity in the pylon set
        "cycles": cycles, "cells_mv": cells_mv,
        "min_mv": min(cells_mv) if cells_mv else 0,
        "max_mv": max(cells_mv) if cells_mv else 0,
        "delta_mv": (max(cells_mv) - min(cells_mv)) if cells_mv else 0,
        "temps_c": temps_c, "userdef_items": userdef,
    }
    if remain2_raw is not None:
        out["remain2_ah"] = round(remain2_raw / 1000.0, 3)
        out["total2_ah"] = round(total2_raw / 1000.0, 3)
    if leftover:
        out["tail_hex"] = leftover.hex(" ").upper()
    return out


def parse_status_pylon(payload: bytes) -> dict[str, Any]:
    """0x44 status reply, Pylon V3.3 ch. 3.5 layout:
    [flag][cmd][cellCount][cell alarms 1B][tempCount][temp alarms 1B]
    [chgI warn][U warn][disI warn][Status1][Status2][Status3][Status4][Status5].
    Alarm codes: 0 normal, 1 below limit, 2 above limit, F0 other fault."""
    out: dict[str, Any] = {"errors": []}
    try:
        idx = 2
        cell_count = payload[idx]; idx += 1
        cell_warn = [payload[idx + i] for i in range(cell_count)]; idx += cell_count
        temp_count = payload[idx]; idx += 1
        temp_warn = [payload[idx + i] for i in range(temp_count)]; idx += temp_count
        chg_warn, volt_warn, dis_warn = payload[idx], payload[idx + 1], payload[idx + 2]; idx += 3
        status1, status2, status3, status4, status5 = payload[idx:idx + 5]
    except IndexError:
        out["errors"].append("unexpected INFO length while parsing 0x44 (pylon)")
        out["raw_payload_hex"] = payload.hex(" ").upper()
        return out
    cell_faults = []
    for cell in range(1, 17):
        byte = status4 if cell <= 8 else status5
        bit = (cell - 1) if cell <= 8 else (cell - 9)
        if byte & (1 << bit):
            cell_faults.append(cell)
    out.update({
        "cell_warn": [LEVEL_CODES.get(w, f"code 0x{w:02X}") for w in cell_warn if w],
        "temp_warn": [LEVEL_CODES.get(w, f"code 0x{w:02X}") for w in temp_warn if w],
        "charge_current_warn": LEVEL_CODES.get(chg_warn, f"code 0x{chg_warn:02X}") if chg_warn else None,
        "voltage_warn": LEVEL_CODES.get(volt_warn, f"code 0x{volt_warn:02X}") if volt_warn else None,
        "discharge_current_warn": LEVEL_CODES.get(dis_warn, f"code 0x{dis_warn:02X}") if dis_warn else None,
        "protection": _bits(status1, PYLON_STATUS1_BITS),
        "system": _bits(status2, PYLON_STATUS2_BITS),
        "state": _bits(status3, PYLON_STATUS3_BITS),
        "cell_faults": cell_faults,
        "protection_bits": status1,
        "alarm_bits": status3,
        "system_bits": status2,
        "cell_fault_mask": status4 | (status5 << 8),
        "raw": f"s1={status1:02X} s2={status2:02X} s3={status3:02X} "
               f"s4={status4:02X} s5={status5:02X}",
        "raw_payload_hex": payload.hex(" ").upper(),
    })
    return out


def _extract_module_sn(payload: bytes) -> dict[str, Any] | None:
    """0x93 reply (Pylon V3.3 ch. 3.7): [flag][cmd][16-byte ASCII SN].
    The last 16 bytes are taken so replies with or without the flag/cmd
    prefix both parse (the paceic layout echoes the pack address there)."""
    if len(payload) < 16:
        return None
    raw = payload[-16:].decode("ascii", errors="replace")
    sn = raw.strip().strip("\x00").strip()
    if not sn:
        return None
    clean = sn if all(32 <= ord(ch) < 127 for ch in sn) else None
    return {"raw": raw, "sn": clean}


def parse_charge_limits_pylon(payload: bytes) -> dict[str, Any] | None:
    """0x92 reply (Pylon V3.3 ch. 3.6): [flag][cmd][charge U 2B mV]
    [discharge U 2B mV][charge I 2B 0.1 A][discharge I 2B 0.1 A][flags 1B]:
    bit7 charge enable, bit6 discharge enable, bit5/4 charge immediately,
    bit3 full charge request. The last 9 bytes are used so replies with or
    without the flag/cmd prefix parse; implausible values (unknown firmware
    layout) keep only the raw bytes."""
    if len(payload) < 9:
        return None
    data = payload[-9:]
    charge_v = int.from_bytes(data[0:2], "big") / 1000.0
    discharge_v = int.from_bytes(data[2:4], "big") / 1000.0
    charge_i = _signed16(int.from_bytes(data[4:6], "big")) / 10.0
    discharge_i = _signed16(int.from_bytes(data[6:8], "big")) / 10.0
    flags = data[8]
    out: dict[str, Any] = {"flags": flags, "raw_payload_hex": payload.hex(" ").upper()}
    if not (10.0 <= charge_v <= 120.0 and 10.0 <= discharge_v <= 120.0
            and -1000.0 <= charge_i <= 1000.0 and -1000.0 <= discharge_i <= 1000.0):
        return out  # implausible for a low-voltage pack: keep raw bytes only
    out.update({
        "charge_voltage_limit_v": charge_v,
        "discharge_voltage_limit_v": discharge_v,
        "charge_current_limit_a": charge_i,
        "discharge_current_limit_a": discharge_i,
        "charge_enable": bool(flags & 0x80),
        "discharge_enable": bool(flags & 0x40),
        "charge_immediately": bool(flags & 0x30),
        "full_charge_request": bool(flags & 0x08),
    })
    return out


def parse_system_params_pylon(payload: bytes) -> dict[str, Any] | None:
    """0x47 reply (Pylon V3.3 ch. 3.4): [flag][12 x 2B]:
    cell U high / cell U low (alarm) / cell U low (protect), charge T high/low,
    charge I limit, module U high / low (alarm) / low (protect),
    discharge T high/low, discharge I limit. Voltages are unsigned mV (a
    58.4 V module limit does not fit into signed 2B), temperatures unsigned
    0.1 K with the -2731 offset; only the current limits are signed 0.01 A
    (doc: "A, with symbol"). Implausible values keep only the raw bytes."""
    if len(payload) < 24:
        return None
    data = payload[-24:]
    values = [int.from_bytes(data[i:i + 2], "big") for i in range(0, 24, 2)]
    (cell_high, cell_low_alarm, cell_low_protect, chg_t_high, chg_t_low, chg_i,
     mod_high, mod_low_alarm, mod_low_protect, dis_t_high, dis_t_low, dis_i) = values
    chg_i, dis_i = _signed16(chg_i), _signed16(dis_i)
    out: dict[str, Any] = {"raw_payload_hex": payload.hex(" ").upper()}
    cell_ok = 0.5 <= cell_high / 1000.0 <= 6.0 and 0.5 <= cell_low_alarm / 1000.0 <= 6.0
    mod_ok = 20.0 <= mod_high / 1000.0 <= 120.0 and 20.0 <= mod_low_alarm / 1000.0 <= 120.0
    temp_ok = all(-50.0 <= (raw - 2731) / 10.0 <= 100.0 for raw in (chg_t_high, chg_t_low, dis_t_high, dis_t_low))
    cur_ok = all(-1000.0 <= raw / 100.0 <= 1000.0 for raw in (chg_i, dis_i))
    if not (cell_ok and mod_ok and temp_ok and cur_ok):
        return out  # unknown firmware layout: keep raw bytes only
    def _c(raw: int) -> float:
        return round((raw - 2731) / 10.0, 1)
    out.update({
        "cell_voltage_high_limit_v": cell_high / 1000.0,
        "cell_voltage_low_alarm_v": cell_low_alarm / 1000.0,
        "cell_voltage_low_protect_v": cell_low_protect / 1000.0,
        "charge_high_temp_limit_c": _c(chg_t_high),
        "charge_low_temp_limit_c": _c(chg_t_low),
        "charge_current_limit_a": chg_i / 100.0,
        "module_voltage_high_limit_v": mod_high / 1000.0,
        "module_voltage_low_alarm_v": mod_low_alarm / 1000.0,
        "module_voltage_low_protect_v": mod_low_protect / 1000.0,
        "discharge_high_temp_limit_c": _c(dis_t_high),
        "discharge_low_temp_limit_c": _c(dis_t_low),
        "discharge_current_limit_a": dis_i / 100.0,
    })
    return out


def _bits(byte: int, table: list) -> list[str]:
    return [name for bit, name in table if byte & (1 << bit)]


def parse_status_v25(payload: bytes) -> dict[str, Any]:
    """0x44 status reply (Pace A.17/A.18; the reference parser uses this layout
    for both variants):
    [flag][pack][cellCount][cell alarms 1B][tempCount][temp alarms 1B]
    [chgI warn][U warn][disI warn][Protect1][Protect2][System][Control]
    [Fault][Bal1][Bal2][Warn1][Warn2]."""
    out: dict[str, Any] = {"errors": []}
    try:
        idx = 2
        cell_count = payload[idx]; idx += 1
        cell_warn = []
        for _ in range(cell_count):
            cell_warn.append(payload[idx]); idx += 1
        temp_count = payload[idx]; idx += 1
        temp_warn = [payload[idx + i] for i in range(temp_count)]; idx += temp_count
        chg_warn, volt_warn, dis_warn = payload[idx], payload[idx + 1], payload[idx + 2]; idx += 3
        prot1, prot2 = payload[idx], payload[idx + 1]; idx += 2
        system, control = payload[idx], payload[idx + 1]; idx += 2
        fault = payload[idx]; idx += 1
        # Pace doc order: first byte = cells 1-8, second byte = cells 9-16.
        # Some firmware swaps the bytes - the raw mask is always kept for checks.
        bal_mask = (payload[idx] << 8) | payload[idx + 1]; idx += 2
        warn1, warn2 = payload[idx], payload[idx + 1]
    except IndexError:
        out["errors"].append("unexpected INFO length while parsing 0x44")
        out["raw_payload_hex"] = payload.hex(" ").upper()
        return out
    bal_cells = []
    for cell in range(1, 17):
        bit = (cell - 1 + 8) if cell <= 8 else (cell - 9)
        if bal_mask & (1 << bit):
            bal_cells.append(cell)
    out.update({
        "cell_warn": [LEVEL_CODES.get(w, f"code 0x{w:02X}") for w in cell_warn if w],
        "temp_warn": [LEVEL_CODES.get(w, f"code 0x{w:02X}") for w in temp_warn if w],
        "charge_current_warn": LEVEL_CODES.get(chg_warn, f"code 0x{chg_warn:02X}") if chg_warn else None,
        "voltage_warn": LEVEL_CODES.get(volt_warn, f"code 0x{volt_warn:02X}") if volt_warn else None,
        "discharge_current_warn": LEVEL_CODES.get(dis_warn, f"code 0x{dis_warn:02X}") if dis_warn else None,
        "protection": _bits(prot1, PROTECTION1_BITS) + _bits(prot2, PROTECTION2_BITS),
        "system": _bits(system, SYSTEM_BITS),
        "fault": _bits(fault, FAULT_BITS),
        "warnings": _bits(warn1, WARNING1_BITS) + _bits(warn2, WARNING2_BITS),
        "balancing_cells": bal_cells,
        "protection_bits": prot1 | (prot2 << 8),
        "alarm_bits": warn1 | (warn2 << 8),
        "system_bits": system,
        "balance_mask": bal_mask,
        "raw": f"prot1={prot1:02X} prot2={prot2:02X} sys={system:02X} ctl={control:02X} "
               f"flt={fault:02X} bal={bal_mask:04X} w1={warn1:02X} w2={warn2:02X}",
        "raw_payload_hex": payload.hex(" ").upper(),
    })
    return out


# --------------------------------------------------------------------- ASCII client


class AsciiBatteryClient:
    """PACE paceic ASCII client (read-only commands only).

    The protocol variant is probed with a strict version check on the first
    exchange and then locked per module address: live MNB hardware answers
    VER=25 even to v20 requests, so a loose probe would misdetect it.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        timeout: float = 2.0,
        variant: str = "auto",
        cmd_gap: float = 1.0,
        serial_factory: Any = None,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.variant = variant if variant in VARIANT_FRAMES else "auto"
        self.cmd_gap = cmd_gap
        self._serial_factory = serial_factory or (serial.Serial if serial else None)
        self._serial: Any = None
        self._last_request_at = 0.0
        self._variants: dict[int, str] = {}

    # ------------------------------------------------------------ transport

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:  # noqa: BLE001
                pass
            self._serial = None

    def _open(self) -> Any:
        if self._serial is not None and getattr(self._serial, "is_open", False):
            return self._serial
        if self._serial_factory is None:
            raise BatteryError("pyserial is not installed")
        self._serial = self._serial_factory(
            self.port, baudrate=self.baudrate, bytesize=8, parity="N", stopbits=1,
            timeout=self.timeout, write_timeout=2,
        )
        return self._serial

    def _respect_gap(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.cmd_gap:
            time.sleep(self.cmd_gap - elapsed)

    def _read_frame(self, ser: Any) -> bytes | None:
        raw = bytearray()
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            chunk = ser.read(64)
            if chunk:
                raw.extend(chunk)
                if raw[-1:] == b"\r":
                    return bytes(raw)
        return None

    def _exchange(
        self,
        addr: int,
        cid2: int,
        info: bytes,
        variant: str,
        attempts: int = 2,
        expect_version: int | None = None,
        expect_cid1: int | None = None,
    ) -> bytes:
        ser = self._open()
        request = build_ascii_request(addr, cid2, info, variant)
        frame_ver, frame_cid1 = VARIANT_FRAMES[variant]
        last_error: Exception | None = None
        try:
            for _ in range(attempts):
                self._respect_gap()
                ser.reset_input_buffer()
                ser.write(request)
                ser.flush()
                self._last_request_at = time.monotonic()
                raw = self._read_frame(ser)
                if raw is None:
                    last_error = BatteryError(f"no response for cid 0x{cid2:02X} from address {addr}")
                    continue
                try:
                    return parse_ascii_response(
                        raw,
                        expect_addr=addr,
                        expect_version=frame_ver if expect_version is None else expect_version,
                        expect_cid1=frame_cid1 if expect_cid1 is None else expect_cid1,
                    )["info"]
                except ForeignFrameError as exc:
                    # Another module answered: skip the frame and listen again.
                    last_error = exc
                    continue
        finally:
            if last_error is not None:
                self.close()
        raise last_error  # type: ignore[misc]

    # -------------------------------------------------------------- variant

    def variant_for(self, addr: int) -> str | None:
        return self._variants.get(addr)

    def _known_variant(self, addr: int) -> str | None:
        """Locked variant for an address; a pinned variant locks itself lazily."""
        variant = self._variants.get(addr)
        if variant is not None:
            return variant
        if self.variant != "auto":
            self._variants[addr] = self.variant
            return self.variant
        return None

    def _probe_auto(self, addr: int) -> tuple[str, bytes]:
        """First contact in auto mode: probe IS the first analog read, its payload
        is reused (the bus is not asked twice). Strict version checking keeps a
        v25 device from being misdetected as v20 (live MNB hardware answers
        VER=25 even to v20 requests). Order: v25, v20, then pylon - a paceic
        v20 device answers pylon-shaped requests too and would be misdetected,
        while a real Pylontech never answers the v20/CID1=4A shape."""
        for candidate in ("v25", "v20", "pylon"):
            info = bytes([addr]) if candidate in ("v25", "pylon") else b""
            try:
                payload = self._exchange(addr, CID_ANALOG, info, candidate, attempts=1)
                parsed = self._parse_analog(candidate, payload)
            except BatteryError:
                continue
            if "error" not in parsed:
                self._variants[addr] = candidate
                LOGGER.info("battery: ASCII variant %s locked for address %s", candidate, addr)
                return candidate, payload
        self.close()
        raise BatteryError(
            f"no ASCII answer from battery address {addr} (tried v25, v20 and pylon shapes)"
        )

    @staticmethod
    def _parse_analog(variant: str, payload: bytes) -> dict[str, Any]:
        if variant == "v25":
            return parse_analog_v25(payload)
        if variant == "pylon":
            return parse_analog_pylon(payload)
        return parse_analog_v20(payload)

    def _variant_and_payload(self, addr: int, cid2: int) -> tuple[str, bytes]:
        variant = self._known_variant(addr)
        if variant is not None:
            info = bytes([addr]) if variant in ("v25", "pylon") else b""
            return variant, self._exchange(addr, cid2, info, variant)
        variant, payload = self._probe_auto(addr)
        if cid2 == CID_ANALOG:
            return variant, payload  # the probe itself was the analog read
        info = bytes([addr]) if variant in ("v25", "pylon") else b""
        return variant, self._exchange(addr, cid2, info, variant)

    # ------------------------------------------------------------ public API

    def request(self, addr: int, cid2: int, info: bytes = b"") -> bytes:
        """Validated raw INFO payload for one command (variant resolved per address)."""
        variant = self._known_variant(addr)
        if variant is None:
            variant, _ = self._probe_auto(addr)
        return self._exchange(addr, cid2, info, variant)

    def read_analog(self, addr: int) -> dict[str, Any]:
        """0x42: cells, temperatures, current, voltage, capacities, cycles."""
        variant, payload = self._variant_and_payload(addr, CID_ANALOG)
        parsed = self._parse_analog(variant, payload)
        if "error" in parsed:
            raise BatteryError(str(parsed["error"]))
        return parsed

    def read_status(self, addr: int) -> dict[str, Any]:
        """0x44: protection, MOSFET state, warnings, balance."""
        variant, payload = self._variant_and_payload(addr, CID_STATUS)
        parsed = parse_status_pylon(payload) if variant == "pylon" else parse_status_v25(payload)
        if parsed.get("errors"):
            raise BatteryError(str(parsed["errors"][0]))
        return parsed

    def read_product_info(self, addr: int) -> dict[str, Any] | None:
        """0xC2 product info (optional metadata). Returns None on any failure."""
        try:
            variant = self._variants.get(addr)
            if variant is None:
                return None  # not probed yet; keep the bus quiet
            info = bytes([addr]) if variant in ("v25", "pylon") else b""
            payload = self._exchange(addr, CID_PRODUCT_INFO, info, variant, attempts=1)
        except Exception as exc:  # noqa: BLE001 - optional metadata must not fail polling
            LOGGER.debug("battery product info read failed for address %s: %s", addr, exc)
            return None
        text = payload.decode("ascii", errors="replace")
        fields = [field for field in text.split("\x00") if field.strip()]
        return {"raw": text.replace("\x00", " ").strip(), "fields": fields}

    def read_extended(self, addr: int) -> dict[str, Any]:
        """One-shot metadata reads from the Pylon V3.3 command set: 0x93 module
        serial number, 0x92 charge/discharge limits, 0x47 system parameters.

        Requests always use the pylon frame shape - the only documented shape
        for these CIDs; the reply is validated against the module's locked
        version (live MNB hardware answers VER=25 to VER=20 requests). Every
        read is optional: a failure (or an unknown reply layout) only omits
        the corresponding key, polling is never affected."""
        out: dict[str, Any] = {}
        variant = self._known_variant(addr)
        if variant is None:
            return out  # not probed yet; keep the bus quiet
        expect_version = VARIANT_FRAMES[variant][0]
        reads = (
            (CID_MODULE_SN, bytes([addr]), _extract_module_sn, "module_sn"),
            (CID_CHARGE_LIMITS, bytes([addr]), parse_charge_limits_pylon, "charge_limits"),
            (CID_SYSTEM_PARAMS, b"", parse_system_params_pylon, "system_params"),
        )
        for cid2, info, parser, key in reads:
            try:
                payload = self._exchange(
                    addr, cid2, info, "pylon", attempts=1, expect_version=expect_version,
                )
                parsed = parser(payload)
                if parsed:
                    out[key] = parsed
            except Exception as exc:  # noqa: BLE001 - optional metadata must not fail polling
                LOGGER.debug("battery extended read 0x%02X failed for address %s: %s", cid2, addr, exc)
        return out


# --------------------------------------------------------------------- Modbus


class PaceModbusBatteryClient:
    """PACE BMS Modbus RTU V1.3 read-only client (registers 0..36)."""

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 2.0,
                 slave_id: int = 1, cmd_gap: float = 0.2, serial_factory: Any = None) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.slave_id = slave_id
        self.cmd_gap = cmd_gap
        self._serial_factory = serial_factory or (serial.Serial if serial else None)
        self._serial: Any = None
        self._last_request_at = 0.0

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:  # noqa: BLE001
                pass
            self._serial = None

    def _open(self) -> Any:
        if self._serial is not None and getattr(self._serial, "is_open", False):
            return self._serial
        if self._serial_factory is None:
            raise BatteryError("pyserial is not installed")
        self._serial = self._serial_factory(
            self.port, baudrate=self.baudrate, bytesize=8, parity="N", stopbits=1,
            timeout=self.timeout, write_timeout=2,
        )
        return self._serial

    def read_registers(self, start: int, count: int, slave_id: int | None = None) -> list[int]:
        ser = self._open()
        slave = self.slave_id if slave_id is None else slave_id
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.cmd_gap:
            time.sleep(self.cmd_gap - elapsed)
        body = bytes((slave, 0x03, start >> 8, start & 0xFF, count >> 8, count & 0xFF))
        ser.reset_input_buffer()
        ser.write(body + crc16(body))
        ser.flush()
        self._last_request_at = time.monotonic()
        raw = bytearray()
        deadline = time.monotonic() + self.timeout
        expected = 3 + count * 2 + 2
        while time.monotonic() < deadline and len(raw) < expected:
            chunk = ser.read(expected - len(raw))
            if chunk:
                raw.extend(chunk)
        if len(raw) < expected:
            self.close()
            raise BatteryError("modbus response timeout")
        if raw[-2:] != crc16(raw[:-2]):
            raise BatteryError("modbus CRC mismatch")
        if raw[0] != slave or raw[1] != 0x03:
            raise BatteryError(f"unexpected response from slave {raw[0]}: function 0x{raw[1]:02X}")
        payload = raw[3:-2]
        return [int.from_bytes(payload[i:i + 2], "big") for i in range(0, len(payload), 2)]

    def read_module(self, addr: int) -> dict[str, Any] | None:
        regs = self.read_registers(0, 37, slave_id=addr)
        cells = [value / 1000.0 for value in regs[15:31]]
        temps = [value / 10.0 for value in regs[31:35]]
        current = _signed16(regs[0]) / 100.0
        temps_clean = [t for t in temps if t > -40]
        metrics = {
            "soc_percent": regs[2] & 0xFF,
            "soh_percent": regs[3] & 0xFF,
            "voltage_v": regs[1] / 100.0,
            "current_a": current,
            "cycles": regs[7],
            "warning_bits": regs[9],
            "protection_bits": regs[10],
            "status_bits": regs[11],
            "balance_bits": regs[12],
            "cell_voltage_min_v": min(cells),
            "cell_voltage_max_v": max(cells),
            "cell_delta_v": round(max(cells) - min(cells), 4),
            "temp_min_c": min(temps_clean) if temps_clean else None,
            "temp_max_c": max(temps_clean) if temps_clean else None,
        }
        payload = {
            "cells_v": cells,
            "temps_c": temps,
            "mos_temp_c": regs[35] / 10.0 if regs[35] > -400 else None,
            "env_temp_c": regs[36] / 10.0 if regs[36] > -400 else None,
            "remain_capacity_ah": regs[4] / 100.0,
            "full_capacity_ah": regs[5] / 100.0,
            "design_capacity_ah": regs[6] / 100.0,
        }
        return {"metrics": metrics, "payload": payload}


# --------------------------------------------------------------------- probing


def detect_client(settings: Any, serial_factory: Any = None) -> Any | None:
    """Probe the first configured module address; ASCII first, then Modbus.

    Returns a connected client or None. Addresses come exclusively from
    SB_BATTERY_ADDRESSES - the bus is never swept automatically.
    """
    if not settings.battery_addresses:
        LOGGER.warning("battery: SB_BATTERY_ADDRESSES is empty - set module DIP addresses (e.g. 2,3)")
        return None
    first = settings.battery_addresses[0]
    if settings.battery_protocol == "modbus":
        return _probe_modbus(settings, serial_factory, first)
    if settings.battery_protocol == "ascii":
        return _probe_ascii(settings, serial_factory, first)
    client = _probe_ascii(settings, serial_factory, first)
    if client:
        return client
    return _probe_modbus(settings, serial_factory, first)


def _probe_ascii(settings: Any, serial_factory: Any, addr: int) -> Any | None:
    variant = settings.battery_variant if settings.battery_variant in VARIANT_FRAMES else "auto"
    client = AsciiBatteryClient(
        settings.battery_serial_port,
        settings.battery_baudrate,
        timeout=settings.serial_timeout,
        variant=variant,
        cmd_gap=settings.battery_cmd_gap_s,
        serial_factory=serial_factory,
    )
    try:
        analog = client.read_analog(addr)
        LOGGER.info(
            "battery: paceic ASCII answer from address %s (variant %s, U=%.2f V, SOC=%.1f%%)",
            addr, client.variant_for(addr), analog["voltage_v"], analog["soc_percent"],
        )
        return client
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("battery ascii probe at address %s failed: %s", addr, exc)
    client.close()
    return None


def _probe_modbus(settings: Any, serial_factory: Any, addr: int) -> Any | None:
    client = PaceModbusBatteryClient(
        settings.battery_serial_port,
        settings.battery_baudrate,
        timeout=settings.serial_timeout,
        slave_id=addr,
        cmd_gap=settings.battery_cmd_gap_s / 2,
        serial_factory=serial_factory,
    )
    try:
        if client.read_module(addr) is not None:
            LOGGER.info("battery: PACE Modbus RTU protocol detected at address %s", addr)
            return client
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("battery modbus probe failed: %s", exc)
    client.close()
    return None


# --------------------------------------------------------------------- poller


class BatteryPoller:
    """Own thread; sweeps the configured module addresses, keeps the freshest cache."""

    def __init__(self, settings: Any, client: Any, addresses: tuple[int, ...] | list[int]) -> None:
        if not addresses:
            raise ValueError("battery address list is empty")
        self.settings = settings
        self.client = client
        self.addresses = tuple(int(addr) for addr in addresses)
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._modules: dict[int, dict[str, Any]] = {}
        self._serials: dict[int, str | None] = {}
        self._extended: dict[int, dict[str, Any]] = {}
        self._health: dict[str, Any] = {
            "ok": False, "last_ok_ts": None, "last_error": None,
            "consecutive_errors": 0, "modules_online": 0, "modules_total": len(self.addresses),
        }
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="solarbridge-battery-poller", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.client.close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def latest_modules(self) -> list[dict[str, Any]] | None:
        with self._lock:
            if not self._modules:
                return None
            modules = []
            for addr in sorted(self._modules):
                module = self._modules[addr]
                modules.append({
                    "module_index": addr,
                    "module_serial": self._serials.get(addr),
                    "metrics": dict(module["metrics"]),
                    "payload": module["payload"],
                })
            return modules

    def health(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._health)

    def _run(self) -> None:
        LOGGER.info(
            "battery poller: %s module(s) on %s at %s baud",
            len(self.addresses), self.settings.battery_serial_port, self.settings.battery_baudrate,
        )
        while not self._stop.is_set():
            started = time.monotonic()
            online = 0
            last_error: str | None = None
            for addr in self.addresses:
                module, error = self._read_module(addr)
                if module is not None:
                    with self._lock:
                        self._modules[addr] = module
                    online += 1
                elif error:
                    last_error = error
            with self._lock:
                self._health.update({
                    "ok": online > 0,
                    "last_ok_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) if online else self._health["last_ok_ts"],
                    "last_error": last_error,
                    "consecutive_errors": 0 if online == len(self.addresses) else self._health["consecutive_errors"] + 1,
                    "modules_online": online,
                })
            self._stop.wait(max(0.0, self.settings.battery_poll_interval - (time.monotonic() - started)))

    def _read_module(self, addr: int) -> tuple[dict[str, Any] | None, str | None]:
        try:
            if isinstance(self.client, PaceModbusBatteryClient):
                module = self.client.read_module(addr)
                if module is None:
                    return None, "no modbus response"
                metrics, payload = dict(module["metrics"]), dict(module["payload"])
                payload["protocol"] = "pace-modbus-rtu"
            else:
                analog = self.client.read_analog(addr)
                status = self.client.read_status(addr)
                cells_mv = analog.get("cells_mv") or []
                temps_c = [t for t in (analog.get("temps_c") or [])]
                soh = analog.get("soh_percent")
                metrics = {
                    "soc_percent": analog.get("soc_percent"),
                    "soh_percent": soh if soh else None,
                    "voltage_v": analog.get("voltage_v"),
                    "current_a": analog.get("current_a"),
                    "cycles": analog.get("cycles"),
                    "protection_bits": status.get("protection_bits"),
                    "alarm_bits": status.get("alarm_bits"),
                    "cell_voltage_min_v": round(min(cells_mv) / 1000.0, 4) if cells_mv else None,
                    "cell_voltage_max_v": round(max(cells_mv) / 1000.0, 4) if cells_mv else None,
                    "cell_delta_v": round((max(cells_mv) - min(cells_mv)) / 1000.0, 4) if cells_mv else None,
                    "temp_min_c": min(temps_c) if temps_c else None,
                    "temp_max_c": max(temps_c) if temps_c else None,
                }
                variant = self.client.variant_for(addr)
                payload = {
                    "protocol": ASCII_PROTOCOL_NAMES.get(variant, f"ascii/{variant}"),
                    "analog": analog, "status": status,
                }
            if addr not in self._serials:
                self._fetch_metadata(addr)
            extended = self._extended.get(addr)
            if extended:
                payload["extended"] = extended
            return {"metrics": metrics, "payload": payload}, None
        except Exception as exc:  # noqa: BLE001 - a dead module must not stop the sweep
            LOGGER.debug("battery module %s read failed: %s", addr, exc)
            return None, str(exc)[:200]

    def _fetch_metadata(self, addr: int) -> None:
        """Serial number and one-shot extended reads (first successful cycle).

        module_serial prefers the 0x93 SN number (Pylon V3.3 ch. 3.7) and
        falls back to the paceic 0xC2 product info text."""
        serial: str | None = None
        extended: dict[str, Any] = {}
        if not isinstance(self.client, PaceModbusBatteryClient):
            try:
                product = self.client.read_product_info(addr)
                if product:
                    serial = str(product.get("raw", ""))[:64] or None
            except Exception:  # noqa: BLE001 - optional metadata must not fail polling
                pass
            read_extended = getattr(self.client, "read_extended", None)
            if callable(read_extended):
                try:
                    extended = dict(read_extended(addr) or {})
                except Exception:  # noqa: BLE001
                    extended = {}
            sn = (extended.get("module_sn") or {}).get("sn")
            if sn:
                serial = str(sn)[:64]
        self._serials[addr] = serial
        self._extended[addr] = extended


def _signed16(value: int) -> int:
    return value - 0x10000 if value >= 0x8000 else value
