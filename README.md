
# MyTesla - OS X Menubar plugin

Displays information regarding your Tesla vehicle in the Mac OS X menubar. Allows you to remotely control your Tesla vehicle as well.

Displays live location of your Tesla:

![Imgur](https://i.imgur.com/ypoAWtv.png)

Shows battery loss due to cold & Battery/window heating & defrosting status.

![Imgur](https://i.imgur.com/duiPFSK.png)

Remotely start charging your Tesla:

![Imgur](https://i.imgur.com/yQ9i437.png)

Remotely control the temperature of your Tesla:

![Imgur](https://i.imgur.com/rhPoEUo.png)

Remotely open & close trunk of your Tesla:

![Imgur](https://i.imgur.com/KSjkkMG.png)
![Imgur](https://i.imgur.com/95Vy90E.png)

Remotely start keyless driving, flash lights and honk horn of your Tesla:

![Imgur](https://i.imgur.com/olexbfV.png)

Remotely unlock & lock your Tesla:

![Imgur](https://i.imgur.com/IYiatlI.png)


Allows you to locate your car in Google Maps and remotely enable / disable your Vehicle Airco.

![Imgur](https://i.imgur.com/14mCiGp.png)


Icloud integration: plugin can read from your iCloud calendar or Reminder list and execute specific commands scheduled as specific times. (Plugin has to be running for the execution to happen)

![Imgur](https://i.imgur.com/IhOCHpL.png)

Supports OS X Dark Mode 

## Changelog: 
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

1. Execute in terminal.app before running : sudo easy_install keyring pyicloud pathos
2. Ensure you have [bitbar](https://github.com/matryer/bitbar/releases/latest) installed.
3. Ensure your bitbar plugins directory does not have a space in the path (A known bitbar bug)
4. Copy [mytesla.15m.py](tesla.15m.py) to your bitbar plugins folder and chmod +x the file from your terminal in that folder
5. Run bitbar
