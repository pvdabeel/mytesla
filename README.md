
# MyTesla - MacOS Menubar plugin

Displays information regarding your Tesla vehicle in the MacOS menubar. Allows you to remotely control your Tesla vehicle as well.

![Imgur](https://i.imgur.com/5xMhwXM.jpg)


| Browse Vehicle options | Browse Vehicle images | Control charging |
| --- | --- | --- |
| ![Imgur](https://i.imgur.com/EJ6sT7E.jpg) | ![Imgur](https://i.imgur.com/o0wx7nD.jpg) | ![Imgur](https://i.imgur.com/5xMhwXM.jpg) | 

| Control Airco | Control Media | Control Navigation |
| --- | --- | --- |
| ![Imgur](https://i.imgur.com/i1tRRsL.jpg) | ![Imgur](https://i.imgur.com/R36v4f9.jpg) | ![Imgur](https://i.imgur.com/ciLkZu8.jpg) |


Want a Tesla with free supercharging Credits? Use my [referral code](http://ts.la/pieter9690)


## Changelog: 

**Update 2023.12.03:**
- [X] Testing new Tesla Fleet API (location tracking)

**Update 2022.11.01:**
- [X] Ready for Python3 and MacOS Ventura
- [X] Improved Seat heating support: supports 7 seats
- [X] Improved Steering heating support
- [X] Displays current Station / Song / Title
- [X] Displays current volume
- [X] Updated composer images

**Update 2022.05.21:**
- [X] Automatically refreshes Tesla's new style 8-hr API tokens

**Update 2021.11.02:**
- [X] Support for xbar, deprecating bitbar
- [X] Provide option to directly provide access_code during initialization

**Update 2021.08.04:**
- [X] Support for auth.tesla.com captcha
- [X] Support for showing battery in menu bar
- [X] Support for white logo in menu bar on Big Sur

**Update 2020.02.06:**
- [X] Offline mode: application shows last known 'state' when vehicle is sleeping. Added a manual wakup option.
- [X] Improved location tracking performance
- [X] Ability to override option_codes for your vehicle (see parameters in file)

**Update 2020.02.04:**
- [X] Support for auth.tesla.com including Multi-Factor authentication
- [X] Code cleanup

**Update 2019.10.02:**
- [X] Display window status
- [X] Show software update progress and version info

**Update 2019.09.30:**
- [X] Larger google map

**Update 2019.09.29:**
- [X] Support for V.10 firmware
- [X] Window control
- [X] Trigger Homelink
- [X] Share to vehicle
- [X] Maximum window defrost

**Update 2019.07.01:**
- [X] Show service appointments
- [X] Mac OS X Catalina beta support

**Update 2019.04.13:**
- [X] Dog Mode 
- [X] Sentry Mode
- [X] More information when vehicle is in service

**Update 2019.03.06:**
- [X] Compose car image based on optionlist

**Update 2019.02.05:**
- [X] Added continuous location tracking to a TinyDB (can be disabled) 
- [X] Google maps are cached (~25% performance improvement)

**Update 2019.01.03:**
- [X] Remote control seat heaters 
- [X] List and nativate to nearby superchargers or destination chargers

**Update 2018.12.16:** 
- [X] Set navigation to nearby charging site (Firmware 2018.48 or higher needed)
- [X] Display vehicle option codes

**Update 2018.12.08:** 
- [X] Remotely set your navigation

**Update 2018.12.01:** 
- [X] Schedule software update 
- [X] Toggle media on and off
- [X] Next and previous track 
- [X] Volume up and down

**Update 2018.07.30:** 
- [X] When running in dark mode, also shows google map in dark mode
- [X] Uses CoreLocation to get own GPS coordinates and put on map together with car, 

**Update 2018.04.05:** 
- [X] Shows vehicle information (VIN, color, wheels, type, model, Ludicrous) 
- [X] Provide indication whether vehicle was uncorked or not
- [X] Copy VIN to clipboard
- [X] Hold ALT when clicking command for the command to be executed in Terminal

**Update 2018.03.22:** 
- [X] Added support for opening & closing trunks and chargeport
- [X] Performance optimizations
- [X] Shows live location (Google Maps) in the url. Alternate between Map and Satellite image.

**Update 2018.02.21:** Updated for Tesla firmware 2018.4 (APIv3) 
- [X] Shows battery loss percentage due to cold. 
- [X] Shows rear and front window defroster status 
- [X] Shows battery heating status

**Update 2017.11.01:** (beta) Schedule vehicle charging and heating using OS X Calendar or OS X reminders

**Update 2017.10.23:** Added color support

**Update 2017.10.22:** Added support for remotely: 
- [X] Start keyless driving
- [X] Set charge levels and control charging
- [X] Unlock and lock the vehicle
- [X] Control airco temperature
- [X] Open and close the sunroof
- [X] Flash lights and honk horn



## Credits: 

Greg Glockner teslajson API [code](https://github.com/gglockner/teslajson/).

## Licence: GPL v3

## Installation instructions: 

0. Download [python](http://www.python.org) version 3
1. Ensure you have [xbar](https://github.com/matryer/xbar/releases/latest) installed.
2. Execute 'sudo easy_install tinydb==3.9 keyring pathos googlemaps' in Terminal.app
3. Copy [mytesla.15m.py](mytesla.15m.py) to your xbar plugins folder and chmod +x the file from your terminal in that folder
4. For advanced users: check the configuration options in the mytesla.15m.py file
5. Run xbar (version 2.1.7-beta or higher). 
