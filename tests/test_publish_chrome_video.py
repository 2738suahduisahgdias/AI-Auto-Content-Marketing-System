import unittest
from unittest.mock import Mock, patch
from content_workbench.publishing.webbridge_worker import prepare_chrome_video

class ChromeVideoTest(unittest.TestCase):
    def data(self):
        return {'target_id':'test','source':{'absolute_video_path':'/test.mp4'},'payload':{'title':'验收','description':'正文','tags':'#AI'}}

    @patch('content_workbench.publishing.webbridge_worker.media_duration', return_value=7.4)
    def test_upload_and_readback(self, duration):
        bridge=Mock()
        state={'title':True,'body':True,'durations':[7.4],'text':'编辑','titleValue':'验收','bodyValue':'正文#AI\u200b'}
        bridge.evaluate.side_effect=[{'file':True,'text':'上传视频'},state,state]
        prepare_chrome_video(bridge,self.data(),'douyin','prepare')
        self.assertEqual(bridge.call.call_args_list[1].args,('upload',{'selector':'input[type=file]','files':['/test.mp4']}))
        self.assertEqual(bridge.result.call_args.args[1],'preview_ready')
        self.assertFalse(bridge.result.call_args.args[3]['auto_published'])
        self.assertFalse(bridge.click_text.called)

    @patch('content_workbench.publishing.webbridge_worker.media_duration', return_value=7.4)
    def test_mismatched_fields_never_ready(self, duration):
        bridge=Mock();state={'title':True,'body':True,'durations':[7.4],'text':'编辑','titleValue':'旧标题','bodyValue':'正文\n#AI'}
        bridge.evaluate.side_effect=[{'file':True,'text':'上传视频'},state,state]
        prepare_chrome_video(bridge,self.data(),'xiaohongshu','prepare')
        self.assertFalse(bridge.result.called);self.assertTrue(bridge.error.called)

    def test_execute_cannot_publish(self):
        bridge=Mock();prepare_chrome_video(bridge,self.data(),'douyin','execute')
        self.assertFalse(bridge.call.called);self.assertTrue(bridge.error.called)

    def test_login_stops_before_upload(self):
        bridge=Mock();bridge.evaluate.return_value={'text':'扫码登录','file':False}
        result=prepare_chrome_video(bridge,self.data(),'douyin','prepare')
        self.assertEqual(result['status'],'login_required');self.assertEqual(bridge.call.call_count,1)

    @patch('content_workbench.publishing.webbridge_worker.media_duration', return_value=7.4)
    def test_retry_resumes_same_target_without_uploading_again(self, duration):
        bridge=Mock();bridge.snapshot.return_value={'url':'https://creator.douyin.com/creator-micro/content/post/video'}
        ready={'title':True,'body':True,'durations':[7.4],'text':'编辑','titleValue':'验收','bodyValue':'正文#AI'}
        bridge.evaluate.side_effect=[ready,ready]
        prepare_chrome_video(bridge,self.data(),'douyin','prepare')
        self.assertFalse(any(c.args[0] in ('navigate','upload') for c in bridge.call.call_args_list))
        self.assertEqual(bridge.result.call_args.args[1],'preview_ready')

    @patch('content_workbench.publishing.webbridge_worker.media_duration', return_value=7.4)
    def test_first_target_without_session_still_uploads(self, duration):
        bridge=Mock();bridge.snapshot.side_effect=RuntimeError('没有当前标签')
        state={'title':True,'body':True,'durations':[7.4],'text':'编辑','titleValue':'验收','bodyValue':'正文#AI'}
        bridge.evaluate.side_effect=[{'file':True,'text':'上传视频'},state,state]
        prepare_chrome_video(bridge,self.data(),'douyin','prepare')
        self.assertEqual(bridge.call.call_args_list[1].args[0],'upload')
