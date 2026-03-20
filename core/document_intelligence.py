import os


class DocumentIntelligence:

    def analyze(self,file_path):

        extension=os.path.splitext(file_path)[1]

        if extension in [".pdf",".docx",".txt"]:

            return{
            "file":file_path,
            "analysis":"document review scaffold",
            "capabilities":[
            "contract review",
            "investment memo analysis",
            "legal review",
            "medical document review"
            ]
            }

        return{
        "file":file_path,
        "analysis":"unsupported format"
        }
