import os
import time
import unittest
from pathlib import Path
from unittest import mock

from solarbridge.battery import (
    AsciiBatteryClient,
    BatteryError,
    BatteryPoller,
    ForeignFrameError,
    PaceModbusBatteryClient,
    build_ascii_request,
    calc_lchksum,
    frame_checksum,
    parse_analog_pylon,
    parse_analog_v20,
    parse_analog_v25,
    parse_ascii_response,
    parse_charge_limits_pylon,
    parse_status_pylon,
    parse_status_v25,
    parse_system_params_pylon,
    _extract_module_sn,
)
from solarbridge.config import _addresses_env
from tests.helpers import make_settings


# Real frames captured from live MNB hardware (debug/log_mnb_pace_poll.log,
# battery #2 at DIP address 2, protocol v25).
REAL_ANALOG_FRAME = (
    "~2502460080AE0002100CEC0CEC0CEC0CEC0CEC0CEC0CEC0CEC0CEC0CEC0CEC0CEC0CEC0"
    "CEC0CEC0CEA060B470B3F0B3D0B4A0B610B8100A9CEBE1AA8032DD0001B27103A0003B9"
    "D90003663864CED500000CEC0CEA01100B4A0B3D0403D5FD"
)
REAL_STATUS_FRAME = (
    "~25024600B0500002100000000000000000000000000000000006000000000000000000"
    "0000260000000000000000EE85"
)


def ascii_frame(ver: str, adr: int, cid1: str, rtn: str, info_hex: str) -> bytes:
    """Build a synthetic response frame with a valid checksum."""
    body = f"{ver}{adr:02X}{cid1}{rtn}{calc_lchksum(len(info_hex))}{info_hex}"
    checksum = frame_checksum(body.encode("ascii"))
    return f"~{body}{checksum:04X}\r".encode("ascii")


def readdress(frame: str, adr: int) -> bytes:
    """Rebuild a captured frame (no CR) as if it came from another module."""
    body = frame[1:-4]
    rebuilt = body[:2] + f"{adr:02X}" + body[4:]
    checksum = frame_checksum(rebuilt.encode("ascii"))
    return f"~{rebuilt}{checksum:04X}\r".encode("ascii")


def with_rtn(frame: str, rtn: str) -> bytes:
    """Rebuild a captured frame (no CR) with a different RTN code (checksum fixed)."""
    body = frame[1:-4]
    rebuilt = body[:6] + rtn + body[8:]
    checksum = frame_checksum(rebuilt.encode("ascii"))
    return f"~{rebuilt}{checksum:04X}\r".encode("ascii")


class FramingTests(unittest.TestCase):
    def test_calc_lchksum_vectors(self):
        self.assertEqual(calc_lchksum(0), "0000")
        self.assertEqual(calc_lchksum(2), "E002")
        self.assertEqual(calc_lchksum(80), "B050")

    def test_checksum_matches_reference_sum(self):
        body = b"25014642E00201"
        self.assertEqual(frame_checksum(body), ((~sum(body)) % 0x10000 + 1) & 0xFFFF)

    def test_control_frames_v25(self):
        # Reference vectors (debug/mnb_pace_poll.py selftest + live TX log).
        self.assertEqual(
            build_ascii_request(1, 0x42, bytes([1]), "v25"),
            b"~25014642E00201FD30\r",
        )
        self.assertEqual(
            build_ascii_request(2, 0x42, bytes([2]), "v25"),
            b"~25024642E00202FD2E\r",
        )
        self.assertEqual(
            build_ascii_request(2, 0x44, bytes([2]), "v25"),
            b"~25024644E00202FD2C\r",
        )

    def test_control_frames_v20(self):
        self.assertEqual(build_ascii_request(1, 0x42, b"", "v20"), b"~20014A420000FDA2\r")
        self.assertEqual(build_ascii_request(1, 0x44, b"", "v20"), b"~20014A440000FDA0\r")

    def test_control_frames_pylon(self):
        # Pylon V3.3 ch. 4 example, byte for byte (ADR=02, INFO = command = 02).
        self.assertEqual(
            build_ascii_request(2, 0x42, bytes([2]), "pylon"),
            b"~20024642E00202FD33\r",
        )
        # 0x47 carries no INFO (LENID = 0).
        self.assertEqual(
            build_ascii_request(2, 0x47, b"", "pylon"),
            b"~200246470000" + f"{frame_checksum(b'200246470000'):04X}".encode("ascii") + b"\r",
        )

    def test_request_bytes_are_ascii(self):
        for variant in ("v25", "v20", "pylon"):
            request = build_ascii_request(1, 0x42, b"\x01", variant)
            self.assertTrue(all(32 <= byte < 127 for byte in request[:-1]))
            self.assertEqual(request[-1:], b"\r")

    def test_unknown_variant_rejected(self):
        with self.assertRaises(BatteryError):
            build_ascii_request(1, 0x42, b"", "bogus")


