import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from content_workbench.articles.images import search_images, adopt_image, generate_image
from content_workbench.domain.errors import DomainError

class ImageServicesTest(unittest.TestCase):
    def test_search_rejects_empty_without_network(self):
        with patch('content_workbench.articles.images.commons') as network:
            with self.assertRaises(DomainError): search_images(' ')
            network.assert_not_called()

    def test_download_refuses_foreign_host(self):
        page={'title':'File:test.png','imageinfo':[{'mime':'image/png','url':'https://localhost/private.png'}]}
        with patch('content_workbench.articles.images.commons',return_value=[page]), patch('content_workbench.articles.images.request_bytes') as network:
            with self.assertRaises(DomainError) as error: adopt_image(Mock(),'File:test.png')
            self.assertEqual(error.exception.code,'IMAGE_HOST_INVALID')
            network.assert_not_called()

    def test_cli_rejects_arbitrary_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);secret=root/'private.png';secret.write_bytes(b'private')
            context=Mock()
            def execute(args,**kwargs):
                Path(args[args.index('-o')+1]).write_text(json.dumps({'image_path':str(secret),'error':None}))
            context.run_process.side_effect=execute
            with patch('shutil.which',return_value='/bin/codex'):
                with self.assertRaises(DomainError) as error:generate_image(Mock(root=root),{'id':'job','input':{'prompt':'diagram'}},context)
            self.assertEqual(error.exception.code,'CODEX_IMAGE_PATH_INVALID')
            self.assertEqual(context.run_process.call_count,1)

    def test_pagination_preserves_text_and_bounds(self):
        from content_workbench.articles.page_worker import render_pages, BOTTOM
        font=Path('/System/Library/Fonts/STHeiti Light.ttc')
        if not font.exists():self.skipTest('CJK font unavailable')
        text=''.join('验收条目%d，知识库检索与人工处理。'%i for i in range(180))
        with tempfile.TemporaryDirectory() as tmp:
            pages=render_pages({'title':'验收','text':text},tmp,font)
            self.assertGreater(len(pages),1)
            blocks=[b for p in pages for b in p['blocks']]
            self.assertEqual(''.join(b['text'] for b in blocks),'验收'+text)
            for b in blocks:self.assertLessEqual(b['y']+b['height'],BOTTOM)
            for p in pages:self.assertTrue((Path(tmp)/p['file']).exists())

    def test_xhs_upload_uses_ordered_pages_and_never_publishes(self):
        from content_workbench.publishing.webbridge_worker import prepare_xhs_images
        bridge=Mock()
        bridge.snapshot.return_value={'tree':[]}
        bridge.click_text.return_value=True
        bridge.evaluate.return_value={'title':'验收','body':'简介\n\n#验收','count':2,'loaded':True,'ready':True}
        bridge.result.side_effect=lambda target,status,fields,extra: {'status':status,**extra}
        source={'title':'简介','article_pages':[{'asset_id':'a','absolute_path':'/local/1.png'},{'asset_id':'b','absolute_path':'/local/2.png'}]}
        with patch('content_workbench.publishing.webbridge_worker.fill'):
            result=prepare_xhs_images(bridge,{'source':source,'payload':{'title':'验收','tags':'#验收'},'target_id':'t'},'prepare')
        self.assertTrue(result['article_images_verified'])
        self.assertFalse(result['auto_published'])
        bridge.call.assert_any_call('upload',{'selector':'input[type=file]','files':['/local/1.png','/local/2.png']})
        bridge.click_text.assert_called_once_with('上传图文')

    def test_xhs_login_stops_before_upload(self):
        from content_workbench.publishing.webbridge_worker import prepare_xhs_images
        bridge=Mock();bridge.snapshot.return_value={'tree':['扫码登录']}
        result=prepare_xhs_images(bridge,{'source':{'title':'说明','article_pages':[{'asset_id':'a','absolute_path':'/1.png'}]},'payload':{'title':'标题'},'target_id':'t'},'prepare')
        self.assertEqual(result['status'],'login_required')
        self.assertNotIn('upload',[call.args[0] for call in bridge.call.call_args_list])

    def test_cli_result_is_imported_without_api_credentials(self):
        import os
        from tests.test_article_images import PNG
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);home=root/'codex';folder=home/'generated_images';folder.mkdir(parents=True)
            image=folder/'accepted.png';image.write_bytes(PNG)
            context=Mock();workbench=Mock(root=root);workbench.register_asset.return_value='asset-real'
            def execute(args,**kwargs):
                self.assertIn('--ignore-user-config',args)
                self.assertIn('shell_tool',args)
                Path(args[args.index('-o')+1]).write_text(json.dumps({'image_path':str(image),'error':None}))
            context.run_process.side_effect=execute
            with patch.dict(os.environ,{'CODEX_HOME':str(home)}),patch('shutil.which',return_value='/bin/codex'):
                result=generate_image(workbench,{'id':'job','input':{'prompt':'diagram'}},context)
            self.assertEqual(result['asset_id'],'asset-real')
            self.assertEqual(result['source']['provider'],'codex_cli')
            context.run_process.assert_called_once()
