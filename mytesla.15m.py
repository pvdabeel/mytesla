#!/usr/bin/env PYTHONIOENCODING=UTF-8 /usr/bin/python 
# -*- coding: utf-8 -*-
#
# <bitbar.title>MyTesla</bitbar.title>
# <bitbar.version>Tesla API v14.0</bitbar.version>
# <bitbar.author>pvdabeel@mac.com</bitbar.author>
# <bitbar.author.github>pvdabeel</bitbar.author.github>
# <bitbar.desc>Control your Tesla vehicle from the Mac OS X menubar</bitbar.desc>
# <bitbar.dependencies>python</bitbar.dependencies>
#
# Licence: GPL v3

# Installation instructions: 
# -------------------------- 
# Execute in terminal.app before running : 
#    sudo easy_install keyring
#
# Ensure you have bitbar installed https://github.com/matryer/bitbar/releases/latest
# Ensure your bitbar plugins directory does not have a space in the path (known bitbar bug)
# Copy this file to your bitbar plugins folder and chmod +x the file from your terminal in that folder
# Run bitbar

_DEBUG_ = False 

# Disabled if you don't want your car location to be tracked to a DB

_LOCATION_TRACKING_ = True

# Download high-resolution images from store composer to cache

_COMPOSER_CACHE_HIGH_ = True

# Google map size

_MAP_SIZE_ = '800x600'

# Tesla API returns wrong options code for cars. Put your option codes here 
# to override those provided by Tesla API. You can get your option list by
# logging in to tesla.com. The option codes can be copied from the url used 
# to show the car image in the overview. Use vehicle ID to have different
# override options per vehicle

_OVERRIDE_OPTION_CODES_ = { 47021733346298627 : "BP00,AH00,AD15,GLTL,AU01,X042,APF2,APH2,APPF,X028,BTX6,BS00,CC02,BC0R,CH04,CF00,CW00,COBE,X039,IDCF,X026,DRLH,DU00,AF02,FMP6,FG02,FR01,X007,X011,INBPB,PI01,IX01,X001,LP01,LT3B,MI02,X037,MDLX,DV4W,X025,X003,PMBL,PK00,X031,PF00,X044,TM00,BR00,RCX0,REEU,RFPX,OSSB,X014,S02B,ME02,QLPB,SR04,SP01,X021,SC05,SU01,TP03,TRA1,TR01,TIG2,DSH7,TW01,MT10A,UTAB,WT22,WXP2,YFCC,CPF1" }

import base64
import binascii
import calendar
import datetime
import getpass                                  
import json
import keyring                                  
import math
import os
import random
import re
import requests
import string
import sys
import time

from googlemaps import Client as googleclient
from hashlib    import sha256
from tinydb     import TinyDB, Query
from urlparse   import parse_qs


# Location where to store state files
home         = os.path.expanduser("~")
state_dir    = home+'/.state/mytesla'

if not os.path.exists(state_dir):
    os.makedirs(state_dir)


# Location tracking database
locationdb = TinyDB(state_dir+'/mytesla-locations.json')


