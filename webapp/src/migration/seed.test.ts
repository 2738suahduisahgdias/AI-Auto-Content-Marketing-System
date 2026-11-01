import {expect,it} from 'vitest';
import {seedYingxuTask} from './seed';
it('已有任务继续带入原稿、录音和已关联素材，不新造空项目',()=>{
 const task:any={title:'旧任务',scripts:{master:'原稿'},files:[{id:7,kind:'asset',original_name:'live.mp4',url:'/api/files/7/media',media_info:{duration_seconds:12}},{id:8,kind:'audio',original_name:'voice.wav',url:'/api/files/8/media'}],asset_plan:[{file_id:7,name:'原镜头',start_seconds:0,end_seconds:99,source:'原来源'}]};
 const seeded=seedYingxuTask(task);
 expect(seeded.manuscript.text).toBe('原稿');expect(seeded.voiceFileId).toBe(8);
 expect(seeded.shots[0].fileId).toBe(7);expect(seeded.shots[0].duration).toBe(12);
 expect(seeded.shots[0].originalPlan.source).toBe('原来源');
 const saved={manuscript:{text:'已编辑'},shots:[]};task.source={yingxu:{snapshot:saved}};
 expect(seedYingxuTask(task)).toBe(saved);
});
