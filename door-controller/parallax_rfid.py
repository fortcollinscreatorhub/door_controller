#!/usr/bin/env python3

import rfid_base
import sys

RateLimitTagEvents = rfid_base.RateLimitTagEvents

# Read tag transmissions from a Parallax RFID reader via serial port,
# convert tag ID to integer, and invoke a handler for each tag transmission.
class ParallaxRfidReader(rfid_base.RFIDReader):
    def __init__(self, port, handler):
        super(ParallaxRfidReader, self).__init__(port, handler)

    baud = 2400
    start_char = b'\n'
    end_char = b'\r'
    leader_len = 2
    tag_len = 8
    crc_len = 0

if __name__ == '__main__':
    tp = rfid_base.TagPrinter()
    rlte = rfid_base.RateLimitTagEvents(tp)
    rdr = ParallaxRfidReader(sys.argv[1], rlte)
    rdr.run()
