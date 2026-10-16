"use strict";
const {app,BrowserWindow,Tray,Menu,ipcMain,dialog,safeStorage,nativeImage}=require("electron");
const {randomBytes}=require("node:crypto");
const {join,resolve}=require("node:path");
const {existsSync,readFileSync,writeFileSync}=require("node:fs");
const fs=require("node:fs/promises");
const {spawn}=require("node:child_process");
if(!app.requestSingleInstanceLock()){app.quit();process.exit(0);}
let dashboard,widget,tray,backend,socket;
let port=null,token=null,quitting=false,restartTimer=null;
const capability=randomBytes(48).toString("hex");
const sessionPath=()=>join(app.getPath("userData"),"session.enc");
function loadSession(){try{if(safeStorage.isEncryptionAvailable()&&existsSync(sessionPath()))token=safeStorage.decryptString(readFileSync(sessionPath()));}catch{token=null;}}
function persistSession(value){token=value;if(safeStorage.isEncryptionAvailable())writeFileSync(sessionPath(),safeStorage.encryptString(value));}
async function clearSession(){token=null;await fs.rm(sessionPath(),{force:true}).catch(()=>{});if(socket){socket.close();socket=null;}}
const allowed=/^\/(health|auth\/(status|register|login|me)|session\/(start|break|resume|finish)|activity\/live|stats\/(day|week|month)|categories(\/[0-9]+)?|settings|export)(\?.*)?$/;
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
 ws.addEventListener("message",e=>{try{broadcast("live:state",JSON.parse(e.data));}catch{}});
 ws.addEventListener("close",()=>{if(socket===ws){socket=null;if(!quitting&&port&&token)setTimeout(()=>{if(!socket)connectLive();},2000);}});
 ws.addEventListener("error",()=>{});
}
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
 const png="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jNz0AAAAASUVORK5CYII=";
 const icon=nativeImage.createFromDataURL("data:image/png;base64,"+png).resize({width:16,height:16});
 tray=new Tray(icon);tray.setToolTip("WorkPulse");
 tray.setContextMenu(Menu.buildFromTemplate([{label:"Dashboard",click:openDashboard},{label:"Floating timer",click:showWidget},{type:"separator"},{label:"Quit WorkPulse",click:()=>{quitting=true;app.quit();}}]));
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
app.on("before-quit",()=>{quitting=true;clearTimeout(restartTimer);if(socket)socket.close();if(backend)backend.kill();});
app.whenReady().then(()=>{loadSession();createTray();launchBackend();if(!process.argv.includes("--hidden"))openDashboard();if(token)showWidget();app.on("activate",openDashboard);});
ipcMain.handle("api:request",async(_e,{path,method,body})=>{
 if(body&&JSON.stringify(body).length>100000)throw Error("Request too large");
 const result=await callApi(path,method,body);
 if(path==="/auth/login"||path==="/auth/register"){persistSession(result.token);connectLive();showWidget();setAutoStart(true);return {user:result.user};}
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
