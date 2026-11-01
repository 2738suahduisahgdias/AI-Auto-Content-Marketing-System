import json
import sys

import xlrd


def main():
    book = xlrd.open_workbook(sys.argv[1])
    sheet = book.sheet_by_index(0)
    first_row = sheet.row_values(0) if sheet.nrows else []
    headers = []
    for column in range(sheet.ncols):
        value = str(first_row[column]).strip() if column < len(first_row) else ""
        headers.append(value or f"column_{column + 1}")
    rows = []
    for index in range(1, sheet.nrows):
        values = sheet.row_values(index)
        rows.append({headers[column]: values[column] if column < len(values) else "" for column in range(sheet.ncols)})
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == "__main__":
    main()
