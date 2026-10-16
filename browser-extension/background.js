// WorkPulse never captures page text, title, URL paths, tabs history or keystrokes.
const HOST_RE=/^(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/;
async function sample(){
  try{
    const data=await chrome.storage.local.get(["enabled","port","token"]);
    if(!data.enabled||!Number.isInteger(data.port)||data.port<1024||data.port>65535||!data.token)return;
    const [tab]=await chrome.tabs.query({active:true,lastFocusedWindow:true});
    if(!tab||!tab.url)return;
    const url=new URL(tab.url);
    if(url.protocol!=="http:"&&url.protocol!=="https:")return;
    const hostname=url.hostname.toLowerCase().replace(/\.$/,"");
    if(!HOST_RE.test(hostname)||hostname.includes(".."))return;
    await fetch("http://127.0.0.1:"+data.port+"/browser/activity",{
      method:"POST",
      headers:{"Content-Type":"application/json","X-Browser-Token":data.token},
      body:JSON.stringify({hostname}),signal:AbortSignal.timeout(3500)
    });
  }catch{/* WorkPulse may be closed; intentionally no telemetry. */}
}
chrome.runtime.onInstalled.addListener(()=>chrome.alarms.create("domain-pulse",{periodInMinutes:0.5}));
chrome.runtime.onStartup.addListener(()=>chrome.alarms.create("domain-pulse",{periodInMinutes:0.5}));
chrome.alarms.onAlarm.addListener(alarm=>{if(alarm.name==="domain-pulse")void sample();});
chrome.tabs.onActivated.addListener(()=>void sample());
chrome.tabs.onUpdated.addListener((_id,change)=>{if(change.status==="complete"||change.url)void sample();});
chrome.windows.onFocusChanged.addListener(()=>void sample());
chrome.storage.onChanged.addListener((_changes,area)=>{if(area==="local")void sample();});