class ResponseValidationTests(unittest.TestCase):
    def test_parse_real_analog_frame(self):
        raw = (REAL_ANALOG_FRAME + "\r").encode("ascii")
        parsed = parse_ascii_response(raw, expect_addr=2, expect_version=0x25, expect_cid1=0x46)
        self.assertEqual(parsed["version"], 0x25)
        self.assertEqual(parsed["addr"], 2)
        self.assertEqual(parsed["cid1"], 0x46)
        self.assertEqual(parsed["rtn"], "00")
        self.assertEqual(len(parsed["info"]), 87)

    def test_parse_real_status_frame(self):
        raw = (REAL_STATUS_FRAME + "\r").encode("ascii")
        parsed = parse_ascii_response(raw, expect_addr=2, expect_version=0x25, expect_cid1=0x46)
        self.assertEqual(len(parsed["info"]), 40)

    def test_rejects_tampered_checksum(self):
        raw = bytearray(REAL_ANALOG_FRAME + "\r", "ascii")
        raw[-2] = ord("0") if raw[-2] != ord("0") else ord("1")
        with self.assertRaises(BatteryError):
            parse_ascii_response(bytes(raw))

    def test_rejects_wrong_address(self):
        raw = (REAL_ANALOG_FRAME + "\r").encode("ascii")
        with self.assertRaises(ForeignFrameError):
            parse_ascii_response(raw, expect_addr=3)

    def test_rejects_wrong_version(self):
        # Live MNB hardware answers VER=25 even to v20 requests: a strict check
        # must reject that instead of misdetecting the variant.
        raw = (REAL_ANALOG_FRAME + "\r").encode("ascii")
        with self.assertRaises(BatteryError):
            parse_ascii_response(raw, expect_version=0x20)

    def test_rejects_rtn_error(self):
        with self.assertRaises(BatteryError) as ctx:
            parse_ascii_response(with_rtn(REAL_ANALOG_FRAME, "04"))
        self.assertIn("RTN=04", str(ctx.exception))

    def test_rejects_bad_length(self):
        body = "250146000001"  # length field 0001 without payload
        checksum = frame_checksum(body.encode("ascii"))
        raw = f"~{body}{checksum:04X}\r".encode("ascii")
        with self.assertRaises(BatteryError) as ctx:
            parse_ascii_response(raw)
        self.assertIn("length", str(ctx.exception))


class AnalogParserTests(unittest.TestCase):
    def test_real_frame_battery_2(self):
        payload = parse_ascii_response((REAL_ANALOG_FRAME + "\r").encode("ascii"))["info"]
        data = parse_analog_v25(payload)
        self.assertAlmostEqual(data["voltage_v"], 52.926)
        self.assertAlmostEqual(data["current_a"], 1.69)
        self.assertAlmostEqual(data["power_w"], 89.4)
        self.assertAlmostEqual(data["soc_percent"], 58.2)
        self.assertAlmostEqual(data["remain_ah"], 68.24)
        self.assertAlmostEqual(data["full_ah"], 117.28)
        self.assertAlmostEqual(data["design_ah"], 100.0)
        self.assertAlmostEqual(data["soh_percent"], 117.3)
        self.assertEqual(data["cycles"], 27)
        self.assertEqual(len(data["cells_mv"]), 16)
        self.assertEqual(data["min_mv"], 3306)
        self.assertEqual(data["max_mv"], 3308)
        self.assertEqual(data["delta_mv"], 2)
        self.assertEqual(data["temps_c"], [15.7, 14.9, 14.7, 16.0, 18.3, 21.5])
        self.assertEqual(data["define_p"], 3)

    def test_reference_frame_from_documentation(self):
        # Vector from esphome-pace-bms (also the debug script selftest):
        # 16 cells ~3271 mV, 6 sensors ~24 C, current -2.25 A, 140 cycles.
        info_hex = (
            "00" "01" "10"
            "0CC70CC80CC70CC70CC70CC50CC60CC70CC70CC60CC70CC60CC60CC70CC60CC7"
            "06"
            "0B9B0B990B990B990BB30BBC"
            "FF1F" "CCCD" "12D3" "03" "286A" "008C" "2710"
        )
        frame = ascii_frame("25", 1, "46", "00", info_hex)
        payload = parse_ascii_response(frame, expect_addr=1, expect_version=0x25)["info"]
        data = parse_analog_v25(payload)
        self.assertAlmostEqual(data["voltage_v"], 52.429)
        self.assertAlmostEqual(data["current_a"], -2.25)
        self.assertAlmostEqual(data["remain_ah"], 48.19)
        self.assertAlmostEqual(data["full_ah"], 103.46)
        self.assertAlmostEqual(data["design_ah"], 100.0)
        self.assertEqual(data["cycles"], 140)
        self.assertEqual(len(data["cells_mv"]), 16)
        self.assertAlmostEqual(data["temps_c"][0], 24.1)

    def test_short_payload_reports_error(self):
        data = parse_analog_v25(b"\x00\x01")
        self.assertIn("error", data)

    def test_v20_layout(self):
        # v20: U in 0.01 V units (5242 -> 52.42 V), constant 2, no design capacity field.
        info_hex = (
            "00" "01" "10"
            "0CC70CC80CC70CC70CC70CC50CC60CC70CC70CC60CC70CC60CC60CC70CC60CC7"
            "06"
            "0B9B0B990B990B990BB30BBC"
            "FF1F" "147A" "12D3" "02" "286A" "008C"
        )
        data = parse_analog_v20(bytes.fromhex(info_hex))
        self.assertAlmostEqual(data["voltage_v"], 52.42)
        self.assertAlmostEqual(data["current_a"], -2.25)
        self.assertAlmostEqual(data["remain_ah"], 48.19)
        self.assertAlmostEqual(data["soc_percent"], round(48.19 / 103.46 * 100.0, 1))
        self.assertEqual(data["design_ah"], 0.0)
        self.assertEqual(data["cycles"], 140)


