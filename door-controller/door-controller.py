from __future__ import print_function

import argparse
try:
    import configparser
except:
    import ConfigParser as configparser
import itertools
import os
import socket
import sys
import queue
import threading
import time
import traceback
import urllib.parse
import urllib.request

door_controller_dir = os.path.dirname(__file__)
app_dir = os.path.dirname(door_controller_dir)
etc_dir = os.path.join(app_dir, 'etc')

def print_with_timestamp(s):
    print(time.strftime('%Y%m%d %H%M%S'), s)
    # Required for log content to show up in systemd
    sys.stdout.flush()

try:
    import RPi.GPIO as GPIO
except:
    print_with_timestamp('WARNING: import RPi.GPIO failed')
    print_with_timestamp('WARNING: EMULATING all GPIO accesses')
    class GPIO:
        BOARD = 0
        OUT = 0
        HIGH = 0
        LOW = 0

        @classmethod
        def setmode(klass, mode):
            print_with_timestamp("GPIO-debug: GPIO.setmode(%s)" % repr(mode))

        @classmethod
        def setup(klass, gpio, direction):
            print_with_timestamp("GPIO-debug: GPIO.setup(%s, %s)" % (repr(gpio), repr(direction)))

        @classmethod
        def output(klass, gpio, value):
            print_with_timestamp("GPIO-debug: GPIO.output(%s, %s)" % (repr(gpio), repr(value)))

class SleepStep(object):
    args_conversions = (int,)

    def __init__(self, delay):
        self.delay = delay

    def __str__(self):
        return 'sleep,' + str(self.delay)

    def __repr__(self):
        return self.__str__()

class GpioSetupOutStep(object):
    args_conversions = (int,)

    def __init__(self, gpio):
        self.gpio = gpio

    def __call__(self):
        GPIO.setup(self.gpio, GPIO.OUT)

    def __str__(self):
        return 'gpio.setup.out,%d' % self.gpio

    def __repr__(self):
        return self.__str__()

class GpioOutStep(object):
    args_conversions = (int, int)

    def __init__(self, gpio, val):
        self.gpio = gpio
        self.val = val

    def __call__(self):
        GPIO.output(self.gpio, self.val)

    def __str__(self):
        return 'gpio.out,%d,%d' % (self.gpio, self.val)

    def __repr__(self):
        return self.__str__()

class LogStep(object):
    args_conversions = (str,)

    def __init__(self, message):
        self.message = message

    def __call__(self):
        print_with_timestamp('LogStep: ' + self.message)

    def __str__(self):
        return 'log,%s' % self.message

    def __repr__(self):
        return self.__str__()

actions = {
    'sleep': SleepStep,
    'gpio.setup.out': GpioSetupOutStep,
    'gpio.out': GpioOutStep,
    'log': LogStep,
}

def parse_sequence(conf_section, seqname):
    sequence = []
    for step_id in itertools.count():
        key = seqname + '.' + str(step_id)
        if key not in conf_section:
            break
        action_str = conf_section[key]
        (action_name, *action_args) = action_str.split(',')
        if action_name not in actions:
            raise Exception('Invalid action in %s' % key)
        action_constructor = actions[action_name]
        args_conversions = action_constructor.args_conversions
        expected_arg_count = len(args_conversions)
        actual_arg_count = len(action_args)
        if actual_arg_count != expected_arg_count:
            raise Exception('Invalid argument count %d in %s' % (actual_arg_count, key))
        try:
            action_args_converted = map(lambda f, x: f(x), args_conversions, action_args)
        except:
            raise Exception('Invalid arguments in %s' % key)
        sequence.append(action_constructor(*action_args_converted))
    return sequence

class SequenceTimer(object):
    def __init__(self, sequence, notifier):
        self.sequence = sequence
        self.notifier = notifier

        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self.threadfunc)

    def start(self):
        self.thread.start()

    def join(self):
        self.thread.join()

    def cancel(self):
        self.queue.put(None)
        self.thread.join()

    def threadfunc(self):
        try:
            delay=0
            for action in self.sequence:
                try:
                    self.queue.get(timeout=delay)
                except queue.Empty as e:
                    if isinstance(action, SleepStep):
                        delay = action.delay
                    else:
                        delay = 0
                        action()
                else:
                    break
        finally:
            if self.notifier:
                self.notifier.sequence_complete(self)

