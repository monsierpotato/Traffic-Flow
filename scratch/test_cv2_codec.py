import cv2
import numpy as np
fourcc = cv2.VideoWriter_fourcc(*'avc1')
out = cv2.VideoWriter('test.mp4', fourcc, 30.0, (640, 480))
if not out.isOpened():
    print("avc1 not supported")
else:
    print("avc1 supported")
out.release()
