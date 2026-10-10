"""Prepare a private QuoteSaarthi CSV from a handover ZIP or a catalogue CSV."""
import argparse
import csv
import io
import os
from pathlib import Path
from zipfile import ZipFile

from dotenv import load_dotenv


def prepare(source, destination):
    source=Path(source)
    if source.suffix.lower()=='.zip':
        with ZipFile(source) as archive:
            names=[name for name in archive.namelist() if name.endswith('/data/hospkart_products.cleaned.csv') and '/.venv/' not in name]
            if len(names)!=1:
                raise ValueError('Choose a handover ZIP with one cleaned product catalogue.')
            content=archive.read(names[0])
    elif source.suffix.lower()=='.csv':
        content=source.read_bytes()
    else:
        raise ValueError('Choose the handover ZIP or a catalogue CSV.')
    rows=csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
    if not {'product_name','vendor_name','price'}.issubset(rows.fieldnames or []):
        raise ValueError('Catalogue requires product_name, vendor_name and price columns.')
    count=sum(1 for row in rows if row.get('product_name','').strip())
    if not count:
        raise ValueError('Catalogue has no named products.')
    target=Path(destination)
    target.parent.mkdir(parents=True,exist_ok=True)
    staging=target.with_suffix('.pending')
    staging.write_bytes(content)
    staging.replace(target)
    return count


if __name__=='__main__':
    root=Path(__file__).parent
    load_dotenv(root/'.env')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,default=Path(os.getenv('QUOTESAARTHI_CATALOG_PATH',str(Path(os.getenv('CRM_DATA_DIR',str(root/'data')))/'quotesaarthi/products.csv'))))
    args=parser.parse_args()
    print('Prepared catalogue rows:',prepare(args.source,args.output))
    print('Restart the CRM server after updating its catalogue.')
