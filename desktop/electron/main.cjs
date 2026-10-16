"use strict";
const {app,BrowserWindow,Tray,Menu,Notification,globalShortcut,shell,ipcMain,dialog,safeStorage,nativeImage}=require("electron");
const {randomBytes}=require("node:crypto");
const {join,resolve}=require("node:path");
const {existsSync,readFileSync,writeFileSync}=require("node:fs");
const fs=require("node:fs/promises");
const {spawn,execFileSync}=require("node:child_process");
const {WebSocket}=require("ws");
const {autoUpdater}=require("electron-updater");
if(!app.requestSingleInstanceLock()){app.quit();process.exit(0);}
let dashboard,widget,tray,backend,socket;
let port=null,token=null,quitting=false,restartTimer=null,lastReminder=null,lastIdlePending=0;
const capability=randomBytes(48).toString("hex");
const sessionPath=()=>join(app.getPath("userData"),"session.enc");
function loadSession(){try{if(safeStorage.isEncryptionAvailable()&&existsSync(sessionPath()))token=safeStorage.decryptString(readFileSync(sessionPath()));}catch{token=null;}}
function persistSession(value){token=value;if(safeStorage.isEncryptionAvailable())writeFileSync(sessionPath(),safeStorage.encryptString(value));}
async function clearSession(){token=null;await fs.rm(sessionPath(),{force:true}).catch(()=>{});if(socket){socket.close();socket=null;}}
const allowed=/^\/(?:health|auth\/(?:status|register|login|me)|session\/(?:start|break|resume|finish)|activity\/live|stats\/(?:day|week|month)|categories(?:\/[0-9]+)?|settings|export|v2\/(?:projects(?:\/analytics|\/[0-9]+)?|tasks(?:\/[0-9]+)?|project-rules(?:\/[0-9]+)?|assignment|privacy(?:\/(?:rules(?:\/[0-9]+)?|pause|resume|purge))?|idle\/(?:pending|[0-9]+\/resolve)|manual(?:\/[0-9]+)?|focus(?:\/(?:start|finish))?|attendance|insights(?:\/ai)?|meetings(?:\/import|\/[0-9]+)?|browser\/pair|backups\/(?:create|prepare-restore)))(\?.*)?$/;
async function callApi(path,method="GET",body){
 if(!allowed.test(path)||!["GET","POST","PATCH","PUT","DELETE"].includes(method))throw Error("Invalid API request");
 if(!port)throw Error("Tracker service is connecting");
 const headers={"X-Agent-Token":capability};
 if(token)headers.Authorization="Bearer "+token;
 if(body!==undefined)headers["Content-Type"]="application/json";
 const response=await fetch("http://127.0.0.1:"+port+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(12000)});
 const kind=response.headers.get("content-type")||"";
 const value=kind.includes("application/json")?await response.json():await response.text();
 if(!response.ok)throw Error(typeof value?.detail==="string"?value.detail:"Request failed ("+response.status+")");
 return value;
}
function broadcast(channel,value){for(const win of [dashboard,widget])if(win&&!win.isDestroyed())win.webContents.send(channel,value);}
function connectLive(){
 if(socket){socket.close();socket=null;}
 if(!port||!token)return;
 const ws=new WebSocket("ws://127.0.0.1:"+port+"/ws/live");socket=ws;
 ws.addEventListener("open",()=>{if(socket===ws)ws.send(JSON.stringify({agent:capability,token}));});
 ws.addEventListener("message",e=>{try{const data=JSON.parse(e.data);broadcast("live:state",data);
  if(data.reminder?.id&&data.reminder.id!==lastReminder){lastReminder=data.reminder.id;
   if(Notification.isSupported())new Notification({title:"WorkPulse - Break reminder",body:data.reminder.message}).show();}
  if(data.idle_pending>lastIdlePending && Notification.isSupported()){
    const n=new Notification({title:"WorkPulse • Idle time to review",body:"Review time away from your computer and classify it accurately."});
    n.on("click",()=>{openDashboard();dashboard?.webContents.send("dashboard:navigate","privacy");});
    n.show();
  }
  lastIdlePending=data.idle_pending||0;
  }catch{}});
 ws.addEventListener("close",()=>{if(socket===ws){socket=null;if(!quitting&&port&&token)setTimeout(()=>{if(!socket)connectLive();},2000);}});
 ws.addEventListener("error",()=>{});
}
let notifiedFocus=null;
function setAutoStart(enabled){if(process.platform==="win32"&&app.isPackaged)app.setLoginItemSettings({openAtLogin:!!enabled,path:process.execPath,args:["--hidden"]});}
function makeWindow(which,options){
 const win=new BrowserWindow({show:false,backgroundColor:"#111827",webPreferences:{preload:join(__dirname,"preload.cjs"),nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true,devTools:!app.isPackaged},...options});
 win.webContents.setWindowOpenHandler(()=>({action:"deny"}));
 win.webContents.on("will-navigate",e=>e.preventDefault());
 if(app.isPackaged)win.loadFile(join(__dirname,"../dist/index.html"),{query:{window:which}});
 else win.loadURL("http://127.0.0.1:5173/?window="+which);
 return win;
}
function openDashboard(){
 if(!dashboard||dashboard.isDestroyed()){
  dashboard=makeWindow("dashboard",{width:1280,height:820,minWidth:940,minHeight:650,title:"WorkPulse"});
  dashboard.on("close",e=>{if(!quitting){e.preventDefault();dashboard.hide();}});
 }
 dashboard.show();dashboard.focus();
}
function showWidget(){
 if(!widget||widget.isDestroyed()){
  widget=makeWindow("widget",{width:310,height:174,resizable:false,frame:false,transparent:true,alwaysOnTop:true,skipTaskbar:true,title:"WorkPulse Mini"});
  widget.setAlwaysOnTop(true,"floating");
  widget.on("close",e=>{if(!quitting){e.preventDefault();widget.hide();}});
 }
 widget.show();
}
function createTray(){
 const icon=nativeImage.createFromPath(join(__dirname,"../assets/tray.png"));
 tray=new Tray(icon);tray.setToolTip("WorkPulse");
 tray.setContextMenu(Menu.buildFromTemplate([{label:"Dashboard",click:openDashboard},{label:"Floating timer",click:showWidget},{label:"Toggle private pause",click:()=>void toggleTrackingPause()},{type:"separator"},{label:"Quit WorkPulse",click:()=>{quitting=true;app.quit();}}]));
 tray.on("double-click",openDashboard);
}
function launchBackend(){
 if(quitting||backend)return;
 port=null;if(socket){socket.close();socket=null;}
 const directory=resolve(__dirname,"../../backend");
 const binary=app.isPackaged?join(process.resourcesPath,"bin","workpulse-backend.exe"):(process.env.WORKPULSE_PYTHON||(process.platform==="win32"?"python":"python3"));
 backend=spawn(binary,app.isPackaged?[]:["-m","workpulse"],{cwd:app.isPackaged?process.resourcesPath:directory,windowsHide:true,stdio:["ignore","pipe","pipe"],env:{...process.env,WORKPULSE_AGENT_TOKEN:capability,PYTHONPATH:directory}});
 backend.on("error",e=>broadcast("live:state",{error:"Service failed: "+e.message}));
 let pending="";
 backend.stdout.on("data",chunk=>{
  pending+=chunk.toString();const lines=pending.split(/\r?\n/);pending=lines.pop()||"";
  for(const line of lines){const m=/^WORKPULSE_PORT=(\d+)$/.exec(line.trim());if(m){port=Number(m[1]);broadcast("backend:ready");if(token)connectLive();}}
 });
 backend.stderr.on("data",chunk=>{if(!app.isPackaged)console.error("[backend]",chunk.toString().trim());});
 backend.on("exit",()=>{backend=null;port=null;broadcast("live:state",{error:"Service disconnected"});if(!quitting)restartTimer=setTimeout(launchBackend,2500);});
}
app.on("second-instance",openDashboard);
app.on("before-quit",()=>{quitting=true;globalShortcut.unregisterAll();clearTimeout(restartTimer);if(socket)socket.close();if(backend)backend.kill();});
app.whenReady().then(()=>{loadSession();createTray();launchBackend();if(!process.argv.includes("--hidden"))openDashboard();if(token)showWidget();registerGlobalShortcuts();setInterval(()=>void checkFocusCompletion(),30000);
  setTimeout(()=>void tryAutoUpdate(),120000);setInterval(()=>void tryAutoUpdate(),12*60*60*1000);app.on("activate",openDashboard);});
