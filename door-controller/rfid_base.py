#!/usr/bin/env python3

import serial
import sys
import time

start_end_timeout = 0.2
repeat_delay = 2.0

# Print a tag value for debugging
class TagPrinter(object):
    def __init__(self):
        pass

    def handle_tag(self, tag, rcv_start_time):
        print('TAG:', tag, rcv_start_time)

    def handle_data_outside_tag(self, data):
        print('OUTSIDE TAG:', repr(data))

    def handle_timeout(self, data):
        print('TIMEOUT; PARTIAL:', repr(data))

    def handle_overlong_tag(self, data):
        print('OVERLONG:', repr(data))

    def handle_validation_error(self, data):
        print('INVALID:', repr(data))

# Rate-limit tag transmissions
class RateLimitTagEvents(object):
    def __init__(self, handler):
        self.handler = handler
        self.reset_tag()

    def reset_tag(self):
        self.last_tag = None
        self.last_rcv_start_time = 0

    def handle_tag(self, tag, rcv_start_time):
        if (tag == self.last_tag and
                rcv_start_time < self.last_rcv_start_time + repeat_delay):
            return
        self.last_tag = tag
        self.last_rcv_start_time = rcv_start_time
        self.handler.handle_tag(tag, rcv_start_time)

    def handle_data_outside_tag(self, data):
        self.handler.handle_data_outside_tag(data)

    def handle_timeout(self, data):
        self.handler.handle_timeout(data)

    def handle_overlong_tag(self, data):
        self.handler.handle_overlong_tag(data)

    def handle_validation_error(self, data):
        self.handler.handle_validation_error(data)

# Read tag transmissions from an RFID reader via serial port, validate any
# applicable CRC, convert tag ID to integer, and invoke a handler for each tag
# transmission.
class RFIDReader(object):
    def __init__(self, port, handler):
        self.handler = handler
        self.rfid_len = self.leader_len + self.tag_len + self.crc_len
        self.ser = serial.Serial(port, self.baud)

    def run(self):
        self._reset_buf()
        while True:
            c = self.ser.read(1)
            t = time.time()
            # Start character?
            # Start receiving new tag data
            if c == self.start_char:
                self.buf = b''
                self.rcv_start_time = t
            # buf is None?
            # Start character not yet seen; ignore
            elif self.buf is None:
                self.handler.handle_data_outside_tag(c)
            # Too long since start character?
            # Tag transmission took too long; reset state
            elif t >= (self.rcv_start_time + start_end_timeout):
                self.handler.handle_timeout(self.buf)
                self._reset_buf()
            # End character?
            # Process received tag data
            elif c == self.end_char:
                tag = self._convert_validate(self.buf)
                if tag:
                    self.handler.handle_tag(tag, self.rcv_start_time)
                else:
                    self.handler.handle_validation_error(self.buf)
                self._reset_buf()
            # Buffer too long for tag data?
            # Corruption, so reset buffer
            elif len(self.buf) >= self.rfid_len:
                self.handler.handle_overlong_tag(self.buf)
                self._reset_buf()
            # Record received character for later use
            else:
                self.buf += c

    def _reset_buf(self):
        self.buf = None
        self.rcv_start_time = None

    def _convert_validate(self, buf):
        if len(buf) != self.rfid_len:
            return None
        try:
            if self.crc_len and not self._crc_valid(buf):
                return None
            return int(buf[self.leader_len:(self.leader_len+self.tag_len)], 16)
        except:
            return None
