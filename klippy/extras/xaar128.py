# XAAR128 Printhead Control
#
# Copyright (C) 2024 Sean Brownlee <skbrownlee@outlook.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging, time
from . import bus

PIN_MIN_TIME = 0.100

class xaar128:
    def __init__(self, config, config_cmd=None):
        self.printer = printer = config.get_printer()
        self._callback = None
        self.min_sample_value = self.max_sample_value = 0
        self._report_clock = 0
        self.last_print_time = 0.
        # Setup SPI Device
        spi_mode = 0      # Replace with the desired SPI mode
        spi_speed = 1000000  # Replace with the desired SPI speed in Hz
        # Instantiate MCU_SPI object
        self.spi = bus.MCU_SPI_from_config(config, spi_mode, pin_option="cs_pin", default_speed=1000000)
        if config_cmd is not None:
            self.spi.spi_send(config_cmd)
        self.mcu = mcu = self.spi.get_mcu()
        # Setup Pins
        ppins = self.printer.lookup_object('pins')
        pin_dict = {
            'output': ['VPPH', 'VPPL', 'nRESET', 'nSS2', 'VDD', 'SCK', 'nSS1', 'PHO', 'nFIRE', 'CLK', 'nFAULT'],
            'input': ['READY', 'nFAULT']
        }
        self.pin_objects = {}
        for pin_type, pin_names in pin_dict.items():  # Change variable name to pin_names
            for pin_name in pin_names:  # Iterate over pin names
                pin = None
                config_name = config.get(f'{pin_name}_pin', None)
                if config_name is not None:
                    if pin_type == 'output':
                        pin = ppins.setup_pin('digital_out', config_name)
                        pin.setup_max_duration(0.)
                        self.pin_objects[pin_name] = pin

        # Register g-code commands
        gcode = printer.lookup_object('gcode')
        handlers = ['L1', 'HEAD_ON', 'HEAD_OFF']
        for cmd in handlers:
            func = getattr(self, 'cmd_' + cmd)
            desc = getattr(self, 'cmd_' + cmd + '_help', None)
            gcode.register_command(cmd, func, True, desc)

    ## Load and Fire Printhead Nozzles
    def cmd_L1(self, gcmd):
        params = gcmd.get_command_parameters()
        try:
            if 'H' in params:
                data = (params['H'])
                eventtime = self.printer.get_reactor().monotonic()
                gcmd.respond_raw("eventtime: " + str(eventtime))
                mcu = self.pin_objects['VDD'].get_mcu()
                print_time = mcu.estimated_print_time(eventtime) + PIN_MIN_TIME
                print_time = max(print_time, self.last_print_time + PIN_MIN_TIME)
                # READY (output from Xaar 128) is HIGH (okay to load data)
                #READ READY PIN
                # Enable nSS2
                self.pin_objects['nSS2'].set_digital(print_time, 1)
                # Clock in 64 bits
                chunks = [data[i:i+8] for i in range(0, len(data), 8)]
                    # Convert each 8-bit chunk to its hexadecimal representation
                hex_values = [hex(int(chunk, 2)) for chunk in chunks]
                    # Remove the '0x' prefix from each hexadecimal value and convert to integer
                byte_values = [int(hex_value, 16) for hex_value in hex_values]
                    # Send the byte values
                self.spi.spi_send(byte_values)
                # Disable nSS2.
                self.pin_objects['nSS2'].set_digital(print_time, 0)
                # LATER USE Enable nSS1
                # LATER USEself.pin_objects['nSS1'].set_digital(print_time, 1)
                # LATER USE Clock in 64 bitS
                # LATER USE Disable nSS1.
                # nFIRE (active LOW) input to Xaar 128 indicates that data is loaded and ready to fire.
                self.pin_objects['nFIRE'].set_digital(print_time, 0)
                # READY goes LOW when firing nozzles.
                # READY returns to HIGH
        except ValueError as e:
            raise gcmd.error("Unable to parse Fire '%s'"
                             % (gcmd.get_commandline()))

    ## Turn on Head Power
    def cmd_HEAD_ON(self, gcmd):
        gcmd.respond_raw("Printhead Powering On...")
        eventtime = self.printer.get_reactor().monotonic()
        gcmd.respond_raw("eventtime: " + str(eventtime))
        mcu = self.pin_objects['VDD'].get_mcu()
        print_time = mcu.estimated_print_time(eventtime) + PIN_MIN_TIME
        print_time = max(print_time, self.last_print_time + PIN_MIN_TIME)
        # nRESET active (active low)
        #self.pin_objects['nRESET'].set_digital(print_time, 1)
        # VDD on
        self.pin_objects['VDD'].set_digital(print_time, 1)
        # Wait 100 ms
        time.sleep(0.1)
        # VPPH/VPPL on
        self.pin_objects['VPPH'].set_digital(print_time, 1)
        # Wait 100 ms
        time.sleep(0.1)
        # nReset inactive (active low)
        self.pin_objects['nRESET'].set_digital(print_time, 1)
        self.last_print_time = print_time
        gcmd.respond_raw("Printhead On!")


    ## Turn off Head Power
    def cmd_HEAD_OFF(self, gcmd):
        gcmd.respond_raw("Printhead Powering Off")
        eventtime = self.printer.get_reactor().monotonic()
        gcmd.respond_raw("eventtime: " + str(eventtime))
        mcu = self.pin_objects['VDD'].get_mcu()
        print_time = mcu.estimated_print_time(eventtime) + PIN_MIN_TIME
        print_time = max(print_time, self.last_print_time + PIN_MIN_TIME)        
        # nRESET active (active low)
        #self.pin_objects['nRESET'].set_digital(print_time, 1)        
        # Wait 100 ms
        time.sleep(0.1)
        # VPPH/VPPL off
        self.pin_objects['VPPH'].set_digital(print_time, 0)
        # Wait 100 ms
        time.sleep(0.1)
        # VDD off
        self.pin_objects['VDD'].set_digital(print_time, 0)
        self.last_print_time = print_time
        gcmd.respond_raw("Printhead Off!")

def load_config(config):
    return xaar128(config)        
        
def load_config_prefix(config):
    return xaar128(config)        