# Tesla option codes
tesla_option_codes = { 
"ACL1":"Ludicrous Mode",
"AD02":"NEMA 14-50",
"AD02":"NEMA 14-50", 
"AD04":"European 3-Phase", 
"AD05":"European 3-Phase, IT", 
"AD06":"Schuko (1 phase, 230V 13A)", 
"AD07":"Red IEC309 (3 phase, 400V 16A)", 
"AD08":"Blue Charging Adapter",
"AD09":"Adapter, Swiss (1 phase, 10A)",
"AD10":"Adapter, Denmark (1 phase, 13A)",
"AD11":"Adapter, Italy (1 phase, 13A)",
"AD15":"Adapter",
"AD15":"Adapter, J1772",
"ADPC2":"Type 2 to Type 2 Connector",
"ADPX2":"Type 2 Public Charging Connector", 
"ADX10":"No - Adapter, Denmark (1 phase, 13A)",
"ADX11":"No - Adapter, Italy (1 phase, 13A)",
"ADX4":"No European 3-Phase",
"ADX5":"European 3-Phase, IT",
"ADX6":"No - Adapter, Schuko (1 phase, 13A)",
"ADX7":"No - 3-ph Red IEC309 (3 phase, 16A)",
"ADX8":"Blue IEC309 (1 phase, 230V 32A)", 
"ADX9":"No - Adapter, Swiss (1 phase, 10A)",
"AF00":"No HEPA Filter", 
"AF02":"HEPA Filter",
"AH00":"No Accessory Hitch", 
"APB1":"Autopilot with convenience features",
"APBS":"Autopilot",
"APE1":"Enhanced Autopilot", 
"APF0":"Autopilot Firmware 2.0 Base",
"APF1":"Autopilot Firmware 2.0 Enhanced",
"APF2":"Full Self-Driving Hardware (Activated)",
"APFB":"Full Self-Driving Hardware",
"APH0":"Autopilot 2.0 Hardware", 
"APH1":"Autopilot 1.0 Hardware",
"APH2":"Autopilot 2.0 Hardware", 
"APH3":"Autopilot 2.5 Hardware", 
"APH4":"Autopilot 3.0 Hardware (FSD)", 
"APPA":"Autopilot 1.0 Hardware", 
"APPB":"Enhanced Autopilot", 
"APPF":"Full Self-Driving Capability",
"AU00":"No Audio Package", 
"AU01":"Ultra High Fidelity Sound", 
"AU3P":"Sound Studio Package",
"BC0B":"Tesla Grey Brake Calipers", 
"BC0R":"Tesla Red Brake Calipers",
"BC3B":"Black Brake Calipers, Model 3",
"BC3R":"Performance Brakes",
"BCMB":"Black Brake Calipers", 
"BCYR":"Performance Brakes",
"BG30":"No Badge",
"BG31":"AWD Badge",
"BG32":"Performance AWD Badge",
"BP00":"No Ludicrous", 
"BP01":"Ludicrous Speed Upgrade",
"BP02":"Uncorked Acceleration",
"BR00":"No Battery Firmware Limit", 
"BR03":"Battery Firmware Limit (60kWh)", 
"BR05":"Battery Firmware Limit (75kWh)", 
"BS00":"Blind Spot Sensor Package",
"BS01":"Special Production Flag", 
"BT37":"75 kWh (Model 3)", 
"BT40":"40 kWh", 
"BT60":"60 kWh", 
"BT70":"70 kWh", 
"BT85":"85 kWh", 
"BTX4":"90 kWh", 
"BTX5":"75 kWh", 
"BTX6":"100 kWh", 
"BTX7":"75 kWh", 
"BTX8":"85 kWh", 
"CC01":"Five Seat Interior", 
"CC02":"Six Seat Interior", 
"CC03":"Seven Seat Interior",
"CC04":"Seven Seat Interior", 
"CC12":"Six Seat Interior with Center Console",
"CDM0":"No CHAdeMO Charging Adaptor", 
"CF00":"High amperage charger",
"CF01":"48amp charger",
"CH00":"Standard Charger (40 Amp)", 
"CH01":"Dual Chargers (80 Amp)", 
"CH04":"72 Amp Charger (Model S/X)", 
"CH05":"48 Amp Charger (Model S/X)", 
"CH07":"48 Amp Charger (Model 3)", 
"COBE":"Country: Belgium",
"CODE":"Country: Germany",
"COES":"Country: Spain",
"COFR":"Country: France",
"COL0":"Signature", 
"COL1":"Solid", 
"COL2":"Metallic", 
"COL3":"Tesla Multi-Coat", 
"CONL":"Country: Netherlands",
"COUS":"Country: United States", 
"CPF0":"Standard Connectivity",
"CPF1":"Premium Connectivity",
"CPW1":"20 inch Performance Wheels",
"CW00":"No Cold Weather Package", 
"CW00":"No Weather Package",
"CW02":"Subzero Weather Package", 
"CW02":"Weather Package",
"DA00":"No Autopilot", 
"DA01":"Active Safety (ACC,LDW,SA)", 
"DA02":"Autopilot Convenience Features", 
"DCF0":"Autopilot Convenience Features",
"DRLH":"Left Hand Drive", 
"DRRH":"Right Hand Drive", 
"DSH5":"Dashboard",
"DSH5":"PUR Dash Pad", 
"DSH7":"Alcantara Dashboard Accents", 
"DSHG":"PUR Dash Pad",
"DU00":"Drive Unit - IR", 
"DU01":"Drive Unit - Infineon", 
"DV2W":"Rear-Wheel Drive", 
"DV4W":"All-Wheel Drive", 
"FC3P":"Front Console Front Console (Premium)",
"FG00":"No Exterior Lighting Package", 
"FG01":"Exterior Lighting Package", 
"FG02":"Exterior Lighting Package", 
"FG31":"Fog Lamps",
"FM3B":"Performance Package",
"FM3U":"Acceleration Boost",
"FMP6":"Performance Firmware",
"FR01":"Base Front Row", 
"FR02":"Ventilated Front Seats",
"FR03":"FR03", 
"FR04":"FR04", 
"GLFR":"Assembly",
"HC00":"No Home Charging installation", 
"HC01":"Home Charging Installation", 
"HL31":"Head Lamp",
"HM31":"Teck Package - Homelink",
"HP00":"No HPWC Ordered", 
"HP01":"HPWC Ordered", 
"ID3W":"Model 3 Wood Decor", 
"ID3W":"Wood Decor",
"IDBA":"Dark Ash Wood Decor", 
"IDBO":"Figured Ash Wood Decor", 
"IDCF":"Carbon Fiber Decor", 
"IDHM":"Matte Obeche Wood Decor",
"IDLW":"Lacewood Decor", 
"IDOG":"Gloss Obeche Wood Decor", 
"IDOK":"Oak Decor",
"IDOM":"Matte Obeche Wood Decor", 
"IDPB":"Piano Black Decor", 
"IL31":"Interior Ambient Lighting Interior",
"IN3BB":"All Black Partial Premium Interior", 
"IN3BW":"All White interior",
"IN3PB":"All Black Premium Interior", 
"IN3PW":"All White Premium Interior",
"INB3C":"All Cream interior",
"INBBS":"Black Premium",
"INBBW":"White Interior", 
"INBC3W":"White Interior",
"INBDS":"Black Premium",
"INBFP":"Classic Black", 
"INBFW":"White Premium",
"INBPB":"Premium Black", 
"INBPP":"Black Interior", 
"INBPW":"White Interior",
"INBTB":"Multi-Pattern Black", 
"INBWS":"White Premium",
"INFBP":"Black Premium",
"INLFC":"Cream Premium",
"INLFP":"Black Premium / Light Headliner",
"INLPC":"Cream Interior", 
"INLPP":"Black / Light Headliner", 
"INWPT":"Tan Interior", 
"INYPB":"Black Interior",
"INYPW":"White Interior",
"IVBPP":"Partial Black Interior",
"IVBPP":"All Black Interior", 
"IVBSW":"Ultra White Interior", 
"IVBTB":"All Black Interior", 
"IVLPC":"Vegan Cream", 
"IX00":"No Extended Nappa Leather Trim", 
"IX01":"Extended Nappa Leather Trim", 
"LLP1":"LLP1",
"LLP1":"LLP1", 
"LLP2":"LLP2",
"LP00":"Lighting Package",
"LP01":"Premium Interior Lighting", 
"LT00":"Vegan interior", 
"LT01":"Standard interior", 
"LT1B":"LT1B", 
"LT1B":"Lower Trim",
"LT3W":"LT3W", 
"LT4B":"LT4B", 
"LT4C":"LT4C", 
"LT4W":"LT4W", 
"LT5C":"LT5C", 
"LT5P":"LT5P", 
"LT6P":"LT6P",
"LT6W":"White Base Lower Trim",
"LTPB":"Lower Trim PUR Black",
"LTPW":"Lower Trim PUR White",
"MDL3":"Model 3", 
"MDLS":"Model S", 
"MDLX":"Model X", 
"MDLY":"Model Y",
"ME01":"Memory Seats",
"ME02":"Memory Seats", 
"ME02":"Seat Memory",
"MI00":"1st Generation Production",
"MI00":"2015 Production Refresh", 
"MI00":"2015 production",
"MI01":"2016 Production Refresh", 
"MI01":"2nd Generation Production",
"MI02":"2017 Production Refresh", 
"MI02":"3rd Generation Production",
"MI03":"2018 Production Refresh",
"MI03":"4th Generation Production",
"MI04":"5th Generation Production",
"MR31":"Tech Package - Mirror",
"MS03":"Model S",
"MS04":"Model S",
"MT300":"Unknown",
"MT301":"Standard Range Plus Rear-wheel drive", 
"MT302":"Unknown",
"MT303":"Unknown",
"MT304":"Unknown",
"MT305":"Unknown",
"MT305":"Mid Range Rear-Wheel Drive", 
"MT307":"Unknown",
"MT308":"Unknown",
"MT309":"Unknown",
"MT310":"Unknown",
"MT311":"Unknown",
"MT314":"Unknown",
"MT315":"Unknown",
"MT316":"Unknown",
"MT317":"Unknown",
"MT320":"Unknown",
"MT336":"Unknown",
"MT337":"Unknown",
"MTS01":"Unknown",
"MTS03":"Unknown",
"MTS04":"Unknown",
"MTS05":"Unknown",
"MTS06":"Unknown",
"MTS07":"Unknown",
"MTS08":"Unknown",
"MTS09":"Unknown",
"MTS10":"Unknown",
"MTS11":"Unknown",
"MTX01":"Unknown",
"MTX03":"Unknown",
"MTX04":"Unknown",
"MTX05":"Unknown",
"MTX06":"Unknown",
"MTX07":"Unknown",
"MTX08":"Unknown",
"MTX10":"Unknown",
"MTX11":"Unknown",
"MTY01":"Unknown",
"MTY02":"Unknown",
"MTY03":"Unknown",
"MTY04":"Unknown",
"MTY05":"Unknown",
"OSSB":"Safety Belt Black",
"OSSW":"Safety Belt White",
"P85D":"P85D", 
"PA00":"No Paint Armor", 
"PBCW":"Catalina White", 
"PBCW":"Solid White Color",
"PBSB":"Solid Black Color",
"PBT8":"Performance 85kWh", 
"PBT85":"Performance 85kWh",
"PC30":"No Performance Chassis",
"PC31":"Performance Chassis",
"PF00":"No Performance Legacy Package", 
"PF01":"Performance Legacy Package", 
"PI00":"No Premium Interior", 
"PI01":"Premium Upgrades Package", 
"PK00":"No Parking Sensors Legacy", 
"PK01":"Parking Sensors",
"PL30":"No Aluminum Pedal",
"PL31":"Performance Pedals",
"PMAB":"Anza Brown Metallic", 
"PMBL":"Obsidian Black Multi-Coat Color",
"PMMB":"Monterey Blue Metallic Color",
"PMMR":"Multi-Coat Red", 
"PMNG":"Midnight Silver Metallic Color",
"PMSG":"Sequoia Green Metallic Color", 
"PMSS":"San Simeon Silver Metallic Color",
"PMTG":"Dolphin Grey Metallic Color",
"PPMR":"Muir Red Multi-Coat", 
"PPSB":"Deep Blue Metallic Color",
"PPSR":"Signature Red Color",
"PPSW":"Shasta Pearl White Multi-Coat Color", 
"PPTI":"Titanium Metallic Color", 
"PRM30":"Partial Premium Interior", 
"PRM31":"Premium Interior", 
"PRM3S":"Unknown",
"PRMY1":"Unknown",
"PS00":"No Parcel Shelf", 
"PS01":"Parcel Shelf", 
"PSP14":"Four Years Prepaid Service",
"PSPX4":"No Four-year prepaid",
"PX00":"No Performance Plus Package", 
"PX01":"Performance Plus", 
"PX4D":"90 kWh Performance",
"PX6D":"Zero to 60 in 2.5 sec", 
"QLBS":"Black Premium Interior",
"QLFC":"Cream Premium Interior",
"QLFP":"Black Premium Interior",
"QLFW":"White Premium Interior",
"QLPB":"Black Premium Interior",
"QLPW":"White Premium Interior",
"QLWS":"White Premium Interior",
"QNET":"Tan NextGen", 
"QPBT":"Black Textile Interior",
"QPMP":"Black seats", 
"QTBS":"Black Premium Interior",
"QTBW":"White Premium Seats", 
"QTFC":"Cream Premium Interior",
"QTFP":"Black Premium Interior",
"QTFW":"White Premium Interior",
"QTPB":"Black Leather Tesla Premium Seats",
"QTPC":"Cream Premium Seats", 
"QTPP":"Black Premium Seats", 
"QTPT":"Tan Premium Seats", 
"QTTB":"Black Textile Interior",
"QTTB":"Multi-Pattern Black Seats", 
"QTWS":"White Premium Interior",
"QVBM":"Multi-Pattern Black Seats", 
"QVPC":"Vegan Cream Seats", 
"QVPP":"Vegan Cream Seats", 
"QVSW":"White Tesla Seats", 
"QXMB":"Black Leather Seat",
"RCX0":"No Rear Console", 
"RCX1":"Rear Console",
"REEU":"Region: Europe", 
"RENA":"Region: North America", 
"RENC":"Region: Canada", 
"RF3G":"Model 3 Glass Roof", 
"RFBC":"Body Color Roof", 
"RFBK":"Black Roof", 
"RFFG":"Glass Roof", 
"RFP0":"All Glass Panoramic Roof", 
"RFP2":"Sunroof",
"RFPO":"All Glass Panoramic Roof",
"RFPX":"Glass Roof",
"RFPX":"Model X Roof", 
"RS3H":"Second Row Seat Rear Seats (Heated)",
"RSF1":"Rear Heated Seats",
"RU00":"No Range Upgrade",
"S01B":"Black Textile Seats",
"S02B":"Seat",
"S02P":"S02P",
"S02W":"White Seats",
"S07W":"White Seats",
"S31B":"S31B",
"S32C":"S32C", 
"S32P":"S32P", 
"S32W":"S32W", 
"S3PB":"Seat Black PUR Premium Seats",
"S3PW":"Seat White PUR Premium Seats",
"SA3P":"Seat Adjustment - Power",
"SC00":"No Supercharging", 
"SC01":"Supercharging Enabled", 
"SC04":"Pay Per Use Supercharging", 
"SC05":"Free Supercharging",
"SC05":"Free Supercharging", 
"SLR0":"No Rear Spoiler",
"SLR1":"Carbon Fibre Spoiler",
"SP00":"No Security Package", 
"SP01":"Security Package",
"SPT31":"Unknown",
"SPTY1":"Unknown",
"SR01":"Standard 2nd row", 
"SR06":"Seven Seat Interior", 
"SR07":"Standard 2nd row", 
"ST00":"Non-leather Steering Wheel", 
"ST01":"Non-heated Leather Steering Wheel", 
"ST31":"Steering Wheel",
"STCP":"Steering Wheel",
"STY5S":"Unknown",
"STY7S":"Unknown",
"SU00":"Standard Suspension", 
"SU01":"Smart Air Suspension", 
"SU03":"Suspension Update",
"SU3C":"Coil Spring Suspension",
"T3MA":"Tires M3",
"TIC4":"All-Season Tires", 
"TIG2":"Summer Tires",
"TIM7":"Summer Tires",
"TIMP":"Tires",
"TIP0":"All-season Tires",
"TM00":"General Production Trim", 
"TM02":"General Production Signature Trim",
"TM0A":"ALPHA PRE-PRODUCTION NON-SALEABLE", 
"TM0B":"BETA PRE-PRODUCTION NON-SALEABLE", 
"TM0C":"PRE-PRODUCTION SALEABLE", 
"TP01":"No Technology Package",
"TP01":"Tech Package - No Autopilot", 
"TP02":"Tech Package with Autopilot", 
"TP03":"Tech Package with Enhanced Autopilot", 
"TR00":"No Rear Facing Seats",
"TR01":"Third Row Seating",
"TRA1":"Third Row HVAC",
"TW00":"No Tow Package",
"TW01":"Tow Package",
"UM01":"Universal Mobile Charger - US Port (Single)", 
"USSB":"US Safety Kit Black",
"USSW":"US Safety Kit White",
"UT3P":"Suede Grey Premium Headliner",
"UTAB":"Black Alcantara Headliner", 
"UTAW":"Light Headliner", 
"UTMF":"Headliner",
"UTPB":"Dark Headliner", 
"UTSB":"Dark Headliner", 
"UTZW":"Light Headliner",
"W32D":"20 inch Gray Performance Wheels",
"W32P":"20 inch Performance Wheels",
"W38B":"18 inch Aero Wheels", 
"W39B":"19 inch Sport Wheels", 
"WR00":"No Wrap",
"WS10":"21 inch Arachnid Wheels",
"WS90":"19 inch Tempest Wheels",
"WT19":"19 inch Wheels",
"WT20":"20 inch Silver Slipstream Wheels",
"WT22":"22 inch Silver Turbine Wheels",
"WTAB":"21 inch Black Arachnid Wheels",
"WTAS":"19 inch Silver Slipstream Wheels", 
"WTDS":"19 inch Sonic Carbon Slipstream Wheels",
"WTHX":"20 inch Turbine Wheels",
"WTNN":"20 inch Nokian Winter Tires (non-studded)",
"WTNS":"20 inch Nokian Winter Tires (studded)",
"WTP2":"20 inch Pirelli Winter Tires",
"WTSC":"20 inch Sonic Carbon Wheels",
"WTSD":"20 inch Two-Tone Slipstream Wheels",
"WTSG":"21 inch Turbine Wheels", 
"WTSP":"21 inch Turbine Wheels",
"WTSS":"21 inch Silver Turbine Wheels",
"WTTB":"19 inch Cyclone Wheels", 
"WTTC":"21 inch Sonic Carbon Twin Turbine Wheels",
"WTTG":"19 inch Cyclone Wheels",
"WTUT":"22 inch Onyx Black Turbine Wheels",
"WTW2":"19 inch Nokian Winter Wheel Set",
"WTW3":"19 inch Pirelli Winter Wheel Set",
"WTW4":"19 inch Winter Tire Set", 
"WTW5":"21 inch Winter Tire Set", 
"WTW6":"19 inch Nokian Winter Tires (studded)",
"WTW7":"19 inch Nokian Winter Tires (non-studded)",
"WTW8":"19 inch Pirelli Winter Tires",
"WTX1":"19 inch Michelin Primacy Tire Upgrade", 
"WX00":"20 inch Cyberstream Wheels",
"WX20":"22 inch Turbine Wheels",
"WXNN":"No 20 inch Nokian Winter Tires (non-studded)",
"WXNS":"No 20 inch Nokian Winter Tires (studded)",
"WXP2":"No 20 inch Pirelli Winter Tires",
"WXW2":"No 19 inch Wheels with Nokian Winter Tyres",
"WXW3":"No 19 inch Wheels with Pirelli Winter Tyres",
"WXW4":"No 19 inch Winter Tire Set", 
"WXW4":"No 19 inch Winter Tyre Set",
"WXW5":"No 21 inch Winter Tire Set", 
"WXW6":"No 19 inch Nokian Winter Tires (studded)",
"WXW7":"No 19 inch Nokian Winter Tires (non-studded)",
"WXW8":"No 19 inch Pirelli Winter Tires",
"WY18B":"Unknown",
"WY19B":"Unknown",
"WY20P":"Unknown",
"X001":"Power Liftgate", 
"X002":"Manual Liftgate",
"X003":"Navigation", 
"X004":"No Navigation", 
"X007":"Daytime running lights", 
"X010":"Base Mirrors", 
"X011":"Homelink", 
"X012":"No Homelink", 
"X013":"Satellite Radio", 
"X014":"No Satellite Radio", 
"X019":"Carbon Fibre Spoiler",
"X020":"No Performance Exterior", 
"X021":"No Active Spoiler",
"X024":"Performance Package", 
"X025":"No Performance Package", 
"X026":"Door handle",
"X027":"Lighted Door Handles", 
"X028":"Battery Badge", 
"X029":"No Battery Badge", 
"X030":"No Passive Entry Pkg", 
"X031":"Keyless Entry", 
"X037":"Powerfolding Mirrors", 
"X039":"DAB Radio", 
"X040":"No DAB Radio", 
"X041":"No Auto Presenting Door",
"X042":"Auto Presenting door", 
"X043":"No Phone Dock Kit", 
"X044":"Phone Dock Kit", 
"YF00":"No Yacht Floor", 
"YF01":"Matching Yacht Floor", 
"YFCC":"Center Console",
"YFFC":"Integrated Center Console" }


