import io
import json
import runpy
import sys
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

from content_workbench.storage.db import PROJECT_ROOT


class XlsReaderCase(unittest.TestCase):
    def test_preserves_numeric_columns_beyond_the_title_row(self):
        matrix = [
            ["", "真实文章标题", "", "", ""],
            ["", "数据指标", "数值", "", ""],
            ["", "阅读(人)", 191.0, "", ""],
        ]
        sheet = SimpleNamespace(nrows=len(matrix), ncols=5, row_values=lambda index: matrix[index])
        book = SimpleNamespace(sheet_by_index=lambda index: sheet)
        output = io.StringIO()
        with mock.patch.dict(sys.modules, {"xlrd": SimpleNamespace(open_workbook=lambda path: book)}), \
                mock.patch.object(sys, "argv", ["xls_reader.py", "article.xls"]), redirect_stdout(output):
            runpy.run_path(str(PROJECT_ROOT / "workers/xls_reader.py"), run_name="__main__")
        rows = json.loads(output.getvalue())
        self.assertEqual("数据指标", rows[0]["真实文章标题"])
        self.assertEqual("数值", rows[0]["column_3"])
        self.assertEqual(191.0, rows[1]["column_3"])


if __name__ == "__main__":
    unittest.main()
