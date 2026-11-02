import unittest
from unittest.mock import Mock, patch
from content_workbench.domain.errors import DomainError
from content_workbench.topics.chrome_collection import collect

class ChromeCollectionTest(unittest.TestCase):
    @patch('content_workbench.topics.chrome_collection.Bridge')
    def test_hot_keeps_original_parser_and_ranks(self, factory):
        bridge = factory.return_value
        bridge.snapshot.return_value = {'url':'https://www.douyin.com/hot'}
        bridge.evaluate.return_value = [{'title':'真实标题','canonical_url':'https://www.douyin.com/hot/1','metadata':{}}]
        result = collect('hot')
        self.assertEqual(1, result['items'][0]['rank'])
        self.assertIn('querySelectorAll',bridge.evaluate.call_args.args[0])

    @patch('content_workbench.topics.chrome_collection.Bridge')
    def test_missing_collection_never_returns_successful_empty_scan(self, factory):
        bridge = factory.return_value
        bridge.snapshot.return_value = {'tree':['收藏夹']}
        bridge.click_text.return_value = False
        bridge.evaluate.return_value = False
        with self.assertRaises(DomainError) as error: collect('favorites',collection='不存在')
        self.assertEqual('COLLECTION_NOT_FOUND',error.exception.code)

    @patch('content_workbench.topics.chrome_collection.Bridge')
    def test_login_requires_positive_collection_evidence(self, factory):
        factory.return_value.snapshot.return_value = {'tree':[]}
        with self.assertRaises(DomainError) as error: collect('login')
        self.assertEqual('LOGIN_REQUIRED',error.exception.code)