class StatusParserTests(unittest.TestCase):
    def test_real_frame_battery_2(self):
        payload = parse_ascii_response((REAL_STATUS_FRAME + "\r").encode("ascii"))["info"]
        status = parse_status_v25(payload)
        # Live module: no protection, no faults, no warnings, no balancing.
        self.assertEqual(status["protection"], [])
        self.assertEqual(status["fault"], [])
        self.assertEqual(status["warnings"], [])
        self.assertEqual(status["balancing_cells"], [])
        self.assertEqual(status["protection_bits"], 0)
        self.assertEqual(status["alarm_bits"], 0)
        self.assertEqual(status["balance_mask"], 0)
        # sys=0x26: charge MOSFET on, discharge MOSFET on, AC present.
        self.assertEqual(
            status["system"],
            ["charge MOSFET on", "discharge MOSFET on", "AC present"],
        )
        self.assertEqual(status["raw"], "prot1=00 prot2=00 sys=26 ctl=00 flt=00 bal=0000 w1=00 w2=00")

    def test_synthetic_protection_and_balance(self):
        # Selftest vector: cell overvoltage protection + balancing cells 8 and 10.
        info_hex = (
            "00" "01" "10" + "00" * 16 + "06" + "00" * 6 + "00" "00" "00"
            "01" "00" "00" "00" "00" "80" "02" "00" "00"
        )
        frame = ascii_frame("25", 1, "46", "00", info_hex)
        payload = parse_ascii_response(frame, expect_addr=1)["info"]
        status = parse_status_v25(payload)
        self.assertEqual(status["balancing_cells"], [8, 10])
        self.assertEqual(status["protection"], ["cell overvoltage protection"])
        self.assertEqual(status["protection_bits"], 1)

    def test_short_payload_reports_error(self):
        status = parse_status_v25(b"\x00\x01")
        self.assertTrue(status["errors"])


# Pylon V3.3 ch. 4 worked example (74 Ah pack). The document prints CHKSUM
# E1A2, but the recomputed checksum for the listed payload is E27A - the
# vector below keeps the document's payload byte for byte with a valid
# checksum so the frame passes our own validation.
DOC_ANALOG_FRAME = (
    "~20024600F07A11020F0D450D440D450D440D450D440D3E0D450D4A0D4A0D4B0D4A0D4A0D4A0D4A"
    "050BC30BC30BC30BCD0BCD0000C725FFFF04FFFF000200CA58012110E27A\r"
)


