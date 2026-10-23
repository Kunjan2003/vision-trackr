"use strict";
// Owns only the process spawned by this application. Never attaches to another
// agent or accepts its port without this launch's capability-authenticated health.
class BackendService {
 constructor(options){
  this.options=options;this.child=null;this.timer=null;this.retry=null;this.probe=null;
  this.generation=0;this.stopped=false;this.attempts=0;
  this.state={status:"starting",message:"Starting the local tracking service…"};
 }
 update(status,message,extra={}){this.state={status,message,...extra};this.options.onState(this.state);}
 clearTimers(){clearTimeout(this.timer);clearTimeout(this.retry);clearTimeout(this.probe);this.timer=this.retry=this.probe=null;}
 async kill(child){if(child)await this.options.kill(child);}
 start(){
  if(this.child||this.stopped)return;
  this.clearTimers();const generation=++this.generation;let child;
  this.update("starting","Starting the local tracking service…");
  try{child=this.options.spawn(this.options.binary,this.options.args,this.options.spawnOptions);this.child=child;}
  catch(error){void this.fail(generation,"Cannot launch tracking service: "+error.message);return;}
  this.options.log("Starting backend attempt "+(this.attempts+1));
  let pending="",tail="",probing=false;
  child.stdout.on("data",chunk=>{
   if(generation!==this.generation)return;
   pending+=chunk.toString();const lines=pending.split(/\r?\n/);pending=lines.pop()||"";
   if(pending.length>8192)pending=pending.slice(-8192);
   for(const line of lines){const match=/^WORKPULSE_PORT=(\d+)$/.exec(line.trim());
    if(match&&!probing){const port=Number(match[1]);if(port>0&&port<=65535){probing=true;void this.checkHealth(generation,port);}}
   }
  });
  child.stderr.on("data",chunk=>{if(generation!==this.generation)return;tail=(tail+chunk.toString()).slice(-6000);this.options.log(chunk.toString());});
  child.once("error",error=>{void this.fail(generation,"Cannot launch tracking service: "+error.message);});
  child.once("exit",(code,signal)=>{
   if(generation!==this.generation)return;
   const detail=tail.trim().split(/\r?\n/).filter(Boolean).slice(-3).join(" ");
   void this.fail(generation,`Tracking service exited (${code??signal??"unknown"}).`+(detail?" "+detail:" Open the startup log for details."));
  });
  this.timer=setTimeout(()=>void this.fail(generation,"The tracking service did not become ready within two minutes. Open the startup log for details."),this.options.startupTimeout??120000);
 }
 async checkHealth(generation,port){
  try{
   const response=await this.options.fetch(`http://127.0.0.1:${port}/health`,{headers:{"X-Agent-Token":this.options.capability},signal:AbortSignal.timeout(this.options.healthTimeout??3000)});
   if(!response.ok||!(await response.json()).ok)throw Error("Service health check failed");
   if(generation!==this.generation||this.stopped)return;
   clearTimeout(this.timer);this.timer=null;
   this.update("ready","Tracking service is ready.",{port});
  }catch(error){
   if(generation!==this.generation||this.stopped)return;
   this.probe=setTimeout(()=>void this.checkHealth(generation,port),this.options.probeDelay??300);
  }
 }
 async fail(generation,message){
  if(generation!==this.generation||this.stopped)return;
  ++this.generation;this.clearTimers();const child=this.child;this.child=null;
  this.options.log(message);
  const retry=this.attempts<(this.options.maxRestarts??2);
  this.update(retry?"starting":"failed",retry?message+" Retrying…":message);
  await this.kill(child);
  if(this.stopped||generation+1!==this.generation)return;
  if(retry){this.attempts++;this.retry=setTimeout(()=>this.start(),this.options.restartDelay??2500);}
 }
 async restart(){await this.stop();this.stopped=false;this.attempts=0;this.start();return this.state;}
 async stop(){this.stopped=true;++this.generation;this.clearTimers();const child=this.child;this.child=null;await this.kill(child);}
}
module.exports={BackendService};
