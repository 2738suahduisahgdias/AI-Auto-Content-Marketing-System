import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from content_workbench.storage.db import connect, expand_schema
from content_workbench.domain.services import Workbench
from content_workbench.providers.local import LocalExecutors

class SkillInjectionTest(unittest.TestCase):
    def test_codex_gets_configured_skills_and_records_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); db=root/'test.db'
            with connect(db) as conn: expand_schema(conn)
            wb=Workbench(db,root)
            item=wb.create_item('article','wechat_official_account','技能测试',{'text':'测试'})
            plan={'platform':'公众号','pictures':[{'id':1,'description':'流程图'}]}
            old=wb.save_revision(item['id'],'draft',{'text':'旧正文','creative_plan':plan},item['version'])
            item=wb.get_item(item['id'])
            wb.approve(item['id'],old,item['manifest']['hash'],kind='article')
            item=wb.get_item(item['id'])
            config={'engine':'codex_cli','prompt':'简明','timeout_seconds':60,'custom':{}}
            snapshot={'skills':[{'path':'skills/writing/test.md','version':'abc'}]}
            with patch('content_workbench.providers.local.require_agent_enabled', return_value=config), patch('content_workbench.agents.writing.writing_context',return_value=('测试技能要求',snapshot)), patch('content_workbench.providers.text.CodexCLIProvider.complete_json',return_value={'text':'真实结构测试正文'}) as generate:
                result=LocalExecutors(wb).generate_text({'kind':'article.draft','aggregate_id':item['id'],'input':{'expected_version':item['version']}},Mock())
            prompt=json.loads(generate.call_args.args[0])
            self.assertEqual(prompt['writing_skills'],'测试技能要求')
            payload=wb.get_revision(result['revision_id'])['payload']
            self.assertEqual(payload['generation'],snapshot)
            self.assertEqual(payload['creative_plan'],plan)
            self.assertNotEqual(wb.get_item(item['id'])['state'],'approved')