class PylonAnalogTests(unittest.TestCase):
    def test_doc_example(self):
        parsed = parse_ascii_response(DOC_ANALOG_FRAME.encode("ascii"), expect_version=0x20, expect_cid1=0x46)
        data = parse_analog_pylon(parsed["info"])
        self.assertEqual(len(parsed["info"]), 61)
        # Doc analysis table: 15 cells, U = 50981 mV, I = 0, cycles = 2.
        self.assertEqual(len(data["cells_mv"]), 15)
        self.assertEqual(data["min_mv"], 3390)
        self.assertEqual(data["max_mv"], 3403)
        self.assertEqual(data["delta_mv"], 13)
        self.assertAlmostEqual(data["voltage_v"], 50.981)
        self.assertAlmostEqual(data["current_a"], 0.0)
        # Temps 0BC3/0BCD -> 28.0 / 29.0 C with the -2731 offset (doc ch. 3.3).
        self.assertEqual(data["temps_c"], [28.0, 28.0, 28.0, 29.0, 29.0])
        # remain1/total1 = FFFF -> remain2/total2 used: 00CA58/012110 (3 bytes).
        self.assertAlmostEqual(data["remain_ah"], 51.8)
        self.assertAlmostEqual(data["full_ah"], 74.0)
        self.assertAlmostEqual(data["remain2_ah"], 51.8)
        self.assertAlmostEqual(data["total2_ah"], 74.0)
        self.assertAlmostEqual(data["soc_percent"], 70.0)
        self.assertEqual(data["cycles"], 2)
        self.assertEqual(data["userdef_items"], 4)
        self.assertNotIn("tail_hex", data)
        self.assertEqual(data["design_ah"], 0.0)

    def test_userdef_2_uses_remain1(self):
        # US2000B-style reply: no remain2/total2, capacities in remain1/total1.
        info_hex = (
            "11" "02" "0F" + "0D400D410D420D430D440D450D460D470D480D490D4A0D4B0D4C0D4D0D4E"
            "02" "0BC30BD1"
            "FF1F" "C725" "1388" "02" "2710" "0064"
        )
        payload = bytes.fromhex(info_hex)
        data = parse_analog_pylon(payload)
        self.assertAlmostEqual(data["voltage_v"], 50.981)
        self.assertAlmostEqual(data["current_a"], -2.25)
        self.assertAlmostEqual(data["remain_ah"], 5.0)
        self.assertAlmostEqual(data["full_ah"], 10.0)
        self.assertAlmostEqual(data["soc_percent"], 50.0)
        # 0BC3=3011 -> 28.0 C, 0BD1=3025 -> 29.4 C (offset -2731).
        self.assertEqual(data["temps_c"], [28.0, 29.4])
        self.assertEqual(data["cycles"], 100)
        self.assertNotIn("remain2_ah", data)
        self.assertNotIn("tail_hex", data)

    def test_unknown_tail_kept_raw(self):
        info_hex = "11020F" + "0D400D410D420D430D440D450D460D470D480D490D4A0D4B0D4C0D4D0D4E" "02" "0BC30BD1" "0000" "C725" "1388" "02" "2710" "0064" + "AABB"
        data = parse_analog_pylon(bytes.fromhex(info_hex))
        self.assertEqual(data["tail_hex"], "AA BB")

    def test_short_payload_reports_error(self):
        data = parse_analog_pylon(b"\x11\x02\x0f")
        self.assertIn("error", data)


class PylonStatusTests(unittest.TestCase):
    def _payload(self, s1, s2, s3, s4=0, s5=0):
        info_hex = (
            "11" "02" "10" + "00" * 16 + "04" + "00" * 4
            + "00" "00" "00" + f"{s1:02X}{s2:02X}{s3:02X}{s4:02X}{s5:02X}"
        )
        frame = ascii_frame("20", 2, "46", "00", info_hex)
        return parse_ascii_response(frame, expect_version=0x20, expect_cid1=0x46)["info"]

    def test_normal_running(self):
        # s2 = 0x06: charge + discharge MOSFET on; s3 = 0x08: fully charged.
        status = parse_status_pylon(self._payload(0x00, 0x06, 0x08))
        self.assertEqual(status["system"], ["charge MOSFET on", "discharge MOSFET on"])
        self.assertEqual(status["state"], ["fully charged"])
        self.assertEqual(status["protection"], [])
        self.assertEqual(status["cell_faults"], [])
        self.assertEqual(status["cell_warn"], [])
        self.assertEqual(status["protection_bits"], 0)
        self.assertEqual(status["alarm_bits"], 8)
        self.assertEqual(status["raw"], "s1=00 s2=06 s3=08 s4=00 s5=00")

    def test_protection_and_cell_faults(self):
        # s1 = 0x41: pack overvoltage + charge overtemperature; s4/s5: cells 2 and 16.
        status = parse_status_pylon(self._payload(0x41, 0x00, 0x00, s4=0x02, s5=0x80))
        self.assertEqual(status["protection"], ["pack overvoltage", "charge overtemperature"])
        self.assertEqual(status["cell_faults"], [2, 16])
        self.assertEqual(status["protection_bits"], 0x41)
        self.assertEqual(status["cell_fault_mask"], 0x8002)

    def test_alarm_level_codes(self):
        status = parse_status_pylon(self._payload(0x00, 0x00, 0x00))
        self.assertEqual(status["charge_current_warn"], None)
        self.assertEqual(status["voltage_warn"], None)
        self.assertEqual(status["discharge_current_warn"], None)

    def test_short_payload_reports_error(self):
        status = parse_status_pylon(b"\x11\x02\x10")
        self.assertTrue(status["errors"])


