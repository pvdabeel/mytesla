#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# <bitbar.title>MyTesla</bitbar.title>
# <bitbar.version>v3.0</bitbar.version>
# <bitbar.author>pvdabeel@mac.com</bitbar.author>
# <bitbar.author.github>pvdabeel</bitbar.author.github>
# <bitbar.desc>Control your Tesla vehicle from the Mac OS X menubar</bitbar.desc>
# <bitbar.dependencies>python</bitbar.dependencies>
#
# Credits: Jason Baker's Tesla bitbar plugin
#          Greg Glockner teslajson code 
#
# Licence: GPL v3

# Installation instructions: 
# -------------------------- 
# Execute in terminal.app before running : 
#    sudo easy_install keyring
#    sudo easy_install pyicloud
#
# Ensure you have bitbar installed https://github.com/matryer/bitbar/releases/latest
# Ensure your bitbar plugins directory does not have a space in the path (known bitbar bug)
# Copy this file to your bitbar plugins folder and chmod +x the file from your terminal in that folder
# Run bitbar


try:   # Python 3 dependencies
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen, build_opener
    from urllib.request import ProxyHandler, HTTPBasicAuthHandler, HTTPHandler, HTTPError, URLError
except: # Python 2 dependencies
    from urllib import urlencode
    from urllib2 import Request, urlopen, build_opener
    from urllib2 import ProxyHandler, HTTPBasicAuthHandler, HTTPHandler, HTTPError, URLError


import ast
import json
import sys
import datetime
import calendar
import base64
import math
import keyring      # Access token is stored in OS X keychain
import getpass      # Getting password without showing chars in terminal.app
import time
import os
import subprocess
import pyicloud     # Icloud integration - retrieving calendar info 
import requests

from pyicloud import PyiCloudService
from datetime import date
from pathos.multiprocessing import ProcessingPool as Pool # Parallelize retrieval of data from Tesla


# Nice ANSI colors
CEND    = '\33[0m'
CRED    = '\33[31m'
CGREEN  = '\33[32m'
CYELLOW = '\33[33m'
CBLUE   = '\33[34m'

# Support for OS X Dark Mode
DARK_MODE=os.getenv('BitBarDarkMode',0)


# Class that represents the connection to Tesla 
class TeslaConnection(object):
    """Connection to Tesla Motors API"""
    def __init__(self,
            email='',
            password='',
            access_token=None,
            proxy_url = '',
            proxy_user = '',
            proxy_password = ''):
        """Initialize connection object
        
        Required parameters:
        email: your login for teslamotors.com
        password: your password for teslamotors.com
        
        Optional parameters:
        access_token: API access token
        proxy_url: URL for proxy server
        proxy_user: username for proxy server
        proxy_password: password for proxy server
        """
        self.proxy_url = proxy_url
        self.proxy_user = proxy_user
        self.proxy_password = proxy_password

        tesla_client = {
            'v1': {
                'id': 'e4a9949fcfa04068f59abb5a658f2bac0a3428e4652315490b659d5ab3f35a9e', 
                'secret': 'c75f14bbadc8bee3a7594412c31416f8300256d7668ea7e6e7f06727bfb9d220', 
                'baseurl': 'https://owner-api.teslamotors.com', 
                'api': '/api/1/'
            }
        }
        current_client = tesla_client['v1']
        self.baseurl = current_client['baseurl']
        self.api = current_client['api']



        if access_token:
            # Case 1: TeslaConnection instantiation using access_token
            self.access_token = access_token 
            self.__sethead(access_token)
        else:
            # Case 2: TeslaConnection instantiation using email and password
            self.access_token = None
            self.expiration = 0 
            self.oauth = {
                "grant_type" : "password",
                "client_id" : current_client['id'],
                "client_secret" : current_client['secret'],
                "email" : email,
                "password" : password }
   
    def vehicles(self):
        return [TeslaVehicle(v, self) for v in self.get('vehicles')['response']]

    def get_token(self):
        # Case 1 : access token known and not expired
        if self.access_token and self.expiration > time.time():
            return self.access_token

        # Case 2 : access token unknown or expired
        auth = self.__open("/oauth/token", data=self.oauth)
        if 'access_token' in auth and auth['access_token']:
            self.access_token = auth['access_token']
            self.expiration = int(time.time()) + auth['expires_in'] - 86400
            return self.access_token

        # Case 3 : could not get access_token, force init
        return None

 
    def get(self, command):
        """Utility command to get data from API"""
        return self.post(command, None)
    
    def post(self, command, data={}):
        """Utility command to post data to API"""
        now = calendar.timegm(datetime.datetime.now().timetuple())
        if now > self.expiration:
            auth = self.__open("/oauth/token", data=self.oauth)
            self.__sethead(auth['access_token'],
                           auth['created_at'] + auth['expires_in'] - 86400)
        return self.__open("%s%s" % (self.api, command), headers=self.head, data=data)
    
    def __sethead(self, access_token, expiration=float('inf')):
        """Set HTTP header"""
        self.access_token = access_token
        self.expiration = expiration
        self.head = {"Authorization": "Bearer %s" % access_token}
    
    def __open(self, url, headers={}, data=None, baseurl=""):
        """Raw urlopen command"""
        if not baseurl:
            baseurl = self.baseurl
        req = Request("%s%s" % (baseurl, url), headers=headers)
        try:
            req.data = urlencode(data).encode('utf-8') # Python 3
        except:
            try:
                req.add_data(urlencode(data)) # Python 2
            except:
                pass

        # Proxy support
        if self.proxy_url:
            if self.proxy_user:
                proxy = ProxyHandler({'https': 'https://%s:%s@%s' % (self.proxy_user,
                                                                     self.proxy_password,
                                                                     self.proxy_url)})
                auth = HTTPBasicAuthHandler()
                opener = build_opener(proxy, auth, HTTPHandler)
            else:
                handler = ProxyHandler({'https': self.proxy_url})
                opener = build_opener(handler)
        else:
            opener = build_opener()
        resp = opener.open(req)
        charset = resp.info().get('charset', 'utf-8')
        return json.loads(resp.read().decode(charset))
        

