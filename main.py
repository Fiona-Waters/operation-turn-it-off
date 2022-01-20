import time
import datetime
from datetime import datetime
from sense_hat import SenseHat, ACTION_PRESSED
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
from firebase_admin import credentials, storage, db
from picamera import PiCamera
import photo
import face_detect
import os


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

# Function converting temp from celsius to fahrenheit
def convertCtoF(temp):
    result = (temp * 9) / 5 + 32
    formatted_result = "{:.2f}".format(result)
    return formatted_result

# Function to get environment data from sense hat 
# and power status from smart socket
def getData():
    # Get data from sensehat - calculate realistic temp - round data to 2 decimal places
    output=subprocess.check_output("cat /sys/class/thermal/thermal_zone0/temp", shell=True)
    cpu=int(output)/1000
    avgtemp=(round(sense.temperature,2))
    temp=round(avgtemp-(cpu-avgtemp),2)   
    pressure=round((sense.pressure),2)
    humidity=round((sense.humidity),2)
    # get status from smart socket, in json format
    powerStatus=requests.get("http://10.100.0.149/cm?cmnd=Power")
    powerStatus = powerStatus.json()
    fahrenheit = convertCtoF(temp)
    return {'temp':temp, 'pressure':pressure, 'humidity':humidity, 'powerStatus':powerStatus['POWER'], 'fahrenheit':fahrenheit}


# Firebase credentials
cred=credentials.Certificate('./serviceAccountKey.json')
firebase_admin.initialize_app(cred, {
    'storageBucket': 'operationturnitoff-assignment.appspot.com',
    'databaseURL': 'https://operationturnitoff-assignment-default-rtdb.europe-west1.firebasedatabase.app/'
})

bucket = storage.bucket()

# Function to store image to Firebase storage
def storeImage(fileLoc):
    filename=os.path.basename(fileLoc)
    blob = bucket.blob(filename)
    outfile=fileLoc
    blob.upload_from_filename(outfile)

# Function to send data to Firebase realtime database
def storeData(data):
    now=datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    filename=os.path.basename(fileLoc)
    ref = db.reference('/readings')
    ref.push({
            'temp':data['temp'],
            'fahrenheit':data['fahrenheit'],
            'pressure' : data['pressure'],
            'humidity' : data['humidity'],
            'powerStatus':data['powerStatus'],
            'decision':data['decision'],
            'timestamp': dt_string,
            'image': filename
        })

# Print current data to console
# Depending on current temp and powerStatus of smart socket turn on/off socket/heater
# Display message on raspberry pi LEDs depending on value of temp
# Run every 300 seconds (5 minutes)

# Set temperature restrictions
lowTemp=17 # temp should be lower than this for the heater to be turned on
highTemp=22 # temp should be higher than this for the heater to be turned off

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

       # frame = 1    
        fileLoc = photo.capturePhoto() # set variable to result of run photo.capturePhoto function
        # Send image to firebase storage
        storeImage(fileLoc)

        # use joystick on sense hat to update temperature restrictions(lowTemp and highTemp values)
        for event in sense.stick.get_events():
            if event.action == "pressed":
                if event.direction == "up":
                    lowTemp += 1
                    print("lowTemp increased")
                    print(lowTemp)
                elif event.direction == "down":
                    lowTemp -= 1
                    print("lowTemp decreased")
                    print(lowTemp)
                elif event.direction == "left":
                    highTemp +=1
                    print("highTemp increased")
                    print(highTemp)
                elif event.direction == "right":
                    highTemp -=1
                    print("highTemp decreased")
                    print(highTemp)
        # If temp is lower and the heater is turned off
        if temp < lowTemp and powerStatus == "OFF":
            # Check if the room is occupied
            if face_detect.detectFace(fileLoc):
                # If a face has been detected turn the smart socket/heater on
                # Show message on sense hat LEDs    
                requests.get("http://10.100.0.149/cm?cmnd=Power%20On")
                sense.show_message("Brrr Turning Heater On", text_colour=blue)
                current['decision']="Turn ON"
                print("face detected, heater turned on")
            else: 
                current['decision']="No Change"   
        # if temp is higher and heater is turned on         
        elif temp > highTemp and  powerStatus == "ON":
            # Turn the smart socket/heater off
            # Show message on sense hat LEDs
            requests.get("http://10.100.0.149/cm?cmnd=Power%20Off")
            sense.show_message("Turning Heater Off", text_colour=red)
            current['decision']="Turn OFF"
            print("Turning Heater Off")

        # Or show this message on sense hat LEDs
        else:  
            sense.show_message("Nice and Cosy", text_colour=green)
            current['decision']="No Change"

        # Send data to firebase realtime database
        storeData(current) 

        # publish data to ThingSpeak 
        payload=f"field1={temp}&field2={humidity}&field3={pressure}&field4={powerStatusLog}"
        mqttc.publish(topic, payload)
        # Run every 300 seconds (5 minutes)
        sleep(300)
        
    # If there is an error print what it is and exit.
    except Exception as e:
        print('something wrong '+ str(e))
        print(e)
        logging.info('Interrupted')
        sys.exit(0) 
    
# to run - python3 main.py mqtt://mqtt3.thingspeak.com:8883