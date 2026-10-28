#!/usr/bin/env python3
"""DS2000A USB/VXI-11 helper. No acquisition or arbitrary SCPI writes."""
import argparse
import csv
from contextlib import closing
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys


def block_payload(raw):
    if len(raw) < 2 or raw[:1] != b"#" or raw[1:2] not in b"123456789":
        raise ValueError("Expected definite-length IEEE block")
    digits = int(raw[1:2])
    field = raw[2:2 + digits]
    if len(field) != digits or not field.isdigit():
        raise ValueError("Malformed block length")
    end = 2 + digits + int(field)
    if len(raw) < end or raw[end:] not in (b"", b"\n", b"\r\n"):
        raise ValueError("Truncated block or unexpected trailing bytes")
    return raw[2 + digits:end]


def preamble(text):
    values = [float(x) for x in text.split(',')]
    if len(values) != 10 or not all(math.isfinite(x) for x in values):
        raise ValueError("Invalid waveform preamble")
    names = ('format', 'type', 'points', 'count', 'xinc', 'xorigin', 'xref',
             'yinc', 'yorigin', 'yref')
    p = dict(zip(names, values))
    if p['format'] != 0 or p['xinc'] <= 0 or p['yinc'] <= 0:
        raise ValueError("Expected BYTE format and positive scaling")
    return p


def coordinates(data, p):
    for i, value in enumerate(data):
        yield ((i - p['xref']) * p['xinc'] + p['xorigin'],
               (value - p['yref'] - p['yorigin']) * p['yinc'])


def query(scope, command):
    return scope.query(command).strip()


def binary(scope, command):
    # USBTMC/VXI-11 provide end-of-message. Never terminate at LF in binary data.
    previous = scope.read_termination
    scope.read_termination = None
    try:
        scope.write(command)
        return block_payload(scope.read_raw())
    finally:
        scope.read_termination = previous


def channel_info(scope, channel):
    return {key: query(scope, ':CHAN{}:{}?'.format(channel, key))
            for key in ('DISP', 'PROB', 'SCAL', 'OFFS', 'COUP', 'UNITs')}


def identity(scope):
    value = query(scope, '*IDN?')
    fields = value.split(',')
    if len(fields) < 4 or 'RIGOL' not in fields[0].upper() or not re.fullmatch(
            r'(?:DS|MSO)2\d{3}A(?:-S)?', fields[1].strip().upper()):
        raise ValueError('Unexpected instrument identity: ' + value)
    return value


def discover_usb():
    # This backend API avoids ResourceManager's all-interface discovery.
    from pyvisa_py.usb import USBInstrSession
    import usb.core
    result = {'usb_resources': list(USBInstrSession.list_resources()), 'diagnostics': []}
    for device in usb.core.find(find_all=True, idVendor=0x1ab1):
        try:
            device.serial_number
        except (usb.core.USBError, ValueError, NotImplementedError) as error:
            result['diagnostics'].append(dict(
                vid='0x{:04x}'.format(device.idVendor), pid='0x{:04x}'.format(device.idProduct),
                usb_path='/dev/bus/usb/{:03d}/{:03d}'.format(device.bus, device.address),
                error=str(error), hint='Device enumerated; check permissions and USB descriptors.'))
    return result


