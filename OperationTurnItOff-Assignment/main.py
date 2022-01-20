import time
import datetime
from datetime import datetime
from sense_hat import SenseHat
import subprocess
import requests
import sys
import logging
import paho.mqtt.client as mqtt
from urllib.parse import urlparse
from dotenv import dotenv_values
import subprocess
from time import sleep, strftime, time
import json
import firebase_admin
from firebase_admin import credentials, db


#initialist sensehat
sense = SenseHat()

# set colour variables for use with sensehat leds
green = (0,255,0)
red = (255,0,0)
blue = (0,0,255)

#load MQTT configuration values from .env file
config = dotenv_values(".env")

#configure Logging
logging.basicConfig(level=logging.INFO)

# Define event callbacks for MQTT
def on_connect(client, userdata, flags, rc):
    logging.info("Connection Result: " + str(rc))

def on_publish(client, obj, mid):
    logging.info("Message Sent ID: " + str(mid))

mqttc = mqtt.Client(client_id=config["clientId"])

# Assign event callbacks
mqttc.on_connect = on_connect
mqttc.on_publish = on_publish

# parse mqtt url for connection details
url_str = sys.argv[1]
print(url_str)
url = urlparse(url_str)
base_topic = url.path[1:]

# Configure MQTT client with user name and password
mqttc.username_pw_set(config["username"], config["password"])
# Load CA certificate for Transport Layer Security
mqttc.tls_set("./broker.thingspeak.crt")

#Connect to MQTT Broker
mqttc.connect(url.hostname, url.port)
mqttc.loop_start()

#Set Thingspeak Channel to publish to
topic = "channels/"+config["channelId"]+"/publish"

# function to get environment data from sense hat 
# and power status from smart socket
def getData():
    #get data from sensehat - calculate realistic temp - round data to 2 decimal places
    output=subprocess.check_output("cat /sys/class/thermal/thermal_zone0/temp", shell=True)
    cpu=int(output)/1000
    avgtemp=(round(sense.temperature,2))
    temp=round(avgtemp-(cpu-avgtemp),2)   
    pressure=round((sense.pressure),2)
    humidity=round((sense.humidity),2)
    # get status from smart socket, in json format
    powerStatus=requests.get("http://10.100.0.149/cm?cmnd=Power")
    powerStatus = powerStatus.json()
    return {'temp':temp, 'pressure':pressure, 'humidity':humidity, 'powerStatus':powerStatus['POWER']}


#firebase credentials
cred=credentials.Certificate('./serviceAccountKey.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://operationturnitoff-assignment-default-rtdb.europe-west1.firebasedatabase.app/'
})

ref = db.reference('/')

#send data to Firebase realtime database
def storeData(data):
    now=datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    ref = db.reference('/readings')
    ref.push({
        'temp':data['temp'],
        'pressure' : data['pressure'],
        'humidity' : data['humidity'],
        'powerStatus':data['powerStatus'],
        'decision':data['decision'],
        'timestamp': dt_string
    })

# print current data to console
# depending on current temp and powerStatus of switch turn on/off switch/heater
# display message on raspberry pi LEDs depending on value of temp
# run every 300 seconds (5 minutes)
while True:
    try:
        current=getData()
        print(current['temp'], current['pressure'], current['humidity'])
        print(current['powerStatus'])
        temp=current['temp']
        pressure=current['pressure']
        humidity=current['humidity']
        powerStatus=current['powerStatus']
        if powerStatus== "OFF":
            powerStatusLog=0
        else: powerStatusLog=1

        if temp < 12 and powerStatus == "OFF":
            requests.get("http://10.100.0.149/cm?cmnd=Power%20On")
            sense.show_message("Brrr Turning Heater On", text_colour=blue)
            current['decision']="Turn ON"

        elif temp > 17 and  powerStatus == "ON":
            requests.get("http://10.100.0.149/cm?cmnd=Power%20Off")
            sense.show_message("Turning Heater Off", text_colour=red)
            current['decision']="Turn OFF"

        else:   
            sense.show_message("Nice and Cosy", text_colour=green)
            current['decision']="No Change"
  
        storeData(current) 
        payload=f"field1={temp}&field2={humidity}&field3={pressure}&field4={powerStatusLog}"
        mqttc.publish(topic, payload)
        sleep(15)
    
    except Exception as e:
        logging.error('Something went wrong: '+str(e))
        logging.info('Interrupted')
        sys.exit(0) 
    