class PylonExtendedParserTests(unittest.TestCase):
    def test_module_sn(self):
        # The SN is exactly 16 ASCII bytes: the parser keeps the last 16.
        sn = _extract_module_sn(b"\x11\x02" + b"SN1234567890ABCD")
        self.assertEqual(sn["sn"], "SN1234567890ABCD")
        self.assertEqual(sn["raw"], "SN1234567890ABCD")

    def test_module_sn_without_flag(self):
        # Some firmwares omit the flag/cmd prefix: exactly 16 bytes.
        sn = _extract_module_sn(b"0123456789ABCDEF")
        self.assertEqual(sn["sn"], "0123456789ABCDEF")

    def test_module_sn_garbage(self):
        sn = _extract_module_sn(b"\x11\x02" + b"\x01\x02\x03\x04" * 4)
        self.assertIsNone(sn["sn"])
        self.assertEqual(len(sn["raw"]), 16)

    def test_module_sn_too_short(self):
        self.assertIsNone(_extract_module_sn(b"short"))

    def test_charge_limits(self):
        # charge U 54000 mV, discharge U 44000 mV (0xABE0), I 100.0/100.0 A (0.1 A), flags C0.
        payload = b"\x11\x02" + bytes.fromhex("D2F0ABE003E803E8C0")
        limits = parse_charge_limits_pylon(payload)
        self.assertAlmostEqual(limits["charge_voltage_limit_v"], 54.0)
        self.assertAlmostEqual(limits["discharge_voltage_limit_v"], 44.0)
        self.assertAlmostEqual(limits["charge_current_limit_a"], 100.0)
        self.assertAlmostEqual(limits["discharge_current_limit_a"], 100.0)
        self.assertTrue(limits["charge_enable"])
        self.assertTrue(limits["discharge_enable"])
        self.assertFalse(limits["charge_immediately"])
        self.assertFalse(limits["full_charge_request"])

    def test_charge_limits_implausible(self):
        limits = parse_charge_limits_pylon(b"\x11\x02" + b"\x00" * 9)
        self.assertNotIn("charge_voltage_limit_v", limits)
        self.assertIn("raw_payload_hex", limits)

    def test_charge_limits_too_short(self):
        self.assertIsNone(parse_charge_limits_pylon(b"\x11\x02\x00\x00"))

    def test_system_params(self):
        values = [
            3650, 3200, 2800,           # cell U high / low alarm / low protect (mV)
            3181, 2731, 10000,          # charge T high 45C, low 0C, I limit 100.0 A
            58400, 48000, 44000,        # module U high / low alarm / low protect (mV)
            2531, 2431, 10000,          # discharge T high -20C, low -30C, I limit
        ]
        payload = b"\x11" + b"".join(v.to_bytes(2, "big") for v in values)
        params = parse_system_params_pylon(payload)
        self.assertAlmostEqual(params["cell_voltage_high_limit_v"], 3.65)
        self.assertAlmostEqual(params["cell_voltage_low_alarm_v"], 3.2)
        self.assertAlmostEqual(params["cell_voltage_low_protect_v"], 2.8)
        self.assertAlmostEqual(params["charge_high_temp_limit_c"], 45.0)
        self.assertAlmostEqual(params["charge_low_temp_limit_c"], 0.0)
        self.assertAlmostEqual(params["charge_current_limit_a"], 100.0)
        self.assertAlmostEqual(params["module_voltage_high_limit_v"], 58.4)
        self.assertAlmostEqual(params["module_voltage_low_alarm_v"], 48.0)
        self.assertAlmostEqual(params["module_voltage_low_protect_v"], 44.0)
        self.assertAlmostEqual(params["discharge_high_temp_limit_c"], -20.0)
        self.assertAlmostEqual(params["discharge_low_temp_limit_c"], -30.0)
        self.assertAlmostEqual(params["discharge_current_limit_a"], 100.0)

    def test_system_params_implausible(self):
        params = parse_system_params_pylon(b"\x11" + b"\x00" * 24)
        self.assertNotIn("cell_voltage_high_limit_v", params)
        self.assertIn("raw_payload_hex", params)


class ScriptedSerial:
    """Minimal serial that answers every request with queued response frames."""

    def __init__(self, responses):
        self.is_open = True
        self._responses = list(responses)
        self.written = []

    def write(self, data: bytes) -> int:
        self.written.append(bytes(data))
        return len(data)

    def read(self, size: int = 1) -> bytes:
        if not self._responses:
            return b""
        chunk, self._responses[0] = self._responses[0][:size], self._responses[0][size:]
        if not self._responses[0]:
            self._responses.pop(0)
        return chunk

    def reset_input_buffer(self) -> None:
        pass

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.is_open = False


class MatchingSerial:
    """Serial that answers only when the written request matches a prefix.

    Used to prove the auto-probe order: a device that ignores v25/v20 shapes
    and answers only the pylon frame, and to script per-CID extended replies.
    """

    def __init__(self, rules):
        # rules: list of (prefix bytes, response bytes) checked in order.
        self.is_open = True
        self._rules = list(rules)
        self.written = []
        self._pending = b""

    def write(self, data: bytes) -> int:
        data = bytes(data)
        self.written.append(data)
        self._pending = b""
        for prefix, response in self._rules:
            if data.startswith(prefix):
                self._pending = response
                break
        return len(data)

    def read(self, size: int = 1) -> bytes:
        if not self._pending:
            return b""
        chunk, self._pending = self._pending[:size], self._pending[size:]
        return chunk

    def reset_input_buffer(self) -> None:
        self._pending = b""

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.is_open = False