# Nice ANSI colors
CEND    = '\33[0m'
CRED    = '\33[31m'
CGREEN  = '\33[32m'
CYELLOW = '\33[33m'
CBLUE   = '\33[34m'

# Support for OS X Dark Mode
DARK_MODE=os.getenv('BitBarDarkMode',0)


class TeslaAuthenticator(object):
    """Manages Tesla authentication. Supports MFA"""

    client = {
        "id"                    : "81527cff06843c8634fdc09e8ac0abefb46ac849f38fe1e431c2ef2106796384",
        "secret"                : "c7257eb71a564034f9419ee651c7d0e5f7aa6bfbd18bafb5c5c033b093bb2fa3",
    } 

    headers = {
        "User-Agent"            : "github.com/pvdabeel/mytesla",
        "x-tesla-user-agent"    : "github.com/pvdabeel/mytesla",
        "X-Requested-With"      : "com.teslamotors.tesla" 
    }

    credentials = {}


    def __init__(self):
        return None 


    def dialog_username(self):
        print ('Enter your tesla.com username:')
        return raw_input()
    
    def dialog_password(self):
        print ('Enter your tesla.com password:')
        return getpass.getpass()
 
    def dialog_mfa(self):
        print ('Enter multi-factor authentication code:')                                   
        return raw_input()  


    def generate_challenge(self,verifier):
        return base64urlencode(sha256(verifier).hexdigest())


    def perform_login(self): 

        session         = requests.Session()
        
        state           = random_string(12)
        code_verifier   = random_string(86)
        code_challenge  = self.generate_challenge(code_verifier) 
 
        #----------------------------#
        # STEP 1: Get the login page #
        #----------------------------#

        query = {
            "client_id"             : "ownerapi",
            "code_challenge"        : code_challenge,
            "code_challenge_method" : "S256",
            "redirect_uri"          : "https://auth.tesla.com/void/callback",
            "response_type"         : "code",
            "scope"                 : "openid email offline_access",
            "state"                 : state }

        response        = session.get("https://auth.tesla.com/oauth2/v3/authorize", params=query, headers=self.headers)

        if not response.status_code == requests.codes.ok:
            raise Exception('Loginpage not available. Please try again later.')
       

        #--------------------------------------#
        # STEP 2: Obtain an authorization code #
        #--------------------------------------#

        email           = self.dialog_username()
        password        = self.dialog_password()

        csrf            = re.search(r'name="_csrf".+value="([^"]+)"', response.text).group(1)
        transaction_id  = re.search(r'name="transaction_id".+value="([^"]+)"', response.text).group(1)
 
        formdata = {
            "_csrf"                 : csrf,
            "_phase"                : "authenticate",
            "_process"              : "1",
            "transaction_id"        : transaction_id,
            "cancel"                : "",
            "identity"              : email,
            "credential"            : password } 
      
        response        = session.post("https://auth.tesla.com/oauth2/v3/authorize", params=query, data=formdata, headers=self.headers, allow_redirects=False)

        password        = ''

        if response.status_code == 401:
            raise Exception('Authentication failed: wrong username or password')
       

        #--------------------------------------#
        # STEP 2a: Multi-Factor authentication #
        #--------------------------------------#

        is_mfa = True if response.status_code == 200 and "/mfa/verify" in response.text else False

        if is_mfa:

            # Get MFA Factor
            response    = session.get("https://auth.tesla.com/oauth2/v3/authorize/mfa/factors?transaction_id="+transaction_id, headers=self.headers)
            factor_id   = response.json()["data"][0]["id"]
            
            # Request MFA code from user
            mfa_code    = self.dialog_mfa()  

            # Perform MFA authentication
            mfa_data    = {"transaction_id": transaction_id, "factor_id": factor_id, "passcode": mfa_code}
            response    = session.post("https://auth.tesla.com/oauth2/v3/authorize/mfa/verify", json=mfa_data)

            if "error" in response.text or not response.json()["data"]["approved"] or not response.json()["data"]["valid"]:
                raise Exception('Authentication failed: wrong MFA code') 

            mfa_data    = {"transaction_id": transaction_id}
            response    = session.post("https://auth.tesla.com/oauth2/v3/authorize",params=query, data=mfa_data, headers=self.headers, allow_redirects=False)
       

        if not response.headers.get("location"):
            raise Exception('Unable to log in at this time. Please try again later.')

        auth_code       = parse_qs(response.headers["location"])["https://auth.tesla.com/void/callback?code"]


        #---------------------------------------------#
        # STEP 3: Exchange auth code for bearer token #
        #---------------------------------------------#

        payload = {
            "grant_type"            : "authorization_code",
            "client_id"             : "ownerapi",
            "code"                  : auth_code,
            "code_verifier"         : code_verifier,
            "redirect_uri"          : "https://auth.tesla.com/void/callback" }
       
        response        = session.post("https://auth.tesla.com/oauth2/v3/token", json=payload, headers=self.headers)
        
        resp_json       = response.json()
        refresh_token   = resp_json["refresh_token"]
        bearer_token    = resp_json["access_token"]


        #------------------------------------------------#
        # STEP 4: Exchange bearer token for access token #
        #------------------------------------------------#

        self.headers["authorization"] = "bearer " + bearer_token

        payload = {
            "grant_type"            : "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "client_id"             : self.client['id'],
            "client_secret"         : self.client['secret'] }

        response         = session.post("https://owner-api.teslamotors.com/oauth/token", json=payload, headers=self.headers)

        self.credentials = response.json()

        self.save_credentials()


    def load_credentials(self):
        self.credentials    = { 
            "access_token"  : keyring.get_password("mytesla-bitbar","access_token"),
            "expires_in"    : keyring.get_password("mytesla-bitbar","expires_in"),
            "refresh_token" : keyring.get_password("mytesla-bitbar","refresh_token"),
            "created_at"    : keyring.get_password("mytesla-bitbar","created_at"),
            "token_type"    : "bearer" }

    def save_credentials(self):
        keyring.set_password("mytesla-bitbar","access_token",self.credentials["access_token"])
        keyring.set_password("mytesla-bitbar","expires_in",self.credentials["expires_in"])
        keyring.set_password("mytesla-bitbar","refresh_token",self.credentials["refresh_token"])
        keyring.set_password("mytesla-bitbar","created_at",self.credentials["created_at"])


    def refresh_credentials(self):

        payload = {
            "grant_type"            : "refresh_token",
            "client_id"             : "ownerapi",    
            "refresh_token"         : self.credentials["refresh_token"],
            "scope"                 : "openid email offline_access" }

        session         = requests.Session()
    
        response        = session.post("https://auth.tesla.com/oauth2/v3/token", json=payload, headers=self.headers)

        resp_json       = resp.json()
        refresh_token   = resp_json["refresh_token"]
        bearer_token    = resp_json["access_token"]
        
        self.headers["authorization"] = "bearer " + bearer_token

        payload = {                                                             
            "grant_type"            : "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "client_id"             : self.client['id'] }
                                                                                
        response         = session.post("https://owner-api.teslamotors.com/oauth/token", json=payload, headers=self.headers)
                                                                                
        self.credentials = resp.json()                                                 
                                                                                
        self.save_credentials()



class TeslaConnection(object):

    headers = {
        "User-Agent"            : "github.com/pvdabeel/mytesla",
        "x-tesla-user-agent"    : "github.com/pvdabeel/mytesla",
        "X-Requested-With"      : "com.teslamotors.tesla" 
    }

    
    def __init__(self,access_token): 
        self.headers["authorization"] = "bearer " + access_token
        self.session = requests.Session()


    def vehicles(self):
        return [TeslaVehicle(v, self) for v in self.get('vehicles')['response']]

    def appointments(self):
        return self.get('users/service_scheduling_data')['response']

     
    def get(self, command):
        return self.session.get("https://owner-api.teslamotors.com/api/1/"+command, headers=self.headers).json()

    def post(self, command, data={}):
        return self.session.post("https://owner-api.teslamotors.com/api/1/"+command, data=data, headers=self.headers).json()



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
    

    def vehicle_data(self):
        """Get vehicle data"""
        if self.asleep(): 
            try:
                # Vehicle asleep, getting info from local cache
                Q = Query()
                result = locationdb.search(Q.vehicle==self['id'])[-1]['vehicle_data']
                return result['response']
            except:
                # Local cache failed, waking up vehicle
                self.post('wake_up')
                time.sleep(30)
                pass
        # Retrieve the vehicle data from Tesla API
        result = self.get('vehicle_data')
        # Updating local cache
        if _LOCATION_TRACKING_:
            locationdb.insert({'vehicle':self['id'],'date':str(datetime.datetime.now()),'vehicle_data':result})
        else:
            locationdb.purge()
            locationdb.insert({'vehicle':self['id'],'date':str(datetime.datetime.now()),'vehicle_data':result})
        return result['response']
    

    def data_request(self, name):
        """Get vehicle data"""
        result = self.get('data_request/%s' % name)
        return result['response']
    

    def asleep(self):
        """Check if vehichle is asleep"""
        return self['state'] == "asleep"

    def wake_up(self):
        """Wake the vehicle"""
        return self.post('wake_up')
  

    def mobile_access(self):
        """Check if vehicle mobile access is enabled"""
        result = self.get('mobile_enabled')
        return result['response']


    def nearby_charging_sites(self):
        """Return list of nearby chargers"""
        try: # Firmware 2018.48 or higher needed
           return self.get('nearby_charging_sites')['response']
        except: 
           return []


    def model_short(self,model):
        """Return the short name for the vehicle model"""
        switcher = { 'modelx':'mx', 'models':'ms', 'model3':'m3'} 
        return switcher.get(model,model)

    def option_codes(self): 
        """Tesla does not return the option codes correctly, so we read them from the override parameter in this file"""
        try: 
            return _OVERRIDE_OPTION_CODES_[self['id']]
        except: 
            return self['option_codes'] 


    def command(self, name, data={}):
        """Run the command for the vehicle"""
        return self.post('command/%s' % name, data)

    def get(self, command):
        """Utility command to get data from API"""
        return self.connection.get('vehicles/%i/%s' % (self['id'], command))

    def post(self, command, data={}):
        """Utility command to post data to API"""
        return self.connection.post('vehicles/%i/%s' % (self['id'], command), data)

 
    def compose_url(self, model, size=2048, view='STUD_SIDE', background='1'):
        """Returns composed image url representing the car"""
        return 'https://static-assets.tesla.com/v1/compositor/?model='+self.model_short(model)+'&view='+view+'&size='+str(size)+'&options='+self.option_codes()+'&bkba_opt='+str(background)+'&context=design_studio_desktop'
        

    def compose_image(self, model, size=512, view='STUD_SIDE', background='1'):
        """Returns composed image representing the car"""
        try:
            with open(state_dir+'/mytesla-composed-'+str(self['vehicle_id'])+'-'+str(size)+'-'+str(view)+'-'+str(background)+'.png') as composed_img_cache:
                composed_img = composed_img_cache.read()
                composed_img_cache.close()
                return base64.b64encode(composed_img)
        except:
            my_headers = {'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Upgrade-Insecure-Requests': '1', 'DNT': '1', 'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36'} 
            composed_url = self.compose_url(model,size,view,background)
            composed_img = requests.get(composed_url,headers=my_headers)
            if (len(composed_img.content) > 0):
                with open(state_dir+'/mytesla-composed-'+str(self['vehicle_id'])+'-'+str(size)+'-'+view+'-'+str(background)+'.png','w') as composed_img_cache:
                   composed_img_cache.write(composed_img.content)
                   composed_img_cache.close()
            return base64.b64encode(composed_img.content)


        
# Create a random string
def random_string(size):
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(size))