# Class that represents a Tesla vehicle
class TeslaVehicle(dict):
    """TeslaVehicle class, subclassed from dictionary.
    
    There are 3 primary methods: wake_up, data_request and command.
    data_request and command both require a name to specify the data
    or command, respectively. These names can be found in the
    Tesla JSON API."""
    def __init__(self, data, connection):
        """Initialize vehicle class
        
        Called automatically by the TeslaConnection class
        """
        super(TeslaVehicle, self).__init__(data)
        self.connection = connection
    
    def data_request(self, name):
        """Get vehicle data"""
        result = self.get('data_request/%s' % name)
        return result['response']
    
    def wake_up(self):
        """Wake the vehicle"""
        return self.post('wake_up')
    
    def command(self, name, data={}):
        """Run the command for the vehicle"""
        return self.post('command/%s' % name, data)
    
    def get(self, command):
        """Utility command to get data from API"""
        return self.connection.get('vehicles/%i/%s' % (self['id'], command))
    
    def post(self, command, data={}):
        """Utility command to post data to API"""
        return self.connection.post('vehicles/%i/%s' % (self['id'], command), data)


# Class that represents a Tesla Calendar
class Icloud(dict):
    """iCloud class, subclassed from dictionary."""

    def __init__(self):
        """Initialize"""
        self.api=None
        return

    def init(self):    
        """Get iCloud credentials and store them in keyring"""
        print ('Enter your iCloud username:')
        icloud_username = raw_input()
        print ('Enter your iCloud password:')
        icloud_password = getpass.getpass()
        try: 
           self.api = PyiCloudService(icloud_username,icloud_password)
        except Exception as e:
           print('Error: Failed to authenticate to iCloud')
           print e
           return
        keyring.set_password("mytesla-bitbar","icloud_username",icloud_username)
        keyring.set_password("mytesla-bitbar","icloud_password",icloud_password)
        return

    def authenticate(self): # TODO: add 2fa auth support
        # https://pypi.python.org/pypi/pyicloud/0.9.1
        """Get iCloud credentials and store them in keyring"""
        icloud_username = keyring.get_password("mytesla-bitbar","icloud_username")
        icloud_password = keyring.get_password("mytesla-bitbar","icloud_password")
        try: 
           self.api = PyiCloudService(icloud_username,icloud_password)
        except Exception as e:
           self.init()
           return
        return       

    def devices(self):
        """Get iCloud devices"""
        return self.api.devices

    def calendarevents(self):
        """Get iCloud calendar events"""
        return self.api.calendar.events(date.today(),date.today())

    def reminders(self):
        """Get iCloud reminders"""
        self.api.reminders.refresh()
        return self.api.reminders.lists


# Convertors
def convert_temp(temp_unit,temp):
    if temp_unit == 'F':
        return (temp * 1.8) + 32
    else:
        return temp

def convert_distance(distance_unit,distance):
    if distance_unit == 'km':
        return math.ceil(distance * 160.9344)/100
    else:
        return distance

# Pretty print
def door_state(dooropen):
    if bool(dooropen):
        return CRED + 'Open' + CEND + ' '
    else:
        return CGREEN + 'Closed' + CEND + ' '

def cold_state(percentage):
    return CBLUE + '(-' + str(percentage) + '%)' + CEND

def port_state(portopen,engaged):
    if bool(portopen):
        if (engaged == 'Engaged'):
           return CYELLOW + 'In use' + CEND
        else:
           return CRED + 'Open' + CEND
    else:
        return CGREEN + 'Closed' + CEND
        

def lock_state(locked):
    if bool(locked):
        return CGREEN + 'Locked' + CEND
    else:
        return CRED + 'Unlocked' + CEND

