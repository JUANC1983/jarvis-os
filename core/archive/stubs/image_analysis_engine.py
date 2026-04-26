import cv2

class ImageAnalysisEngine:

    def analyze(self,path):

        img=cv2.imread(path)

        height,width,_=img.shape

        return{
        "resolution":f"{width}x{height}",
        "analysis":"image processed"
        }