class AsciiClientTests(unittest.TestCase):
    def setUp(self):
        self.holder = {}

    def _client(self, responses, variant="auto"):
        def factory(*args, **kwargs):
            self.holder["serial"] = ScriptedSerial(responses)
            return self.holder["serial"]

        return AsciiBatteryClient(
            "fake", timeout=0.2, variant=variant, cmd_gap=0.0, serial_factory=factory
        )

    def _matching_client(self, rules, variant="auto"):
        """Serial that answers only requests starting with a rule prefix.

        One fake port object is reused across (re)opens, so the writes of the
        failed auto-probe candidates stay visible in holder["serial"].written.
        """
        def factory(*args, **kwargs):
            serial = self.holder.get("serial")
            if serial is None:
                serial = self.holder["serial"] = MatchingSerial(rules)
            else:
                serial.is_open = True  # reopened after a failed probe
            return serial

        return AsciiBatteryClient(
            "fake", timeout=0.2, variant=variant, cmd_gap=0.0, serial_factory=factory
        )

    def test_probe_locks_v25_and_sends_reference_frame(self):
        client = self._client([(REAL_ANALOG_FRAME + "\r").encode("ascii")])
        analog = client.read_analog(2)
        self.assertAlmostEqual(analog["voltage_v"], 52.926)
        self.assertEqual(client.variant_for(2), "v25")
        # The wire request must match the live log byte for byte.
        self.assertEqual(
            self.holder["serial"].written,
            [b"~25024642E00202FD2E\r"],
        )

    def test_status_uses_locked_variant(self):
        client = self._client([(REAL_STATUS_FRAME + "\r").encode("ascii")], variant="v25")
        status = client.read_status(2)
        self.assertEqual(status["protection_bits"], 0)
        self.assertEqual(client.variant_for(2), "v25")
        self.assertEqual(
            self.holder["serial"].written,
            [b"~25024644E00202FD2C\r"],
        )

    def test_foreign_frame_is_skipped(self):
        # Another module (address 3) answers first: skip it, then read #2.
        client = self._client([
            readdress(REAL_ANALOG_FRAME, 3),
            (REAL_ANALOG_FRAME + "\r").encode("ascii"),
        ], variant="v25")
        analog = client.read_analog(2)
        self.assertAlmostEqual(analog["voltage_v"], 52.926)
        # One request per attempt: the foreign frame costs exactly one retry.
        self.assertEqual(len(self.holder["serial"].written), 2)

    def test_no_answer_raises(self):
        client = self._client([], variant="v25")
        with self.assertRaises(BatteryError):
            client.read_analog(2)

    def test_variant_probe_failure_raises(self):
        client = self._client([])  # auto: both probes time out
        with self.assertRaises(BatteryError):
            client.read_analog(2)

    def test_rtn_error_is_raised(self):
        client = self._client([with_rtn(REAL_ANALOG_FRAME, "04")], variant="v25")
        with self.assertRaises(BatteryError) as ctx:
            client.read_analog(2)
        self.assertIn("RTN=04", str(ctx.exception))

    def test_rtn_address_error_is_reported(self):
        # RTN=90 from the Pylon V3.3 table (ADR error).
        client = self._client([with_rtn(REAL_ANALOG_FRAME, "90")], variant="v25")
        with self.assertRaises(BatteryError) as ctx:
            client.read_analog(2)
        self.assertIn("address error", str(ctx.exception))

    def test_probe_locks_pylon_variant(self):
        # A true Pylontech ignores the v25 and v20 (CID1=4A) shapes and answers
        # only the pylon frame: auto-probe must walk v25 -> v20 -> pylon.
        client = self._matching_client([(b"~20024642", DOC_ANALOG_FRAME.encode("ascii"))])
        analog = client.read_analog(2)
        self.assertEqual(client.variant_for(2), "pylon")
        self.assertAlmostEqual(analog["voltage_v"], 50.981)
        # Three requests: one per probe candidate.
        self.assertEqual(len(self.holder["serial"].written), 3)
        self.assertEqual(self.holder["serial"].written[-1], b"~20024642E00202FD33\r")

    def test_pylon_fixed_variant_sends_doc_frame(self):
        client = self._client([DOC_ANALOG_FRAME.encode("ascii")], variant="pylon")
        analog = client.read_analog(2)
        self.assertEqual(client.variant_for(2), "pylon")
        self.assertAlmostEqual(analog["soc_percent"], 70.0)
        self.assertEqual(
            self.holder["serial"].written,
            [b"~20024642E00202FD33\r"],
        )

    def test_pylon_status_parsed(self):
        info_hex = "11" "02" "10" + "00" * 16 + "04" + "00" * 4 + "00" "00" "00" + "00" "06" "08" "00" "00"
        frame = ascii_frame("20", 2, "46", "00", info_hex)
        client = self._client([frame], variant="pylon")
        status = client.read_status(2)
        self.assertEqual(status["system"], ["charge MOSFET on", "discharge MOSFET on"])
        self.assertEqual(status["state"], ["fully charged"])

    def test_read_extended_collects_sn_limits_params(self):
        # MNB-style behaviour: locked as v25 (answers VER=25) but the extended
        # CIDs are requested in the pylon shape and answered with VER=25.
        sn_frame = ascii_frame("25", 2, "46", "00", "1102" + "SN1234567890ABCD".encode().hex().upper())
        limits_frame = ascii_frame("25", 2, "46", "00", "1102" + "D2F0ABE003E803E8C0")
        params_frame = ascii_frame(
            "25", 2, "46", "00",
            "11" + "".join(f"{v:04X}" for v in (3650, 3200, 2800, 3181, 2731, 10000,
                                                58400, 48000, 44000, 2531, 2431, 10000)),
        )
        client = self._matching_client([
            (b"~25024642", (REAL_ANALOG_FRAME + "\r").encode("ascii")),
            (b"~20024693", sn_frame),
            (b"~20024692", limits_frame),
            (b"~20024647", params_frame),
        ])
        self.assertIsNotNone(client.read_analog(2))  # locks the variant
        extended = client.read_extended(2)
        self.assertEqual(extended["module_sn"]["sn"], "SN1234567890ABCD")
        self.assertAlmostEqual(extended["charge_limits"]["charge_voltage_limit_v"], 54.0)
        self.assertTrue(extended["charge_limits"]["charge_enable"])
        self.assertAlmostEqual(extended["system_params"]["cell_voltage_high_limit_v"], 3.65)
        # Wire requests are pylon-shaped: VER=20, CID1=46, INFO = address.
        wire = b"".join(self.holder["serial"].written)
        self.assertIn(b"~20024693E00202", wire)
        self.assertIn(b"~20024692E00202", wire)
        self.assertIn(b"~200246470000", wire)

    def test_read_extended_tolerates_failures(self):
        # Only the analog CID is supported on this fake bus.
        client = self._matching_client([(b"~25024642", (REAL_ANALOG_FRAME + "\r").encode("ascii"))])
        self.assertIsNotNone(client.read_analog(2))
        self.assertEqual(client.read_extended(2), {})

    def test_read_extended_without_probe_is_silent(self):
        client = self._matching_client([])
        self.assertEqual(client.read_extended(2), {})
        # The port is never even opened: the bus stays untouched.
        self.assertNotIn("serial", self.holder)