class RfidReaderThread(threading.Thread):
    def __init__(self, conf_section):
        super(RfidReaderThread, self).__init__()

        self.reader_type = conf_section['reader_type']
        self.serial_port = conf_section['serial_port']
        self.auth_host = conf_section['auth_host']
        self.auth_port = int(conf_section['auth_port'])
        self.acl = conf_section['acl']
        self.restart_action = conf_section.getboolean('restart_action')
        self.init_seq = parse_sequence(conf_section, 'init')
        self.authorized_seq = parse_sequence(conf_section, 'authorized')
        self.unauthorized_seq = parse_sequence(conf_section, 'unauthorized')

        self.seq_timer = None
        self.sw_state_lock = threading.Lock()

    def run(self):
        try:
            GPIO.setmode(GPIO.BOARD)
            print_with_timestamp('Running init sequence')
            st = SequenceTimer(self.init_seq, None)
            st.start()
            st.join()
            print_with_timestamp('Completed init sequence')
            if self.reader_type == 'rdm6300':
                import rdm6300
                rlte = rdm6300.RateLimitTagEvents(self)
                rdr = rdm6300.RDM6300Reader(self.serial_port, rlte)
            elif self.reader_type == 'parallax':
                import parallax_rfid
                rlte = parallax_rfid.RateLimitTagEvents(self)
                rdr = parallax_rfid.ParallaxRfidReader(self.serial_port, rlte)
            else:
                raise Exception('Invalid reader type: ' + self.reader_type)
            rdr.run()
        except:
            print_with_timestamp('EXCEPTION in main loop (exiting):')
            traceback.print_exc()
            sys.exit(1)

    def handle_tag(self, tag, rcv_start_time):
        print_with_timestamp('Tag: ' + repr(tag))

        authorized = self.validate_tag(tag)
        if authorized:
            print_with_timestamp('Tag authorized')
        else:
            print_with_timestamp('Tag NOT authorized')

        previously_running_timer = None
        with self.sw_state_lock:
            # We can't use self.seq_timer without sw_state_lock held,
            # since the timer callback could run and clear
            # self.seq_timer.
            previously_running_timer = self.seq_timer

        if previously_running_timer:
            if not (authorized and self.restart_action):
                print_with_timestamp('Ignore; previous sequence is running')
                return

        if previously_running_timer:
            print_with_timestamp('Cancelling existing sequence')
            previously_running_timer.cancel()
            # The following join() must happen without sw_state_lock held,
            # since the timer callback can hold that lock, and if we hold it,
            # join() might deadlock waiting for the timer callback to complete,
            # yet it can't complete since we hold the lock.
            previously_running_timer.join()
            self.seq_timer = None

        with self.sw_state_lock:
            if authorized:
                seq = self.authorized_seq
            else:
                seq = self.unauthorized_seq
            self.seq_timer = SequenceTimer(seq, self)
            self.seq_timer.start()

    def sequence_complete(self, seq_timer):
        with self.sw_state_lock:
            if self.seq_timer == seq_timer:
                self.seq_timer = None

    def handle_data_outside_tag(self, data):
        pass

    def handle_timeout(self, data):
        pass

    def handle_overlong_tag(self, data):
        pass

    def handle_validation_error(self, data):
        pass

    def validate_tag(self, tag):
        try:
            url = 'http://%s:%d/api/check-access-0/%s/%s' % (
                self.auth_host,
                self.auth_port,
                urllib.parse.quote(self.acl),
                urllib.parse.quote(str(tag)))
            with urllib.request.urlopen(url) as f:
                answer = f.read()
                return answer.decode('utf-8') == 'True'
        except:
            print_with_timestamp('EXCEPTION in access check (squashed):')
            traceback.print_exc()
            pass
        return False

config = configparser.ConfigParser(inline_comment_prefixes=('#'))
config.read(etc_dir + '/door-controller.ini')
# FIXME: To enable multiple device controllers on one host, take a cmdline arg
# naming the device this process should handle, and add that device name into
# each entry in sec_names. Or, search for all section names with our hostname,
# and start a thread for each.
sec_names = [
    'conf.' + socket.gethostname(),
    'conf'
]
sec = None
for sec_name in sec_names:
    if sec_name in config:
        sec = config[sec_name]
        break
if sec is None:
    raise Exception('No valid section found in configuration file')
rfid_reader_thread = RfidReaderThread(sec)
rfid_reader_thread.start()
rfid_reader_thread.join()
