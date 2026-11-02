import json
import shutil
import subprocess
import unittest
from content_workbench.accounts.existing_browser import xhs_favorite_cards


@unittest.skipUnless(shutil.which('node'), 'Node required for DOM parser fixture')
class XhsBoardParserTest(unittest.TestCase):
    def test_board_note_links_are_collected_without_board_or_author_links(self):
        class FixtureBridge:
            def evaluate(self, script):
                harness = '''const vm=require('node:vm');
                const image={alt:'AI 客服落地案例',src:'https://example.com/cover.jpg'};
                const card={innerText:'AI 客服落地案例\\n作者\\n303',querySelector:()=>image};
                const link=href=>({href,innerText:card.innerText,closest:()=>card,querySelector:()=>image});
                const links=[link('https://www.xiaohongshu.com/board/album123'),link('https://www.xiaohongshu.com/board/album123/note456?xsec_token=test'),link('https://www.xiaohongshu.com/board/album123/note456'),link('https://www.xiaohongshu.com/user/profile/author')];
                console.log(JSON.stringify(vm.runInNewContext(process.argv[1],{document:{querySelectorAll:()=>links}})));'''
                return json.loads(subprocess.check_output(['node', '-e', harness, script], text=True))
        items=xhs_favorite_cards(FixtureBridge())
        self.assertEqual(1,len(items))
        self.assertEqual('note456',items[0]['platform_item_id'])
        self.assertEqual('AI 客服落地案例',items[0]['title'])
        self.assertNotIn('xsec_token',items[0]['canonical_url'])


class XhsCollectionReadinessTest(unittest.TestCase):
    def test_collection_waits_for_clickable_dom_after_ax_text_arrives(self):
        from unittest.mock import patch, Mock
        from content_workbench.accounts.existing_browser import wait_click_dom_text
        with patch('content_workbench.accounts.existing_browser.click_dom_text',side_effect=[False,False,True]) as click, patch('content_workbench.accounts.existing_browser.time.sleep'):
            self.assertTrue(wait_click_dom_text(Mock(),'精选选题',timeout=1))
            self.assertEqual(click.call_count,3)

    def test_missing_collection_has_bounded_wait_not_successful_empty_scan(self):
        from unittest.mock import patch, Mock
        from content_workbench.accounts.existing_browser import wait_click_dom_text
        with patch('content_workbench.accounts.existing_browser.click_dom_text',return_value=False), patch('content_workbench.accounts.existing_browser.time.sleep'), patch('content_workbench.accounts.existing_browser.time.monotonic',side_effect=[0,0,1,2]):
            self.assertFalse(wait_click_dom_text(Mock(),'不存在',timeout=2))

    @unittest.skipUnless(shutil.which('node'), 'Node required for DOM parser fixture')
    def test_hidden_duplicate_title_does_not_block_visible_collection(self):
        from content_workbench.accounts.existing_browser import click_dom_text
        class FixtureBridge:
            observed = None
            def evaluate(self, script):
                harness = """const vm=require('node:vm');let hiddenClicks=0,visibleClicks=0;
                const hidden={childElementCount:0,innerText:'精选选题',getBoundingClientRect:()=>({width:0,height:0}),click:()=>hiddenClicks++};
                const visible={childElementCount:0,innerText:'精选选题',getBoundingClientRect:()=>({width:100,height:30}),click:()=>visibleClicks++};
                const result=vm.runInNewContext(process.argv[1],{document:{querySelectorAll:()=>[hidden,visible]}});
                console.log(JSON.stringify({result,hiddenClicks,visibleClicks}));"""
                self.observed=json.loads(subprocess.check_output(['node','-e',harness,script],text=True))
                return self.observed['result']
        bridge=FixtureBridge();self.assertTrue(click_dom_text(bridge,'精选选题'))
        self.assertEqual(0,bridge.observed['hiddenClicks']);self.assertEqual(1,bridge.observed['visibleClicks'])
