
# Mytesla - bitbar plugin

A simple plugin that displays information regarding your Tesla vehicle in the Mac OS X menubar. 

Supports OS X Dark Mode 

**Update 2017.10.22:** 
- [X] Added support for remotely starting keyless driving.
- [X] Added support for setting charge levels and starting/stopping charging.
- [X] Added support for unlocking and locking the vehicle.
- [X] Added support for controlling airco temperature.
- [X] Added support for opening and closing the sunroof.
- [X] Added support for flashing lights and honking horn.

Remotely start charging your Tesla:

![Imgur](https://i.imgur.com/FZ6DB18.jpg)

Remotely control the temperature of your Tesla:

[Imgur](https://i.imgur.com/qPHZtQo.jpg)

Remotely start keyless driving, flash lights and honk horn of your Tesla:

[Imgur](https://i.imgur.com/GTliktQ.png)

Remotely unlock & lock your Tesla:

[Imgur](https://i.imgur.com/IYiatlI.png)


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
