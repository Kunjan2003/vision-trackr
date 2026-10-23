import type {TimeSection} from "./TimeWorkspace";
import type {SuiteSection} from "./WorkspaceV2";
import type React from "react";
import {Suspense,lazy,useEffect,useState} from "react";
import {Activity,CalendarDays,ChevronDown,Clock3,Coffee,LayoutDashboard,LogOut,Play,Plus,Settings2,ShieldCheck,Square,Tag,Trash2,Monitor,FolderKanban,Target,CalendarCheck,BrainCircuit,Globe2,FileBarChart,DatabaseBackup} from "lucide-react";
import type {Live,Rule,Settings,User} from "./types";
import {display} from "./utils";

type View=TimeSection|"categories"|"settings"|SuiteSection;
const TimeWorkspace=lazy(()=>import("./TimeWorkspace"));
const WorkspaceV2=lazy(()=>import("./WorkspaceV2"));
const api=window.workpulse.request;
function errorText(e:unknown){return e instanceof Error?e.message:String(e);}
function Brand(){return <div className="brand"><div className="brand-icon"><Activity size={22}/></div><span>Vision<span className="accent">Tracker</span><small>A LITTLE MORE FOCUS</small></span></div>;}

function Auth({registered,onDone}:{registered:boolean;onDone:(user:User)=>void}){
 const [mode]=useState<"login"|"register">(registered?"login":"register");
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
  <div className="auth-card"><div className="eyebrow">WELCOME TO VISION TRACKER</div><h2>{mode==="register"?"Create your account":"Welcome back"}</h2><p className="muted">{mode==="register"?"Set up your private workspace in seconds.":"Sign in to continue tracking your workday."}</p>
   <form onSubmit={submit}>
    {mode==="register"&&<><label>Full name<input required minLength={2} maxLength={120} value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})} placeholder="Your full name"/></label><label>Department / role<input maxLength={120} value={form.department} onChange={e=>setForm({...form,department:e.target.value})} placeholder="e.g. Engineering"/></label></>}
    <label>Email address<input type="email" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})} placeholder="you@example.com"/></label>
    <label>Password<input required type="password" minLength={mode==="register"?8:1} value={form.password} onChange={e=>setForm({...form,password:e.target.value})} placeholder="Your password"/></label>
    {mode==="register"&&<label className="privacy-notice"><input type="checkbox" checked={accepted} onChange={e=>setAccepted(e.target.checked)}/><span>I understand that Vision Tracker locally records app names, window titles, and durations. It does not record keystrokes or screenshots. All activity remains on this computer.</span></label>}
    {error&&<p className="error-box" role="alert">{error}</p>}
    <button className="primary wide" disabled={busy||mode==="register"&&!accepted}>{busy?"Please wait...":mode==="register"?"Create account & start tracking":"Sign in"} <ChevronDown size={16} className="arrow-right"/></button>
   </form>
  </div>
 </div></div>;
}
export default function App(){
 const [phase,setPhase]=useState<"loading"|"login"|"register"|"ready">("loading");
 const [profile,setProfile]=useState<User|null>(null);
 const [view,setView]=useState<View>("overview");
 const [revision,setRevision]=useState(0);
 const [live,setLive]=useState<Live|null>(null);
 const [settings,setSettings]=useState<Settings|null>(null);
 const [rules,setRules]=useState<Rule[]>([]);
 const [draftRule,setDraftRule]=useState({pattern:"",category:"productive"});
 const [busy,setBusy]=useState(false);
 const [notice,setNotice]=useState("");
 const [error,setError]=useState("");
 const loadData=async()=>{setRevision(n=>n+1);};
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
 useEffect(()=>window.workpulse.onNavigate(next=>{if(next==="privacy")setView("privacy");}),[]);
 useEffect(()=>{
  if(phase!=="ready"||!profile)return;
  void api("/activity/live").then(setLive).catch(e=>setError(errorText(e)));
  void api("/settings").then(setSettings).catch(e=>setError(errorText(e)));
  void api("/categories").then(setRules).catch(e=>setError(errorText(e)));
 },[phase,profile]);
 useEffect(()=>{document.body.setAttribute("data-theme",settings?.theme||"dark");},[settings?.theme]);
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
 async function signout(){try{await window.workpulse.signOut();setProfile(null);setLive(null);setPhase("login");}catch(e){setError(errorText(e));}}
 if(phase==="loading")return <div className="loading-screen"><Brand/><span className="spinner"/><p>{error||"Connecting to your private tracking service..."}</p></div>;
 if(phase!=="ready"||!profile)return <Auth registered={phase==="login"} onDone={user=>{setProfile(user);setPhase("ready");}}/>;
 return <div className="app-shell"><aside className="sidebar"><Brand/><div className="sidebar-title">WORKSPACE</div>
  <nav className="nav-menu">{([
   ["overview",LayoutDashboard,"Overview"],["activity",Clock3,"Activity explorer"],["apps",Monitor,"Apps & websites"],["timesheets",CalendarDays,"Timesheets"],["billing",FileBarChart,"Client billing"],
   ["categories",Tag,"App categories"],["projects",FolderKanban,"Projects & tasks"],["focus",Target,"Focus mode"],["attendance",CalendarCheck,"Attendance"],["insights",BrainCircuit,"Productivity coach"],["privacy",ShieldCheck,"Privacy & recovery"],["calendar",CalendarDays,"Calendar meetings"],["reports",FileBarChart,"Advanced reports"],["browser",Globe2,"Website integration"],["backups",DatabaseBackup,"Backup & updates"],["settings",Settings2,"Settings"]
  ] as const).map(([id,Icon,label])=><button key={id} title={label} aria-label={label} aria-current={view===id?"page":undefined} className={"nav-link "+(view===id?"selected":"")} onClick={()=>{setView(id);setError("");setNotice("");}}><Icon size={19}/>{label}</button>)}</nav>
  <div className="sidebar-bottom"><div className="privacy-chip"><ShieldCheck size={16}/><span>Private & local<br/><small>Data never leaves this PC</small></span></div><button className="account" onClick={signout}><span className="avatar">{profile.full_name.slice(0,1).toUpperCase()}</span><span className="account-name"><strong>{profile.full_name}</strong><small>{profile.department||profile.email}</small></span><LogOut size={17}/></button></div>
 </aside><main className="main-content">
  <header className="topbar"><span className="breadcrumb">Workspace <span>/</span> {display(view)}</span><div className="top-right"><div className="session-toolbar">{!live||live.status==="finished"?<button disabled={busy||!live} onClick={()=>void action("start")}><Play size={14}/> Start</button>:<><button disabled={busy} onClick={()=>void action(live?.status==="break"?"resume":"break")}>{live?.status==="break"?<Play size={14}/>:<Coffee size={14}/>} {live?.status==="break"?"Resume":"Break"}</button><button disabled={busy} title="Finish day" onClick={()=>void action("finish")}><Square size={13}/></button></>}</div><span className="online"><span className="status-dot"/> {!live?"Connecting":live.state==="private"?"Private pause":live?.status==="break"?"On break":live?.status==="finished"?"Finished":live?.state==="idle"?"Idle":"Tracking"}</span><span className="today-label"><CalendarDays size={16}/> {new Date().toLocaleDateString([], {month:"short",day:"numeric",year:"numeric"})}</span></div></header>
  <div className="content">
   {(live?.idle_pending||0)>0&&<div className="alert alert-ok"><span>You have {live?.idle_pending} idle period(s) to review. Correct your timesheet when ready.</span><button onClick={()=>setView("privacy")}>Review idle time</button></div>}
   {error&&<div className="alert alert-error" role="alert">{error}<button onClick={()=>setError("")}>×</button></div>}
   {notice&&<div className="alert alert-ok" role="status">{notice}<button onClick={()=>setNotice("")}>×</button></div>}
   {(["overview","activity","apps","timesheets","billing"] as string[]).includes(view)&&<Suspense fallback={<div className="empty-state">Loading workspace…</div>}><TimeWorkspace revision={revision} section={view as TimeSection} profile={profile} live={live} onNavigate={next=>setView(next as View)}/></Suspense>}
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
   {(["projects","focus","attendance","insights","privacy","calendar","reports","browser","backups"] as const).includes(view as SuiteSection)&&<Suspense fallback={<div className="empty-state">Loading workspace…</div>}><WorkspaceV2 section={view as SuiteSection} onRefresh={()=>void loadData()}/></Suspense>}
  </div>
 </main></div>;
}
