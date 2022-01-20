from __future__ import print_function
from google.cloud import vision
import io

# Function to detect presence of a face using Google Cloud Vision AI
def detectFace(image_uri):
    client = vision.ImageAnnotatorClient()
    with io.open(image_uri, 'rb') as image_file:
            content = image_file.read()

    image = vision.Image(content=content)

    response = client.face_detection(image=image)
    faces = response.face_annotations

    for face in faces:
        print('=' * 30)
        vertices = ['(%s,%s)' % (v.x, v.y) for v in face.bounding_poly.vertices]
        print('Face bounds:', ",".join(vertices))

    return faces 