# Base64 urlencode function
def base64urlencode(arg):
    stripped = arg.split("=")[0]
    filtered = stripped.replace("+", "-").replace("/", "_")
    return filtered

# Base64 urldecode function
def base64urldecode(arg):
    filtered = arg.replace("-", "+").replace("_", "/")
    padded = filtered + "=" * ((len(filtered) * -1) % 4)
    return padded

# Convertor for temperature
def convert_temp(temp_unit,temp):
    if temp_unit == 'F':
        return (temp * 1.8) + 32
    else:
        return temp

# Convertor for distance
def convert_distance(distance_unit,distance):
    if distance_unit == 'km':
        return math.ceil(distance * 160.9344)/100
    else:
        return distance

# Pretty print door state
def door_state(dooropen):
    if bool(dooropen):
        return CRED + 'Open' + CEND + ' '
    else:
        return CGREEN + 'Closed' + CEND + ' '

# Pretty print window state
def window_state(windowopen):
    if (windowopen == 0):
        return CGREEN + 'Closed' + CEND + ' '
    elif (windowopen == 1):
        return CYELLOW + 'Vent' + CEND + ' '
    else: 
        return CRED + 'Open' + CEND + ' '

# Pretty print battery loss due to cold
def cold_state(percentage):
    if (percentage != 0):
        return CBLUE + '(-' + str(percentage) + '%)' + CEND
    else:
        return ''

# Pretty print seat heater setting
def seat_state(temp):
    if (temp == 0):
        return 'Off'
    else:
        return CRED  + 'On, level: ' + str(temp) + CEND

# Pretty print charge port state 
def port_state(portopen,engaged):
    if bool(portopen):
        if (engaged == 'Engaged'):
           return CYELLOW + 'In use' + CEND
        else:
           return CRED + 'Open' + CEND
    else:
        return CGREEN + 'Closed' + CEND
        
# Pretty print car lock state 
def lock_state(locked):
    if bool(locked):
        return CGREEN + 'Locked' + CEND
    else:
        return CRED + 'Unlocked' + CEND

# Pretty print sentry mode state 
def sentry_state(state):
    if bool(state):
        return CGREEN + '(Sentry On)'+ CEND
    else: 
        return CRED + '(Sentry Off)' + CEND

# Pretty print sleeping time 
def sleeping_since(time=False):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    from datetime import datetime
    now = datetime.now()
    if type(time) is int:
        diff = now - datetime.fromtimestamp(time/1000)
    elif isinstance(time,datetime):
        diff = now - time
    elif not time:
        diff = now - now
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return 'Jetlagged'

    if day_diff == 0:
        if second_diff < 10:
            return "Started sleeping a few moments ago"
        if second_diff < 60:
            return "Started sleeping "+str(second_diff) + " seconds ago"
        if second_diff < 120:
            return "Started sleeping a minute ago"
        if second_diff < 3600:
            return "Sleeping since "+str(second_diff / 60) + " minutes ago"
        if second_diff < 7200:
            return "Sleeping since an hour ago"
        if second_diff < 86400:
            return "Sleeping since "+ str(second_diff / 3600) + " hours ago"
    if day_diff == 1:
        return "Sleeping since Yesterday"
    if day_diff < 7:
        return "Sleeping since "+sstr(day_diff) + " days"
    if day_diff < 31:
        return "Sleeping since "+str(day_diff / 7) + " weeks"
    if day_diff < 365:
        return "Sleeping since "+str(day_diff / 30) + " months"
    return "Sleeping since "+str(day_diff / 365) + " year"

