import pdfplumber
import docx

class DocumentAnalysisEngine:

    def analyze_pdf(self,path):

        text=""

        with pdfplumber.open(path) as pdf:

            for page in pdf.pages:

                text+=page.extract_text() or ""

        return{
        "summary":text[:2000]
        }


    def analyze_docx(self,path):

        doc=docx.Document(path)

        text=" ".join([p.text for p in doc.paragraphs])

        return{
        "summary":text[:2000]
        }