ipcMain.handle("api:request",async(_e,{path,method,body})=>{
 if(body&&JSON.stringify(body).length>100000)throw Error("Request too large");
 const result=await callApi(path,method,body);
 if(path==="/auth/login"||path==="/auth/register"){persistSession(result.token);connectLive();showWidget();try{const s=await callApi("/settings");setAutoStart(s.auto_start);}catch{}return {user:result.user};}
 return result;
});
ipcMain.handle("api:export",async(_e,{format,day,tz})=>{
 if(!["csv","pdf"].includes(format)||!/^\d{4}-\d{2}-\d{2}$/.test(day)||!Number.isInteger(tz)||Math.abs(tz)>840)throw Error("Invalid export");
 if(!port||!token)throw Error("Sign in first");
 const response=await fetch("http://127.0.0.1:"+port+"/export?format="+format+"&day="+day+"&tz="+tz,{headers:{"X-Agent-Token":capability,Authorization:"Bearer "+token}});
 if(!response.ok)throw Error("Report generation failed");
 const destination=await dialog.showSaveDialog({defaultPath:"WorkPulse-"+day+"."+format,filters:[{name:format.toUpperCase(),extensions:[format]}]});
 if(destination.canceled||!destination.filePath)return null;
 await fs.writeFile(destination.filePath,Buffer.from(await response.arrayBuffer()));
 return destination.filePath;
});
ipcMain.handle("window:dashboard",openDashboard);
ipcMain.handle("window:compact",(_e,compact)=>{if(widget)widget.setSize(compact?164:310,compact?66:174);});
ipcMain.handle("window:hide",()=>dashboard&&dashboard.hide());
ipcMain.handle("system:autostart",(_e,enabled)=>setAutoStart(enabled));
ipcMain.handle("auth:signout",async()=>{await clearSession();if(widget)widget.hide();});