# Pretty print charge time left in hours & minutes
def calculate_time_left(hours_to_full_charge):
    mins_to_full_charge = hours_to_full_charge * 60
  
    remaining_hours = int(mins_to_full_charge // 60)
    remaining_minutes = mins_to_full_charge - (remaining_hours * 60)
  
    time_left = ""

    if (mins_to_full_charge == 0):
        return 'Calculating time remaining'

    if (remaining_hours == 0):
       time_left = '\t%d mins left' % (remaining_minutes)
    elif (remaining_hours == 1):
       time_left = '\t1 hour %d  mins left' % (remaining_minutes)
    elif (remaining_minutes == 0):
       time_left = '\t%d hours left' % (remaining_hours)
    elif (remaining_minutes == 1):
       time_left = '\t%d hours 1 min left' % (remaining_hours)
    else:
       time_left = '\t%d hours %d mins left' % (remaining_hours, remaining_minutes)

    return time_left

# Function to retrieve goole map & sat images for a given location
def retrieve_google_maps(latitude,longitude):
   todayDate = datetime.date.today()
    
   try:
      with open(state_dir+'/mytesla-location-map-'+todayDate.strftime("%Y%m")+'-'+latitude+'-'+longitude+'.png') as location_map:
         my_img1 = base64.b64encode(location_map.read())
         location_map.close()
      with open(state_dir+'/mytesla-location-sat-'+todayDate.strftime("%Y%m")+'-'+latitude+'-'+longitude+'.png') as location_sat:
         my_img2 = base64.b64encode(location_sat.read())
         location_sat.close()
   except: 
      with open(state_dir+'/mytesla-location-map-'+todayDate.strftime("%Y%m")+'-'+latitude+'-'+longitude+'.png','w') as location_map, open(state_dir+'/mytesla-location-sat-'+todayDate.strftime("%Y%m")+'-'+latitude+'-'+longitude+'.png','w') as location_sat:
         my_google_key = '&key=AIzaSyBrgHowqRH-ewRCNrhAgmK7EtFsuZCdXwk'
         my_google_dark_style = ''
                
         if bool(DARK_MODE):
            my_google_dark_style = '&style=feature:all|element:labels|visibility:on&style=feature:all|element:labels.text.fill|saturation:36|color:0x000000|lightness:40&style=feature:all|element:labels.text.stroke|visibility:on|color:0x000000|lightness:16&style=feature:all|element:labels.icon|visibility:off&style=feature:administrative|element:geometry.fill|color:0x000000|lightness:20&style=feature:administrative|element:geometry.stroke|color:0x000000|lightness:17|weight:1.2&style=feature:administrative.country|element:labels.text.fill|color:0x838383&style=feature:administrative.locality|element:labels.text.fill|color:0xc4c4c4&style=feature:administrative.neighborhood|element:labels.text.fill|color:0xaaaaaa&style=feature:landscape|element:geometry|color:0x000000|lightness:20&style=feature:poi|element:geometry|color:0x000000|lightness:21|visibility:on&style=feature:poi.business|element:geometry|visibility:on&style=feature:road.highway|element:geometry.fill|color:0x6e6e6e|lightness:0&style=feature:road.highway|element:geometry.stroke|visibility:off&style=feature:road.highway|element:labels.text.fill|color:0xffffff&style=feature:road.arterial|element:geometry|color:0x000000|lightness:18&style=feature:road.arterial|element:geometry.fill|color:0x575757&style=feature:road.arterial|element:labels.text.fill|color:0xffffff&style=feature:road.arterial|element:labels.text.stroke|color:0x2c2c2c&style=feature:road.local|element:geometry|color:0x000000|lightness:16&style=feature:road.local|element:labels.text.fill|color:0x999999&style=feature:transit|element:geometry|color:0x000000|lightness:19&style=feature:water|element:geometry|color:0x000000|lightness:17'
       
         my_google_size = '&size='+_MAP_SIZE_
         my_google_zoom = '&zoom=17'
         my_url1 ='https://maps.googleapis.com/maps/api/staticmap?center='+latitude+','+longitude+my_google_key+my_google_dark_style+my_google_zoom+my_google_size+'&markers=color:red%7C'+latitude+','+longitude
         my_url2 ='https://maps.googleapis.com/maps/api/staticmap?center='+latitude+','+longitude+my_google_key+my_google_zoom+my_google_size+'&maptype=hybrid&markers=color:red%7C'+latitude+','+longitude
         s = requests.Session()
         my_cnt1 = s.get(my_url1).content
         my_cnt2 = s.get(my_url2).content
         my_img1 = base64.b64encode(my_cnt1)
         my_img2 = base64.b64encode(my_cnt2)
         location_map.write(my_cnt1)
         location_sat.write(my_cnt2)
         location_map.close()
         location_sat.close()
   return [my_img1,my_img2]

# Logo for both dark mode and regular mode
def app_print_logo():
    if bool(DARK_MODE):
        print ('|image=iVBORw0KGgoAAAANSUhEUgAAABYAAAAWCAYAAADEtGw7AAAAAXNSR0IArs4c6QAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAFU2lUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iWE1QIENvcmUgNS40LjAiPgogICA8cmRmOlJERiB4bWxuczpyZGY9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkvMDIvMjItcmRmLXN5bnRheC1ucyMiPgogICAgICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIgogICAgICAgICAgICB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iCiAgICAgICAgICAgIHhtbG5zOnhtcE1NPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvbW0vIgogICAgICAgICAgICB4bWxuczpzdFJlZj0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL3NUeXBlL1Jlc291cmNlUmVmIyIKICAgICAgICAgICAgeG1sbnM6dGlmZj0iaHR0cDovL25zLmFkb2JlLmNvbS90aWZmLzEuMC8iCiAgICAgICAgICAgIHhtbG5zOnhtcD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wLyI+CiAgICAgICAgIDxkYzp0aXRsZT4KICAgICAgICAgICAgPHJkZjpBbHQ+CiAgICAgICAgICAgICAgIDxyZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+dGVzbGFfVF9CVzwvcmRmOmxpPgogICAgICAgICAgICA8L3JkZjpBbHQ+CiAgICAgICAgIDwvZGM6dGl0bGU+CiAgICAgICAgIDx4bXBNTTpEZXJpdmVkRnJvbSByZGY6cGFyc2VUeXBlPSJSZXNvdXJjZSI+CiAgICAgICAgICAgIDxzdFJlZjppbnN0YW5jZUlEPnhtcC5paWQ6NjFlOGM3OTktZDk2Mi00Y2JlLWFiNDItY2FmYjlmOTYxY2VlPC9zdFJlZjppbnN0YW5jZUlEPgogICAgICAgICAgICA8c3RSZWY6ZG9jdW1lbnRJRD54bXAuZGlkOjYxZThjNzk5LWQ5NjItNGNiZS1hYjQyLWNhZmI5Zjk2MWNlZTwvc3RSZWY6ZG9jdW1lbnRJRD4KICAgICAgICAgPC94bXBNTTpEZXJpdmVkRnJvbT4KICAgICAgICAgPHhtcE1NOkRvY3VtZW50SUQ+eG1wLmRpZDpCNkM1NEUzNDlERTAxMUU3QTRFNEExMTMwMUY5QkJBNTwveG1wTU06RG9jdW1lbnRJRD4KICAgICAgICAgPHhtcE1NOkluc3RhbmNlSUQ+eG1wLmlpZDpCNkM1NEUzMzlERTAxMUU3QTRFNEExMTMwMUY5QkJBNTwveG1wTU06SW5zdGFuY2VJRD4KICAgICAgICAgPHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD51dWlkOjI3MzY3NDg0MTg2QkRGMTE5NjZBQjM5RDc2MkZFOTlGPC94bXBNTTpPcmlnaW5hbERvY3VtZW50SUQ+CiAgICAgICAgIDx0aWZmOk9yaWVudGF0aW9uPjE8L3RpZmY6T3JpZW50YXRpb24+CiAgICAgICAgIDx4bXA6Q3JlYXRvclRvb2w+QWRvYmUgSWxsdXN0cmF0b3IgQ0MgMjAxNSAoTWFjaW50b3NoKTwveG1wOkNyZWF0b3JUb29sPgogICAgICA8L3JkZjpEZXNjcmlwdGlvbj4KICAgPC9yZGY6UkRGPgo8L3g6eG1wbWV0YT4KI5WHQwAAANVJREFUOBHtU8ENwjAMTBADdJRuACMwUjdgBEaAEcoEgQlSJmCEcJYS6VzlYVfiV0snn6/na5SqIez17xuIvReUUi7QT8AInIFezRBfwDPG+OgZlIbQL5BrT7Xf0YcK4eJpz7LMKqQ3wDSJEViXBArWJd6pl6U0mORkVyADchUBXVXVRogZuAGDCrEOWExAq2TZO1hM8CzkY06yptbgN60xJ1lTa/BMa8xJ1tQavNAac5I30vblrOtHqxG+2eENnmD5fc3lCf6YU2H0BLtO7DnE7t12Az8xb74dVbfynwAAAABJRU5ErkJggg==')
    else:
        print ('|image=iVBORw0KGgoAAAANSUhEUgAAABYAAAAWCAYAAADEtGw7AAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAA/xpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADw/eHBhY2tldCBiZWdpbj0i77u/IiBpZD0iVzVNME1wQ2VoaUh6cmVTek5UY3prYzlkIj8+IDx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IkFkb2JlIFhNUCBDb3JlIDUuMy1jMDExIDY2LjE0NTY2MSwgMjAxMi8wMi8wNi0xNDo1NjoyNyAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0UmVmPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VSZWYjIiB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8iIHhtbG5zOmRjPSJodHRwOi8vcHVybC5vcmcvZGMvZWxlbWVudHMvMS4xLyIgeG1wTU06T3JpZ2luYWxEb2N1bWVudElEPSJ1dWlkOjI3MzY3NDg0MTg2QkRGMTE5NjZBQjM5RDc2MkZFOTlGIiB4bXBNTTpEb2N1bWVudElEPSJ4bXAuZGlkOkI2QzU0RTM0OURFMDExRTdBNEU0QTExMzAxRjlCQkE1IiB4bXBNTTpJbnN0YW5jZUlEPSJ4bXAuaWlkOkI2QzU0RTMzOURFMDExRTdBNEU0QTExMzAxRjlCQkE1IiB4bXA6Q3JlYXRvclRvb2w9IkFkb2JlIElsbHVzdHJhdG9yIENDIDIwMTUgKE1hY2ludG9zaCkiPiA8eG1wTU06RGVyaXZlZEZyb20gc3RSZWY6aW5zdGFuY2VJRD0ieG1wLmlpZDo2MWU4Yzc5OS1kOTYyLTRjYmUtYWI0Mi1jYWZiOWY5NjFjZWUiIHN0UmVmOmRvY3VtZW50SUQ9InhtcC5kaWQ6NjFlOGM3OTktZDk2Mi00Y2JlLWFiNDItY2FmYjlmOTYxY2VlIi8+IDxkYzp0aXRsZT4gPHJkZjpBbHQ+IDxyZGY6bGkgeG1sOmxhbmc9IngtZGVmYXVsdCI+dGVzbGFfVF9CVzwvcmRmOmxpPiA8L3JkZjpBbHQ+IDwvZGM6dGl0bGU+IDwvcmRmOkRlc2NyaXB0aW9uPiA8L3JkZjpSREY+IDwveDp4bXBtZXRhPiA8P3hwYWNrZXQgZW5kPSJyIj8+ux4+7QAAALlJREFUeNpi/P//PwMtABMDjcDQM5gFmyAjI2MAkLIHYgMgdsCh9wAQXwDig8B42oAhC4o8ZAwE74H4PpQ+D6XXA7EAFK9HkwOrxTAHi8ENUA3/0fB6KEYXB6ltIMZgkKv6oS4xgIqhGAYVM4CqmQ/SQ9BgbBjqbZjB54nRQ2yqeICDTXFyu4iDTbHBB3CwKTaY5KBgJLYQAmaa/9B0z0h2ziMiOKhq8AVaGfxwULiYcbQGobnBAAEGADCCwy7PWQ+qAAAAAElFTkSuQmCC')
    print('---')


# --------------------------
# The init function
# --------------------------

# The init function: Called to store your username and access_code in OS X Keychain on first launch
def init():
    try:
        auth = TeslaAuthenticator()
        auth.perform_login()
        return
    except Exception as e:
        print ("Error: %s" % e)
        time.sleep(0.5)
        return



# --------------------------
# The main function
# --------------------------

def main(argv):

    # CASE 1: init was called 
    if 'init' in argv:
       init()
       return
  
    # CASE 2: init was not called, keyring not initialized
    if DARK_MODE:
        color = '#FFDEDEDE'
        info_color = '#808080'
    else:
        color = 'black' 
        info_color = '#808080'

    ACCESS_TOKEN = keyring.get_password("mytesla-bitbar","access_token")
   
    if not ACCESS_TOKEN:   
       # restart in terminal calling init 
       app_print_logo()
       print ('Login to tesla.com | refresh=true terminal=true bash="\'%s\'" param1="%s" color=%s' % (sys.argv[0], 'init', color))
       return


    # CASE 3: init was not called, keyring initialized, no connection (access code not valid)
    try:
       # create connection to tesla account
       c = TeslaConnection(access_token = ACCESS_TOKEN)
       vehicles = c.vehicles()
       appointments = c.appointments()
    except: 
       app_print_logo()
       print ('Login to tesla.com | refresh=true terminal=true bash="\'%s\'" param1="%s" color=%s' % (sys.argv[0], 'init', color))
       return


    # CASE 4: all ok, specific command for a specific vehicle received
    if (len(sys.argv) > 1) and not('debug' in argv):
        v = vehicles[int(sys.argv[1])]


        if sys.argv[2] == "wake_up":
            print ('Waking up your car... this may take up to 30 seconds.')
            v.wake_up()
            time.sleep(30)
        else:
            if (len(sys.argv) == 2) and (sys.argv[2] != 'remote_start_drive'):
                # argv is of the form: CMD + vehicleid + command 
                v.command(sys.argv[2])
            elif sys.argv[2] == 'remote_start_drive':
                # ask for password
                print ('Enter your tesla.com password:')
                password = getpass.getpass()
                v.command(sys.argv[2],password)
                password = ''
            elif sys.argv[2] == 'navigation_request':
                # ask for address
                print ('Enter the address to set your navigation to:')
                address = raw_input()
                current_timestamp = int(time.time())
                json_data = json.dumps({"type":"share_ext_content_raw", "locale":"en-US","timestamp_ms":str(current_timestamp), "value" : {"android.intent.ACTION" : "android.intent.action.SEND", "android.intent.TYPE":"text\/plain", "android.intent.extra.SUBJECT":"MyTesla address","android.intent.extra.TEXT": str(address)}})
                v.command('share',json_data)
            elif sys.argv[2] == 'navigation_set_charger':
                address = binascii.unhexlify(sys.argv[3])
                current_timestamp = int(time.time())
                json_data = json.dumps({"type":"share_ext_content_raw", "locale":"en-US","timestamp_ms":str(current_timestamp), "value" : {"android.intent.ACTION" : "android.intent.action.SEND", "android.intent.TYPE":"text\/plain", "android.intent.extra.SUBJECT":"MyTesla address","android.intent.extra.TEXT": str(address)}})
                print ('Setting navigation to: %s' % address)
                v.command('share',json_data)
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
           vehicle_access = vehicle.mobile_access()
           if vehicle_access == False:
                 print ('%sVehicle mobile access disabled. Click to try again. | refresh=true terminal=false bash="echo refresh" color=%s' % (prefix, color))
                 return
         
           if vehicle['in_service'] == True:
                 print ('%sVehicle in service. Click to try again. | refresh=true terminal=false bash="echo refresh" color=%s' % (prefix, color))
                 return     
 
           # get the data for the vehicle       
           vehicle_info = vehicle.vehicle_data() 
   
           if vehicle['state'] == 'asleep':
                 print ('%sVehicle state:\t\t\t\t%s. | color=%s' % (prefix, sleeping_since(vehicle_info['drive_state']['timestamp']), color))
                 print ('%s--Wake up | refresh=true terminal=true bash="%s" param1=%s param2=%s color=%s' % (prefix, sys.argv[0], str(i), "wake_up", color))
                 print ('%s---' % prefix)
           
           elif vehicle['state'] != 'online':
                 print ('%sVehicle offline. Click to try again. | refresh=true terminal=false bash="echo refresh" color=%s' % (prefix, color))
                 return     
 
           elif vehicle['state'] == 'online':
                 print ('%sVehicle state:\t\t\t\tOnline | color=%s' % (prefix, color))
                 print ('%s---' % prefix)


        except Exception as e: 
           print ('%sError: Failed to get info from Tesla. Click to try again. | refresh=true terminal=false bash="true" color=%s' % (prefix, color))
           print e
           return         

	vehicle_name = vehicle['display_name']
	vehicle_vin  = vehicle['vin'] 

        gui_settings    = vehicle_info['gui_settings']
        charge_state    = vehicle_info['charge_state']
        climate_state   = vehicle_info['climate_state']
        drive_state     = vehicle_info['drive_state']
        vehicle_state   = vehicle_info['vehicle_state']
        vehicle_config  = vehicle_info['vehicle_config']

        nearby_charging_sites = vehicle.nearby_charging_sites()

        temp_unit = gui_settings['gui_temperature_units'].encode('utf-8')
        distance_unit='km'  
        if gui_settings['gui_distance_units'] == 'mi/hr':
            distance_unit = 'mi'


        if _COMPOSER_CACHE_HIGH_:
            for view in ['STUD_3QTR','STUD_SIDE','STUD_REAR','STUD_SEAT']:
                for background in ['1','2','3','4']:
                    for size in ['512','1024','2048','4096']:
                        vehicle.compose_image(vehicle_config['car_type'],view=view,size=size,background=background)

        # --------------------------------------------------
        # DEBUG MENU
        # --------------------------------------------------

        if 'debug' in argv:
            print vehicle.option_codes()
            print ('>>> vehicle:\n%s\n'        % vehicle)
            print ('>>> vehicle_info:\n%s\n'   % vehicle_info)
            print ('>>> gui_settings:\n%s\n'   % gui_settings)
            print ('>>> charge_state:\n%s\n'   % charge_state)
            print ('>>> climate_state:\n%s\n'  % climate_state)
            print ('>>> drive_state:\n%s\n'    % drive_state)
            print ('>>> vehicle_state:\n%s\n'  % vehicle_state)
            print ('>>> vehicle_config:\n%s\n' % vehicle_config)
            print ('>>> appointments:\n%s\n'   % appointments)
            return

        # --------------------------------------------------
        # SOFTWARE UPDATE MENU 
        # --------------------------------------------------

        if (vehicle_state['software_update']['status'] == 'available'):
           print ('%sSoftware update:				%s available for installation | refresh=true terminal=false bash="%s" param1=%s param2=schedule_software_update param3=%s color=%s' % (prefix, vehicle_state['software_update']['version'], sys.argv[0], str(i), "offset_sec:0", color))
           print ('%s---' % prefix)
        elif (vehicle_state['software_update']['status'] == 'downloading'):
           print ('%sSoftware update:				Downloading %s (%s%%) | color=%s' % (prefix, vehicle_state['software_update']['version'], vehicle_state['software_update']['download_perc'], color))
           print ('%s---' % prefix)
        elif (vehicle_state['software_update']['status'] == 'scheduled'):
           print ('%sSoftware update:				Preparing to install %s | color=%s' % (prefix, vehicle_state['software_update']['version'], color))
           print ('%s---' % prefix)
        elif (vehicle_state['software_update']['status'] == 'installing'):
           print ('%sSoftware update:				Installing %s (%s%%) | color=%s' % (prefix, vehicle_state['software_update']['version'], vehicle_state['software_update']['install_perc'], color))
           print ('%s---' % prefix)


        # --------------------------------------------------
        # SERVICE APPOINTMENT MENU 
        # --------------------------------------------------

        try: 
           if (appointments['enabled_vins'][0]['next_appt_timestamp'] != None):
              next_appt = datetime.datetime.strptime(appointments['enabled_vins'][0]['next_appt_timestamp'],"%Y-%m-%dT%H:%M:%S")
              print ('%sService appoinment:\t\t\t%s | color=%s' % (prefix, next_appt.strftime("%b %d %Y, %H:%M"), color))
              print ('%s---' % prefix)
        except: 
           pass


        # --------------------------------------------------
        # BATTERY MENU 
        # --------------------------------------------------

        battery_loss_cold = int(charge_state['battery_level']) - int(charge_state['usable_battery_level'])
        battery_distance  = ""

        if (gui_settings['gui_range_display'] == 'Rated'):
           battery_distance = convert_distance(distance_unit,charge_state['battery_range'])
        else: 
           battery_distance = convert_distance(distance_unit,charge_state['ideal_battery_range'])


        print ('%sBattery:\t\t\t\t\t\t%s%% %s (%s %s) | color=%s' % (prefix, charge_state['battery_level'], cold_state(battery_loss_cold), battery_distance, distance_unit, color))
        print ('%s--Charge Level set to:\t\t\t%s%% | color=%s' % (prefix, charge_state['charge_limit_soc'], color))
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


        print ('%s-----' % prefix)
        print ('%s--Rated battery range:\t\t\t%s %s| color=%s' % (prefix, convert_distance(distance_unit,charge_state['battery_range']),distance_unit,info_color))
        print ('%s--Ideal battery range:\t\t\t%s %s| color=%s' % (prefix, convert_distance(distance_unit,charge_state['ideal_battery_range']),distance_unit,info_color))
        print ('%s--Estimated battery range:\t\t%s %s| color=%s' % (prefix, convert_distance(distance_unit,charge_state['est_battery_range']),distance_unit,info_color))

        print ('%s-----' % prefix)
        print ('%s--Energy added:\t\t\t\t+%s kwh| color=%s' % (prefix, charge_state['charge_energy_added'],info_color))
        print ('%s--Rated range added:\t\t\t+%s %s| color=%s' % (prefix, convert_distance(distance_unit,charge_state['charge_miles_added_rated']), distance_unit, info_color))
        print ('%s--Ideal range added:\t\t\t+%s %s| color=%s' % (prefix, convert_distance(distance_unit,charge_state['charge_miles_added_ideal']), distance_unit, info_color))
 


        # --------------------------------------------------
        # CHARGING MENU 
        # --------------------------------------------------

        if (charge_state['charging_state']=="Disconnected"):
            print ('%sCharger: \t\t\t\t\tDisconnected | color=%s' % (prefix, color))


        elif (charge_state['charging_state']=='Starting'): 
            print ('%sCharger: \t\t\t\t\tStarting | color=%s' % (prefix, color))
            print ('%s--Stop charging | refresh=true terminal=false bash="%s" param1=%s param2=charge_stop color=%s' % (prefix, sys.argv[0], str(i), color))
            print ('%s--Stop charging | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=charge_stop color=%s' % (prefix, sys.argv[0], str(i), color))


        elif (charge_state['charging_state']=="Stopped"): 
            print ('%sCharger: \t\t\t\t\tStopped | color=%s' % (prefix, color))
            print ('%s--Continue charging | refresh=true terminal=false bash="%s" param1=%s param2=charge_start color=%s' % (prefix, sys.argv[0], str(i), color))
            print ('%s--Continue charging | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=charge_start color=%s' % (prefix, sys.argv[0], str(i), color))


        elif (charge_state['charging_state']=="Complete"): 
            print ('%sCharger: \t\t\t\t\tCompleted | color=%s' % (prefix, color))


        elif (charge_state['charging_state']=="Charging"):
            time_left = calculate_time_left(charge_state['time_to_full_charge'])
            charger_description = "Charger:\t"

            if (charge_state['fast_charger_present']):
               charger_description = "Supercharger:" 

            print ('%s%s\t\t\t\t%s (%s %s/h) | color=%s' % (prefix, charger_description, time_left, convert_distance(distance_unit,charge_state['charge_rate']), distance_unit, color))
            print ('%s--Stop charging | refresh=true terminal=false bash="%s" param1=%s param2=charge_stop color=%s' % (prefix, sys.argv[0], str(i), color))
            print ('%s--Stop charging | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=charge_stop color=%s' % (prefix, sys.argv[0], str(i), color))
 
            print ('%s-----' % prefix)

            if bool(charge_state['charger_pilot_current']):
               print ('%s--Maximum current:\t%s A| color=%s' % (prefix, charge_state['charger_pilot_current'],info_color))
            else:
               print ('%s--Maximum current:\tNo information| color=%s' % (prefix,info_color))
            print ('%s--Actual current:\t\t%s A| color=%s' % (prefix, charge_state['charger_actual_current'],info_color))
            print ('%s--Power:\t\t\t\t%s Kw| color=%s' % (prefix, charge_state['charger_power'],info_color))
            print ('%s--Voltage:\t\t\t\t%s V| color=%s' % (prefix, charge_state['charger_voltage'],info_color))
            print ('%s--Phases:\t\t\t\t%s| color=%s' % (prefix, charge_state['charger_phases'],info_color))


        else:
            print ('%sCharger: \t\t\t\t\t%s | color=%s' % (prefix, charge_state['charging_state'],color))
       
        print ('%s---' % prefix)


        # --------------------------------------------------
        # VEHICLE STATE MENU 
        # --------------------------------------------------

        # Car & Alarm overview
        
        sentry_available = False
        sentry_description = ""
        sentry_state = 'off'

        try:
            if (vehicle_state['sentry_mode'] == True):
                sentry_available = True
                sentry_description = CGREEN+'(Sentry On)'+CEND
                sentry_state = 'on'
            else: 
                sentry_available = True
                sentry_description = CRED+'(Sentry Off)'+CEND
                sentry_state = 'off'
        except:
            pass
  
        print ('%sVehicle security:\t\t\t\t%s %s | color=%s' % (prefix, lock_state(vehicle_state['locked']), sentry_description, color))

        if bool(vehicle_state['locked']):
            print ('%s--%s | refresh=true terminal=false bash="%s" param1=%s param2=door_unlock color=%s' % (prefix, CRED+'Unlock'+CEND, sys.argv[0], str(i), color))
            print ('%s--%s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=door_unlock color=%s' % (prefix, CRED+'Unlock'+CEND, sys.argv[0], str(i), color))
            if bool(sentry_available): 
                print ('%s-----' % (prefix))
                if (sentry_state == 'off'):
                   print ('%s--%s | refresh=true terminal=false bash="%s" param1=%s param2=set_sentry_mode param3="on:true" color=%s' % (prefix, CGREEN+'Turn on Sentry'+CEND, sys.argv[0], str(i), color))
                   print ('%s--%s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_sentry_mode param3="on:true" color=%s' % (prefix, CGREEN+'Turn on Sentry'+CEND, sys.argv[0], str(i), color))
                else:
                   print ('%s--%s | refresh=true terminal=false bash="%s" param1=%s param2=set_sentry_mode param3="on:false" color=%s' % (prefix, CRED+'Turn off Sentry'+CEND, sys.argv[0], str(i), color))
                   print ('%s--%s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_sentry_mode param3="on:false" color=%s' % (prefix, CRED+'Turn off Sentry'+CEND, sys.argv[0], str(i), color))
 
        else:
            print ('%s--%s | refresh=true terminal=false bash="%s" param1=%s param2=door_lock color=%s' % (prefix, CGREEN+'Lock'+CEND, sys.argv[0], str(i), color))
            print ('%s--%s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=door_lock color=%s' % (prefix, CGREEN+'Lock'+CEND, sys.argv[0], str(i), color))


        # Door overview

        print ('%s-----' % prefix)
        print ('%s--Driver front door:\t\t\t\t%s| color=%s' % (prefix, door_state(vehicle_state['df']),info_color))
        print ('%s--Driver rear door:\t\t\t\t%s| color=%s' % (prefix, door_state(vehicle_state['dr']),info_color))
        print ('%s--Passenger front door:\t\t\t%s| color=%s' % (prefix, door_state(vehicle_state['pf']),info_color))
        print ('%s--Passenger rear door:\t\t\t%s| color=%s' % (prefix, door_state(vehicle_state['pr']),info_color))
        print ('%s-----' % prefix)


        # Window overview
        
        print ('%s--Driver front window:\t\t\t%s| color=%s' % (prefix, window_state(vehicle_state['fd_window']),info_color))
        if (vehicle_state['fd_window'] == 0):
            print ('%s----Open | refresh=true terminal=false bash="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, sys.argv[0], str(i), 'command:vent', 'lat:0', 'lon:0', color))
            print ('%s----Open | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, sys.argv[0], str(i), 'command:vent', 'lat:0', 'lon:0', color))
        else:
            print ('%s----Close (Not available) | refresh=true terminal=false bash="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, sys.argv[0], str(i), 'command:close', 'lat:0', 'lon:0', info_color))
            print ('%s----Close (Not available) | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, sys.argv[0], str(i), 'command:close', 'lat:0', 'lon:0', info_color))
        print ('%s--Driver rear window:\t\t\t%s| color=%s' % (prefix, window_state(vehicle_state['rd_window']),info_color))
        if (vehicle_state['fd_window'] == 0):
            print ('%s----Open | refresh=true terminal=false bash="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, sys.argv[0], str(i), 'command:vent', 'lat:0', 'lon:0', color))
            print ('%s----Open | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, sys.argv[0], str(i), 'command:vent', 'lat:0', 'lon:0', color))
        else:
            print ('%s----Close (Not available) | refresh=true terminal=false bash="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, sys.argv[0], str(i), 'command:close', 'lat:0', 'lon:0', info_color))
            print ('%s----Close (Not available) | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, sys.argv[0], str(i), 'command:close', 'lat:0', 'lon:0', info_color))
 
        print ('%s--Passenger front window:\t\t%s| color=%s' % (prefix, window_state(vehicle_state['fp_window']),info_color))
        if (vehicle_state['fp_window'] == 0):
            print ('%s----Open | refresh=true terminal=false bash="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, sys.argv[0], str(i), 'command:vent', 'lat:0', 'lon:0', color))
            print ('%s----Open | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, sys.argv[0], str(i), 'command:vent', 'lat:0', 'lon:0', color))
        else:
            print ('%s----Close (Not available) | refresh=true terminal=false bash="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, sys.argv[0], str(i), 'command:close', 'lat:0', 'lon:0', info_color))
            print ('%s----Close (Not available) | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, sys.argv[0], str(i), 'command:close', 'lat:0', 'lon:0', info_color))
        print ('%s--Passenger rear window:\t\t%s| color=%s' % (prefix, window_state(vehicle_state['rp_window']),info_color))
        if (vehicle_state['rp_window'] == 0):
            print ('%s----Open | refresh=true terminal=false bash="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, sys.argv[0], str(i), 'command:vent', 'lat:0', 'lon:0', color))
            print ('%s----Open | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, sys.argv[0], str(i), 'command:vent', 'lat:0', 'lon:0', color))
        else:
            print ('%s----Close (Not available) | refresh=true terminal=false bash="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, sys.argv[0], str(i), 'command:close', 'lat:0', 'lon:0', info_color))
            print ('%s----Close (Not available) | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=window_control param3=%s param4=%s param5=%s color=%s' % (prefix, sys.argv[0], str(i), 'command:close', 'lat:0', 'lon:0', info_color))
        print ('%s-----' % prefix)


        # Sunroof overview

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
 

        # Trunk and frunk overview

        print ('%s--Front trunk:\t\t\t\t\t%s| color=%s' % (prefix, door_state(vehicle_state['ft']),color))
        if (bool(vehicle_state['ft'])):
        	print ('%s----Close | refresh=true terminal=false bash="%s" param1=%s param2=actuate_trunk param3=%s color=%s' % (prefix, sys.argv[0], str(i), "which_trunk:front", color))
        	print ('%s----Close | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=actuate_trunk param3=%s color=%s' % (prefix, sys.argv[0], str(i), "which_trunk:front", color))
        else: 
        	print ('%s----Open | refresh=true terminal=false bash="%s" param1=%s param2=actuate_trunk param3=%s color=%s' % (prefix, sys.argv[0], str(i), "which_trunk:front", color))
        	print ('%s----Open | refresh=true alternate=true terminal=true  bash="%s" param1=%s param2=actuate_trunk param3=%s color=%s' % (prefix, sys.argv[0], str(i), "which_trunk:front", color))

        print ('%s--Rear trunk:\t\t\t\t\t%s| color=%s' % (prefix, door_state(vehicle_state['rt']),info_color))
        if (bool(vehicle_state['rt'])):
        	print ('%s----Close | refresh=true terminal=false bash="%s" param1=%s param2=actuate_trunk param3=%s color=%s' % (prefix, sys.argv[0], str(i), "which_trunk:rear", color))
        	print ('%s----Close | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=actuate_trunk param3=%s color=%s' % (prefix, sys.argv[0], str(i), "which_trunk:rear", color))
        else: 
        	print ('%s----Open | refresh=true terminal=false bash="%s" param1=%s param2=actuate_trunk param3=%s color=%s' % (prefix, sys.argv[0], str(i), "which_trunk:rear", color))
        	print ('%s----Open | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=actuate_trunk param3=%s color=%s' % (prefix, sys.argv[0], str(i), "which_trunk:rear", color))

       	charge_port_defrost = ""
        try:
           if (charge_state['charge_port_cold_weather_mode']):
              charge_port_defrost = CBLUE + '(defrosting)' + CEND
        except:
           pass
 
        print ('%s--Charge port:\t\t\t\t\t%s %s| color=%s' % (prefix, port_state(charge_state['charge_port_door_open'],charge_state['charge_port_latch']), charge_port_defrost, color))
        if (bool(charge_state['charge_port_door_open'])) and (not(charge_state['charge_port_latch'] == 'Engaged')):
                print ('%s----Close | refresh=true terminal=false bash="%s" param1=%s param2=charge_port_door_close color=%s' % (prefix, sys.argv[0], str(i), color))
        	print ('%s----Close | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=charge_port_door_close color=%s' % (prefix, sys.argv[0], str(i), color))
        if (not(bool(charge_state['charge_port_door_open']))):
        	print ('%s----Open | refresh=true terminal=false bash="%s" param1=%s param2=charge_port_door_open color=%s' % (prefix, sys.argv[0], str(i), color))
        	print ('%s----Open | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=charge_port_door_open color=%s' % (prefix, sys.argv[0], str(i), color))

        if bool(drive_state['speed']):
            print ('%sVehicle speed:\t\t\t\t%s %s/h| color=%s' % (prefix, convert_distance(distance_unit,drive_state['speed']),distance_unit,color))
        else:
            print ('%sVehicle speed:\t\t\t\tParked| color=%s' % (prefix,color))
 
        

        # Vehicle location overview

        gmaps = googleclient('AIzaSyCtVR6-HQOVMYVGG6vOxWvPxjeggFz39mg')
        car_location_address = gmaps.reverse_geocode((str(drive_state['latitude']),str(drive_state['longitude'])))[0]['formatted_address']

        print ('%s-----' % prefix)
        print ('%s--Address:\t\t%s| color=%s' % (prefix, car_location_address, color))
        print ('%s-----' % prefix)
        print ('%s--Lat:\t\t\t\t%s| color=%s' % (prefix, drive_state['latitude'], info_color))
        print ('%s--Lon:\t\t\t\t%s| color=%s' % (prefix, drive_state['longitude'], info_color))
        print ('%s--Heading:\t\t%s°| color=%s' % (prefix, drive_state['heading'], info_color))

        print ('%s---' % prefix)
        
        
        # --------------------------------------------------
        # VEHICLE MAP MENU 
        # --------------------------------------------------

        google_maps = retrieve_google_maps(str(drive_state['latitude']),str(drive_state['longitude']))
        vehicle_location_map = google_maps[0]
        vehicle_location_sat = google_maps[1]

        print ('%s|image=%s href="https://maps.google.com?q=%s,%s" color=%s' % (prefix, vehicle_location_map, drive_state['latitude'],drive_state['longitude'],color))
        print ('%s|image=%s alternate=true href="https://maps.google.com?q=%s,%s" color=%s' % (prefix, vehicle_location_sat, drive_state['latitude'],drive_state['longitude'],color))

        print ('%s---' % prefix)

        # --------------------------------------------------
        # CLIMATE STATE MENU 
        # --------------------------------------------------
   
        try:
            print ('%sInside temp:\t\t\t\t\t%.1f° %s| color=%s' % (prefix, convert_temp(temp_unit,climate_state['inside_temp']),temp_unit,color))
        except:
            print ('%sInside temp:\t\t\t\t\tUnavailable| color=%s' % (prefix,color))
        if climate_state['is_climate_on']:
            print ('%s--Turn off airco | refresh=true terminal=false bash="%s" param1=%s param2=auto_conditioning_stop color=%s' % (prefix, sys.argv[0], str(i), color))
            print ('%s--Turn off airco | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=auto_conditioning_stop color=%s' % (prefix, sys.argv[0], str(i), color))
        else:
            print ('%s--Turn on airco | refresh=true terminal=false bash="%s" param1=%s param2=auto_conditioning_start color=%s' % (prefix, sys.argv[0], str(i), color))
            print ('%s--Turn on airco | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=auto_conditioning_start color=%s' % (prefix, sys.argv[0], str(i), color))
        
        if climate_state['is_front_defroster_on']:
            print ('%s--Turn off window defrost | refresh=true terminal=false bash="%s" param1=%s param2=set_preconditioning_max param3=%s color=%s' % (prefix, sys.argv[0], str(i), 'on:false', color))
            print ('%s--Turn off window defrost | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_preconditioning_max param3=%s color=%s' % (prefix, sys.argv[0], str(i), 'on:false', color))
        else:
            print ('%s--Turn on window defrost | refresh=true terminal=false bash="%s" param1=%s param2=set_preconditioning_max param3=%s color=%s' % (prefix, sys.argv[0], str(i), 'on:true', color))
            print ('%s--Turn on window defrost | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_preconditioning_max param3=%s color=%s' % (prefix, sys.argv[0], str(i), 'on:true', color))

        print ('%s-----' % prefix)
        print ('%s--Airco set to:\t\t\t%.1f° %s | color=%s' % (prefix, convert_temp(temp_unit,climate_state['driver_temp_setting']), temp_unit, color))
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


        # TODO: Dog Mode API unpublished - to be verified

        if climate_state['climate_keeper_mode'] == 'dog':
            print ('%s--Dog Mode:\t\t\tOn | color=%s' % (prefix, color))
            print ('%s----Turn off | refresh=true terminal=false bash="%s" param1=%s param2=set_climate_keeper param3="on:false" color=%s' % (prefix, sys.argv[0], str(i), color))
            print ('%s----Turn off | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_climate_keeper param3="on:false" color=%s' % (prefix, sys.argv[0], str(i), color))
        else:
            print ('%s--Dog Mode:\t\t\tOff | color=%s' % (prefix, color))
            print ('%s----Turn on | refresh=true terminal=false bash="%s" param1=%s param2=set_climate_keeper param3="on:true" color=%s' % (prefix, sys.argv[0], str(i), color))
            print ('%s----Turn on | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=set_climate_keeper param3="on:true" color=%s' % (prefix, sys.argv[0], str(i), color))


        print ('%s-----' % prefix)
        print ('%s--Seat heating | color=%s' % (prefix, color))
        try:
           print ('%s----Driver:\t\t\t%s | color=%s' % (prefix, seat_state(climate_state['seat_heater_left']), color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '0', sys.argv[0], str(i), "heater:0","level:0", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '0', sys.argv[0], str(i), "heater:0","level:0", color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '1',sys.argv[0], str(i), "heater:0","level:1", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '1',sys.argv[0], str(i), "heater:0","level:1", color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '2', sys.argv[0], str(i), "heater:0","2", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '2', sys.argv[0], str(i), "heater:0","level:2", color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '3', sys.argv[0], str(i), "heater:0","level:3", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '3', sys.argv[0], str(i), "heater:0","level:3", color))
        except:
           pass
        try:    
           print ('%s----Passenger:\t\t%s | color=%s' % (prefix, seat_state(climate_state['seat_heater_right']), color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '0', sys.argv[0], str(i), "heater:1","level:0", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '0', sys.argv[0], str(i), "heater:1","level:0", color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '1',sys.argv[0], str(i), "heater:1","level:1", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '1',sys.argv[0], str(i), "heater:1","level:1", color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '2', sys.argv[0], str(i), "heater:1","level:2", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '2', sys.argv[0], str(i), "heater:1","level:2", color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '3', sys.argv[0], str(i), "heater:1","level:3", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '3', sys.argv[0], str(i), "heater:1","level:3", color))
        except: 
           pass
        try:
           print ('%s----Rear left:\t\t%s | color=%s' % (prefix, seat_state(climate_state['seat_heater_rear_left']), color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '0', sys.argv[0], str(i), "heater:2","level:0", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '0', sys.argv[0], str(i), "heater:2","level:0", color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '1',sys.argv[0], str(i), "heater:2","level:1", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '1',sys.argv[0], str(i), "heater:2","level:1", color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '2', sys.argv[0], str(i), "heater:2","level:2", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '2', sys.argv[0], str(i), "heater:2","level:2", color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '3', sys.argv[0], str(i), "heater:2","level:3", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '3', sys.argv[0], str(i), "heater:2","level:3", color))
        except:
           pass
        try:
           print ('%s----Rear center:\t\t%s | color=%s' % (prefix, seat_state(climate_state['seat_heater_rear_center']),color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '0', sys.argv[0], str(i), "heater:3","level:0", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '0', sys.argv[0], str(i), "heater:3","level:0", color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '1',sys.argv[0], str(i), "heater:3","level:1", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '1',sys.argv[0], str(i), "heater:3","level:1", color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '2', sys.argv[0], str(i), "heater:3","level:2", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '2', sys.argv[0], str(i), "heater:3","level:2", color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '3', sys.argv[0], str(i), "heater:3","level:3", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '3', sys.argv[0], str(i), "heater:3","level:3", color))
        except: 
           pass
        try:
           print ('%s----Rear right:\t\t%s | color=%s' % (prefix, seat_state(climate_state['seat_heater_rear_right']),color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '0', sys.argv[0], str(i), "heater:4","level:0", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '0', sys.argv[0], str(i), "heater:4","level:0", color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '1',sys.argv[0], str(i), "heater:4","level:1", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '1',sys.argv[0], str(i), "heater:4","level:1", color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '2', sys.argv[0], str(i), "heater:4","level:2", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '2', sys.argv[0], str(i), "heater:4","level:2", color))
           print ('%s------ %s | refresh=true terminal=false bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '3', sys.argv[0], str(i), "heater:4","level:3", color))
           print ('%s------ %s | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_seat_heater_request param3=%s param4=%s color=%s' % (prefix, '3', sys.argv[0], str(i), "heater:4","level:3", color))
        except: 
           pass
        try:
           if climate_state['steering_wheel_heater']: 
              print ('%s--Steering heating:\tOn| color=%s' % (prefix, color))
              print ('%s----Turn off | refresh=true terminal=false bash="%s" param1=%s param2=remote_steering_wheel_heater_request param3="on:false" color=%s' % (prefix, sys.argv[0], str(i), color))
              print ('%s----Turn off | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_steering_wheel_heater_request param3="on:false" color=%s' % (prefix, sys.argv[0], str(i), color))
           else:
              print ('%s--Steering heating:\tOff| color=%s' % (prefix, color))
              print ('%s----Turn off | refresh=true terminal=false bash="%s" param1=%s param2=remote_steering_wheel_heater_request param3="on:true" color=%s' % (prefix, sys.argv[0], str(i), color))
              print ('%s----Turn off | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=remote_steering_wheel_heater_request param3="on:true" color=%s' % (prefix, sys.argv[0], str(i), color))
        except:
           pass

        try:
           if climate_state['is_front_defroster_on']:
              print ('%s-- Front window defrosting | color=%s' % (prefix, color))
	except:
           pass
        try:
           if climate_state['is_rear_defroster_on']:
              print ('%s-- Rear window defrosting | color=%s' % (prefix, color))
	except:
           pass
        try:
           if charge_state['battery_heater_on']:
              print ('%s--Battery heating | color=%s' % (prefix, color))
	except:
           pass
 
        try:
            print ('%sOutside Temp:\t\t\t\t%.1f° %s| color=%s' % (prefix, convert_temp(temp_unit,climate_state['outside_temp']),temp_unit,color))
        except:
            print ('%sOutside Temp:\t\t\t\tUnavailable| color=%s' % (prefix, color))

        print ('%s---' % prefix)

        print ('%sVehicle info| color=%s' % (prefix,color))
        print ('%s--|image=%s href=%s color=%s' % (prefix, vehicle.compose_image(vehicle_config['car_type']), vehicle.compose_url(vehicle_config['car_type']), color))
        print ('%s--|image=%s alternate=true href=%s color=%s' % (prefix, vehicle.compose_image(vehicle_config['car_type'],view='STUD_REAR'), vehicle.compose_url(vehicle_config['car_type']), color))
        print ('%s-----' % prefix)
        print ('%s--Name: 			%s | color=%s' % (prefix, vehicle_name, color))
        print ('%s--VIN: 			%s | terminal=true bash="echo %s | pbcopy" color=%s' % (prefix, vehicle_vin, vehicle_vin, color))
        print ('%s--Firmware:		%s | terminal=true bash="echo %s | pbcopy" color=%s' % (prefix, vehicle_state['car_version'],vehicle_state['car_version'], color))
        print ('%s-----' % prefix)
        print ('%s--Model:			%s | color=%s' % (prefix, vehicle_config['car_type'], info_color))
        print ('%s--Type: 			%s | color=%s' % (prefix, vehicle_config['trim_badging'], info_color))
        print ('%s--Ludicrous:		%s | color=%s' % (prefix, vehicle_config['has_ludicrous_mode'], info_color))
        try: # since 2019.20.1 no longer in API
           print ('%s--Uncorked: 		%s | color=%s' % (prefix, vehicle_config['perf_config'], info_color))
        except:
           pass 
        print ('%s--Color: 			%s | color=%s' % (prefix, vehicle_config['exterior_color'], info_color))
        print ('%s--Wheels: 			%s | color=%s' % (prefix, vehicle_config['wheel_type'], info_color))
        print ('%s-----' % prefix)
        print ('%s--Options | color=%s' % (prefix , info_color))
        print ('%s----Note: Tesla API currently returning incorrect info| color=%s' % (prefix, color))
        print ('%s-------' % (prefix))
        
        for option in vehicle.option_codes().split(','):
           try:
              option_description = tesla_option_codes[option]
           except: 
              option_description = 'Unknown'
           print ('%s----%s:\t\t %s | color=%s' % (prefix, option, option_description,info_color))
        print ('%s--Images| color=%s' % (prefix , info_color))
        for view in ['STUD_3QTR','STUD_SIDE','STUD_REAR','STUD_SEAT']:
           print ('%s----|image=%s href=%s color=%s' % (prefix, vehicle.compose_image(vehicle_config['car_type'],size=512,view=view,background='4'), vehicle.compose_url(vehicle_config['car_type'],size=2048,view=view,background='4'), color))
           print ('%s----|image=%s alternate=true href=%s color=%s' % (prefix, vehicle.compose_image(vehicle_config['car_type'],size=512,view=view,background='2'), vehicle.compose_url(vehicle_config['car_type'],size=2048,view=view,background='1'), color))

        print ('%s-----' % prefix)
        print ('%s--Odometer: 		%s %s | color=%s' % (prefix, convert_distance(distance_unit,vehicle_state['odometer']), distance_unit, color))


        print ('%sVehicle commands| color=%s' % (prefix,color))
        print ('%s--Flash lights | refresh=true terminal=false bash="%s" param1=%s param2=flash_lights color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s--Flash lights | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=flash_lights color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s--Honk horn | refresh=true terminal=false bash="%s" param1=%s param2=honk_horn color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s--Honk horn | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=honk_horn color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s--Media| color=%s' % (prefix,color))
        print ('%s----Toggle playback| refresh=true terminal=false bash="%s" param1=%s param2=media_toggle_playback color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s----Toggle playback| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=media_toggle_playback color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s-------' % prefix)
        print ('%s----Track| color=%s' % (prefix,color))
        print ('%s------Previous| refresh=true terminal=false bash="%s" param1=%s param2=media_prev_track color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s------Previous| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=media_prev_track color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s------Next| refresh=true terminal=false bash="%s" param1=%s param2=media_next_track color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s------Next| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=media_next_track color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s----Volume| color=%s' % (prefix,color))
        print ('%s------Up| refresh=true terminal=false bash="%s" param1=%s param2=media_volume_up color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s------Up| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=media_volume_up color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s------Down| refresh=true terminal=false bash="%s" param1=%s param2=media_volume_down color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s------Down| refresh=true alternate=true terminal=true bash="%s" param1=%s param2=media_volume_down color=%s' % (prefix, sys.argv[0], str(i), color))
        print ('%s-----' % prefix)
        print ('%s--Navigate to address| refresh=true terminal=true bash="%s" param1=%s param2=navigation_request color=%s' % (prefix, sys.argv[0], str(i), color))
        
        if nearby_charging_sites:
           print ('%s--Navigate to nearby charger | color=%s' % (prefix, color))
           print ('%s----Tesla Superchargers | color=%s' % (prefix, color))
           for site, charger in enumerate(nearby_charging_sites['superchargers']): 
              print ('%s------%.2f %s\t(%s/%s)\t%s | refresh=true terminal=false bash="%s" param1=%s param2=navigation_set_charger param3=%s color=%s' % (prefix, convert_distance(distance_unit,charger['distance_miles']),distance_unit,charger['available_stalls'],charger['total_stalls'], charger['name'], sys.argv[0], str(i), binascii.hexlify('Tesla Supercharger '+charger['name']), color))
              print ('%s------%.2f %s\t(%s/%s)\t%s | alternate=true refresh=true terminal=true bash="%s" param1=%s param2=navigation_set_charger param3=%s color=%s' % (prefix, convert_distance(distance_unit,charger['distance_miles']),distance_unit,charger['available_stalls'],charger['total_stalls'], charger['name'], sys.argv[0], str(i), binascii.hexlify('Tesla Supercharger '+charger['name']), color))
           print ('%s----Destination Chargers | color=%s' % (prefix, color))
           for site, charger in enumerate(nearby_charging_sites['destination_charging']): 
              print ('%s------%.2f %s\t%s\t | refresh=true terminal=false bash="%s" param1=%s param2=navigation_set_charger param3=%s color=%s' % (prefix, convert_distance(distance_unit,charger['distance_miles']),distance_unit,charger['name'].encode('utf-8', 'ignore'), sys.argv[0], str(i), binascii.hexlify(charger['name'].encode('utf-8','ignore')), color))
              print ('%s------%.2f %s\t%s\t | alternate=true refresh=true terminal=true bash="%s" param1=%s param2=navigation_set_charger param3=%s color=%s' % (prefix, convert_distance(distance_unit,charger['distance_miles']),distance_unit,charger['name'].encode('utf-8', 'ignore'), sys.argv[0], str(i), binascii.hexlify(charger['name'].encode('utf-8','ignore')), color))

        print ('%s-----' % prefix)
        print ('%s--Trigger Homelink | refresh=true terminal=false bash="%s" param1=%s param2=trigger_homelink param3=%s param4=%s color=%s' % (prefix, sys.argv[0], str(i), 'lat:'+str(drive_state['latitude']),'lon:'+str(drive_state['longitude']), color))
        print ('%s--Trigger Homelink | refresh=true alternate=true terminal=true bash="%s" param1=%s param2=trigger_homelink param3=%s param4=%s color=%s' % (prefix, sys.argv[0], str(i), 'lat:'+str(drive_state['latitude']),'lon:'+str(drive_state['longitude']), color))
        print ('%s-----' % prefix)
        print ('%s--Remote start | refresh=true terminal=true bash="%s" param1=%s param2=remote_start_drive color=%s' % (prefix, sys.argv[0], str(i), color))
 

if __name__ == '__main__':
    main(sys.argv)
