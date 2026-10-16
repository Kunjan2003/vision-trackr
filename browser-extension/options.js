(async()=>{
const $=id=>document.getElementById(id);
const saved=await chrome.storage.local.get(["port","token","enabled"]);
$("port").value=saved.port||"";$("token").value=saved.token||"";$("enabled").checked=Boolean(saved.enabled);
$("save").addEventListener("click",async()=>{
 const port=Number($("port").value),token=$("token").value.trim();
 if(!Number.isInteger(port)||port<1024||port>65535||token.length<32){$("status").textContent="Enter the port and pairing token shown in WorkPulse.";return;}
 await chrome.storage.local.set({port,token,enabled:$("enabled").checked});
 $("status").textContent="Pairing saved. Open a website to start domain-only tracking.";
});
})();
