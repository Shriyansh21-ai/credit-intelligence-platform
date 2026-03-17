import pytesseract
import cv2
import numpy as np
from pdf2image import convert_from_path


class DocumentProcessor:

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path

    def pdf_to_images(self):
        images = convert_from_path(self.pdf_path)
        return images

    def preprocess_image(self, image):

        img = np.array(image)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        thresh = cv2.threshold(
            gray,
            150,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )[1]

        return thresh

    def extract_text(self, image):

        text = pytesseract.image_to_string(image)
        return text

    def process_document(self):

        images = self.pdf_to_images()

        full_text = ""

        for img in images:

            processed = self.preprocess_image(img)
            text = self.extract_text(processed)

            full_text += text

        return full_text