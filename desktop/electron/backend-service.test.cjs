const test=require("node:test");
const assert=require("node:assert/strict");
const {EventEmitter}=require("node:events");
const {BackendService}=require("./backend-service.cjs");
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function fixture(overrides={}){
 const children=[],states=[],logs=[],killed=[];
 const service=new BackendService({binary:"test-backend",args:[],spawnOptions:{},capability:"test-launch-capability",
  spawn:()=>{const child=new EventEmitter();child.stdout=new EventEmitter();child.stderr=new EventEmitter();child.pid=100+children.length;children.push(child);return child;},
  fetch:async(url,options)=>{assert.equal(options.headers["X-Agent-Token"],"test-launch-capability");return {ok:true,json:async()=>({ok:true})};},
  kill:async child=>{killed.push(child);},log:value=>logs.push(value),onState:state=>states.push(state),
  restartDelay:5,probeDelay:5,startupTimeout:1000,...overrides});
 return {service,children,states,logs,killed};
}
test("slow startup remains pending beyond the old renderer timeout and fragmented CRLF port becomes healthy",async t=>{
 const f=fixture({startupTimeout:undefined});t.after(()=>f.service.stop());f.service.start();
 assert.equal(f.service.timer._idleTimeout,120000);assert.equal(f.service.state.status,"starting");
 f.children[0].stdout.emit("data","WORKPULSE_PO");f.children[0].stdout.emit("data","RT=43123\r\n");await delay(5);
 assert.deepEqual(f.service.state,{status:"ready",message:"Tracking service is ready.",port:43123});
 assert.equal(f.service.timer,null);
});
test("spawn failure is visible and retry launches a new process",async t=>{
 const f=fixture({maxRestarts:0});t.after(()=>f.service.stop());f.service.start();
 f.children[0].emit("error",Error("spawn ENOENT"));await delay(5);
 assert.equal(f.service.state.status,"failed");assert.match(f.service.state.message,/ENOENT/);
 await f.service.restart();assert.equal(f.children.length,2);
 f.children[1].stdout.emit("data","WORKPULSE_PORT=43124\n");await delay(5);assert.equal(f.service.state.status,"ready");
});
test("service exit records stderr and automatic retries are bounded",async t=>{
 const f=fixture({maxRestarts:1});t.after(()=>f.service.stop());f.service.start();
 f.children[0].stderr.emit("data","RuntimeError: another agent is running\n");f.children[0].emit("exit",2);await delay(15);
 assert.equal(f.children.length,2);
 f.children[1].stderr.emit("data","migration failed\n");f.children[1].emit("exit",1);await delay(15);
 assert.equal(f.service.state.status,"failed");assert.match(f.service.state.message,/migration failed/);assert.equal(f.children.length,2);
 assert(f.logs.some(line=>line.includes("another agent")));
});
test("port marker alone is insufficient; authenticated health must succeed",async t=>{
 let healthy=false;const f=fixture({fetch:async()=>({ok:healthy,json:async()=>({ok:healthy})})});t.after(()=>f.service.stop());f.service.start();
 f.children[0].stdout.emit("data","WORKPULSE_PORT=43210\n");await delay(10);assert.equal(f.service.state.status,"starting");
 healthy=true;await delay(20);assert.equal(f.service.state.status,"ready");
});
test("startup deadline stops the child and exposes a terminal error",async t=>{
 const f=fixture({startupTimeout:10,maxRestarts:0});t.after(()=>f.service.stop());f.service.start();await delay(25);
 assert.equal(f.service.state.status,"failed");assert.equal(f.killed.length,1);
});
test("stale health completion and child exits cannot override a newer launch",async t=>{
 let resolveFirst;let calls=0;const f=fixture({fetch:async()=>{calls++;if(calls===1)return new Promise(resolve=>resolveFirst=resolve);return {ok:true,json:async()=>({ok:true})};}});t.after(()=>f.service.stop());f.service.start();
 const old=f.children[0];old.stdout.emit("data","WORKPULSE_PORT=43123\n");await delay(5);
 await f.service.restart();f.children[1].stdout.emit("data","WORKPULSE_PORT=43124\n");await delay(5);
 resolveFirst({ok:true,json:async()=>({ok:true})});old.emit("exit",1);await delay(5);
 assert.equal(f.service.state.port,43124);assert.equal(f.service.state.status,"ready");
});
test("shutdown cancels restart timers and releases its own child",async()=>{
 const f=fixture();f.service.start();const child=f.children[0];await f.service.stop();child.emit("exit",0);await delay(15);
 assert.equal(f.children.length,1);assert.equal(f.killed[0],child);assert.equal(f.service.child,null);
});
