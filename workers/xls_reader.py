import json
import sys

import xlrd


def main():
    book = xlrd.open_workbook(sys.argv[1])
    sheet = book.sheet_by_index(0)
    headers = [str(value).strip() for value in sheet.row_values(0)]
    rows = []
    for index in range(1, sheet.nrows):
        values = sheet.row_values(index)
        rows.append({headers[column]: value for column, value in enumerate(values)})
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == "__main__":
    main()
