import cv2
import mediapipe as mp
import numpy as np

class GolfSwingVisionPro:

    def __init__(self):

        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose()

    def analyze(self,video_path):

        cap = cv2.VideoCapture(video_path)

        frames = []

        while True:

            ret,frame = cap.read()

            if not ret:
                break

            frames.append(frame)

        cap.release()

        posture_flags = []

        for frame in frames[::10]:

            img = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)

            results = self.pose.process(img)

            if results.pose_landmarks:

                landmarks = results.pose_landmarks.landmark

                shoulder = landmarks[11]
                hip = landmarks[23]

                spine_angle = abs(shoulder.y - hip.y)

                if spine_angle < 0.05:

                    posture_flags.append("loss_of_posture")

        faults = []

        if posture_flags:
            faults.append("Postura perdida durante el swing")

        return {

            "faults":faults,

            "recommendations":[
                "Mantener inclinación de columna estable",
                "Trabajar drills de postura",
                "Fortalecer core"
            ]

        }

