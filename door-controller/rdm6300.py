#!/usr/bin/env python3

import rfid_base
import sys

RateLimitTagEvents = rfid_base.RateLimitTagEvents

# Read tag transmissions from an RDM6300 via serial port, validate the CRC,
# convert tag ID to integer, and invoke a handler for each tag transmission.
class RDM6300Reader(rfid_base.RFIDReader):
    def __init__(self, port, handler):
        super(RDM6300Reader, self).__init__(port, handler)

    baud = 9600
    start_char = b'\x02'
    end_char = b'\x03'
    leader_len = 2
    tag_len = 8
    crc_len = 2

    def _crc_valid(self, buf):
        crc_calc = 0
        for x in [buf[i:i+2] for i in range(0, len(buf), 2)]:
            crc_calc ^= int(x, 16)
        return crc_calc == 0

if __name__ == '__main__':
    tp = rfid_base.TagPrinter()
    rlte = rfid_base.RateLimitTagEvents(tp)
    rdr = RDM6300Reader(sys.argv[1], rlte)
    rdr.run()