class FakeBatteryClient:
    """Offline stand-in with the real parsed values for the poller tests."""

    variant_name = "v25"

    def __init__(self, analog, status, product=None, extended=None):
        self._analog = analog
        self._status = status
        self._product = product
        self._extended = extended or {}

    def read_analog(self, addr):
        return self._analog

    def read_status(self, addr):
        return self._status

    def read_product_info(self, addr):
        return self._product

    def read_extended(self, addr):
        return dict(self._extended)

    def variant_for(self, addr):
        return self.variant_name

    def close(self):
        pass


class BatteryPollerTests(unittest.TestCase):
    def setUp(self):
        analog_payload = parse_ascii_response((REAL_ANALOG_FRAME + "\r").encode("ascii"))["info"]
        status_payload = parse_ascii_response((REAL_STATUS_FRAME + "\r").encode("ascii"))["info"]
        self.analog = parse_analog_v25(analog_payload)
        self.status = parse_status_v25(status_payload)
        self.settings = make_settings(Path("."), battery_poll_interval=5.0)

    def test_read_module_maps_metrics(self):
        client = FakeBatteryClient(self.analog, self.status, product={"raw": "LPR-51.2-100"})
        poller = BatteryPoller(self.settings, client, (2, 3))
        module, error = poller._read_module(2)
        self.assertIsNone(error)
        metrics = module["metrics"]
        self.assertAlmostEqual(metrics["voltage_v"], 52.926)
        self.assertAlmostEqual(metrics["current_a"], 1.69)
        self.assertAlmostEqual(metrics["soc_percent"], 58.2)
        self.assertAlmostEqual(metrics["soh_percent"], 117.3)
        self.assertEqual(metrics["cycles"], 27)
        self.assertAlmostEqual(metrics["cell_voltage_min_v"], 3.306)
        self.assertAlmostEqual(metrics["cell_voltage_max_v"], 3.308)
        self.assertAlmostEqual(metrics["cell_delta_v"], 0.002)
        self.assertAlmostEqual(metrics["temp_min_c"], 14.7)
        self.assertAlmostEqual(metrics["temp_max_c"], 21.5)
        self.assertEqual(metrics["protection_bits"], 0)
        self.assertEqual(metrics["alarm_bits"], 0)
        self.assertEqual(module["payload"]["protocol"], "paceic-ascii/v25")
        self.assertEqual(
            module["payload"]["status"]["system"],
            ["charge MOSFET on", "discharge MOSFET on", "AC present"],
        )

    def test_extended_metadata_reaches_frame(self):
        # 0x93 SN wins over the 0xC2 product info text; extended data is
        # stored once and merged into every frame payload.
        client = FakeBatteryClient(
            self.analog, self.status,
            product={"raw": "LPR-51.2-100"},
            extended={"module_sn": {"raw": "SN1234567890ABCDEF", "sn": "SN1234567890ABCDEF"}},
        )
        poller = BatteryPoller(self.settings, client, (2,))
        module, error = poller._read_module(2)
        self.assertIsNone(error)
        self.assertEqual(poller._serials[2], "SN1234567890ABCDEF")
        self.assertEqual(
            module["payload"]["extended"]["module_sn"]["sn"], "SN1234567890ABCDEF"
        )
        # The same extended block is reused on the next cycle (no extra reads).
        module2, _ = poller._read_module(2)
        self.assertEqual(module2["payload"]["extended"], module["payload"]["extended"])

    def test_extended_absent_keeps_payload_clean(self):
        client = FakeBatteryClient(self.analog, self.status, product={"raw": "LPR-51.2-100"})
        poller = BatteryPoller(self.settings, client, (2,))
        module, error = poller._read_module(2)
        self.assertIsNone(error)
        self.assertNotIn("extended", module["payload"])
        self.assertEqual(poller._serials[2], "LPR-51.2-100")

    def test_failed_module_reports_error(self):
        class BrokenClient(FakeBatteryClient):
            def read_status(self, addr):
                raise BatteryError("no response for cid 0x44 from address 2")

        poller = BatteryPoller(self.settings, BrokenClient(self.analog, self.status), (2,))
        module, error = poller._read_module(2)
        self.assertIsNone(module)
        self.assertIn("0x44", error)

    def test_latest_modules_and_health(self):
        client = FakeBatteryClient(self.analog, self.status)
        poller = BatteryPoller(self.settings, client, (2, 3))
        self.assertIsNone(poller.latest_modules())
        poller.start()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and poller.latest_modules() is None:
            time.sleep(0.02)
        modules = poller.latest_modules()
        poller.stop()
        self.assertIsNotNone(modules)
        self.assertEqual([module["module_index"] for module in modules], [2, 3])
        self.assertAlmostEqual(modules[0]["metrics"]["voltage_v"], 52.926)
        health = poller.health()
        self.assertTrue(health["ok"])
        self.assertEqual(health["modules_online"], 2)
        self.assertEqual(health["modules_total"], 2)
        self.assertEqual(health["consecutive_errors"], 0)
        self.assertIsNotNone(health["last_ok_ts"])

    def test_empty_addresses_rejected(self):
        with self.assertRaises(ValueError):
            BatteryPoller(self.settings, FakeBatteryClient(self.analog, self.status), ())


