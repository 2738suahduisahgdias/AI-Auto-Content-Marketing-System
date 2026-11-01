import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {afterEach,expect,it,vi} from 'vitest';
import CollectionKnowledge from './CollectionKnowledge';
vi.mock('@/AppContext',()=>({useApp:()=>({resources:{accounts:{collection_knowledge:{categories:[],entities:[
 {id:'douyin:research',platform:'douyin',category:'research',title:'抖音热榜',url:'https://www.douyin.com/hot',status:'verified',capabilities:{read:true},fields:{rank:'number'},agent_usage:[],errors:[]},
 {id:'douyin:research',platform:'douyin',category:'research',title:'收藏夹研究',url:'https://www.douyin.com/user/self',status:'verified',capabilities:{read:true},fields:{collection:'string'},agent_usage:[],errors:[]}
]}}}})}));
afterEach(cleanup);
it('selects distinct research entities even when the original API repeats the category id',()=>{
 const errors=vi.spyOn(console,'error').mockImplementation(()=>{});
 try{
 render(<MemoryRouter><CollectionKnowledge/></MemoryRouter>);
 expect(screen.getByRole('heading',{name:'抖音热榜'})).toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:/收藏夹研究/}));
 expect(screen.getByRole('heading',{name:'收藏夹研究'})).toBeInTheDocument();
 expect(screen.getByText(/"collection": "string"/)).toBeInTheDocument();
 expect(errors).not.toHaveBeenCalled();
 }finally{errors.mockRestore()}
});
