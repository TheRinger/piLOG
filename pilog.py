#! /usr/bin/env python
# Created by Tyrell Rutledge - tytek2012@gmail.com & IRC Freenode as TheRinger, Contributions welcome and will be credited.
from influxdb import InfluxDBClient
from influxdb import SeriesHelper
import RPi.GPIO as GPIO
import time
import datetime
import logging
import random
import Adafruit_DHT
import sys
import serial
import os


# InfluxDB connections settings
host = 'localhost'
port = 8086
user = 'root'
password = 'root'
dbname = 'test'
dbname2 = 'relays'

myclient = InfluxDBClient(host, port, user, password, dbname)
relayclient = InfluxDBClient(host, port, user, password, dbname2)

rpi_device = True
driver = Adafruit_DHT.DHT11

names = ['fahrenheit','celsius','humidity','co2']

daytime = True		# Set by Photocell Reading.. (Tell Co2 to sleep while it's dark, plants don't use co2 at night, no need for timer.)
off_button = False	# External Override Button 
co2_low = 456		# Co2 must drop to this number before the CO2 Generator will turn on
co2_high = 900		# Once this level of CO2 PPM is reached the CO2 Generator will turn off
temp_low = 75		# At this temperature the exhaust fan will turn off
temp_high = 80		# At this temperature the exhaust fan will turn on
humidity_high = 65	# Excess Co2 creates humidity, at this percent, the exhaust fan should turn on

# Attempt at creating a class that would allow the initialization of several types of sensors ( work in progress )
class Sensor(object):
	def __init__(self, pin, name, driver):
		self.pin = pin
		self.name = name
		self.driver = driver

	def status(self):
		if 'celsius' in self.name:
			return self.celsius()
		elif 'fahrenheit' in self.name:
			return self.fahrenheit()
		elif 'humidity' in self.name:
			return self.humidity()
		else:
			print "No Results for that sensor type"

	def loc(self):
		return "{0} sensor, located on pin {1}".format(self.name, self.pin)

	def show(self):
		print self.name

	def fahrenheit(self):
		result = Adafruit_DHT.read_retry(self.driver, self.pin)
		celsius = result[1]
		fahrenheit = 9.0/5.0 * celsius + 32
		return fahrenheit

	def humidity(self):
		result = Adafruit_DHT.read_retry(self.driver, self.pin)
		humidity = result[0]
		return humidity

	def celsius(self):
		result = Adafruit_DHT.read_retry(self.driver, self.pin)
		celsius = result[1]
		return celsius

	def check(self):
		if self is not None:
			return
		else:
			print "error"
# Class for the setup of a K30 Co2 Sensor connected to to the serial bus
class Co2(object):
        def __init__(self, name, pins, driver):
            self.name = name
            self.pins = pins
            self.driver = driver
            self.ser = serial.Serial("/dev/ttyAMA0")
            self.ser.flushInput()
            #print "Serial Connected!"

        def __call__(self):
            return self.status()

        def status(self):
	    self.ser.write("\xFE\x44\x00\x08\x02\x9F\x25")
	    time.sleep(.01)
	    resp = self.ser.read(7)
	    high = ord(resp[3])
	    low = ord(resp[4])
	    co2 = (high*256) + low
            return co2
            
        def show(self):
            return self.name
            
        def pins(self):
             return "Connected to pins: {0}".format(self.pins)

        def info(self):
	     return "{0} sensor, connected to pins {1}".format(str(self.name), str(self.pins))

        def flush(self):
            print "Flushing {0} sensor".format(self.name)
            self.ser.flushInput()
            print "Serial Input has been flushed successfully"
