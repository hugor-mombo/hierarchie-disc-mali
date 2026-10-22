'use client';
import {useEffect,useId,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
type Option={value:string;label:string};
export default function SelectMenu({label,value,options,onChange}:{label:string;value:string;options:Option[];onChange:(value:string)=>void}){
 const id=useId(),trigger=useRef<HTMLButtonElement>(null),list=useRef<HTMLDivElement>(null),typed=useRef({text:'',at:0});
 const[open,setOpen]=useState(false),[active,setActive]=useState(0),[position,setPosition]=useState({left:0,top:0,width:0,maxHeight:280});
 const selected=options.findIndex(o=>o.value===value);
 function show(index=selected<0?0:selected){
  const rect=trigger.current!.getBoundingClientRect(),below=window.innerHeight-rect.bottom-12,above=rect.top-12,up=below<180&&above>below;
  const maxHeight=Math.max(40,Math.min(280,up?above:below)),width=Math.min(Math.max(rect.width,220),window.innerWidth-24);
  setPosition({left:Math.max(12,Math.min(rect.left,window.innerWidth-width-12)),top:up?rect.top-maxHeight-4:rect.bottom+4,width,maxHeight});setActive(index);setOpen(true);
  requestAnimationFrame(()=>document.getElementById(id+'-'+index)?.scrollIntoView({block:'nearest'}));
 }
 function move(index:number){setActive(index);document.getElementById(id+'-'+index)?.scrollIntoView({block:'nearest'});}
 function choose(index:number){if(options[index])onChange(options[index].value);setOpen(false);}
 useEffect(()=>{
  if(!open)return;
  const outside=(e:PointerEvent)=>{if(!trigger.current?.contains(e.target as Node)&&!list.current?.contains(e.target as Node))setOpen(false);};
  const close=(e:Event)=>{if(!list.current?.contains(e.target as Node))setOpen(false);};
  document.addEventListener('pointerdown',outside);window.addEventListener('resize',close);window.addEventListener('scroll',close,true);
  return()=>{document.removeEventListener('pointerdown',outside);window.removeEventListener('resize',close);window.removeEventListener('scroll',close,true);};
 },[open]);
 return <div className="select-menu"><span id={id+'-label'}>{label}</span><button ref={trigger} type="button" role="combobox" aria-labelledby={id+'-label'} aria-expanded={open} aria-controls={open?id:undefined} aria-haspopup="listbox" aria-activedescendant={open?id+'-'+active:undefined} onClick={()=>open?setOpen(false):show()} onKeyDown={e=>{
  if(e.key==='Tab'){setOpen(false);return;}
  if(e.key==='Escape'){e.preventDefault();setOpen(false);return;}
  if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?options.length-1:Math.max(0,Math.min(options.length-1,(open?active:Math.max(0,selected))+(e.key==='ArrowDown'?1:-1)));if(open)move(next);else show(next);return;}
  if(e.key==='Enter'||e.key===' '){e.preventDefault();if(open)choose(active);else show();return;}
  if(e.key.length===1&&!e.ctrlKey&&!e.metaKey&&!e.altKey){e.preventDefault();const now=Date.now(),text=(now-typed.current.at<700?typed.current.text:'')+e.key;typed.current={text,at:now};const index=options.findIndex(o=>o.label.toLocaleLowerCase('fr').startsWith(text.toLocaleLowerCase('fr')));if(index>=0){if(open)move(index);else show(index);}}
 }}><span>{options[selected]?.label||options[0]?.label}</span><span aria-hidden="true">⌄</span></button>{open&&createPortal(<div ref={list} id={id} className="select-menu-options" role="listbox" aria-labelledby={id+'-label'} style={position}>{options.map((option,index)=><div id={id+'-'+index} key={option.value} role="option" aria-selected={option.value===value} className={index===active?'highlighted':''} onMouseDown={e=>e.preventDefault()} onMouseEnter={()=>setActive(index)} onClick={()=>choose(index)}>{option.label}{option.value===value&&<span aria-hidden="true">✓</span>}</div>)}</div>,document.body)}</div>;
}