def waveform(scope, args, idn):
    output = Path(args.output).expanduser()
    paths = (output, Path(str(output) + '.bin'), Path(str(output) + '.json'))
    if any(p.exists() for p in paths):
        raise ValueError('Output exists; choose a new filename')
    state = query(scope, ':TRIG:STAT?')
    if args.mode == 'RAW' and state != 'STOP':
        raise ValueError('RAW requires STOP; acquisition was not changed')
    count = args.points if args.points is not None else 1400
    if count < 1 or count > (1400 if args.mode == 'NORM' else 56000000):
        raise ValueError('Point count outside documented range')
    if args.mode == 'RAW' and args.points is None:
        raise ValueError('RAW needs explicit --points based on current memory depth')
    ch = channel_info(scope, args.channel)
    if ch['DISP'] not in ('1', 'ON'):
        raise ValueError('Selected channel is disabled; it was not enabled')
    keys = ('SOUR', 'MODE', 'FORM', 'POIN', 'STAR', 'STOP')
    saved = {k: query(scope, ':WAV:{}?'.format(k)) for k in keys}
    # On failure do not send more commands into a desynchronized session.
    print('Transfer settings before: ' + json.dumps(saved) +
          '. On failure these may remain changed.', file=sys.stderr)
    scope.write(':WAV:SOUR CHAN{}'.format(args.channel))
    scope.write(':WAV:MODE ' + args.mode)
    scope.write(':WAV:FORM BYTE')
    scope.write(':WAV:POIN {}'.format(count))
    actual = int(query(scope, ':WAV:POIN?'))
    if actual != count:
        raise ValueError('Instrument did not accept requested point count: {}'.format(actual))
    scope.write(':WAV:STAR 1')
    scope.write(':WAV:STOP {}'.format(min(count, 250000)))
    p_text = query(scope, ':WAV:PRE?')
    p = preamble(p_text)
    if p['type'] != (0 if args.mode == 'NORM' else 2):
        raise ValueError('Instrument did not accept waveform mode')
    data = bytearray()
    for start in range(1, count + 1, 250000):
        end = min(start + 249999, count)
        # Extend stop before advancing start to avoid transient start > stop.
        scope.write(':WAV:STOP {}'.format(end))
        scope.write(':WAV:STAR {}'.format(start))
        if (int(query(scope, ':WAV:STAR?')), int(query(scope, ':WAV:STOP?'))) != (start, end):
            raise ValueError('Waveform range readback mismatch')
        part = binary(scope, ':WAV:DATA?')
        if len(part) != end - start + 1:
            raise ValueError('Short or oversized waveform block')
        data.extend(part)
    after = query(scope, ':TRIG:STAT?')
    final_ch = channel_info(scope, args.channel)
    final_p = preamble(query(scope, ':WAV:PRE?'))
    scale_keys = ('format', 'type', 'xinc', 'xorigin', 'xref', 'yinc', 'yorigin', 'yref')
    if (ch != final_ch or any(p[k] != final_p[k] for k in scale_keys)
            or (state == 'STOP' and after != 'STOP')):
        raise ValueError('Acquisition/configuration changed during transfer')
    for key in ('SOUR', 'MODE', 'FORM', 'POIN'):
        scope.write(':WAV:{} {}'.format(key, saved[key]))
    scope.write(':WAV:STAR 1')
    scope.write(':WAV:STOP ' + saved['STOP'])
    scope.write(':WAV:STAR ' + saved['STAR'])
    restored = {k: query(scope, ':WAV:{}?'.format(k)) for k in keys}
    if restored != saved:
        raise ValueError('Transfer settings restoration mismatch: ' + repr(restored))
    metadata = dict(idn=idn, resource=args.resource, utc=datetime.now(timezone.utc).isoformat(),
                    mode=args.mode, channel=args.channel, points=len(data), preamble=p_text,
                    channel_settings=ch, acquisition_before=state, acquisition_after=after,
                    frozen=(state == after == 'STOP'), transfer_before=saved, transfer_after=restored,
                    complete=True)
    paths[0].parent.mkdir(parents=True, exist_ok=True)
    with paths[0].open('x', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(('time_s', 'value_' + ch['UNITs']))
        writer.writerows(coordinates(data, p))
    with paths[1].open('xb') as handle:
        handle.write(data)
    with paths[2].open('x') as handle:
        json.dump(metadata, handle, indent=2)
    return dict(files=[str(p) for p in paths], points=len(data), frozen=metadata['frozen'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resource', help='Explicit USB...::INSTR or TCPIP...::INSTR')
    parser.add_argument('--timeout-ms', type=int, default=10000)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('discover')
    sub.add_parser('info')
    sub.add_parser('options', help='Query reported option status; never change licenses')
    measure = sub.add_parser('measure')
    measure.add_argument('--channel', type=int, choices=(1, 2), default=1)
    shot = sub.add_parser('screenshot')
    shot.add_argument('--output', required=True)
    wave = sub.add_parser('waveform')
    wave.add_argument('--channel', type=int, choices=(1, 2), default=1)
    wave.add_argument('--mode', choices=('NORM', 'RAW'), default='NORM')
    wave.add_argument('--points', type=int)
    wave.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.action != 'discover' and (not args.resource or not re.fullmatch(
            r'(USB\d*|TCPIP\d*)::.+::INSTR', args.resource, re.I)):
        parser.error('An explicit USB/TCPIP INSTR resource is required')
    import pyvisa
    if args.action == 'discover':
        # ResourceManager.list_resources filters only AFTER probing every backend,
        # including LAN. Use the USB backend alone for local-only enumeration.
        print(json.dumps(discover_usb(), indent=2))
        return
    with closing(pyvisa.ResourceManager('@py')) as rm:
        with closing(rm.open_resource(args.resource, open_timeout=args.timeout_ms)) as scope:
            scope.timeout = args.timeout_ms
            scope.read_termination = '\n'
            scope.write_termination = '\n'
            scope.chunk_size = 1024 * 1024
            idn = identity(scope)
            if args.action == 'info':
                result = dict(idn=idn, resource=args.resource,
                              queries={cmd: query(scope, cmd) for cmd in
                                       (':TRIG:STAT?', ':ACQ:SRAT?', ':ACQ:MDEP?', ':TIM:SCAL?')},
                              channels={str(ch): channel_info(scope, ch) for ch in (1, 2)})
            elif args.action == 'options':
                result = dict(idn=idn, reported_options={module: query(
                    scope, ':SYST:OPT:VAL? ' + module)
                    for module in ('TRIG', 'DEC', 'CAN', 'MEMD')})
            elif args.action == 'measure':
                result = dict(idn=idn, channel=args.channel, values={})
                for item in ('FREQ', 'VPP', 'VRMS'):
                    raw = query(scope, ':MEAS:{}? CHAN{}'.format(item, args.channel))
                    value = float(raw)
                    result['values'][item] = dict(raw=raw, value=value if
                                                 math.isfinite(value) and abs(value) < 9e37 else None)
            elif args.action == 'screenshot':
                output = Path(args.output).expanduser()
                if output.suffix.lower() != '.bmp' or output.exists():
                    raise ValueError('Choose a new .bmp output path')
                data = binary(scope, ':DISP:DATA?')
                if len(data) < 54 or data[:2] != b'BM' or int.from_bytes(data[2:6], 'little') != len(data):
                    raise ValueError('Invalid BMP payload')
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open('xb') as handle:
                    handle.write(data)
                result = dict(idn=idn, file=str(output), bytes=len(data))
            else:
                result = waveform(scope, args, idn)
            print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('ERROR: {}: {}. Session closed; no automatic retry/reset.'.format(
            type(error).__name__, error), file=sys.stderr)
        sys.exit(1)