# Class for setting up relays
class Relay(object):
		def __init__(self, pin, name, start_high=False):
			if(rpi_device):
				self.pin = pin
				self.name = name
				GPIO.setmode(GPIO.BOARD)

				#Set initial state of pin
				if start_high is True:
					state = "On"
					GPIO.setup(self.pin, GPIO.OUT, initial=GPIO.HIGH)
					logging.info("{0} relay initialized on pin {1} and is currently {2}".format(name, pin, state))
				else:
					state = "Off"
					GPIO.setup(self.pin, GPIO.OUT)
					logging.info("{0} relay initialized on pin {1} and is currently {2}".format(name, pin, state))
				logging.info("  Relay Set  ")
				
		def status(self):  
			port_list = {0:"GPIO.OUT", 1:"GPIO.IN",40:"GPIO.SERIAL",41:"GPIO.SPI",42:"GPIO.I2C",43:"GPIO.HARD_PWM", -1:"GPIO.UNKNOWN"}  
			# loop through the list of ports/pins querying and displaying the status of each  
			nothing = "Pin type not available in port_list"
			port_used = GPIO.gpio_function(self.pin)
			for k,v in port_list.items():
				if port_used == k:
					return v  
				else:
					logging.info(" Status Unknown ")
					return "none" 

		@property
		def state(self):
			#0/1 or False/True or LOW/HIGH
			if GPIO.input(self.pin) == 0:
				return False
			elif GPIO.input(self.pin) == 1:
				return True
			else:
				return "error"

		@property
		def see_state(self):
			#0/1 or False/True or LOW/HIGH
			if GPIO.input(self.pin) == 0:
				x = "1"
				return int(x)
			elif GPIO.input(self.pin) == 1:
				x = "1000"
				return int(x)
			else:
				return "error"

		@property
		def on(self):
			#Enable relay
			time.sleep(0.1)
			logging.info(" Relay on ")
			return GPIO.output(self.pin, True)

		@property
		def off(self):
			#Disable relay
			time.sleep(0.1)
			logging.info(" Relay off ")
			return GPIO.output(self.pin, False)

		def clean(self):
			GPIO.cleanup(self.pin)
			logging.info(" Pin {0}, cleared ").format(self.pin)

# First attempt at hysteresis using python.. This will most likely need revised, with fault protection.
def mon_co2(low, high):
	if co2() < co2_low and daytime == True and f.status() <= temp_low:
		#print "  Relay {0} is turning on  ".format(name1)
		return r1.on
	elif co2() > co2_high or off_button == True:
		#print "  Relay {0} is turning off ".format(name1)
		return r1.off
def mon_temp(low, high):
	if f.status() >= temp_high or h.status >= humidity_high:
		print "  Relay {0} is turning off ".format(name1)
		r1.off
		print "  Relay {0} turning on off ".format(name2)
		return r2.on


#These help get the data ready for pushing to Influxdb, there is a better way and should be implemented.
class Series(SeriesHelper):
		class Meta:
				client = myclient
				series_name = 'sensor.{sensor_name}'
				fields = ['stat']
				tags = ['sensor_name']
class Relay_Log(SeriesHelper):
    class Meta:
    	client = relayclient
        series_name = 'relay.{name}'
        fields = ['state']
        tags = ['name']
        autocommit = True

co2 = Co2(name="K30 Co2", pins="34,33", driver="ttyAMA0")   # K30 Co2 Sensor
f = Sensor(pin=23, name="fahrenheit", driver=driver)		# DH11 Fahrenheit Sensor
c = Sensor(pin=23, name="celsius", driver=driver)			# DH11 Celsius
h = Sensor(pin=23, name="humidity", driver=driver)			# DH11 Humidity 
r1 = Relay(40, "Co2_Generator", start_high=False)			# This SSR-25da controls the on/off of a Co2 Generator device
r2 = Relay(38, "Exhaust_Fan", start_high=False)				# This SSR-25da controls the on/off of an Exhaust Fan
name1 = r1.name 											# Influxdb gives errors unless these are converted to strings first
name2 = r2.name 											# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

try:
	while True:
		mon_co2(co2_low, co2_high)
		time.sleep(5)
		mon_temp(temp_low, temp_high)
		time.sleep(5)
		state1 = r1.see_state  #
		Relay_Log(name=name1, state=state1)
		state2 = r2.see_state + 2000 # This is done because Graphana has limited support for boolean type logging, and so that logs do not overlap.
		Relay_Log(name=name2, state=state2)
		statuses = [f.status(), c.status(), h.status(), co2()]
		x = 0
		while x < len(names):
			name = names[x]
			status = statuses[x]
			#print "{0} : {1}".format(name,status)
			Series(sensor_name=name, stat=status)
			time.sleep(2)
			x += 1

		#Series._json_body_()
		Series.commit()
		#print ""
		#print "Sleeping 30 seconds..."
		#print "InfluxDB is at http://192.168.1.11:8086"
		#print "Graphana is at http://192.168.1.11:3000"
		#print ""
		time.sleep(30)

except KeyboardInterrupt:
	GPIO.cleanup()
	pass
exit()
