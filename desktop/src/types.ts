export type State="productive"|"neutral"|"non_productive"|"idle"|"break";
export type Totals=Record<State,number>&{work:number;productivity:number};
export type User={id:number;full_name:string;email:string;department:string};
export type Live={status:"working"|"break"|"finished";state:State|"finished"|"private";started_at:string|null;break_seconds?:number;today?:Totals;reminder?:{id:string;message:string}|null;foreground?:{app_name:string;title:string};error?:string};
export type Day={date:string;totals:Totals;apps:{app_name:string;seconds:number;category:string}[];timeline:{start:string;end:string;state:State;app_name:string;title:string;seconds:number}[];hourly:Array<{hour:string}&Record<State,number>>};
export type Period={start:string;totals:Totals;days:Array<{date:string}&Totals>};
export type Settings={idle_threshold:number;poll_interval:number;auto_start:boolean;break_reminder_minutes:number;daily_goal_minutes:number;theme:"dark"|"light"};
export type Rule={id:number;pattern:string;category:"productive"|"neutral"|"non_productive";enabled:boolean};
declare global {interface Window{workpulse:{
 request:(path:string,method?:string,body?:unknown)=>Promise<any>;
 exportReport:(format:"csv"|"pdf",day:string,tz:number)=>Promise<string|null>;
 onLive:(fn:(d:Live)=>void)=>(()=>void);
 onReady:(fn:()=>void)=>(()=>void);
 showDashboard:()=>Promise<void>;
 shrinkWidget:(compact:boolean)=>Promise<void>;
 closeDashboard:()=>Promise<void>;
 setAutoStart:(enabled:boolean)=>Promise<void>;
 signOut:()=>Promise<void>;
 exportCustom:(format:"csv"|"pdf",start:string,end:string,tz:number)=>Promise<string|null>;
 importCalendar:()=>Promise<{imported:number}|null>;
 createBackup:(password:string)=>Promise<string|null>;
 restoreBackup:(password:string)=>Promise<{restart_required:boolean}|null>;
 checkUpdates:()=>Promise<{available:boolean;version?:string;message:string}>;
 getAutoUpdates:()=>Promise<{enabled:boolean;signed:boolean}>;
 setAutoUpdates:(enabled:boolean)=>Promise<{enabled:boolean;signed:boolean}>;
 showBrowserExtension:()=>Promise<boolean>;
}}}
export {};
