import collections
import serial

MeasureScan = collections.namedtuple('MeasureScan', ['length', 'width', 'height', 'weight', 'dimweight', 'factor'])

# See documentation for CubiScan 125

CS_PREFIX = bytes([0x02])
CS_SUFFIX = bytes([0x03, 0x0d, 0x0a])

def cmd(char):
    b2 = bytes([ord(char)])
    return CS_PREFIX + b2 + CS_SUFFIX

def coerce_float(s):
    """
    >>> coerce_float('_____')
    >>> coerce_float('~~~~')
    >>> coerce_float(' 3.60')
    3.6
    """
    # From the fine manual page 111:  "This field may contain underscores,
    # dashes, or overscores indicating an under, unstable, or over error
    # condition, respectively."
    if s.strip('_') == '' or s.strip('-') == '' or s.strip('~') == '':
        return None
    return float(s)

def convert(eventtype, payload):
    if chr(eventtype) in 'mMA':
        # Sample payload:
        # b'AC      ,L 3.60,W12.05,H 5.10in,K 1.545,D 1.333lb,F0166,D'
        p = str(payload, encoding='ascii')
        measures = p.split(',')
        if len(measures) != 8:
            raise RuntimeError('unrecognized measurement payload')
        kwargs = {}
        # exclude initial flags and final D/I (domestic, international)
        for m in measures[1:-1]:
            if m[0] == 'L':
                kwargs['length'] = coerce_float(m[1:])
            if m[0] == 'W':
                kwargs['width'] = coerce_float(m[1:])
            if m[0] == 'H':
                kwargs['height'] = coerce_float(m[1:-2])
            if m[0] == 'K':
                kwargs['weight'] = coerce_float(m[1:])
            if m[0] == 'D':
                kwargs['dimweight'] = coerce_float(m[1:-2])
            if m[0] == 'F':
                kwargs['factor'] = int(m[1:])
        return chr(eventtype), MeasureScan(**kwargs)
    return chr(eventtype), payload

class CubiScanScanner:
    def __init__(self, comport):
        self._serial = serial.Serial('COM{}'.format(comport), timeout=.25)

        self._queue = b''

    def close(self):
        self._serial.close()

    def _parse_bytes(self):
        while len(self._queue) > 0:
            b = self._queue
            if len(b) < len(CS_PREFIX+CS_SUFFIX):
                break

            length = len(CS_SUFFIX)+b.find(CS_SUFFIX)
            rec = self._queue[:length]
            data = rec[len(CS_PREFIX):-len(CS_SUFFIX)]
            eventtype = data[1]
            payload = data[1:]
            yield (eventtype, convert(eventtype, payload))
            self._queue = b[length+4:]

    def read_scans(self):
        while True:
            read = self._serial.read(100)
            self._queue += read
            if len(self._queue) == 0 or len(read) == 0:
                break
            if self._queue.find(CS_SUFFIX) >= 0:
                for _, value in self._parse_bytes():
                    yield value

    def measure(self):
        self._serial.write(cmd('M'))
