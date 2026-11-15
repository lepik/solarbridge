import unittest

from solarbridge.decode import (
    decode_charger_identity,
    decode_snapshot,
    decode_inverter_status,
    packed_energy_kwh,
    signed16,
    version,
)


class DecodeTests(unittest.TestCase):
    def test_signed16_and_version(self):
        self.assertEqual(signed16(0xFFF0), -16)
        self.assertEqual(version([22534], 0), "2.25.34")
        self.assertEqual(version([0], 0), "1.00.00")

    def test_packed_energy_kwh_uses_protocol_units(self):
        # high = 1000 KWH steps, low = 0.1 KWH steps (decimal packing)
        self.assertEqual(packed_energy_kwh([0, 5100], 0), 510.0)
        self.assertEqual(packed_energy_kwh([1, 500], 0), 1050.0)
        self.assertIsNone(packed_energy_kwh([1], 0))

    def test_identity_block_starts_at_20000(self):
        identity = [0] * 17
        identity[0] = 2  # 20000 machine type high (PV/PH/EP series)
        identity[1] = 1800  # 20001 machine type low
        identity[2] = 0xFFFF  # 20002 serial high
        identity[3] = 0xFFFF  # 20003 serial low
        identity[4] = 10101  # 20004 hardware version
        identity[5] = 22534  # 20005 software version
        identity[6] = 10414  # 20006 communication protocol edition
        identity[9] = 16384  # 20009 battery voltage calibration
        decoded = decode_snapshot(
            sections={"identity": identity},
            captured_at="2026-11-12T12:00:00Z",
            source={"port": "test", "slave_id": 4, "baudrate": 19200},
            errors={},
            latency_ms=1.0,
        )
        identity_out = decoded["identity"]
        self.assertEqual(identity_out["model"], "PV1800")
        self.assertEqual(identity_out["machine_type_high_code"], 2)
        self.assertEqual(identity_out["serial_number"], "FFFFFFFF")
        self.assertEqual(identity_out["hardware_version"], "1.01.01")
        self.assertEqual(identity_out["software_version"], "2.25.34")
        self.assertEqual(identity_out["communication_protocol_version"], "1.04.14")
        self.assertEqual(identity_out["battery_voltage_calibration"], 16384)

    def test_charger_identity_block(self):
        decoded = decode_charger_identity([1600, 0x1234, 0x5678, 10100, 10500])
        self.assertEqual(decoded["model"], "PC1600")
        self.assertEqual(decoded["serial_number"], "12345678")
        self.assertEqual(decoded["hardware_version"], "1.01.00")
        self.assertEqual(decoded["software_version"], "1.05.00")

    def test_inverter_status_faults_relays_arrow_and_power_factor(self):
        inverter = [0] * 79
        inverter[0] = 4  # bypass
        inverter[2] = 3200  # rated power VA (25203)
        inverter[12] = 2200  # Pinverter
        inverter[16] = 2500  # SInverter -> cos phi 0.88
        inverter[36] = 1  # inverter relay connected
        inverter[37] = 0  # grid relay open
        inverter[60] = (1 << 2) | (1 << 4)  # error message 1: bits 2 and 4
        inverter[61] = 1 << 12  # error message 2: bit 12
        inverter[62] = 0x00FF  # error message 3 raw (undocumented bits)
        inverter[64] = 1 << 3  # warning message 1: bit 3
        inverter[65] = 0x8000  # warning message 2: reserved bit
        inverter[73] = 0xFFF6  # battery current -10 A
        inverter[76] = 3200  # rated power W (25277)
        inverter[78] = (1 << 0) | (1 << 4) | (1 << 5) | (2 << 6) | (1 << 8)  # arrow flag

        decoded = decode_inverter_status(inverter)
        self.assertEqual(decoded["rated_power_va"], 3200)
        self.assertEqual(decoded["power_factor"], 0.88)
        self.assertTrue(decoded["inverter_relay_connected"])
        self.assertFalse(decoded["grid_relay_connected"])
        self.assertEqual(decoded["battery_current_a"], -10)
        self.assertEqual(
            decoded["error_flags"],
            [
                {"bit": 2, "code": "E1-02", "key": "fault.inv.e1.2", "message": 1},
                {"bit": 4, "code": "E1-04", "key": "fault.inv.e1.4", "message": 1},
                {"bit": 12, "code": "E2-12", "key": "fault.inv.e2.12", "message": 2},
            ],
        )
        self.assertEqual(
            decoded["warning_flags"],
            [
                {"bit": 3, "code": "W1-03", "key": "fault.inv.w1.3", "message": 1},
                {"bit": 15, "code": "W2-15", "key": "fault.inv.w2.15", "message": 2},
            ],
        )
        self.assertEqual(decoded["error_code_3"], 0x00FF)
        arrow = decoded["arrow"]
        self.assertTrue(arrow["pv_present"])
        self.assertTrue(arrow["pv_to_machine"])
        self.assertTrue(arrow["machine_to_load"])
        self.assertEqual(arrow["machine_battery"], 2)  # batt -> machine (discharge)
        self.assertEqual(arrow["machine_grid"], 1)  # machine -> grid (sell)
        self.assertFalse(arrow["load_present"])

    def test_charger_status_stages_relays_flags_and_uptime(self):
        charger = [0] * 21
        charger[0] = 2  # work mode
        charger[1] = 1  # MPPT
        charger[2] = 2  # float charge
        charger[10] = 1  # battery relay connected
        charger[11] = 0  # PV relay open
        charger[12] = 1 << 4  # error bit 4
        charger[13] = 1 << 0  # warning bit 0 (fan error)
        charger[16] = 1  # accumulated PV power high
        charger[17] = 500  # accumulated PV power low
        charger[18] = 3  # days
        charger[19] = 4  # hours
        charger[20] = 25  # minutes
        decoded = decode_snapshot(
            sections={"charger_status": charger},
            captured_at="2026-11-12T12:00:00Z",
            source={"port": "test", "slave_id": 4, "baudrate": 19200},
            errors={},
            latency_ms=1.0,
        )["status"]["charger"]
        self.assertEqual(decoded["work_state_code"], 2)
        self.assertEqual(decoded["mppt_state_code"], 1)
        self.assertEqual(decoded["charging_state_code"], 2)
        self.assertTrue(decoded["battery_relay_connected"])
        self.assertFalse(decoded["pv_relay_connected"])
        self.assertEqual(
            decoded["error_flags"],
            [{"bit": 4, "code": "CE-04", "key": "fault.chg.e.4"}],
        )
        self.assertEqual(
            decoded["warning_flags"],
            [{"bit": 0, "code": "CW-00", "key": "fault.chg.w.0"}],
        )
        self.assertEqual(decoded["accumulated_pv_power_kwh"], 1050.0)
        self.assertEqual(decoded["uptime"], {"days": 3, "hours": 4, "minutes": 25})

    def test_snapshot_exposes_known_metrics_and_raw_sections(self):
        identity = [0] * 17
        identity[1] = 1800
        identity[2] = 0xFFFF
        identity[3] = 0xFFFF
        identity[4] = 10101
        identity[5] = 22534
        charger = [0] * 21
        charger[4] = 280
        charger[5] = 268
        charger[6] = 12
        charger[7] = 250
        inverter = [0] * 79
        inverter[2] = 3200
        inverter[4] = 268
        inverter[5] = 2297
        inverter[6] = 2306
        inverter[12] = 22
        inverter[13] = 380
        inverter[14] = 361
        inverter[15] = 16
        inverter[24] = 4995
        inverter[25] = 4995
        inverter[44] = 0
        inverter[45] = 1234  # accumulated charger power -> 123.4 KWH
        inverter[70] = 10101
        inverter[71] = 22534
        inverter[76] = 3200
        inverter[77] = 10414

        snapshot = decode_snapshot(
            sections={
                "identity": identity,
                "charger_status": charger,
                "inverter_status": inverter,
                "charger_identity": [1600, 0, 0, 10100, 10500],
            },
            captured_at="2026-11-12T12:00:00Z",
            source={"port": "test", "slave_id": 4, "baudrate": 19200},
            errors={},
            latency_ms=123.4,
        )
        self.assertEqual(snapshot["identity"]["model"], "PV1800")
        self.assertEqual(snapshot["charger_identity"]["model"], "PC1600")
        self.assertEqual(snapshot["metrics"]["rated_power_w"], 3200)
        self.assertEqual(snapshot["metrics"]["rated_power_va"], 3200)
        self.assertEqual(snapshot["metrics"]["load_power_w"], 361)
        self.assertEqual(snapshot["metrics"]["grid_voltage_v"], 230.6)
        self.assertEqual(snapshot["metrics"]["grid_frequency_hz"], 49.95)
        self.assertEqual(snapshot["status"]["inverter"]["accumulated_charger_power_kwh"], 123.4)
        self.assertEqual(snapshot["raw"]["inverter_status"], inverter)

    def test_inverter_config_system_setting_flags_20142(self):
        from solarbridge.decode import decode_inverter_config

        registers = [0] * 44
        registers[41] = 0x0057  # bits 0,1,2,4,6
        config = decode_inverter_config(registers)
        flags = config["system_setting_flags"]
        self.assertTrue(flags["overload_restart_forbid"])
        self.assertTrue(flags["overtemp_restart_forbid"])
        self.assertTrue(flags["overload_bypass_forbid"])
        self.assertFalse(flags["auto_turn_page_forbid"])
        self.assertTrue(flags["grid_buzzer_enable"])
        self.assertFalse(flags["buzzer_forbid"])
        self.assertTrue(flags["lcd_light_enable"])
        self.assertEqual(decode_inverter_config([0] * 44)["system_setting_flags"]["lcd_light_enable"], False)
        self.assertIsNone(decode_inverter_config(None))

    def test_no_dangerous_write_registers_inside_read_blocks(self):
        from solarbridge.modbus import ModbusRTU

        for name, (start, count) in ModbusRTU.RANGES.items():
            end = start + count - 1
            self.assertNotIn(20213, range(start, end + 1), f"{name} covers RW register 20213")
            self.assertNotIn(20214, range(start, end + 1), f"{name} covers RW register 20214")


if __name__ == "__main__":
    unittest.main()
