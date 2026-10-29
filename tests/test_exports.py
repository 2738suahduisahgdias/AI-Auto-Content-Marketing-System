import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from unittest import mock

from content_workbench.accounts.exports import channels_metrics, douyin_metrics, official_metrics, read_xlsx, xhs_metrics


def workbook(path, rows):
    body = []
    for row_index, row in enumerate(rows, 1):
        cells = []
        for index, value in enumerate(row):
            reference = f"{chr(65 + index)}{row_index}"
            cells.append(f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        body.append(f'<row r="{row_index}">' + "".join(cells) + "</row>")
    sheet = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(body) + "</sheetData></worksheet>"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>")
        archive.writestr("_rels/.rels", "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'/>")
        archive.writestr("xl/workbook.xml", "<workbook xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main' xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'><sheets><sheet name='Sheet1' sheetId='1' r:id='rId1'/></sheets></workbook>")
        archive.writestr("xl/_rels/workbook.xml.rels", "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'><Relationship Id='rId1' Target='worksheets/sheet1.xml'/></Relationships>")
        archive.writestr("xl/worksheets/sheet1.xml", sheet)


class ExportCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="account-exports-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_xlsx_and_platform_metric_mapping(self):
        watch = self.root / "watch.xlsx"
        interaction = self.root / "interaction.xlsx"
        followers = self.root / "followers.xlsx"
        publishing = self.root / "publishing.xlsx"
        workbook(watch, [["指标", "数值"], ["曝光", 361], ["观看", 124], ["封面点击率(%)", 8.3],
                         ["平均观看时长(s)", 44.3], ["总观看时长(s)", 1129], ["总完播率(%)", 0.8]])
        workbook(interaction, [["指标", "数值"], ["点赞", 4], ["评论", 0], ["收藏", 2], ["分享", 0]])
        workbook(followers, [["指标", "数值"], ["净涨粉", 0], ["新增关注", 1], ["取消关注", 0],
                             ["主页访客", 8], ["主页转粉率(%)", 12.5]])
        workbook(publishing, [["指标", "数值"], ["总发布", 2], ["发布视频", 1], ["发布图文", 1]])
        self.assertEqual("361", read_xlsx(watch)["Sheet1"][1][1])
        metrics = xhs_metrics({"watch": watch, "interaction": interaction, "followers": followers, "publishing": publishing})
        self.assertEqual(124, metrics["views"])
        self.assertEqual(44.3, metrics["avgConsumptionSeconds"])
        self.assertEqual(8, metrics["profileVisits"])
        self.assertEqual(2, metrics["periodPublications"])

    def test_douyin_daily_export_aggregates_counts_and_latest_fans(self):
        work = self.root / "work.xlsx"
        fans = self.root / "fans.xlsx"
        workbook(work, [["日期", "投稿量", "总播放量", "总点赞量", "总分享量", "总评论量"],
                        ["2026-10-27", 0, 6, 0, 0, 0], ["2026-10-28", 1, 239, 2, 0, 0]])
        workbook(fans, [["日期", "总粉丝量", "粉丝净增", "吸粉量", "脱粉量", "回访粉丝量"],
                        ["2026-10-27", 45, 0, 0, 0, 1], ["2026-10-28", 45, 0, 0, 0, 1]])
        metrics = douyin_metrics(work, fans)
        self.assertEqual(245, metrics["views"])
        self.assertEqual(2, metrics["likes"])
        self.assertEqual(1, metrics["periodPublications"])
        self.assertEqual(45, metrics["fans"])
        self.assertEqual(2, metrics["returningFans"])
    def test_channels_csv_and_official_history(self):
        path = self.root / "channels.csv"
        path.write_text("视频号视频详情数据,,,,,\n说明,,,,,\n时间,播放,推荐,喜欢,评论,分享,关注\n2026/10/28,10,0,1,0,0,0\n2026/10/27,20,0,2,0,0,1\n", encoding="utf-8-sig")
        metrics = channels_metrics(path)
        self.assertEqual(10, metrics["views"])
        self.assertEqual(30, metrics["periodViews"])
        self.assertEqual(3, metrics["likes"])
        rows = [{"日期": "20251028", "阅读次数": 5, "阅读人数": 4, "分享次数": 1, "收藏次数": 2, "群发篇数": 1, "渠道": "全部"}]
        with mock.patch("content_workbench.accounts.exports.read_xls", return_value=rows):
            official = official_metrics("unused.xls")
        self.assertEqual(5, official["views"])
        self.assertEqual(2, official["favorites"])
        self.assertEqual(1, len(official["daily_history"]))


if __name__ == "__main__":
    unittest.main()
