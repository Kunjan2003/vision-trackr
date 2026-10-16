import {useCallback,useEffect,useState} from "react";
import {
  FolderKanban,Plus,Save,ShieldCheck,PauseCircle,PlayCircle,Trash2,
  Timer,CalendarDays,BrainCircuit,Download,LockKeyhole,Globe2,
  RefreshCcw,FileClock,Link2,Archive,CheckCircle2,AlertCircle
} from "lucide-react";
import {duration,hours,localDay,offset} from "./utils";

export type SuiteSection="projects"|"focus"|"attendance"|"insights"|"privacy"|"calendar"|"reports"|"browser"|"backups";
type Project={id:number;name:string;client:string;hourly_rate:number;budget_hours:number;archived:boolean};
type Task={id:number;name:string;project_id:number;status:"todo"|"doing"|"done";estimate_minutes:number};
type ProjectRule={id:number;project_id:number;pattern:string};
type Privacy={paused:boolean;hide_window_titles:boolean;retention_days:number;browser_opt_in:boolean;ai_opt_in:boolean;meeting_opt_in:boolean};
type PrivacyRule={id:number;pattern:string;action:"exclude"|"mask"};
type Assignment={project_id:number|null;task_id:number|null};
type IdleItem={id:number;start:string;end:string;seconds:number};
type Focus={id:number;started_at:string;finished_at:string|null;duration_minutes:number;status:"running"|"completed"|"finished";task_id:number|null};
type Attendance={days:{date:string;work:number;productivity:number;goal_met:boolean;status:string}[];total_work:number;goal_days:number};
type Insights={work_hours:number;productive_hours:number;productivity:number;context_switches:number;longest_focus_minutes:number;peak_hours:number[];active_days:number;tips:string[]};
type Meeting={id:number;title:string;starts_at:string;ends_at:string};
type ProjectReport={id:number;name:string;client:string;hours:number;hourly_rate:number;billable:number;budget_hours:number};
const api=window.workpulse.request;
const errorMsg=(e:unknown)=>e instanceof Error?e.message:String(e);
const blankProject={name:"",client:"",hourly_rate:0,budget_hours:0,archived:false};
const blankTask={name:"",project_id:0,status:"todo" as const,estimate_minutes:0};
const heading:Record<SuiteSection,[string,string]>={
 projects:["Projects & tasks","Automatically tag work, track clients and manage billable time."],
 focus:["Deep work","Build focus streaks with Pomodoro sessions and fewer context switches."],
 attendance:["Attendance","Review workdays, daily goals, consistency and time tracked."],
 insights:["Productivity coach","Private, evidence-based feedback from your own working patterns."],
 privacy:["Privacy & idle recovery","Decide what WorkPulse may retain, and correct time spent away."],
 calendar:["Calendar integration","Import local iCalendar events. No cloud account required."],
 reports:["Advanced reports","Export custom periods and review project billing."],
 browser:["Website integration","Optionally pair Chrome or Edge to share the active domain only."],
 backups:["Backup & updates","Protect your records with encrypted backups and check releases."]
};
export default function WorkspaceV2({section,onRefresh}:{section:SuiteSection;onRefresh?:()=>void}){
 const [projects,setProjects]=useState<Project[]>([]);
 const [tasks,setTasks]=useState<Task[]>([]);
 const [rules,setRules]=useState<ProjectRule[]>([]);
 const [assignment,setAssignment]=useState<Assignment>({project_id:null,task_id:null});
 const [projectForm,setProjectForm]=useState(blankProject);
 const [editing,setEditing]=useState<number|null>(null);
 const [taskForm,setTaskForm]=useState<Task>( {...blankTask,id:0} );
 const [pattern,setPattern]=useState("");
 const [ruleProject,setRuleProject]=useState<number>(0);
 const [privacy,setPrivacy]=useState<Privacy|null>(null);
 const [privacyRules,setPrivacyRules]=useState<PrivacyRule[]>([]);
 const [privacyPattern,setPrivacyPattern]=useState("");
 const [privacyAction,setPrivacyAction]=useState<"exclude"|"mask">("exclude");
 const [idle,setIdle]=useState<IdleItem[]>([]);
 const [idleDecision,setIdleDecision]=useState<Record<number,string>>({});
 const [focus,setFocus]=useState<Focus|null>(null);
 const [focusMinutes,setFocusMinutes]=useState(25);
 const [clock,setClock]=useState(Date.now());
 const [month,setMonth]=useState(localDay().slice(0,7));
 const [attendance,setAttendance]=useState<Attendance|null>(null);
 const [insights,setInsights]=useState<Insights|null>(null);
 const [aiText,setAiText]=useState("");
 const [meetings,setMeetings]=useState<Meeting[]>([]);
 const [calendarDay,setCalendarDay]=useState(localDay());
 const [reportStart,setReportStart]=useState(localDay(new Date(Date.now()-6*86400000)));
 const [reportEnd,setReportEnd]=useState(localDay());
 const [projectReport,setProjectReport]=useState<ProjectReport[]>([]);
 const [backupPassword,setBackupPassword]=useState("");
 const [pair,setPair]=useState<{port:number;token:string}|null>(null);
 const [update,setUpdate]=useState("");
 const [updateEnabled,setUpdateEnabled]=useState(false);
 const [signedInstaller,setSignedInstaller]=useState(false);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const refresh=useCallback(async()=>{
  try{
   if(section==="projects"){
    const [p,t,r,a]=await Promise.all([api("/v2/projects"),api("/v2/tasks"),api("/v2/project-rules"),api("/v2/assignment")]);
    setProjects(p);setTasks(t);setRules(r);setAssignment(a);
   }else if(section==="privacy"){
    const [p,r,i]=await Promise.all([api("/v2/privacy"),api("/v2/privacy/rules"),api("/v2/idle/pending")]);
    setPrivacy(p);setPrivacyRules(r);setIdle(i);
   }else if(section==="focus"){setFocus(await api("/v2/focus"));}
   else if(section==="attendance"){
    const [year,m]=month.split("-").map(Number);
    setAttendance(await api("/v2/attendance?year="+year+"&month="+m+"&tz="+offset()));
   }else if(section==="insights"){setInsights(await api("/v2/insights"));}
   else if(section==="calendar"){setMeetings(await api("/v2/meetings?day="+calendarDay));}
   else if(section==="reports"){setProjectReport(await api("/v2/projects/analytics?start="+reportStart+"&end="+reportEnd));}
   else if(section==="browser"){setPrivacy(await api("/v2/privacy"));}
   setError("");
  }catch(e){setError(errorMsg(e));}
 },[section,month,calendarDay,reportStart,reportEnd]);
 useEffect(()=>{void refresh();},[refresh]);
 useEffect(()=>{if(section==="backups")void window.workpulse.getAutoUpdates().then(x=>{setUpdateEnabled(x.enabled);setSignedInstaller(x.signed);}).catch(()=>{});},[section]);
 useEffect(()=>{if(section!=="focus")return;const i=setInterval(()=>{setClock(Date.now());void api("/v2/focus").then(setFocus).catch(()=>{});},5000);return ()=>clearInterval(i);},[section]);
 async function run(fn:()=>Promise<unknown>,success:string){
  setBusy(true);setError("");setNotice("");
  try{await fn();setNotice(success);await refresh();onRefresh?.();}
  catch(e){setError(errorMsg(e));}
  finally{setBusy(false);}
 }
 async function saveProject(){
  if(!projectForm.name.trim()){setError("Give the project a name.");return;}
  await run(async()=>{
   await api("/v2/projects"+(editing!==null?"/"+editing:""),editing!==null?"PATCH":"POST",projectForm);
   setEditing(null);setProjectForm(blankProject);
  },"Project saved.");
 }
 async function saveTask(){
  if(!taskForm.name.trim()||!taskForm.project_id){setError("Choose a project and task name.");return;}
  await run(async()=>{
   await api("/v2/tasks"+(taskForm.id?"/"+taskForm.id:""),taskForm.id?"PATCH":"POST",{
     project_id:taskForm.project_id,name:taskForm.name,status:taskForm.status,estimate_minutes:taskForm.estimate_minutes});
   setTaskForm({...blankTask,id:0});
  },"Task saved.");
 }
 async function setActive(projectId:number|null,taskId:number|null=null){
  await run(async()=>{await api("/v2/assignment","PUT",{project_id:projectId,task_id:taskId});},"Active assignment updated.");
 }
 async function patchPrivacy(next:Partial<Privacy>){
  await run(async()=>{setPrivacy(await api("/v2/privacy","PATCH",next));},"Privacy settings saved.");
 }
 const completeFocus=focus?.status==="running"?Math.max(0,focus.duration_minutes*60-(clock-new Date(focus.started_at).getTime())/1000):0;
 const [year,monthNumber]=month.split("-").map(Number);
 const firstOffset=(new Date(year,monthNumber-1,1).getDay()+6)%7;
 const cells=[...Array(firstOffset).fill(null),...(attendance?.days||[])];
 return <div className="suite-root">
  <div className="page-heading"><div><div className="eyebrow">WORKPULSE 2.0</div><h1>{heading[section][0]}</h1><p className="muted">{heading[section][1]}</p></div><button className="secondary" onClick={()=>void refresh()}><RefreshCcw size={15}/> Refresh</button></div>
  {error&&<div className="alert alert-error">{error}<button onClick={()=>setError("")}>×</button></div>}
  {notice&&<div className="alert alert-ok">{notice}<button onClick={()=>setNotice("")}>×</button></div>}

  {section==="projects"&&<>
   <div className="suite-grid"><section className="panel"><h3>{editing?"Edit project":"Add project / client"}</h3>
    <div className="suite-form">
     <label>Project name<input value={projectForm.name} onChange={e=>setProjectForm({...projectForm,name:e.target.value})} placeholder="e.g. Quiz Master" maxLength={120}/></label>
     <label>Client / organization<input value={projectForm.client} onChange={e=>setProjectForm({...projectForm,client:e.target.value})} placeholder="Optional" maxLength={120}/></label>
     <div className="form-row"><label>Hourly rate<input type="number" min="0" value={projectForm.hourly_rate} onChange={e=>setProjectForm({...projectForm,hourly_rate:Number(e.target.value)})}/></label><label>Budget hours<input type="number" min="0" value={projectForm.budget_hours} onChange={e=>setProjectForm({...projectForm,budget_hours:Number(e.target.value)})}/></label></div>
     {editing&&<label className="inline-check"><input type="checkbox" checked={projectForm.archived} onChange={e=>setProjectForm({...projectForm,archived:e.target.checked})}/> Archive project</label>}
     <div className="suite-actions"><button disabled={busy} className="primary" onClick={()=>void saveProject()}><Save size={16}/> {editing?"Save changes":"Create project"}</button>{editing&&<button className="secondary" onClick={()=>{setEditing(null);setProjectForm(blankProject);}}>Cancel</button>}</div>
    </div>
   </section><section className="panel"><h3>Automatic project tagging</h3><p className="muted">Match a workspace name, file title or executable, such as "quiz-master". Longest rule wins.</p>
    <div className="suite-form"><label>Match pattern<input value={pattern} onChange={e=>setPattern(e.target.value)} placeholder="window title keyword"/></label><label>Assign project<select value={ruleProject||""} onChange={e=>setRuleProject(Number(e.target.value))}><option value="">Select project</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label><button className="primary" disabled={busy||!pattern.trim()||!ruleProject} onClick={()=>void run(async()=>{await api("/v2/project-rules","POST",{pattern,project_id:ruleProject});setPattern("");},"Rule added.")}><Plus size={16}/> Add matching rule</button></div>
    <div className="mini-list">{rules.map(r=><div className="mini-row" key={r.id}><span><b>{r.pattern}</b><small>{projects.find(p=>p.id===r.project_id)?.name||"Unknown"}</small></span><button className="icon-action" title="Remove rule" onClick={()=>void run(()=>api("/v2/project-rules/"+r.id,"DELETE"),"Rule removed.")}><Trash2 size={16}/></button></div>)}</div>
   </section></div>
   <section className="panel suite-space"><div className="panel-heading"><div><h3>Your projects</h3><p>Set a manual active project or allow automatic title matching.</p></div></div>
    <div className="suite-actions"><label>Tracking assignment<select value={assignment.project_id??""} onChange={e=>void setActive(e.target.value?Number(e.target.value):null)}><option value="">Automatic matching</option>{projects.filter(p=>!p.archived).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
     <label>Active task<select value={assignment.task_id??""} disabled={!assignment.project_id} onChange={e=>void setActive(assignment.project_id,e.target.value?Number(e.target.value):null)}><option value="">No specific task</option>{tasks.filter(t=>t.project_id===assignment.project_id).map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></label></div>
    <div className="table-wrap"><table><thead><tr><th>PROJECT</th><th>CLIENT</th><th>RATE</th><th>BUDGET</th><th>STATUS</th><th className="right">EDIT</th></tr></thead><tbody>{projects.map(p=><tr key={p.id}><td>{p.name}</td><td>{p.client||"—"}</td><td>{p.hourly_rate.toFixed(2)}</td><td>{p.budget_hours||"—"}</td><td>{p.archived?"Archived":"Active"}</td><td className="right"><button className="secondary" onClick={()=>{setEditing(p.id);setProjectForm({name:p.name,client:p.client,hourly_rate:p.hourly_rate,budget_hours:p.budget_hours,archived:p.archived});}}>Edit</button></td></tr>)}{!projects.length&&<tr><td colSpan={6} className="empty-state">Add your first project above.</td></tr>}</tbody></table></div>
   </section>
   <section className="panel suite-space"><h3>Task board</h3>
    <div className="suite-form suite-horizontal"><input aria-label="Task name" placeholder="New task" maxLength={160} value={taskForm.name} onChange={e=>setTaskForm({...taskForm,name:e.target.value})}/>
     <select aria-label="Task project" value={taskForm.project_id||""} onChange={e=>setTaskForm({...taskForm,project_id:Number(e.target.value)})}><option value="">Project</option>{projects.filter(p=>!p.archived).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
     <select aria-label="Task status" value={taskForm.status} onChange={e=>setTaskForm({...taskForm,status:e.target.value as Task["status"]})}>{(["todo","doing","done"] as const).map(x=><option key={x}>{x}</option>)}</select>
     <input title="Estimated minutes" type="number" min="0" placeholder="Minutes" value={taskForm.estimate_minutes} onChange={e=>setTaskForm({...taskForm,estimate_minutes:Number(e.target.value)})}/>
     <button className="primary" disabled={busy} onClick={()=>void saveTask()}><Plus size={16}/> {taskForm.id?"Save":"Add task"}</button></div>
    <div className="task-board">{(["todo","doing","done"] as const).map(status=><div key={status}><h4>{status.toUpperCase()} <span>{tasks.filter(t=>t.status===status).length}</span></h4>{tasks.filter(t=>t.status===status).map(t=><button className="task-tile" key={t.id} onClick={()=>setTaskForm(t)}><strong>{t.name}</strong><small>{projects.find(p=>p.id===t.project_id)?.name} · {t.estimate_minutes} min estimated</small></button>)}</div>)}</div>
   </section>
  </>}

  {section==="focus"&&<div className="suite-grid"><section className="panel focus-card"><div className="eyebrow">FOCUS SESSION</div><Timer size={35} color="#83eabb"/><div className="focus-clock">{focus?.status==="running"?duration(completeFocus):duration(focusMinutes*60)}</div><p className="muted">{focus?.status==="running"?"Stay focused on one important task.":"Start a distraction-free work block."}</p>
   <div className="suite-actions center">{focus?.status==="running"?<button disabled={busy} className="secondary" onClick={()=>void run(async()=>{await api("/v2/focus/finish","POST");setFocus(await api("/v2/focus"));},"Focus session ended.")}><PauseCircle size={17}/> Finish session</button>:<><select aria-label="Focus duration" value={focusMinutes} onChange={e=>setFocusMinutes(Number(e.target.value))}>{[5,15,25,45,50,90].map(x=><option key={x} value={x}>{x} minutes</option>)}</select><button disabled={busy} className="primary" onClick={()=>void run(async()=>{setFocus(await api("/v2/focus/start","POST",{minutes:focusMinutes,task_id:null}));},"Focus session started.")}><PlayCircle size={17}/> Start focus</button></>}</div><p className="small-note">Completion is checked by the desktop agent even when the dashboard is hidden.</p></section>
   <section className="panel"><h3>Deep-work routine</h3><div className="mini-list"><div className="mini-row"><CheckCircle2 size={18}/> Select one important task and a 25–50 minute block.</div><div className="mini-row"><CheckCircle2 size={18}/> Optional category rules help you identify distractions.</div><div className="mini-row"><CheckCircle2 size={18}/> Use Ctrl+Alt+Shift+B to take or end a break.</div><div className="mini-row"><CheckCircle2 size={18}/> Track long productive blocks in the Insights screen.</div></div></section></div>}

  {section==="attendance"&&<section className="panel"><div className="suite-actions between"><h3>Monthly attendance</h3><label>Month <input type="month" value={month} onChange={e=>setMonth(e.target.value||localDay().slice(0,7))}/></label></div>
   <div className="attendance-summary"><b>{hours(attendance?.total_work||0)}</b><span>Total work this month</span><b>{attendance?.goal_days||0}</b><span>Goal days reached</span></div>
   <div className="calendar-grid">{["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map(x=><strong key={x}>{x}</strong>)}{cells.map((d,i)=>d?<div key={d.date} className={"day-cell "+(d.goal_met?"goal-met":d.work>0?"some-work":"no-work")} title={d.date+" • "+hours(d.work)}><b>{Number(d.date.slice(-2))}</b><span>{d.work?hours(d.work):"—"}</span></div>:<div key={"pad"+i} className="day-cell empty"/>)}</div><p className="small-note">Green indicates your daily goal was met; dim indicates no tracked work.</p>
  </section>}

  {section==="insights"&&<><div className="metric-grid suite-metrics">{[
    ["Work this week",String(insights?.work_hours||0)+"h"],
    ["Productivity",String(insights?.productivity||0)+"%"],
    ["App switches",String(insights?.context_switches||0)],
    ["Longest focus",String(insights?.longest_focus_minutes||0)+" min"],
    ["Active days",String(insights?.active_days||0)],
    ["Best focus hours",(insights?.peak_hours||[]).map(h=>h+":00").join(", ")||"—"]
  ].map(([a,b])=><div className="metric-card" key={a}><p className="muted">{a}</p><div className="metric-value">{b}</div></div>)}</div>
   <section className="panel suite-space"><h3>Local productivity recommendations</h3><p className="muted">Computed on-device from category totals and context-switching patterns. No cloud service.</p><div className="mini-list">{insights?.tips.map((tip,i)=><div className="mini-row" key={i}><BrainCircuit color="#83eabb" size={19}/>{tip}</div>)}</div></section>
   <section className="panel suite-space"><div className="suite-actions between"><div><h3>Optional AI coach (Ollama)</h3><p className="muted">Only summary metrics are passed to your own localhost Ollama model. Enable local AI consent under Privacy first.</p></div><button disabled={busy} className="primary" onClick={()=>void run(async()=>{const r=await api("/v2/insights/ai","POST");setAiText(r.text);},"Local AI insight generated.")}><BrainCircuit size={17}/> Generate AI advice</button></div>{aiText&&<pre className="insight-text">{aiText}</pre>}</section>
  </>}

  {section==="privacy"&&<><section className="panel"><div className="suite-actions between"><div><h3>Private tracking pause</h3><p className="muted">Stop capturing new app and window intervals immediately.</p></div><button className={privacy?.paused?"primary":"secondary"} disabled={busy} onClick={()=>void run(()=>api(privacy?.paused?"/v2/privacy/resume":"/v2/privacy/pause","POST"),"Tracking privacy preference updated.")}>{privacy?.paused?<PlayCircle size={16}/>:<PauseCircle size={16}/>} {privacy?.paused?"Resume tracking":"Pause tracking"}</button></div>
   <div className="privacy-options">{([
    ["hide_window_titles","Always mask window titles","Store only application names, not document or tab titles."],
    ["browser_opt_in","Enable browser domain integration","Requires explicit extension pairing. Stores hostname only while browser active."],
    ["ai_opt_in","Enable local AI recommendations","Aggregated statistics may be sent only to your localhost Ollama model."],
    ["meeting_opt_in","Enable calendar meeting detection","Use meetings from a locally imported .ics calendar file."]
   ] as const).map(([key,title,desc])=><label className="suite-toggle" key={key}><span><strong>{title}</strong><small>{desc}</small></span><input type="checkbox" checked={Boolean(privacy?.[key])} onChange={e=>void patchPrivacy({[key]:e.target.checked})}/></label>)}
    <div className="settings-row"><div><strong>Keep tracking data for</strong><p>Old activities and manual time are cleaned up daily.</p></div><select value={privacy?.retention_days||90} onChange={e=>void patchPrivacy({retention_days:Number(e.target.value)})}>{[7,30,90,180,365,730,3650].map(x=><option key={x} value={x}>{x} days</option>)}</select></div>
    <button className="secondary" disabled={busy} onClick={()=>void run(async()=>{const result=await api("/v2/privacy/purge","POST");setNotice("Deleted "+result.deleted+" expired records.");},"Retention applied.")}><Trash2 size={16}/> Clean expired records now</button>
   </div></section>
   <div className="suite-grid suite-space"><section className="panel"><h3>Sensitive application rules</h3><p className="muted">Exclude an application entirely or mask its window titles.</p><div className="suite-form"><input aria-label="Privacy app pattern" placeholder="App name or title keyword" value={privacyPattern} onChange={e=>setPrivacyPattern(e.target.value)}/><select aria-label="Privacy action" value={privacyAction} onChange={e=>setPrivacyAction(e.target.value as "exclude"|"mask")}><option value="exclude">Exclude tracking</option><option value="mask">Mask titles</option></select><button className="primary" disabled={busy||privacyPattern.trim().length<2} onClick={()=>void run(async()=>{await api("/v2/privacy/rules","POST",{pattern:privacyPattern,action:privacyAction});setPrivacyPattern("");},"Privacy rule added.")}><Plus size={15}/> Add rule</button></div><div className="mini-list">{privacyRules.map(rule=><div className="mini-row" key={rule.id}><LockKeyhole size={16}/><span><b>{rule.pattern}</b><small>{rule.action==="exclude"?"Never record":"Hide title"}</small></span><button className="icon-action" onClick={()=>void run(()=>api("/v2/privacy/rules/"+rule.id,"DELETE"),"Rule removed.")}><Trash2 size={16}/></button></div>)}</div></section>
    <section className="panel"><h3>Review idle periods</h3><p className="muted">Correct time away from your device after returning. Unreviewed idle intervals stay idle.</p><div className="mini-list">{!idle.length&&<p className="small-note">No pending idle periods.</p>}{idle.map(item=><div className="idle-review" key={item.id}><strong>{new Date(item.start).toLocaleTimeString()} · {duration(item.seconds)}</strong><div className="suite-actions"><select aria-label={"Classify idle "+item.id} value={idleDecision[item.id]||"keep_idle"} onChange={e=>setIdleDecision({...idleDecision,[item.id]:e.target.value})}><option value="keep_idle">Keep idle</option><option value="productive">Worked away</option><option value="neutral">Neutral work</option><option value="break">Break</option></select><button className="secondary" onClick={()=>void run(()=>api("/v2/idle/"+item.id+"/resolve","POST",{decision:idleDecision[item.id]||"keep_idle"}),"Idle interval reviewed.")}><CheckCircle2 size={15}/> Apply</button></div></div>)}</div></section></div>
  </>}

  {section==="calendar"&&<div className="suite-grid"><section className="panel"><CalendarDays size={31} color="#83eabb"/><h3 className="suite-space">Import an iCalendar file</h3><p className="muted">Export an .ics file from your preferred calendar and import it locally. Descriptions and attendee addresses are discarded. Meeting detection must be enabled under Privacy.</p><div className="suite-actions suite-space"><button className="primary" disabled={busy} onClick={()=>void run(async()=>{const result=await window.workpulse.importCalendar();if(result)setNotice("Imported "+result.imported+" calendar events.");},"Calendar imported.")}><Plus size={16}/> Select .ics file</button></div></section>
    <section className="panel"><h3>Imported meetings</h3><label className="suite-inline-label">Day <input type="date" value={calendarDay} onChange={e=>setCalendarDay(e.target.value)}/></label><div className="mini-list">{meetings.map(item=><div className="mini-row" key={item.id}><CalendarDays size={16}/><span><b>{item.title}</b><small>{new Date(item.starts_at).toLocaleTimeString()} — {new Date(item.ends_at).toLocaleTimeString()}</small></span><button className="icon-action" onClick={()=>void run(()=>api("/v2/meetings/"+item.id,"DELETE"),"Meeting removed.")}><Trash2 size={16}/></button></div>)}{!meetings.length&&<p className="small-note">No imported meetings on this date.</p>}</div></section></div>}

  {section==="reports"&&<><section className="panel"><h3>Custom report period</h3><div className="suite-actions suite-space"><label>From <input type="date" value={reportStart} max={reportEnd} onChange={e=>setReportStart(e.target.value)}/></label><label>To <input type="date" value={reportEnd} min={reportStart} onChange={e=>setReportEnd(e.target.value)}/></label><button className="primary" disabled={busy} onClick={()=>void run(async()=>{const path=await window.workpulse.exportCustom("csv",reportStart,reportEnd,offset());if(path)setNotice("Saved "+path);},"CSV generated.")}><Download size={15}/> CSV</button><button className="secondary" disabled={busy} onClick={()=>void run(async()=>{const path=await window.workpulse.exportCustom("pdf",reportStart,reportEnd,offset());if(path)setNotice("Saved "+path);},"PDF generated.")}><Download size={15}/> PDF</button></div></section>
   <section className="panel suite-space"><h3>Client & project billable hours</h3><div className="table-wrap"><table><thead><tr><th>PROJECT</th><th>CLIENT</th><th>HOURS</th><th>RATE</th><th>BILLABLE</th><th>BUDGET</th></tr></thead><tbody>{projectReport.map(p=><tr key={p.id}><td>{p.name}</td><td>{p.client||"—"}</td><td>{p.hours}</td><td>{p.hourly_rate}</td><td><strong>{p.billable.toFixed(2)}</strong></td><td>{p.budget_hours?p.budget_hours+"h":"—"}</td></tr>)}{!projectReport.length&&<tr><td colSpan={6} className="empty-state">Assign work to projects to view client billing.</td></tr>}</tbody></table></div></section>
  </>}

  {section==="browser"&&<div className="suite-grid"><section className="panel"><Globe2 size={31} color="#83eabb"/><h3 className="suite-space">Opt-in browser pairing</h3><p className="muted">Load the included browser-extension directory in Chrome or Edge through Extensions → Developer mode → Load unpacked. Enable browser tracking in Privacy, then generate a pairing token.</p><div className="suite-actions suite-space"><button disabled={busy} className="primary" onClick={()=>void run(async()=>{setPair(await api("/v2/browser/pair","POST"));},"One-time pairing token generated.")}><Link2 size={16}/> Generate pairing</button><button disabled={busy} className="secondary" onClick={()=>void run(async()=>{await api("/v2/browser/pair","DELETE");setPair(null);},"Browser pairing revoked.")}>Revoke</button></div>
    {pair&&<div className="pair-details"><label>127.0.0.1 port<input readOnly value={pair.port} onFocus={e=>e.target.select()}/></label><label>Pairing token (shown once)<input readOnly value={pair.token} onFocus={e=>e.target.select()}/></label><p className="small-note">Enter these in the extension popup. Pairing tokens are only for domain hints; they cannot read other WorkPulse data.</p></div>}</section>
    <section className="panel"><h3>Data collected</h3><div className="mini-list">{["Active website hostname, for example github.com","Only while its browser window is foreground","No URL paths, page content or passwords","No browsing history or network traffic capture","Domain hints expire automatically and can be revoked"].map(x=><div key={x} className="mini-row"><ShieldCheck size={17} color="#83eabb"/>{x}</div>)}</div></section></div>}

  {section==="backups"&&<div className="suite-grid"><section className="panel"><LockKeyhole size={30} color="#83eabb"/><h3 className="suite-space">Encrypted backup & restore</h3><p className="muted">Backups are encrypted with AES-256-GCM using a password you provide. Keep the password safely: it cannot be recovered by WorkPulse. Restoring restarts the background tracking service.</p>
    <div className="suite-form"><label>Backup password (12+ characters)<input type="password" autoComplete="new-password" value={backupPassword} onChange={e=>setBackupPassword(e.target.value)} placeholder="Create or enter backup password"/></label><div className="suite-actions"><button disabled={busy||backupPassword.length<12} className="primary" onClick={()=>void run(async()=>{const p=await window.workpulse.createBackup(backupPassword);if(p)setNotice("Backup saved: "+p);},"Encrypted backup exported.")}><Download size={16}/> Export backup</button><button disabled={busy||backupPassword.length<12} className="secondary" onClick={()=>{if(!confirm("Restore a prior database? Current records will be replaced after a tracker restart."))return;void run(async()=>{const result=await window.workpulse.restoreBackup(backupPassword);if(result)setNotice("Restore staged and service restarting.");},"Restore requested.");}}><Archive size={16}/> Restore backup</button></div></div></section>
   <section className="panel"><RefreshCcw size={30} color="#83eabb"/><h3 className="suite-space">Application updates</h3><p className="muted">WorkPulse checks the official GitHub release feed. Updates must be signed by a trusted publisher before automatic installation is supported. Unsigned builds never silently auto-install upgrades.</p><label className="suite-toggle"><span><strong>Automatically install verified updates</strong><small>Opt in to GitHub release checks every 12 hours. Only enabled for publisher-signed Windows builds.</small></span><input type="checkbox" checked={updateEnabled} onChange={e=>void run(async()=>{const state=await window.workpulse.setAutoUpdates(e.target.checked);setUpdateEnabled(state.enabled);setSignedInstaller(state.signed);},"Update preference saved.")}/></label><p className="small-note">{signedInstaller?"Signed publisher verified.":"Current build is unsigned or running in development mode."}</p><button className="primary suite-space" disabled={busy} onClick={()=>void run(async()=>{const r=await window.workpulse.checkUpdates();setUpdate(r.message+(r.available?" New release: "+r.version:""));},"Update check completed.")}><RefreshCcw size={16}/> Check for updates</button>{update&&<p className="small-note">{update}</p>}<p className="small-note">Automatic local migration backups are also retained for recent app starts.</p></section></div>}
 </div>;
}