// All system keyboard shortcuts are explicit key combinations. No key events are recorded.
function registerGlobalShortcuts(){
 if(process.platform!=="win32")return;
 globalShortcut.register("CommandOrControl+Alt+Shift+W",openDashboard);
 globalShortcut.register("CommandOrControl+Alt+Shift+B",()=>{
  if(!token||!port)return;
  void callApi("/activity/live").then(d=>{
   if(d.status==="working")return callApi("/session/break","POST");
   if(d.status==="break")return callApi("/session/resume","POST");
  }).catch(()=>{});
 });
 globalShortcut.register("CommandOrControl+Alt+Shift+P",()=>void toggleTrackingPause());
}
async function toggleTrackingPause(){
 if(!token||!port)return;
 try{
  const status=await callApi("/v2/privacy");
  const next=await callApi(status.paused?"/v2/privacy/resume":"/v2/privacy/pause","POST");
  if(Notification.isSupported())new Notification({title:"WorkPulse",body:next.paused?"Private pause enabled":"Tracking resumed"}).show();
 }catch{}
}
async function checkFocusCompletion(){
 if(!token||!port)return;
 try{
  const focus=await callApi("/v2/focus");
  if(focus?.status==="completed"&&focus.id!==notifiedFocus){
   notifiedFocus=focus.id;
   if(Notification.isSupported())new Notification({title:"Focus session completed",body:"Your focused work block is complete. Time for a short break."}).show();
  }
 }catch{}
}
async function saveReportBytes(uri,filename,filters){
 if(!port||!token)throw Error("Sign in first");
 const response=await fetch("http://127.0.0.1:"+port+uri,{
  headers:{"X-Agent-Token":capability,Authorization:"Bearer "+token}});
 if(!response.ok)throw Error("Export generation failed");
 const result=await dialog.showSaveDialog({defaultPath:filename,filters});
 if(result.canceled||!result.filePath)return null;
 await fs.writeFile(result.filePath,Buffer.from(await response.arrayBuffer()));
 return result.filePath;
}
ipcMain.handle("report:custom",async(_event,{format,start,end,tz})=>{
 if(!["csv","pdf"].includes(format)||![start,end].every(x=>/^\d{4}-\d{2}-\d{2}$/.test(x))
    ||!Number.isInteger(tz)||Math.abs(tz)>840)throw Error("Invalid report options");
 const uri="/v2/reports/export?format="+format+"&start="+start+"&end="+end+"&tz="+tz;
 return saveReportBytes(uri,"WorkPulse-"+start+"-"+end+"."+format,[{name:format.toUpperCase(),extensions:[format]}]);
});
ipcMain.handle("calendar:import",async()=>{
 const selected=await dialog.showOpenDialog({title:"Import local calendar",properties:["openFile"],filters:[{name:"iCalendar",extensions:["ics"]}]});
 if(selected.canceled||!selected.filePaths.length)return null;
 const stat=await fs.stat(selected.filePaths[0]);
 if(stat.size>1500000)throw Error("Calendar is too large (maximum 1.5 MB)");
 return callApi("/v2/meetings/import","POST",{text:await fs.readFile(selected.filePaths[0],"utf8")});
});
ipcMain.handle("backup:create",async(_event,password)=>{
 if(typeof password!=="string"||password.length<12||password.length>256)throw Error("Use a password of at least 12 characters");
 const value=await callApi("/v2/backups/create","POST",{password});
 const selected=await dialog.showSaveDialog({title:"Save encrypted WorkPulse backup",defaultPath:value.filename,filters:[{name:"WorkPulse encrypted backup",extensions:["wpbackup"]}]});
 if(selected.canceled||!selected.filePath)return null;
 await fs.writeFile(selected.filePath,Buffer.from(value.payload,"base64"));
 return selected.filePath;
});
ipcMain.handle("backup:restore",async(_event,password)=>{
 if(typeof password!=="string"||password.length<12||password.length>256)throw Error("Use the password from the backup");
 const selected=await dialog.showOpenDialog({title:"Restore encrypted WorkPulse backup",properties:["openFile"],filters:[{name:"WorkPulse encrypted backup",extensions:["wpbackup"]}]});
 if(selected.canceled||!selected.filePaths.length)return null;
 const bytes=await fs.readFile(selected.filePaths[0]);
 if(bytes.length>220*1024*1024)throw Error("Backup file exceeds 220 MB");
 const result=await callApi("/v2/backups/prepare-restore","POST",{password,payload:bytes.toString("base64")});
 if(result.restart_required&&backend){
   if(socket){socket.close();socket=null;}
   backend.kill(); // supervisor starts a new backend, which atomically applies staged restore
 }
 return result;
});
// Updates require a Windows Authenticode-signed installer and configured GitHub
// release metadata. Never install an unsigned update silently.
const updateSettingsPath=()=>join(app.getPath("userData"),"updates.json");
function updateEnabled(){
 try{return JSON.parse(readFileSync(updateSettingsPath(),"utf8")).enabled===true;}catch{return false;}
}
function signedInstaller(){
 if(!app.isPackaged||process.platform!=="win32")return false;
 try{
  const path=process.execPath.replace(/'/g,"''");
  const script="if ((Get-AuthenticodeSignature -LiteralPath '"+path+"').Status -eq 'Valid') {exit 0} else {exit 1}";
  execFileSync("powershell.exe",["-NoProfile","-NonInteractive","-Command",script],{windowsHide:true,timeout:10000,stdio:"ignore"});
  return true;
 }catch{return false;}
}
async function tryAutoUpdate(){
 if(!updateEnabled()||!signedInstaller())return;
 try{
  autoUpdater.autoDownload=true;
  autoUpdater.autoInstallOnAppQuit=true;
  await autoUpdater.checkForUpdates();
 }catch{/* No signed release or currently offline. */}
}
autoUpdater.autoDownload=false;
autoUpdater.autoInstallOnAppQuit=false;
autoUpdater.on("update-downloaded",()=>{
 if(Notification.isSupported())new Notification({title:"WorkPulse update ready",body:"The signed update will install when you quit WorkPulse."}).show();
});
autoUpdater.on("error",()=>{});
ipcMain.handle("updates:get",()=>({enabled:updateEnabled(),signed:signedInstaller()}));
ipcMain.handle("updates:set",async(_event,enabled)=>{
 if(typeof enabled!=="boolean")throw Error("Invalid update setting");
 await fs.writeFile(updateSettingsPath(),JSON.stringify({enabled}),{mode:0o600});
 if(enabled)void tryAutoUpdate();
 return {enabled,signed:signedInstaller()};
});
ipcMain.handle("updates:check",async()=>{
 if(!signedInstaller())
  return {available:false,message:"Updates require an installed, publisher-signed WorkPulse release. The current development or unsigned installer cannot auto-update."};
 try{
  const release=await autoUpdater.checkForUpdates();
  return {available:Boolean(release?.updateInfo && release.updateInfo.version!==app.getVersion()),
   version:release?.updateInfo?.version||app.getVersion(),
   message:"Only install authenticated, publisher-signed releases. If a release is available, obtain it from the verified GitHub repository."};
 }catch(e){
  return {available:false,message:"No published, signed WorkPulse update feed is currently available."};
 }
});

ipcMain.handle("browser:show-extension",async()=>{const path=app.isPackaged?join(process.resourcesPath,"browser-extension","manifest.json"):resolve(__dirname,"../../browser-extension/manifest.json");if(!existsSync(path))throw Error("Browser extension directory not found");shell.showItemInFolder(path);return true;});
