import {useEffect,useState} from "react";
import {Activity,ArrowUpRight,Coffee,Maximize2,Minimize2,Minus,Play,Square} from "lucide-react";
import type {Live} from "./types";
import {duration} from "./utils";
export default function Widget(){
 const [live,setLive]=useState<Live|null>(null);
 const [compact,setCompact]=useState(false);
 const [busy,setBusy]=useState(false);
 useEffect(()=>window.workpulse.onLive(setLive),[]);
 const isBreak=live?.status==="break";
 const finished=live?.status==="finished";
 const label=finished?"Finished":isBreak?"On break":live?.state==="private"?"Private pause":live?.state==="idle"?"Idle":"Working";
 const timer=isBreak?(live?.break_seconds||0):(live?.today?.work||0);
 async function change(action:string){
  if(action==="finish"&&!window.confirm("Finish your workday? Your activity will be saved."))return;
  setBusy(true);
  try{await window.workpulse.request("/session/"+action,"POST");}
  catch(e){window.alert(e instanceof Error?e.message:String(e));}
  finally{setBusy(false);}
 }
 function toggle(compactMode:boolean){setCompact(compactMode);void window.workpulse.shrinkWidget(compactMode);}
 return <div className={"widget-shell "+(compact?"compact":"")}>
  {compact?<div className="widget-pill drag"><span className="status-dot"/><span className="widget-time">{duration(timer)}</span><button className="icon-action no-drag" aria-label="Expand widget" onClick={()=>toggle(false)}><Maximize2 size={15}/></button></div>:
   <><div className="widget-header drag"><span className="brandmark"><Activity size={14}/></span><strong>WorkPulse</strong><span className="widget-spacer"/><button className="icon-action no-drag" title="Compact widget" aria-label="Compact widget" onClick={()=>toggle(true)}><Minimize2 size={14}/></button><button className="icon-action no-drag" title="Minimize to tray" aria-label="Minimize to tray" onClick={()=>window.workpulse.minimizeWidget()}><Minus size={15}/></button><button className="icon-action no-drag" title="Dashboard" onClick={()=>window.workpulse.showDashboard()}><ArrowUpRight size={15}/></button></div>
   <div className="widget-main"><div><span className={"status-dot "+(isBreak?"pause":"")}/><span className="widget-status">{label}</span></div><div className="widget-clock">{duration(live?.today?.work||0)}</div>
    <div className="widget-actions">{finished?<button className="widget-primary" disabled={busy} onClick={()=>change("start")}><Play size={13}/> Start work</button>:<><button className="widget-primary" disabled={busy} onClick={()=>change(isBreak?"resume":"break")}>{isBreak?<Play size={13}/>:<Coffee size={13}/>} {isBreak?"Resume":"Take break"}</button><button className="widget-secondary" disabled={busy} onClick={()=>change("finish")}><Square size={12}/> Finish day</button></>}</div>
   </div></>}
 </div>;
}
