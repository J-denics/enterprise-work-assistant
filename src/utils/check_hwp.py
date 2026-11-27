import argparse
import json

from hwpx import HwpxDocument


parser = argparse.ArgumentParser()
parser.add_argument("file", help="Path to the original HWP file")
args = parser.parse_args()

doc = HwpxDocument.open(args.file)

for number, table in enumerate(doc.tables.map()["tables"], start=1):
    for cell in table["cells"]:
        record = {
            "table": number,
            "row": cell["row"],
            "col": cell["col"],
            "text": cell["text"],
        }
        print(json.dumps(record, ensure_ascii=False))
