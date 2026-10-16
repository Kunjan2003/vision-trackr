const {contextBridge,ipcRenderer}=require("electron");
contextBridge.exposeInMainWorld("workpulse",{
 request:(path,method="GET",body)=>ipcRenderer.invoke("api:request",{path,method,body}),
 exportReport:(format,day,tz)=>ipcRenderer.invoke("api:export",{format,day,tz}),
 onLive:cb=>{const fn=(_,data)=>cb(data);ipcRenderer.on("live:state",fn);return ()=>ipcRenderer.removeListener("live:state",fn);},
 onReady:cb=>{const fn=()=>cb();ipcRenderer.on("backend:ready",fn);return ()=>ipcRenderer.removeListener("backend:ready",fn);},
 showDashboard:()=>ipcRenderer.invoke("window:dashboard"),
 shrinkWidget:compact=>ipcRenderer.invoke("window:compact",compact),
 closeDashboard:()=>ipcRenderer.invoke("window:hide"),
 setAutoStart:enabled=>ipcRenderer.invoke("system:autostart",enabled),
 signOut:()=>ipcRenderer.invoke("auth:signout"),
 exportCustom:(format,start,end,tz)=>ipcRenderer.invoke("report:custom",{format,start,end,tz}),
 importCalendar:()=>ipcRenderer.invoke("calendar:import"),
 createBackup:password=>ipcRenderer.invoke("backup:create",password),
 restoreBackup:password=>ipcRenderer.invoke("backup:restore",password),
 checkUpdates:()=>ipcRenderer.invoke("updates:check"),
 getAutoUpdates:()=>ipcRenderer.invoke("updates:get"),
 setAutoUpdates:enabled=>ipcRenderer.invoke("updates:set",enabled),
 showBrowserExtension:()=>ipcRenderer.invoke("browser:show-extension")
});