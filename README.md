
# MyTesla - OS X Menubar plugin

Displays information regarding your Tesla vehicle in the Mac OS X menubar. Allows you to remotely control your Tesla vehicle as well.

![Imgur](https://i.imgur.com/EafJBW9.jpg)

Supports OS X dark mode:

![Imgur](https://i.imgur.com/740jhtw.jpg)


## Changelog: 

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

Jason Baker's Tesla bitbar [plugin](https://github.com/therippa/tesla-bitbar/).
Greg Glockner teslajson API [code](https://github.com/gglockner/teslajson/).

## Licence: GPL v3

## Installation instructions: 

1. Ensure you have [bitbar](https://github.com/matryer/bitbar/releases/latest) installed.
2. Execute 'sudo easy_install keyring pyicloud pathos pyobjc-framework-CoreLocation' in Terminal.app
3. Ensure your bitbar plugins directory does not have a space in the path (A known bitbar bug)
4. Copy [mytesla.15m.py](mytesla.15m.py) to your bitbar plugins folder and chmod +x the file from your terminal in that folder
5. Run bitbar
