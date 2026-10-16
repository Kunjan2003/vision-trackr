import WorkspaceV2, {type SuiteSection} from "./WorkspaceV2";
import type React from "react";
import {useCallback,useEffect,useState} from "react";
import {Activity,BarChart3,CalendarDays,Check,ChevronDown,Clock3,Coffee,Download,LayoutDashboard,LogOut,Pause,Play,Plus,Settings2,ShieldCheck,Square,Tag,Timer,Trash2,TrendingUp,Monitor,FolderKanban,Target,CalendarCheck,BrainCircuit,Globe2,FileBarChart,DatabaseBackup} from "lucide-react";
import {ResponsiveContainer,BarChart,Bar,CartesianGrid,XAxis,YAxis,Tooltip,LineChart,Line,PieChart,Pie,Cell} from "recharts";
import type {Day,Live,Period,Rule,Settings,State,Totals,User} from "./types";
import {duration,display,hours,localDay,offset} from "./utils";

type View="overview"|"activity"|"categories"|"settings"|SuiteSection;
type Range="today"|"week"|"month";
const colors:Record<State,string>={productive:"#80e1b4",neutral:"#7b92b7",non_productive:"#fa9c80",idle:"#c2a4e6",break:"#efc873"};
const states:State[]=["productive","neutral","non_productive","idle","break"];
const blank:Totals={productive:0,neutral:0,non_productive:0,idle:0,break:0,work:0,productivity:0};
const api=window.workpulse.request;
const fmtTime=(iso:string)=>new Date(iso).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});
function errorText(e:unknown){return e instanceof Error?e.message:String(e);}
function Brand(){return <div className="brand"><div className="brand-icon"><Activity size={22}/></div><span>Work<span className="accent">Pulse</span><small>WORK SMARTER, LIVE BETTER</small></span></div>;}

