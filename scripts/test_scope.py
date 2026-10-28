"""Offline protocol and export tests; no real instrument connections."""
import argparse
import csv
import json
from pathlib import Path
import tempfile
import struct
import unittest

import scope


class Instrument:
    def __init__(self, state='STOP', short=False):
        self.state, self.short = state, short
        self.read_termination = '\n'
        self.values = dict(SOUR='CHAN2', MODE='NORM', FORM='BYTE',
                           POIN='1400', STAR='1', STOP='1400')
        self.original = self.values.copy()
        self.writes = []
        self.read_ranges = []

    def query(self, command):
        if command == ':TRIG:STAT?':
            return self.state
        if command.startswith(':CHAN'):
            key = command.split(':')[-1][:-1]
            return dict(DISP='1', PROB='10', SCAL='1', OFFS='0', COUP='DC', UNITs='VOLT')[key]
        if command == ':WAV:PRE?':
            return '0,{},{},1,0.001,-0.01,0,0.04,0,127'.format(
                0 if self.values['MODE'] == 'NORM' else 2, self.values['POIN'])
        return self.values[command.split(':')[-1][:-1]]

    def write(self, command):
        self.writes.append(command)
        if command != ':WAV:DATA?':
            key, value = command.split(' ')
            self.values[key.split(':')[-1]] = value

    def read_raw(self):
        assert self.read_termination is None
        start, end = int(self.values['STAR']), int(self.values['STOP'])
        self.read_ranges.append((start, end))
        data = bytes((i % 256 for i in range(start - 1, end)))
        if self.short:
            data = data[:-1]
        return b'#9' + str(len(data)).zfill(9).encode() + data + b'\n'


class Tests(unittest.TestCase):
    def bitmap(self, declared):
        data = bytearray(1152054)
        data[:2] = b'BM'
        struct.pack_into('<I', data, 2, declared)
        struct.pack_into('<IIiiHHI', data, 10, 54, 40, 800, 480, 1, 24, 0)
        return data

    def test_bitmap_standard_and_firmware_size_field(self):
        for size in (1152054, 1152000):
            info = scope.bmp_info(self.bitmap(size))
            self.assertEqual(info['pixel_only_size_field'], size == 1152000)

    def test_bitmap_bad_length_rejected(self):
        for data in (self.bitmap(1152054)[:-1], self.bitmap(42)):
            with self.assertRaises(ValueError):
                scope.bmp_info(data)

    def test_binary_embedded_lf_and_trailers(self):
        for trailer in (b'', b'\n', b'\r\n'):
            self.assertEqual(scope.block_payload(b'#13\x00\n\xff' + trailer), b'\x00\n\xff')

    def test_reject_bad_blocks(self):
        for data in (b'', b'#0abc', b'#212ab', b'#1x', b'#11ab', b'#9'):
            with self.assertRaises(ValueError):
                scope.block_payload(data)

    def test_scaling(self):
        p = scope.preamble('0,0,3,1,0.001,-0.01,0,0.04,0,127')
        rows = list(scope.coordinates(bytes([127, 152, 102]), p))
        self.assertEqual([r[1] for r in rows], [0, 1, -1])
        self.assertAlmostEqual(rows[2][0], -0.008)

    def test_invalid_preamble(self):
        for p in ('0,0', '0,0,3,1,nan,0,0,1,0,0', '1,0,3,1,1,0,0,1,0,0'):
            with self.assertRaises(ValueError):
                scope.preamble(p)

    def args(self, folder, mode='RAW', points=250001):
        return argparse.Namespace(output=str(Path(folder) / 'wave.csv'), mode=mode,
                                  points=points, channel=1, resource='FAKE')

    def test_running_raw_refused_without_writes(self):
        device = Instrument(state='RUN')
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'requires STOP'):
                scope.waveform(device, self.args(folder), 'FAKE')
        self.assertEqual(device.writes, [])

    def test_multiblock_export_and_restore(self):
        device = Instrument()
        with tempfile.TemporaryDirectory() as folder:
            args = self.args(folder)
            result = scope.waveform(device, args, 'FAKE')
            self.assertEqual(result['points'], 250001)
            self.assertEqual(device.read_ranges, [(1, 250000), (250001, 250001)])
            self.assertEqual(device.values, device.original)
            self.assertEqual(Path(args.output + '.bin').stat().st_size, 250001)
            with open(args.output + '.json') as handle:
                self.assertTrue(json.load(handle)['frozen'])
            with open(args.output) as handle:
                reader = csv.reader(handle)
                next(reader)
                last = None
                for last in reader:
                    pass
                self.assertAlmostEqual(float(last[0]), 249.99)
            self.assertFalse(any(x in device.writes for x in (':STOP', ':RUN', '*RST')))

    def test_short_block_fails_without_further_writes(self):
        device = Instrument(short=True)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'waveform block'):
                scope.waveform(device, self.args(folder, 'NORM', 100), 'FAKE')
            self.assertEqual(list(Path(folder).iterdir()), [])
        self.assertEqual(device.writes[-1], ':WAV:DATA?')

    def test_running_screen_is_marked_unfrozen(self):
        device = Instrument(state='RUN')
        with tempfile.TemporaryDirectory() as folder:
            result = scope.waveform(device, self.args(folder, 'NORM', 100), 'FAKE')
            self.assertFalse(result['frozen'])


if __name__ == '__main__':
    unittest.main()
