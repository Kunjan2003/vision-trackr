export function duration(seconds:number){
 const s=Math.floor(Math.max(0,seconds||0));
 return [Math.floor(s/3600),Math.floor(s/60)%60,s%60].map(n=>String(n).padStart(2,"0")).join(":");
}
export const hours=(n:number)=>(Math.max(0,n||0)/3600).toFixed(1)+"h";
export const localDay=(date:Date=new Date())=>[date.getFullYear(),String(date.getMonth()+1).padStart(2,"0"),String(date.getDate()).padStart(2,"0")].join("-");
export const offset=()=>new Date().getTimezoneOffset();
export const display=(s:string)=>s.replace(/_/g," ").replace(/\b\w/g,x=>x.toUpperCase());