# Logo for both dark mode and regular mode
def app_print_logo():
    if bool(DARK_MODE):
        print ('|image=iVBORw0KGgoAAAANSUhEUgAAABYAAAAWCAYAAADEtGw7AAAAAXNSR0IArs4c6QAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAFU2lUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iWE1QIENvcmUgNS40LjAiPgogICA8cmRmOlJERiB4bWxuczpyZGY9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkvMDIvMjItcmRmLXN5bnRheC1ucyMiPgogICAgICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIgogICAgICAgICAgICB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iCiAgICAgICAgICAgIHhtbG5zOnhtcE1NPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvbW0vIgogICAgICAgICAgICB4bWxuczpzdFJlZj0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL3NUeXBlL1Jlc291cmNlUmVmIyIKICAgICAgICAgICAgeG1sbnM6dGlmZj0iaHR0cDovL25zLmFkb2JlLmNvbS90aWZmLzEuMC8iCiAgICAgICAgICAgIHhtbG5zOnhtcD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wLyI+CiAgICAgICAgIDxkYzp0aXRsZT4KICAgICAgICAgICAgPHJkZjpBbHQ+CiAgICAgICAgICAgICAgIDxyZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+dGVzbGFfVF9CVzwvcmRmOmxpPgogICAgICAgICAgICA8L3JkZjpBbHQ+CiAgICAgICAgIDwvZGM6dGl0bGU+CiAgICAgICAgIDx4bXBNTTpEZXJpdmVkRnJvbSByZGY6cGFyc2VUeXBlPSJSZXNvdXJjZSI+CiAgICAgICAgICAgIDxzdFJlZjppbnN0YW5jZUlEPnhtcC5paWQ6NjFlOGM3OTktZDk2Mi00Y2JlLWFiNDItY2FmYjlmOTYxY2VlPC9zdFJlZjppbnN0YW5jZUlEPgogICAgICAgICAgICA8c3RSZWY6ZG9jdW1lbnRJRD54bXAuZGlkOjYxZThjNzk5LWQ5NjItNGNiZS1hYjQyLWNhZmI5Zjk2MWNlZTwvc3RSZWY6ZG9jdW1lbnRJRD4KICAgICAgICAgPC94bXBNTTpEZXJpdmVkRnJvbT4KICAgICAgICAgPHhtcE1NOkRvY3VtZW50SUQ+eG1wLmRpZDpCNkM1NEUzNDlERTAxMUU3QTRFNEExMTMwMUY5QkJBNTwveG1wTU06RG9jdW1lbnRJRD4KICAgICAgICAgPHhtcE1NOkluc3RhbmNlSUQ+eG1wLmlpZDpCNkM1NEUzMzlERTAxMUU3QTRFNEExMTMwMUY5QkJBNTwveG1wTU06SW5zdGFuY2VJRD4KICAgICAgICAgPHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD51dWlkOjI3MzY3NDg0MTg2QkRGMTE5NjZBQjM5RDc2MkZFOTlGPC94bXBNTTpPcmlnaW5hbERvY3VtZW50SUQ+CiAgICAgICAgIDx0aWZmOk9yaWVudGF0aW9uPjE8L3RpZmY6T3JpZW50YXRpb24+CiAgICAgICAgIDx4bXA6Q3JlYXRvclRvb2w+QWRvYmUgSWxsdXN0cmF0b3IgQ0MgMjAxNSAoTWFjaW50b3NoKTwveG1wOkNyZWF0b3JUb29sPgogICAgICA8L3JkZjpEZXNjcmlwdGlvbj4KICAgPC9yZGY6UkRGPgo8L3g6eG1wbWV0YT4KI5WHQwAAANVJREFUOBHtU8ENwjAMTBADdJRuACMwUjdgBEaAEcoEgQlSJmCEcJYS6VzlYVfiV0snn6/na5SqIez17xuIvReUUi7QT8AInIFezRBfwDPG+OgZlIbQL5BrT7Xf0YcK4eJpz7LMKqQ3wDSJEViXBArWJd6pl6U0mORkVyADchUBXVXVRogZuAGDCrEOWExAq2TZO1hM8CzkY06yptbgN60xJ1lTa/BMa8xJ1tQavNAac5I30vblrOtHqxG+2eENnmD5fc3lCf6YU2H0BLtO7DnE7t12Az8xb74dVbfynwAAAABJRU5ErkJggg==')
    else:
        print ('|image=iVBORw0KGgoAAAANSUhEUgAAABYAAAAWCAYAAADEtGw7AAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAA/xpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADw/eHBhY2tldCBiZWdpbj0i77u/IiBpZD0iVzVNME1wQ2VoaUh6cmVTek5UY3prYzlkIj8+IDx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IkFkb2JlIFhNUCBDb3JlIDUuMy1jMDExIDY2LjE0NTY2MSwgMjAxMi8wMi8wNi0xNDo1NjoyNyAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0UmVmPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VSZWYjIiB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8iIHhtbG5zOmRjPSJodHRwOi8vcHVybC5vcmcvZGMvZWxlbWVudHMvMS4xLyIgeG1wTU06T3JpZ2luYWxEb2N1bWVudElEPSJ1dWlkOjI3MzY3NDg0MTg2QkRGMTE5NjZBQjM5RDc2MkZFOTlGIiB4bXBNTTpEb2N1bWVudElEPSJ4bXAuZGlkOkI2QzU0RTM0OURFMDExRTdBNEU0QTExMzAxRjlCQkE1IiB4bXBNTTpJbnN0YW5jZUlEPSJ4bXAuaWlkOkI2QzU0RTMzOURFMDExRTdBNEU0QTExMzAxRjlCQkE1IiB4bXA6Q3JlYXRvclRvb2w9IkFkb2JlIElsbHVzdHJhdG9yIENDIDIwMTUgKE1hY2ludG9zaCkiPiA8eG1wTU06RGVyaXZlZEZyb20gc3RSZWY6aW5zdGFuY2VJRD0ieG1wLmlpZDo2MWU4Yzc5OS1kOTYyLTRjYmUtYWI0Mi1jYWZiOWY5NjFjZWUiIHN0UmVmOmRvY3VtZW50SUQ9InhtcC5kaWQ6NjFlOGM3OTktZDk2Mi00Y2JlLWFiNDItY2FmYjlmOTYxY2VlIi8+IDxkYzp0aXRsZT4gPHJkZjpBbHQ+IDxyZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+dGVzbGFfVF9CVzwvcmRmOmxpPiA8L3JkZjpBbHQ+IDwvZGM6dGl0bGU+IDwvcmRmOkRlc2NyaXB0aW9uPiA8L3JkZjpSREY+IDwveDp4bXBtZXRhPiA8P3hwYWNrZXQgZW5kPSJyIj8+ux4+7QAAALlJREFUeNpi/P//PwMtABMDjcDQM5gFmyAjI2MAkLIHYgMgdsCh9wAQXwDig8B42oAhC4o8ZAwE74H4PpQ+D6XXA7EAFK9HkwOrxTAHi8ENUA3/0fB6KEYXB6ltIMZgkKv6oS4xgIqhGAYVM4CqmQ/SQ9BgbBjqbZjB54nRQ2yqeICDTXFyu4iDTbHBB3CwKTaY5KBgJLYQAmaa/9B0z0h2ziMiOKhq8AVaGfxwULiYcbQGobnBAAEGADCCwy7PWQ+qAAAAAElFTkSuQmCC')
    print('---')


