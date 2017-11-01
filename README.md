
# Mytesla - bitbar plugin

A simple plugin that displays information regarding your Tesla vehicle in the Mac OS X menubar. 

Supports OS X Dark Mode 

**Update 2017.11.01:** (beta) Schedule vehicle charging and heating using OS X Calendar or OS X reminders

![Imgur](https://i.imgur.com/IhOCHpL.png)

**Update 2017.10.23:** Added color support

**Update 2017.10.22:** Added support for remotely: 
- [X] Start keyless driving
- [X] Set charge levels and control charging
- [X] Unlock and lock the vehicle
- [X] Control airco temperature
- [X] Open and close the sunroof
- [X] Flash lights and honk horn


Remotely start charging your Tesla:

![Imgur](https://i.imgur.com/X035ZoW.png)

Remotely control the temperature of your Tesla:

![Imgur](https://i.imgur.com/rhPoEUo.png)

Remotely start keyless driving, flash lights and honk horn of your Tesla:

![Imgur](https://i.imgur.com/olexbfV.png)

Remotely unlock & lock your Tesla:

![Imgur](https://i.imgur.com/IYiatlI.png)


Allows you to locate your car in Google Maps and remotely enable / disable your Vehicle Airco.

![Imgur](https://i.imgur.com/14mCiGp.png)


## Credits: 

Jason Baker's Tesla bitbar [plugin](https://github.com/therippa/tesla-bitbar/).
Greg Glockner teslajson API [code](https://github.com/gglockner/teslajson/).

## Licence: GPL v3

## Installation instructions: 

1. Execute in terminal.app before running : sudo easy_install keyring
2. Ensure you have [bitbar](https://github.com/matryer/bitbar/releases/latest) installed.
3. Ensure your bitbar plugins directory does not have a space in the path (A known bitbar bug)
4. Copy [mytesla.15m.py](tesla.15m.py) to your bitbar plugins folder and chmod +x the file from your terminal in that folder
5. Run bitbar
