import {useEffect,useRef} from 'react';
import {mountYingxu} from './yingxu-runtime';
import './yingxu-native.css';
export default function YingxuStudio({onHandoff,onOpenPublisher,onNavigate}:{onHandoff:(payload:{title:string})=>void;onOpenPublisher:()=>void;onNavigate:(page:string)=>void}){
 const host=useRef<HTMLDivElement>(null);const callbacks=useRef({onHandoff,onOpenPublisher,onNavigate});callbacks.current={onHandoff,onOpenPublisher,onNavigate};
 useEffect(()=>{const root=host.current!;root.innerHTML=`<span id="crumb" hidden></span><div class="yx-save-status"><small id="saved"></small></div><div id="main"></div><div id="modal" class="overlay" hidden></div><div id="toast" role="status"></div><input id="upload" type="file" hidden>`;return mountYingxu(root,p=>callbacks.current.onHandoff(p),()=>callbacks.current.onOpenPublisher(),page=>callbacks.current.onNavigate(page))},[]);
 return <div className="yx-native" ref={host}/>;
}
