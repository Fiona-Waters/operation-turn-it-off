
from picamera import PiCamera
import datetime
import time

# Initialise camera
camera = PiCamera()

# Function to capture a photo and return where it is stored
def capturePhoto():
    camera.start_preview()
    currentTime = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    fileLoc = f'/home/pi/OperationTurnItOff-Assignment/images/frame{currentTime}.jpg' # set the location of image file and current time
    camera.capture(fileLoc) # capture image and store in fileLoc
    print(f'Photo taken at {currentTime}') # print frame number to console
    camera.stop_preview()
    return fileLoc
    
