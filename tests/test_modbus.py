import unittest

from solarbridge.config import Settings
from solarbridge.modbus import ModbusError, ModbusRTU, crc16


class FakeSerial:
    def __init__(self, responses, **_kwargs):
        self.responses = responses
        self.buffer = bytearray()
        self.is_open = True
        self.writes = []
        self.rts = None
        self.dtr = None

    def reset_input_buffer(self):
        self.buffer.clear()

    def write(self, data):
        self.writes.append(data)
        start = int.from_bytes(data[2:4], "big")
        count = int.from_bytes(data[4:6], "big")
        self.buffer.extend(self.responses[(start, count)])
        return len(data)

    def flush(self):
        pass

    def read(self, size=1):
        result = bytes(self.buffer[:size])
        del self.buffer[:size]
        return result

    def close(self):
        self.is_open = False


def response(slave_id, registers):
    body = bytes((slave_id, 3, len(registers) * 2))
    payload = b"".join(value.to_bytes(2, "big") for value in registers)
    return body + payload + crc16(body + payload)


def exception_response(slave_id, function, code):
    body = bytes((slave_id, function | 0x80, code))
    return body + crc16(body)


def settings():
    return Settings(
        base_dir=None,
        public_dir=None,
        db_path=None,
        seed_dir=None,
        receivers_file=None,
        host="127.0.0.1",
        port=8090,
        source_mode="serial",
        master_id="test",
        serial_port="fake",
        slave_id=4,
        baudrate=19200,
        poll_interval=15,
        sample_interval=60,
        config_interval=300,
        serial_timeout=0.2,
        inter_request_delay=0,
        retention_days=730,
        forward_backfill_days=60,
        forward_batch=240,
        forward_pause_s=1.0,
        forward_parallel=2,
        heartbeat_interval=15,
        offline_after_s=180,
        seed_max_age_days=0,
        seed_token_ttl_hours=24,
        seed_token_max_downloads=10,
        ingest_token="",
        ingest_allowlist=(),
        trust_proxy=False,
        battery_mode="off",
        battery_serial_port="",
        battery_baudrate=9600,
        battery_protocol="auto",
        battery_commandset="auto",
        battery_variant="auto",
        battery_protocol_version="",
        battery_addresses=(),
        battery_cmd_gap_s=1.0,
        battery_poll_interval=15,
        host_stats=True,
        auth_enabled=False,
        user_list_path=None,
        disk_min_free_percent=10.0,
    )


class ModbusTests(unittest.TestCase):
    def test_read_holding_registers_validates_frame(self):
        fake = FakeSerial({(25201, 2): response(4, [0x1234, 0xFFF0])})
        client = ModbusRTU(settings(), serial_factory=lambda *args, **kwargs: fake)
        self.assertEqual(client.read_holding(25201, 2), [0x1234, 0xFFF0])
        self.assertEqual(fake.writes[0], bytes.fromhex("04 03 62 71 00 02 8b fd"))

    def test_bad_crc_is_rejected(self):
        frame = bytearray(response(4, [1]))
        frame[-1] ^= 0xFF
        fake = FakeSerial({(25201, 1): bytes(frame)})
        client = ModbusRTU(settings(), serial_factory=lambda *args, **kwargs: fake)
        with self.assertRaisesRegex(ModbusError, "CRC"):
            client.read_holding(25201, 1)

    def test_device_exception_is_reported(self):
        fake = FakeSerial({(25201, 1): exception_response(4, 3, 2)})
        client = ModbusRTU(settings(), serial_factory=lambda *args, **kwargs: fake)
        with self.assertRaisesRegex(ModbusError, "exception code: 2"):
            client.read_holding(25201, 1)

    def test_poll_once_reads_expected_ranges_and_decodes(self):
        responses = {
            (20000, 17): response(4, [2] + [0] * 16),
            (15201, 21): response(4, [2, 1, 2] + [0] * 18),
            (25201, 79): response(4, [0] * 79),
            (10001, 5): response(4, [1600, 0, 0, 10100, 10500]),
            (10101, 24): response(4, [0] * 24),
            (20101, 44): response(4, [0] * 44),
        }
        fake = FakeSerial(responses)
        client = ModbusRTU(settings(), serial_factory=lambda *args, **kwargs: fake)
        snapshot = client.poll_once(include_config=True)
        self.assertEqual(
            [(write[2] << 8) | write[3] for write in fake.writes],
            [20000, 15201, 25201, 10001, 10101, 20101],
        )
        self.assertEqual(snapshot["identity"]["machine_type_high_code"], 2)
        self.assertEqual(snapshot["charger_identity"]["model"], "PC1600")
        self.assertEqual(snapshot["status"]["charger"]["work_state_code"], 2)
        self.assertEqual(snapshot["status"]["charger"]["mppt_state_code"], 1)
        self.assertEqual(snapshot["status"]["charger"]["charging_state_code"], 2)
        self.assertEqual(snapshot["connection"]["status"], "online")

    def test_poll_once_uses_cached_charger_identity(self):
        responses = {
            (20000, 17): response(4, [0] + [0] * 16),
            (15201, 21): response(4, [0] * 21),
            (25201, 79): response(4, [0] * 79),
            (10001, 5): response(4, [1600, 0, 0, 10100, 10500]),
            (10101, 24): response(4, [0] * 24),
            (20101, 44): response(4, [0] * 44),
        }
        fake = FakeSerial(dict(responses))
        client = ModbusRTU(settings(), serial_factory=lambda *args, **kwargs: fake)
        client.poll_once(include_config=True)
        # Next fast cycle: only the three status blocks are polled.
        fake.responses = {
            (20000, 17): response(4, [0] + [0] * 16),
            (15201, 21): response(4, [0] * 21),
            (25201, 79): response(4, [0] * 79),
        }
        snapshot = client.poll_once(include_config=False)
        self.assertEqual([(write[2] << 8) | write[3] for write in fake.writes[-3:]], [20000, 15201, 25201])
        self.assertEqual(snapshot["charger_identity"]["model"], "PC1600")

    def test_identity_falls_back_to_legacy_block(self):
        # Firmware without register 20000: exception for 20000..20016,
        # valid legacy block at 20001..20016.
        legacy = [0] * 16
        legacy[0] = 1800
        legacy[1] = 0xFFFF
        legacy[2] = 0xFFFF
        legacy[4] = 22534
        responses = {
            (20000, 17): exception_response(4, 3, 2),
            (20001, 16): response(4, legacy),
            (15201, 21): response(4, [0] * 21),
            (25201, 79): response(4, [0] * 79),
            (10001, 5): response(4, [1600, 0, 0, 10100, 10500]),
            (10101, 24): response(4, [0] * 24),
            (20101, 44): response(4, [0] * 44),
        }
        fake = FakeSerial(responses)
        client = ModbusRTU(settings(), serial_factory=lambda *args, **kwargs: fake)
        snapshot = client.poll_once(include_config=True)
        self.assertNotIn("identity", snapshot["connection"]["section_errors"])
        self.assertIsNone(snapshot["identity"]["machine_type_high_code"])
        self.assertEqual(snapshot["identity"]["model"], "PV1800")
        self.assertEqual(snapshot["identity"]["software_version"], "2.25.34")


if __name__ == "__main__":
    unittest.main()
