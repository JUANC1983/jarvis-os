import os

class FileUploadEngine:

    def __init__(self):

        self.upload_dir="uploads"

        os.makedirs(self.upload_dir,exist_ok=True)


    def save(self,file):

        path=os.path.join(self.upload_dir,file.filename)

        with open(path,"wb") as f:

            f.write(file.file.read())

        return{
        "path":path,
        "filename":file.filename
        }