# The init function: Called to store your username and access_code in OS X Keychain on first launch

def init():
    # Here we do the setup
    # Store access_token in OS X keychain on first run
    print ('Enter your tesla.com username:')
    init_username = raw_input()
    print ('Enter your tesla.com password:')
    init_password = getpass.getpass()
    init_access_token = None

    try:
        c = TeslaConnection(init_username,init_password)
        init_password = ''
        init_access_token = c.get_token()
    except HTTPError as e:
        print ('Error contacting Tesla servers. Try again later.')
        print e
        time.sleep(0.5)
        return
    except URLError as e:
        print ('Error: Unable to connect. Check your connection settings.')
        print e
        return
    except AttributeError as e:
        print ('Error: Could not get an access token from Tesla. Try again later.')
        print e
        return
    keyring.set_password("mytesla-bitbar","username",init_username)
    keyring.set_password("mytesla-bitbar","access_token",init_access_token)


# The main function

def main(argv):

    # CASE 1: init was called 
    if 'init' in argv:
       init()
       return
  
    if 'icloud' in argv:
       ic = Icloud()
       ic.authenticate()
       print ic.reminders()
       return


    # CASE 2: init was not called, keyring not initialized
    if DARK_MODE:
        color = '#FFDEDEDE'
        info_color = '#808080'
    else:
        color = 'black' 
        info_color = '#808080'

    USERNAME = keyring.get_password("mytesla-bitbar","username")
    ACCESS_TOKEN = keyring.get_password("mytesla-bitbar","access_token")
    
    if not USERNAME:   
       # restart in terminal calling init 
       app_print_logo()
       print ('Login to tesla.com | refresh=true terminal=true bash="\'%s\'" param1="%s" color=%s' % (sys.argv[0], 'init', color))
       return


    # CASE 3: init was not called, keyring initialized, no connection (access code not valid)
    try:
       # create connection to tesla account
       c = TeslaConnection(access_token = ACCESS_TOKEN)
       vehicles = c.vehicles()
    except: 
       app_print_logo()
       print ('Login to tesla.com | refresh=true terminal=true bash="\'%s\'" param1="%s" color=%s' % (sys.argv[0], 'init', color))
       return


    # CASE 4: all ok, specific command for a specific vehicle received
    if len(sys.argv) > 1:
        v = vehicles[int(sys.argv[1])]
        v.wake_up()
        if sys.argv[2] != "wakeup":
            if (len(sys.argv) == 2) and (sys.argv[2] != 'remote_start_drive'):
                # argv is of the form: CMD + vehicleid + command 
                v.command(sys.argv[2])
            elif sys.argv[2] == 'remote_start_drive':
                # ask for password
                print ('Enter your tesla.com password:')
                password = getpass.getpass()
                # v.command(sys.argv[2],password)
                password = ''
            else:
                # argv is of the form: CMD + vehicleid + command + key:value pairs 
                v.command(sys.argv[2],dict(map(lambda x: x.split(':'),sys.argv[3:])))
        return


    # CASE 5: all ok, all other cases
    app_print_logo()
    prefix = ''
    if len(vehicles) > 1:
        # Create a submenu for every vehicle
        prefix = '--'

    # loop through vehicles, print menu with relevant info       
    for i, vehicle in enumerate(vehicles):
        if prefix:
            print vehicle['display_name']

	try:
           # wake up the vehicle
           if vehicle['state'] == 'offline':
                 vehicle.wake_up()
                 print ('%sVehicle offline. Click to try again. | refresh=true terminal=false bash="true" color=%s' % (prefix, color))
                 return     

           # get the data for the vehicle       
           dataset = ['gui_settings','charge_state','climate_state','drive_state','vehicle_state','vehicle_config']
	   pool = Pool(6)
           vehicle_info = pool.map(vehicle.data_request,dataset)
        except: 
           print ('%sError: Faild to get info from Tesla. Click to try again. | refresh=true terminal=false bash="true" color=%s' % (prefix, color))
           return         

	vehicle_name = vehicle['display_name']
	vehicle_vin  = vehicle['vin'] 

        gui_settings   = vehicle_info[0] # vehicle.data_request('gui_settings')
        charge_state   = vehicle_info[1] # vehicle.data_request('charge_state')
        climate_state  = vehicle_info[2] # vehicle.data_request('climate_state')
        drive_state    = vehicle_info[3] # vehicle.data_request('drive_state')
        vehicle_state  = vehicle_info[4] # vehicle.data_request('vehicle_state')
        vehicle_config = vehicle_info[5] # vehicle.data_request('vehicle_config')

        temp_unit = gui_settings['gui_temperature_units'].encode('utf-8')
        distance_unit='km'  

        if gui_settings['gui_distance_units'] == 'mi/hr':
            distance_unit = 'mi'

        # print the data for the vehicle
        # if charge_state['battery_level'] == charge_state['usable_battery_level']:
        #   print ('%sBattery Level:				%s%% | color=%s' % (prefix, charge_state['battery_level'],color))
        # else:
        loss_cold = int(charge_state['battery_level']) - int(charge_state['usable_battery_level'])



        print ('%sBattery Level:				%s%% %s | color=%s' % (prefix, charge_state['battery_level'], cold_state(loss_cold), color))
 
        print ('%s--Charge Level set to: %s%% | color=%s' % (prefix, charge_state['charge_limit_soc'], color))
        print ('%s---- 80%% | refresh=true terminal=false bash="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:80", info_color))
        print ('%s---- 80%% | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:80", info_color))
        print ('%s---- 85%% | refresh=true terminal=false bash="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:85", info_color))
        print ('%s---- 85%% | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:85", info_color))
        print ('%s---- 90%% (Default)| refresh=true terminal=false bash="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:90", color))
        print ('%s---- 90%% (Default)| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:90", color))
        print ('%s---- 95%% | refresh=true terminal=false bash="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:95", info_color))
        print ('%s---- 95%% | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:95", info_color))
        print ('%s---- 100%% (Trip only)| refresh=true terminal=false bash="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:100", info_color))
        print ('%s---- 100%% (Trip only)| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_charge_limit param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:100", info_color))
        try:
           if charge_state['battery_heater_on']:
              print ('%s--Battery heating | color=%s' % (prefix, color))
	except:
           pass
        print ('%sCharging State:				%s   | color=%s' % (prefix, charge_state['charging_state'],color))
        if (charge_state['charging_state']=="Charging") or (charge_state['charging_state']=='Starting'):
            print ('%s--Stop charging | refresh=true terminal=false bash="%s" param1=%s param2=charge_stop color=%s' % (prefix, sys.argv[0], str(i), color))
            print ('%s--Stop charging | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=charge_stop color=%s' % (prefix, sys.argv[0], str(i), color))
        if (charge_state['battery_level'] < charge_state['charge_limit_soc']) and (charge_state['charging_state']!='Starting') and (charge_state['charging_state']!='Charging') and (charge_state['charging_state']!='Disconnected'):
            print ('%s--Start charging | refresh=true terminal=false bash="%s" param1=%s param2=charge_start color=%s' % (prefix, sys.argv[0], str(i), color))
            print ('%s--Start charging | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=charge_start color=%s' % (prefix, sys.argv[0], str(i), color))
 
        print ('%sVehicle State:				%s   | color=%s' % (prefix, lock_state(vehicle_state['locked']),color))
        if bool(vehicle_state['locked']):
            print ('%s--Unlock | refresh=true terminal=false bash="%s" param1=%s param2=door_unlock color=%s' % (prefix, sys.argv[0], str(i), color))
            print ('%s--Unlock | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=door_unlock color=%s' % (prefix, sys.argv[0], str(i), color))
        else:
            print ('%s--Lock | refresh=true terminal=false bash="%s" param1=%s param2=door_lock color=%s' % (prefix, sys.argv[0], str(i), color))
            print ('%s--Lock | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=door_lock color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s---' % prefix)
        
        try:
            print ('%sInside Temp:					%.1f° %s| color=%s' % (prefix, convert_temp(temp_unit,climate_state['inside_temp']),temp_unit,color))
        except:
            print ('%sInside Temp:					Unavailable| color=%s' % (prefix,color))
        if climate_state['is_climate_on']:
            print ('%s--Turn off airco | refresh=true terminal=false bash="%s" param1=%s param2=auto_conditioning_stop color=%s' % (prefix, sys.argv[0], str(i), color))
            print ('%s--Turn off airco | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=auto_conditioning_stop color=%s' % (prefix, sys.argv[0], str(i), color))
        else:
            print ('%s--Turn on airco | refresh=true terminal=false bash="%s" param1=%s param2=auto_conditioning_start color=%s' % (prefix, sys.argv[0], str(i), color))
            print ('%s--Turn on airco | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=auto_conditioning_start color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s--Airco set to:	%.1f° %s | color=%s' % (prefix, convert_temp(temp_unit,climate_state['driver_temp_setting']), temp_unit, color))
        print ('%s---- 18° %s| refresh=true terminal=false bash="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, temp_unit, sys.argv[0], str(i), "driver_temp:18","passenger_temp:18", color))
        print ('%s---- 18° %s| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, temp_unit, sys.argv[0], str(i), "driver_temp:18","passenger_temp:18", color))
        print ('%s---- 19° %s| refresh=true terminal=false bash="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, temp_unit, sys.argv[0], str(i), "driver_temp:19","passenger_temp:19", color))
        print ('%s---- 19° %s| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, temp_unit, sys.argv[0], str(i), "driver_temp:19","passenger_temp:19", color))
        print ('%s---- 20° %s| refresh=true terminal=false bash="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, temp_unit, sys.argv[0], str(i), "driver_temp:20","passenger_temp:20", color))
        print ('%s---- 20° %s| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, temp_unit, sys.argv[0], str(i), "driver_temp:20","passenger_temp:20", color))
        print ('%s---- 21° %s| refresh=true terminal=false bash="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, temp_unit, sys.argv[0], str(i), "driver_temp:21","passenger_temp:21", color))
        print ('%s---- 21° %s| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, temp_unit, sys.argv[0], str(i), "driver_temp:21","passenger_temp:21", color))
        print ('%s---- 22° %s| refresh=true terminal=false bash="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, temp_unit, sys.argv[0], str(i), "driver_temp:22","passenger_temp:22", color))
        print ('%s---- 22° %s| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, temp_unit, sys.argv[0], str(i), "driver_temp:22","passenger_temp:22", color))
        print ('%s---- 23° %s| refresh=true terminal=false bash="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, temp_unit, sys.argv[0], str(i), "driver_temp:23","passenger_temp:23", color))
        print ('%s---- 23° %s| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, temp_unit, sys.argv[0], str(i), "driver_temp:23","passenger_temp:23", color))
        print ('%s---- 24° %s| refresh=true terminal=false bash="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, temp_unit, sys.argv[0], str(i), "driver_temp:24","passenger_temp:24", color))
        print ('%s---- 24° %s| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, temp_unit, sys.argv[0], str(i), "driver_temp:24","passenger_temp:24", color))
        print ('%s---- 25° %s| refresh=true terminal=false bash="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, temp_unit, sys.argv[0], str(i), "driver_temp:25","passenger_temp:25", color))
        print ('%s---- 25° %s| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_temps param3=%s param4=%s color=%s' % (prefix, temp_unit, sys.argv[0], str(i), "driver_temp:25","passenger_temp:25", color))
        try:
           if climate_state['is_rear_defroster_on']:
              print ('%s-- Rear window defrosting | color=%s' % (prefix, color))
	except:
           pass
        try:
           if climate_state['is_front_defroster_on']:
              print ('%s-- Front window defrosting | color=%s' % (prefix, color))
	except:
           pass

        try:
            print ('%sOutside Temp:				%.1f° %s| color=%s' % (prefix, convert_temp(temp_unit,climate_state['outside_temp']),temp_unit,color))
        except:
            print ('%sOutside Temp:				Unavailable| color=%s' % (prefix, color))
        print ('%s---' % prefix)
        
        if bool(drive_state['speed']):
            print ('%sVehicle Speed:				%s %s/h| color=%s' % (prefix, convert_distance(distance_unit,drive_state['speed']),distance_unit,color))
        else:
            print ('%sVehicle Speed:				Parked| color=%s' % (prefix,color))
        print ('%sVehicle Lat:					%s| color=%s' % (prefix, drive_state['latitude'],info_color))
        print ('%sVehicle Lon:					%s| color=%s' % (prefix, drive_state['longitude'],info_color))
        print ('%sVehicle Heading: 			%s°| color=%s' % (prefix, drive_state['heading'],info_color))
        print ('%s---' % prefix)
        
        print ('%sFirmware Version:			%s| color=%s' % (prefix, vehicle_state['car_version'],color))
        print ('%s---' % prefix)
        print ('%sDriver front door:				%s| color=%s' % (prefix, door_state(vehicle_state['df']),info_color))
        print ('%sDriver rear door:				%s| color=%s' % (prefix, door_state(vehicle_state['dr']),info_color))
        print ('%sPassenger front door:			%s| color=%s' % (prefix, door_state(vehicle_state['pf']),info_color))
        print ('%sPassenger rear door:			%s| color=%s' % (prefix, door_state(vehicle_state['pr']),info_color))
        print ('%s---' % prefix)


        print ('%sFront trunk:					%s| color=%s' % (prefix, door_state(vehicle_state['ft']),color))
        if (bool(vehicle_state['ft'])):
        	print ('%s--Close | refresh=true terminal=false bash="%s" param1=%s param2=trunk_open param3=%s color=%s' % (prefix, sys.argv[0], str(i), "which_trunk:front", color))
        	print ('%s--Close | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=trunk_open param3=%s color=%s' % (prefix, sys.argv[0], str(i), "which_trunk:front", color))
        else: 
        	print ('%s--Open | refresh=true terminal=false bash="%s" param1=%s param2=trunk_open param3=%s color=%s' % (prefix, sys.argv[0], str(i), "which_trunk:front", color))
        	print ('%s--Open | refresh=true alternate=true terminal=true  bash="%s" param1=%s param2=trunk_open param3=%s color=%s' % (prefix, sys.argv[0], str(i), "which_trunk:front", color))
        print ('%sRear trunk:					%s| color=%s' % (prefix, door_state(vehicle_state['rt']),info_color))
        if (bool(vehicle_state['rt'])):
        	print ('%s--Close | refresh=true terminal=false bash="%s" param1=%s param2=trunk_open param3=%s color=%s' % (prefix, sys.argv[0], str(i), "which_trunk:rear", color))
        	print ('%s--Close | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=trunk_open param3=%s color=%s' % (prefix, sys.argv[0], str(i), "which_trunk:rear", color))
        else: 
        	print ('%s--Open | refresh=true terminal=false bash="%s" param1=%s param2=trunk_open param3=%s color=%s' % (prefix, sys.argv[0], str(i), "which_trunk:rear", color))
        	print ('%s--Open | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=trunk_open param3=%s color=%s' % (prefix, sys.argv[0], str(i), "which_trunk:rear", color))
        print ('%sCharge port:					%s| color=%s' % (prefix, port_state(charge_state['charge_port_door_open'],charge_state['charge_port_latch']), color))
        if (not(bool(charge_state['charge_port_door_open']))):
        	print ('%s--Open | refresh=true terminal=false bash="%s" param1=%s param2=charge_port_door_open color=%s' % (prefix, sys.argv[0], str(i), color))
        	print ('%s--Open | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=charge_port_door_open color=%s' % (prefix, sys.argv[0], str(i), color))
	print ('%s---' % prefix)

        if (gui_settings['gui_range_display'] == 'Rated'):
            print ('%sRated battery range:			%s %s| color=%s' % (prefix, convert_distance(distance_unit,charge_state['battery_range']),distance_unit,color))
            print ('%sIdeal battery range:			%s %s| color=%s' % (prefix, convert_distance(distance_unit,charge_state['ideal_battery_range']),distance_unit,info_color))
        else: 
            print ('%sRated battery range:			%s %s| color=%s' % (prefix, convert_distance(distance_unit,charge_state['battery_range']),distance_unit,info_color))
            print ('%sIdeal battery range:			%s %s| color=%s' % (prefix, convert_distance(distance_unit,charge_state['ideal_battery_range']),distance_unit,color))

        print ('%sEstimated battery range:		%s %s| color=%s' % (prefix, convert_distance(distance_unit,charge_state['est_battery_range']),distance_unit,info_color))
        print ('%s---' % prefix)

        if bool(charge_state['charger_pilot_current']):
            print ('%sMaximum charger current:	%s A| color=%s' % (prefix, charge_state['charger_pilot_current'],info_color))
        else:
            print ('%sMaximum charger current:	Not connected| color=%s' % (prefix,info_color))

        print ('%sActual charger current:		%s A| color=%s' % (prefix, charge_state['charger_actual_current'],info_color))
        print ('%sCharger power:				%s Kw| color=%s' % (prefix, charge_state['charger_power'],info_color))
        print ('%sCharger voltage:				%s V| color=%s' % (prefix, charge_state['charger_voltage'],info_color))
        print ('%sCharger phases:				%s| color=%s' % (prefix, charge_state['charger_phases'],info_color))
        print ('%sSupercharging:				%s| color=%s' % (prefix, charge_state['fast_charger_present'],info_color))
        print ('%sCharger speed:				%s %s/h| color=%s' % (prefix, convert_distance(distance_unit,charge_state['charge_rate']),distance_unit,info_color))


	hours_to_full_charge = charge_state['time_to_full_charge']
        mins_to_full_charge = hours_to_full_charge * 60

        remaining_hours = int(mins_to_full_charge // 60)
	remaining_minutes = mins_to_full_charge - (remaining_hours * 60)

	if (remaining_hours == 0):
           print ('%sTime to full charge:			%s minutes | color=%s' % (prefix, remaining_minutes,color))
	elif (remaining_hours == 1):
           print ('%sTime to full charge:			%d hour %d mins | color=%s' % (prefix, remaining_hours, remaining_minutes, color))
        elif (remaining_minutes == 0):
           print ('%sTime to full charge:			%d hours | color=%s' % (prefix, remaining_hours, color))
        elif (remaining_minutes == 1):
           print ('%sTime to full charge:			%d hours 1 min | color=%s' % (prefix, remaining_hours, color))
        else:
           print ('%sTime to full charge:			%d hours %d mins | color=%s' % (prefix, remaining_hours, remaining_minutes, color))
        #print ('%sTime to full charge:			%s hours | alternate=true color=%s' % (prefix, charge_state['time_to_full_charge'], color))
        
        print ('%s---' % prefix)

        my_url1 ='https://maps.googleapis.com/maps/api/staticmap?center='+str(drive_state['latitude'])+','+str(drive_state['longitude'])+'&key=AIzaSyBrgHowqRH-ewRCNrhAgmK7EtFsuZCdXwk&zoom=17&size=340x385&markers=color:red%7C'+str(drive_state['latitude'])+','+str(drive_state['longitude'])
        my_url2 ='https://maps.googleapis.com/maps/api/staticmap?center='+str(drive_state['latitude'])+','+str(drive_state['longitude'])+'&key=AIzaSyBrgHowqRH-ewRCNrhAgmK7EtFsuZCdXwk&maptype=hybrid&zoom=17&size=340x385&markers=color:red%7C'+str(drive_state['latitude'])+','+str(drive_state['longitude'])
        my_img1 = base64.b64encode(requests.get(my_url1).content)
        my_img2 = base64.b64encode(requests.get(my_url2).content)
        print ('%s|image=%s href="https://maps.google.com?q=%s,%s" color=%s' % (prefix, my_img1, drive_state['latitude'],drive_state['longitude'],color))
        print ('%s|image=%s alternate=true href="https://maps.google.com?q=%s,%s" color=%s' % (prefix, my_img2, drive_state['latitude'],drive_state['longitude'],color))

        print ('%s---' % prefix)

        print ('%sVehicle info| color=%s' % (prefix,color))
        print ('%s--Name: 			%s | color=%s' % (prefix, vehicle_name, color))
        print ('%s--VIN: 			%s | terminal=true bash="echo %s | pbcopy" color=%s' % (prefix, vehicle_vin, vehicle_vin, color))
        print ('%s-----' % prefix)
        print ('%s--Model:			%s | color=%s' % (prefix, vehicle_config['car_type'], info_color))
        print ('%s--Type: 			%s | color=%s' % (prefix, vehicle_config['trim_badging'], info_color))
        print ('%s--Ludicrous:		%s | color=%s' % (prefix, vehicle_config['has_ludicrous_mode'], info_color))
        print ('%s--Uncorked: 		%s | color=%s' % (prefix, vehicle_config['perf_config'], info_color))
        print ('%s--Color: 			%s | color=%s' % (prefix, vehicle_config['exterior_color'], info_color))
        print ('%s--Wheels: 			%s | color=%s' % (prefix, vehicle_config['wheel_type'], info_color))


        print ('%sVehicle commands| color=%s' % (prefix,color))
        print ('%s--Flash lights | refresh=true terminal=false bash="%s" param1=%s param2=flash_lights color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s--Flash lights | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=flash_lights color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s--Honk horn | refresh=true terminal=false bash="%s" param1=%s param2=honk_horn color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s--Honk horn | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=honk_horn color=%s' % (prefix, sys.argv[0], str(i), color))
        try:
           if bool(vehicle_config['sun_roof_installed']):
              print ('%s-----' % prefix)
              print ('%s--Sun roof open: %s%% | color=%s' % (prefix, vehicle_state['sun_roof_percent_open'], color))
              print ('%s---- 0%% (Closed)| refresh=true terminal=false bash="%s" param1=%s param2=sun_roof_control param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:0", color))
              print ('%s---- 0%% (Closed)| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=sun_roof_control param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:0", color))
              print ('%s---- 15%% (Vent)| refresh=true terminal=false bash="%s" param1=%s param2=sun_roof_control param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:15", color))
              print ('%s---- 15%% (Vent)| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=sun_roof_control param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:15", color))
              print ('%s---- 80%% (Comfort)| refresh=true terminal=false bash="%s" param1=%s param2=sun_roof_control param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:80", color))
              print ('%s---- 80%% (Comfort)| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=sun_roof_control param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:80", color))
              print ('%s---- 100%% (Open)| refresh=true terminal=false bash="%s" param1=%s param2=sun_roof_control param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:100", color))
              print ('%s---- 100%% (Open)| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=sun_roof_control param3=%s color=%s' % (prefix, sys.argv[0], str(i), "percent:100", color))
        except:
           # API change going to firmware 2018.4
           pass
        print ('%s-----' % prefix)
        print ('%s--Remote start | refresh=true terminal=true bash="%s" param1=%s param2=remote_start_drive color=%s' % (prefix, sys.argv[0], str(i), color))
 



       

def run_script(script):
    return subprocess.Popen([script], stdout=subprocess.PIPE, shell=True).communicate()[0].strip()

def password_dialog():
    cmd = "osascript -e 'set my_password to display dialog \"Please enter your Tesla password:\" with title \"Tesla password\" with icon file \"Users:pvdabeel:Documents:Bitbar-plugins:icons:tesla.icns\" default answer \"\" buttons {\"Cancel\",\"Login\"} default button 2 giving up after 180 with hidden answer'"
    print run_script(cmd)

if __name__ == '__main__':
    #password_dialog()
    main(sys.argv)