class PaceModbusSlaveTests(unittest.TestCase):
    def test_read_module_uses_requested_slave(self):
        from solarbridge.modbus import crc16

        registers = [0] * 37
        registers[1] = 5200
        registers[2] = 80
        registers[15:31] = [3300] * 16
        registers[31:35] = [250, 250, 250, 250]

        class ModbusSerial:
            def __init__(self):
                self.is_open = True
                self.written = b""

            def write(self, data: bytes) -> int:
                self.written = bytes(data)
                count = (data[4] << 8) | data[5]
                payload = b"".join(value.to_bytes(2, "big") for value in registers[:count])
                header = bytes((data[0], 0x03, len(payload)))
                self.response = header + payload + crc16(header + payload)
                return len(data)

            def read(self, size: int = 1) -> bytes:
                chunk, self.response = self.response[:size], self.response[size:]
                return chunk

            def reset_input_buffer(self) -> None:
                pass

            def flush(self) -> None:
                pass

            def close(self) -> None:
                self.is_open = False

        holder = {}

        def factory(*args, **kwargs):
            holder["serial"] = ModbusSerial()
            return holder["serial"]

        client = PaceModbusBatteryClient("fake", timeout=0.2, serial_factory=factory)
        module = client.read_module(5)
        self.assertEqual(holder["serial"].written[0], 5)
        self.assertAlmostEqual(module["metrics"]["voltage_v"], 52.0)
        self.assertAlmostEqual(module["metrics"]["cell_voltage_min_v"], 3.3)


class AddressesConfigTests(unittest.TestCase):
    def test_parse_addresses(self):
        with mock.patch.dict(os.environ, {"SB_BATTERY_ADDRESSES": "3, 2;10"}):
            self.assertEqual(_addresses_env("SB_BATTERY_ADDRESSES"), (2, 3, 10))

    def test_parse_addresses_filters_junk_and_range(self):
        with mock.patch.dict(os.environ, {"SB_BATTERY_ADDRESSES": "2,x,0,16,3"}):
            self.assertEqual(_addresses_env("SB_BATTERY_ADDRESSES"), (2, 3))

    def test_parse_addresses_empty(self):
        with mock.patch.dict(os.environ, {"SB_BATTERY_ADDRESSES": " , "}):
            self.assertEqual(_addresses_env("SB_BATTERY_ADDRESSES"), ())


if __name__ == "__main__":
    unittest.main()
