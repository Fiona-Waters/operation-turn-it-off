from __future__ import print_function
from google.cloud import vision

image_uri = '/home/pi/OperationTurnItOff-Assignment/images/frame2.jpg'
#/home/pi/OperationTurnItOff-Assignment/images/frame1.jpg
client = vision.ImageAnnotatorClient()
image = vision.Image()
image.source.image_uri = image_uri

response = client.label_detection(image=image)

print('Labels (and confidence score):')
print('=' * 30)
for label in response.label_annotations:
    print(label.description, '(%.2f%%)' % (label.score*100.))