function Auth({registered,onDone}:{registered:boolean;onDone:(user:User)=>void}){
 const [mode,setMode]=useState<"login"|"register">(registered?"login":"register");
 const [form,setForm]=useState({full_name:"",email:"",password:"",department:""});
 const [accepted,setAccepted]=useState(false);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 async function submit(e:React.FormEvent){
  e.preventDefault();
  if(mode==="register"&&!accepted){setError("Accept the local privacy notice to continue.");return;}
  setBusy(true);setError("");
  try{
   const result=await api("/auth/"+(mode==="register"?"register":"login"),"POST",mode==="register"?form:{email:form.email,password:form.password});
   onDone(result.user);
  }catch(err){setError(errorText(err));}finally{setBusy(false);}
 }
 return <div className="auth-background"><div className="auth-layout">
  <div className="auth-intro"><Brand/><div className="auth-display"><div className="eyebrow"><span className="spark"/> AN INTELLIGENT WORKDAY</div><h1>Your time.<br/><em>In focus.</em></h1><p>Understand your work habits, find your flow, and make every minute count — all from your desktop.</p><div className="auth-features"><span><ShieldCheck size={16}/> Private by design</span><span><Monitor size={16}/> Windows native</span><span><Clock3 size={16}/> Always-on tracking</span></div></div><div className="auth-footnote">Everything stays on your PC. No screenshots. No keylogging.</div></div>
  <div className="auth-card"><div className="eyebrow">WELCOME TO WORKPULSE</div><h2>{mode==="register"?"Create your account":"Welcome back"}</h2><p className="muted">{mode==="register"?"Set up your private workspace in seconds.":"Sign in to continue tracking your workday."}</p>
   <form onSubmit={submit}>
    {mode==="register"&&<><label>Full name<input required minLength={2} maxLength={120} value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})} placeholder="Your full name"/></label><label>Department / role<input maxLength={120} value={form.department} onChange={e=>setForm({...form,department:e.target.value})} placeholder="e.g. Engineering"/></label></>}
    <label>Email address<input type="email" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})} placeholder="you@example.com"/></label>
    <label>Password<input required type="password" minLength={mode==="register"?8:1} value={form.password} onChange={e=>setForm({...form,password:e.target.value})} placeholder="Your password"/></label>
    {mode==="register"&&<label className="privacy-notice"><input type="checkbox" checked={accepted} onChange={e=>setAccepted(e.target.checked)}/><span>I understand that WorkPulse locally records app names, window titles, and durations. It does not record keystrokes or screenshots. All activity remains on this computer.</span></label>}
    {error&&<p className="error-box" role="alert">{error}</p>}
    <button className="primary wide" disabled={busy||mode==="register"&&!accepted}>{busy?"Please wait...":mode==="register"?"Create account & start tracking":"Sign in"} <ChevronDown size={16} className="arrow-right"/></button>
   </form>{registered&&<p className="auth-switch">{mode==="login"?"Already using this device?":"Have an account?"} <button className="text-button" onClick={()=>{setMode(mode==="login"?"register":"login");setError("");}}>{mode==="login"?"Sign in":"Back to login"}</button></p>}
  </div>
 </div></div>;
}
export default function App(){
 const [phase,setPhase]=useState<"loading"|"login"|"register"|"ready">("loading");
 const [profile,setProfile]=useState<User|null>(null);
 const [view,setView]=useState<View>("overview");
 const [range,setRange]=useState<Range>("today");
 const [day,setDay]=useState(localDay());
 const [today,setToday]=useState<Day|null>(null);
 const [period,setPeriod]=useState<Period|null>(null);
 const [live,setLive]=useState<Live|null>(null);
 const [settings,setSettings]=useState<Settings|null>(null);
 const [rules,setRules]=useState<Rule[]>([]);
 const [draftRule,setDraftRule]=useState({pattern:"",category:"productive"});
 const [busy,setBusy]=useState(false);
 const [notice,setNotice]=useState("");
 const [error,setError]=useState("");
 const loadData=useCallback(async()=>{
  if(!profile)return;
  try{
   const query="?day="+day+"&tz="+offset();
   const [daily,aggregate]=await Promise.all([api("/stats/day"+query),range==="today"?Promise.resolve(null):api("/stats/"+range+query)]);
   setToday(daily);
   setPeriod(aggregate||{start:day,days:[{date:day,...daily.totals}],totals:daily.totals});
   setError("");
  }catch(e){setError(errorText(e));}
 },[profile,day,range]);
 useEffect(()=>{
  let cancelled=false;
  async function boot(){
   for(let i=0;i<32;i++){
    try{
     const status=await api("/auth/status");
     if(cancelled)return;
     if(!status.registered){setPhase("register");return;}
     try{const u=await api("/auth/me");if(cancelled)return;setProfile(u);setPhase("ready");}
     catch{if(!cancelled)setPhase("login");}
     return;
    }catch{await new Promise(r=>setTimeout(r,500));}
   }
   if(!cancelled)setError("Cannot reach the local tracking service. Check the Python environment and restart WorkPulse.");
  }
  void boot();
  return ()=>{cancelled=true;};
 },[]);
 useEffect(()=>window.workpulse.onLive(setLive),[]);
 useEffect(()=>{if(phase==="ready"&&profile){void loadData();const id=setInterval(()=>void loadData(),20000);return ()=>clearInterval(id);}},[phase,profile,loadData]);
 useEffect(()=>{
  if(phase!=="ready"||!profile)return;
  void api("/activity/live").then(setLive).catch(()=>{});
  void api("/settings").then(setSettings).catch(()=>{});
  void api("/categories").then(setRules).catch(()=>{});
 },[phase,profile]);
 useEffect(()=>{document.body.setAttribute("data-theme",settings?.theme||"dark");},[settings?.theme]);
 const totals=period?.totals||blank;
 const cards:[string,string,string,React.ReactNode][]=[
  ["Total work",hours(totals.work),"Compared to your goal",<Clock3 size={20}/>],
  ["Productive",hours(totals.productive),"Deep focus & creation",<TrendingUp size={20}/>],
  ["Non-productive",hours(totals.non_productive),"Distractions tracked",<Pause size={20}/>],
  ["Idle time",hours(totals.idle),"Away from keyboard",<Timer size={20}/>],
  ["On break",hours(totals.break),"Recovery & rest",<Coffee size={20}/>],
  ["Productivity",totals.productivity.toFixed(1)+"%","Productive / work time",<BarChart3 size={20}/>]
 ];
 const hourly=(today?.hourly||[]).map(r=>({hour:r.hour.slice(0,2),productive:r.productive/3600,neutral:r.neutral/3600,non_productive:r.non_productive/3600}));
 const trend=(period?.days||[]).map(d=>({day:d.date.slice(5),work:+(d.work/3600).toFixed(2),productive:+(d.productive/3600).toFixed(2)}));
 const donut=states.filter(k=>totals[k]>0).map(k=>({name:display(k),value:totals[k],fill:colors[k]}));
 const goal=Math.min(100,totals.work/60/(settings?.daily_goal_minutes||480)*100);
 async function action(key:string){
  if(key==="finish"&&!confirm("Finish the workday? Your tracked time will be saved."))return;
  setBusy(true);setNotice("");try{const result=await api("/session/"+key,"POST");setLive(old=>({...old,...result}));setNotice(key==="finish"?"Workday saved.":key==="break"?"Break started.":key==="resume"?"Welcome back.":"Tracking started.");await loadData();}catch(e){setError(errorText(e));}finally{setBusy(false);}
 }
 async function refreshRules(){setRules(await api("/categories"));}
 async function saveSettings(next:Partial<Settings>){
  try{const result:Settings=await api("/settings","PATCH",next);setSettings(result);if("auto_start" in next)await window.workpulse.setAutoStart(result.auto_start);setNotice("Settings saved.");}
  catch(e){setError(errorText(e));}
 }
 async function addRule(){
  if(!draftRule.pattern.trim())return;
  try{await api("/categories","POST",{...draftRule,enabled:true});setDraftRule({pattern:"",category:"productive"});await refreshRules();}
  catch(e){setError(errorText(e));}
 }
 async function editRule(rule:Rule,patch:Partial<Rule>){
  try{await api("/categories/"+rule.id,"PUT",{pattern:rule.pattern,category:rule.category,enabled:rule.enabled,...patch});await refreshRules();}
  catch(e){setError(errorText(e));}
 }
 async function deleteRule(rule:Rule){if(!confirm("Remove the rule for "+rule.pattern+"?"))return;try{await api("/categories/"+rule.id,"DELETE");await refreshRules();}catch(e){setError(errorText(e));}}
 async function report(format:"csv"|"pdf"){
  try{const file=await window.workpulse.exportReport(format,day,offset());if(file)setNotice("Report saved: "+file);}
  catch(e){setError(errorText(e));}
 }
 async function signout(){await window.workpulse.signOut();setProfile(null);setPhase("login");}
 if(phase==="loading")return <div className="loading-screen"><Brand/><span className="spinner"/><p>{error||"Connecting to your private tracking service..."}</p></div>;
 if(phase!=="ready"||!profile)return <Auth registered={phase==="login"} onDone={user=>{setProfile(user);setPhase("ready");}}/>;
 return <div className="app-shell"><aside className="sidebar"><Brand/><div className="sidebar-title">WORKSPACE</div>
  <nav className="nav-menu">{([
   ["overview",LayoutDashboard,"Overview"],["activity",Clock3,"Activity timeline"],
   ["categories",Tag,"App categories"],["projects",FolderKanban,"Projects & tasks"],["focus",Target,"Focus mode"],["attendance",CalendarCheck,"Attendance"],["insights",BrainCircuit,"Productivity coach"],["privacy",ShieldCheck,"Privacy & recovery"],["calendar",CalendarDays,"Calendar meetings"],["reports",FileBarChart,"Advanced reports"],["browser",Globe2,"Website integration"],["backups",DatabaseBackup,"Backup & updates"],["settings",Settings2,"Settings"]
  ] as const).map(([id,Icon,label])=><button key={id} className={"nav-link "+(view===id?"selected":"")} onClick={()=>setView(id)}><Icon size={19}/>{label}</button>)}</nav>
  <div className="sidebar-bottom"><div className="privacy-chip"><ShieldCheck size={16}/><span>Private & local<br/><small>Data never leaves this PC</small></span></div><button className="account" onClick={signout}><span className="avatar">{profile.full_name.slice(0,1).toUpperCase()}</span><span className="account-name"><strong>{profile.full_name}</strong><small>{profile.department||profile.email}</small></span><LogOut size={17}/></button></div>
 </aside><main className="main-content">
  <header className="topbar"><span className="breadcrumb">Workspace <span>/</span> {display(view)}</span><div className="top-right"><div className="session-toolbar">{live?.status==="finished"?<button disabled={busy} onClick={()=>void action("start")}><Play size={14}/> Start</button>:<><button disabled={busy} onClick={()=>void action(live?.status==="break"?"resume":"break")}>{live?.status==="break"?<Play size={14}/>:<Coffee size={14}/>} {live?.status==="break"?"Resume":"Break"}</button><button disabled={busy} title="Finish day" onClick={()=>void action("finish")}><Square size={13}/></button></>}</div><span className="online"><span className="status-dot"/> {live?.state==="private"?"Private pause":live?.status==="break"?"On break":live?.status==="finished"?"Finished":live?.state==="idle"?"Idle":"Tracking"}</span><span className="today-label"><CalendarDays size={16}/> {new Date().toLocaleDateString([], {month:"short",day:"numeric",year:"numeric"})}</span></div></header>
  <div className="content">
   {error&&<div className="alert alert-error" role="alert">{error}<button onClick={()=>setError("")}>×</button></div>}
   {notice&&<div className="alert alert-ok" role="status">{notice}<button onClick={()=>setNotice("")}>×</button></div>}
   {view==="overview"||view==="activity"?<>
    <div className="page-heading"><div><div className="eyebrow">YOUR WORKDAY, DECODED</div><h1>{view==="overview"?"Overview":"Activity timeline"}<span className="heading-period"> / {display(range)}</span></h1><p className="muted">See where your time goes, and make more room for what matters.</p></div><div className="heading-actions"><button className="secondary" onClick={()=>report("csv")}><Download size={16}/> CSV</button><button className="secondary" onClick={()=>report("pdf")}><Download size={16}/> PDF</button></div></div>
    <div className="filter-row"><div className="tabs">{(["today","week","month"] as const).map(r=><button key={r} className={range===r?"active":""} onClick={()=>setRange(r)}>{display(r)}</button>)}</div><label className="date-filter"><CalendarDays size={17}/><input aria-label="Select date" type="date" value={day} onChange={e=>setDay(e.target.value||localDay())}/></label></div>
    <div className="metric-grid">{cards.map(([label,value,info,icon],i)=><div className="metric-card" key={label}><div className="metric-head"><span>{label}</span><span className={"metric-icon shade-"+i}>{icon}</span></div><div className="metric-value">{value}</div><div className="metric-note">{info}</div></div>)}</div>
    <div className="focus-banner"><div><div className="eyebrow">DAILY FOCUS GOAL</div><h3>{hours(totals.work)} <span>/ {hours((settings?.daily_goal_minutes||480)*60)}</span></h3></div><div className="goal-right"><strong>{goal.toFixed(0)}% of goal</strong><div className="goal-track"><span style={{width:goal+"%"}}/></div></div></div>
    {view==="overview"&&<><div className="charts-grid"><section className="panel"><div className="panel-heading"><div><h3>Daily activity</h3><p>Work hours across the day</p></div><span className="mini-legend"><i style={{background:colors.productive}}/> Productive</span></div><div className="chart-area"><ResponsiveContainer width="100%" height="100%"><BarChart data={hourly} barSize={9}><CartesianGrid stroke="#253044" vertical={false}/><XAxis dataKey="hour" tickLine={false} axisLine={false} tick={{fill:"#8897ad",fontSize:10}} interval={2}/><YAxis tickLine={false} axisLine={false} tick={{fill:"#8897ad",fontSize:10}} width={28}/><Tooltip contentStyle={{background:"#1c293c",border:"1px solid #36445b",borderRadius:12}}/><Bar dataKey="productive" stackId="a" fill={colors.productive} radius={[3,3,0,0]}/><Bar dataKey="neutral" stackId="a" fill={colors.neutral}/><Bar dataKey="non_productive" stackId="a" fill={colors.non_productive}/></BarChart></ResponsiveContainer></div></section>
     <section className="panel"><div className="panel-heading"><div><h3>Time distribution</h3><p>How your hours were spent</p></div></div><div className="donut-layout"><div className="donut-visual">{donut.length?<ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={donut} dataKey="value" nameKey="name" innerRadius={69} outerRadius={91} paddingAngle={2} stroke="none">{donut.map(d=><Cell key={d.name} fill={d.fill}/>)}</Pie><Tooltip contentStyle={{background:"#1c293c",border:"1px solid #36445b",borderRadius:12}} formatter={(n)=>hours(Number(n))}/></PieChart></ResponsiveContainer>:<div className="empty-ring"/>}<div className="donut-center"><strong>{totals.productivity.toFixed(0)}%</strong><small>productive</small></div></div><div className="donut-legend">{states.map(s=><div key={s}><span><i style={{background:colors[s]}}/>{display(s)}</span><b>{hours(totals[s])}</b></div>)}</div></div></section></div>
     <div className="charts-grid"><section className="panel"><div className="panel-heading"><div><h3>Work trend</h3><p>Work vs productive time</p></div></div><div className="chart-area"><ResponsiveContainer width="100%" height="100%"><LineChart data={trend}><CartesianGrid stroke="#253044" vertical={false}/><XAxis dataKey="day" tick={{fill:"#8897ad",fontSize:11}} axisLine={false} tickLine={false}/><YAxis tick={{fill:"#8897ad",fontSize:11}} axisLine={false} tickLine={false} width={28}/><Tooltip contentStyle={{background:"#1c293c",border:"1px solid #36445b",borderRadius:12}}/><Line type="monotone" dataKey="work" stroke="#7b92b7" strokeWidth={2} dot={false}/><Line type="monotone" dataKey="productive" stroke="#80e1b4" strokeWidth={3} dot={false}/></LineChart></ResponsiveContainer></div></section>
      <section className="panel"><div className="panel-heading"><div><h3>Hourly activity heatmap</h3><p>Intensity by hour on selected day</p></div></div><div className="heatmap">{(today?.hourly||[]).map(h=>{const secs=states.filter(s=>s!=="break").reduce((n,s)=>n+h[s],0);return <div key={h.hour} className="heat-cell" title={h.hour+": "+duration(secs)} style={{opacity:Math.max(.22,Math.min(1,secs/3600))}}><small>{h.hour.slice(0,2)}</small></div>;})}</div><p className="small-note">Darker hours mean less tracked work.</p></section></div></>}
    <div className="charts-grid lower-grid"><section className="panel"><div className="panel-heading"><div><h3>Top applications</h3><p>Most-used apps on selected day</p></div></div><div className="table-wrap"><table><thead><tr><th>APPLICATION</th><th>CATEGORY</th><th className="right">TIME</th></tr></thead><tbody>{today?.apps.length?today.apps.slice(0,10).map(item=><tr key={item.app_name}><td><span className="app-initial">{item.app_name.slice(0,1).toUpperCase()}</span>{item.app_name}</td><td><span className={"category-tag "+item.category}>{display(item.category)}</span></td><td className="right mono">{duration(item.seconds)}</td></tr>):<tr><td colSpan={3} className="empty-state">Start working to see your top apps.</td></tr>}</tbody></table></div></section>
    <section className="panel"><div className="panel-heading"><div><h3>Day timeline</h3><p>Recorded activity intervals</p></div></div><div className="timeline-scroll">{today?.timeline.length?today.timeline.slice().reverse().slice(0,24).map((row,i)=><div className="timeline-item" key={i}><i style={{background:colors[row.state]}}/><span className="timeline-time">{fmtTime(row.start)}</span><span className="timeline-name">{row.app_name||display(row.state)}<small>{row.title||display(row.state)}</small></span><span className="mono">{duration(row.seconds)}</span></div>):<div className="empty-state">Your timeline will appear after activity is detected.</div>}</div></section></div>
   </>:null}
   {view==="categories"&&<><div className="page-heading"><div><div className="eyebrow">MAKE IT YOURS</div><h1>App categories</h1><p className="muted">Set rules to define productive and distracting applications or sites.</p></div></div>
    <section className="panel category-panel"><h3>Add classification rule</h3><div className="add-rule"><input placeholder="App filename or part of window title" value={draftRule.pattern} onChange={e=>setDraftRule({...draftRule,pattern:e.target.value})}/><select aria-label="Rule category" value={draftRule.category} onChange={e=>setDraftRule({...draftRule,category:e.target.value})}>{(["productive","neutral","non_productive"] as const).map(s=><option key={s} value={s}>{display(s)}</option>)}</select><button className="primary" onClick={addRule}><Plus size={16}/> Add rule</button></div><p className="small-note">Longer matching patterns take precedence (for example, "youtube" over "chrome.exe").</p></section>
    <section className="panel category-panel"><h3>Classification rules</h3><div className="table-wrap"><table><thead><tr><th>PATTERN</th><th>CATEGORY</th><th>ENABLED</th><th className="right">ACTION</th></tr></thead><tbody>{rules.map(rule=><tr key={rule.id}><td className="mono">{rule.pattern}</td><td><select aria-label={"Category for "+rule.pattern} value={rule.category} onChange={e=>editRule(rule,{category:e.target.value as Rule["category"]})}>{(["productive","neutral","non_productive"] as const).map(x=><option key={x} value={x}>{display(x)}</option>)}</select></td><td><input aria-label={"Enable "+rule.pattern} type="checkbox" checked={rule.enabled} onChange={e=>editRule(rule,{enabled:e.target.checked})}/></td><td className="right"><button className="icon-action" aria-label={"Delete "+rule.pattern} onClick={()=>deleteRule(rule)}><Trash2 size={17}/></button></td></tr>)}</tbody></table></div></section></>}
   {view==="settings"&&settings&&<><div className="page-heading"><div><div className="eyebrow">CONTROL YOUR WORKFLOW</div><h1>Settings</h1><p className="muted">Personalize tracking, reminders and appearance.</p></div></div><section className="panel settings-panel"><h3>Tracking preferences</h3>
    <div className="settings-row"><div><strong>Idle detection threshold</strong><p>Mark you idle after this much keyboard or mouse inactivity.</p></div><select value={settings.idle_threshold} onChange={e=>saveSettings({idle_threshold:Number(e.target.value)})}>{[60,120,300,600,900,1800].map(x=><option key={x} value={x}>{x/60} minutes</option>)}</select></div>
    <div className="settings-row"><div><strong>Tracking frequency</strong><p>Sample your active application at a regular interval.</p></div><select value={settings.poll_interval} onChange={e=>saveSettings({poll_interval:Number(e.target.value)})}>{[3,4,5].map(x=><option key={x} value={x}>{x} seconds</option>)}</select></div>
    <div className="settings-row"><div><strong>Start with Windows</strong><p>Launch WorkPulse when you sign into your Windows account.</p></div><input type="checkbox" checked={settings.auto_start} onChange={e=>saveSettings({auto_start:e.target.checked})}/></div>
    <div className="settings-row"><div><strong>Break reminder</strong><p>Interval between suggested breaks (0 disables reminders).</p></div><select value={settings.break_reminder_minutes} onChange={e=>saveSettings({break_reminder_minutes:Number(e.target.value)})}>{[0,30,45,60,90,120].map(x=><option key={x} value={x}>{x?x+" minutes":"Off"}</option>)}</select></div>
    <div className="settings-row"><div><strong>Daily work goal</strong><p>Your desired work hours each day.</p></div><select value={settings.daily_goal_minutes} onChange={e=>saveSettings({daily_goal_minutes:Number(e.target.value)})}>{[240,300,360,420,480,540,600].map(x=><option key={x} value={x}>{x/60} hours</option>)}</select></div>
    <div className="settings-row"><div><strong>Appearance</strong><p>Switch between light and dark dashboards.</p></div><select value={settings.theme} onChange={e=>saveSettings({theme:e.target.value as Settings["theme"]})}><option value="dark">Dark</option><option value="light">Light</option></select></div>
   </section><section className="panel privacy-settings"><ShieldCheck size={22}/><div><h3>Privacy first</h3><p>All activity data is stored in a local SQLite database under your Windows user profile. WorkPulse never uploads browsing history, captures screenshots, or logs what you type. Window titles may reveal document names; edit or disable any classification rule at any time.</p></div></section></>}
   {(["projects","focus","attendance","insights","privacy","calendar","reports","browser","backups"] as const).includes(view as SuiteSection)&&<WorkspaceV2 section={view as SuiteSection} onRefresh={()=>void loadData()}/>}
  </div>
 </main></div>;
}
