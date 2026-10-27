"""Synthetic workbook shared by database and browser checks."""
from io import BytesIO
from openpyxl import Workbook


def fixture(*_):
    book=Workbook();sheet=book.active;sheet.title='Hospitals'
    sheet.append(['Name','City','Phone','Status']);sheet.append(['Shared Drive Hospital','Jaipur','0012345678','New Lead'])
    content=BytesIO();book.save(content);content.seek(0)
    return content,'Hospitals.xlsx','.xlsx'

