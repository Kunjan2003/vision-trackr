// Exercises the same supervisor used by Electron against the packaged executable,
// including a second launch with an existing account (not just a clean database).
const assert=require("node:assert/strict");
const {spawn,execFile}=require("node:child_process");
const {resolve,join}=require("node:path");
const {mkdtemp,rm}=require("node:fs/promises");
const {tmpdir}=require("node:os");
const {BackendService}=require("../desktop/electron/backend-service.cjs");
(async()=>{
 const data=await mkdtemp(join(tmpdir(),"vision-startup-"));
 const source=process.argv.includes("--source");
 const root=resolve(__dirname,source?"../backend":"../desktop/release/win-unpacked/resources");
 const capability="ci-startup-smoke-capability";
 let service;
 let signalReady,rejectReady;
 const waitReady=()=>new Promise((resolve,reject)=>{signalReady=resolve;rejectReady=reject;});
 service=new BackendService({binary:source?(process.env.WORKPULSE_PYTHON||(process.platform==="win32"?"python":"python3")):join(root,"bin/workpulse-backend.exe"),args:source?["-m","workpulse"]:[],spawn,fetch,capability,
  maxRestarts:0,startupTimeout:120000,spawnOptions:{cwd:root,windowsHide:true,stdio:["ignore","pipe","pipe"],env:{...process.env,WORKPULSE_DATA_DIR:data,WORKPULSE_PARENT_PID:process.platform==="win32"?String(process.pid):"",WORKPULSE_AGENT_TOKEN:capability,PYTHONUNBUFFERED:"1"}},
  kill:child=>new Promise(resolve=>{if(!child?.pid)return resolve();if(process.platform!=="win32"){child.once("exit",resolve);child.kill();return;}execFile("taskkill",["/pid",String(child.pid),"/t","/f"],{windowsHide:true,timeout:5000},()=>resolve());}),
  log:message=>console.log(message),onState:state=>{if(state.status==="ready")signalReady(state.port);if(state.status==="failed")rejectReady(Error(state.message));}});
 const request=async(port,path,body)=>{
  const response=await fetch(`http://127.0.0.1:${port}${path}`,{method:body?"POST":"GET",headers:{"X-Agent-Token":capability,"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(10000)});
  assert(response.ok,`${path}: HTTP ${response.status}`);return response.json();
 };
 try{
  let ready=waitReady();service.start();let port=await ready;
  assert.equal((await request(port,"/auth/status")).registered,false);
  await request(port,"/auth/register",{full_name:"Startup Test",email:"startup@example.com",password:"StartupTestPassword123!",department:"CI"});
  ready=waitReady();await service.restart();port=await ready;
  assert.equal((await request(port,"/auth/status")).registered,true);
  const result=await request(port,"/auth/login",{email:"startup@example.com",password:"StartupTestPassword123!"});
  assert.equal(result.user.full_name,"Startup Test");
  console.log("Packaged service: authenticated readiness, registration, complete process-tree restart, existing database and login passed.");
 }finally{await service.stop();await rm(data,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});
