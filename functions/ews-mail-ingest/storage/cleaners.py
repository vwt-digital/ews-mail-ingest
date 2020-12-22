import logging
import tempfile

from defusedxml import ElementTree as defusedxml_ET
# Etree is triggered as a security risk by bandit, but we use defusedxml to sanitize before reading into etree
from lxml import etree as ET  # nosec
from PyPDF2 import PdfFileWriter, PdfFileReader


class FileCleaner:
    def __init__(self, file, file_name, content_type):
        self.file = file
        self.file_name = file_name
        self.content_type = content_type

        self.cleaners = {
            'application/pdf': self._clean_pdf,
            'application/xml': self._clean_xml,
            'text/xml': self._clean_xml
        }

        self.clean = self.cleaners.get(self.content_type, self._clean_file)

    def clean(self):
        pass

    def _clean_pdf(self):
        writer = PdfFileWriter()
        with tempfile.TemporaryFile(mode='w+b') as temp_file, self.file as input_file:
            buffer = input_file.read(1024)
            while buffer:
                temp_file.write(buffer)
                buffer = input_file.read(1024)
            reader = PdfFileReader(temp_file, strict=False)
            [writer.addPage(reader.getPage(i)) for i in range(0, reader.getNumPages())]
            writer.removeLinks()
            with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as output_file:
                writer.write(output_file)
        return open(output_file.name, 'rb')

    def _clean_xml(self):
        with self.file as f:
            xml_string = f.read()
        safe_xml_tree = defusedxml_ET.fromstring(xml_string)
        # Etree is triggered as a security risk by bandit, but we use defusedxml to sanitize before reading into etree
        safe_xml_tree = ET.fromstring(defusedxml_ET.tostring(safe_xml_tree))  # nosec

        for elem in safe_xml_tree.getiterator():
            elem.tag = ET.QName(elem).localname

        safe_xml_tree = ET.ElementTree(safe_xml_tree)

        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as cleaned_xml_file:
            safe_xml_tree.write(cleaned_xml_file, encoding="utf-8", method="xml", xml_declaration=True)

        return cleaned_xml_file

    def _clean_file(self):
        logging.error('Attempting to clean file {} with content-type {}. This file type is not supported'
                      .format(self.file_name, self.content_type))
        return self.file
