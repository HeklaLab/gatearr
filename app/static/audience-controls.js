/* Shared, deterministic audience transitions used by the builder and its live test. */
window.GatearrAudience={
 toggle(a,key,on,groups){const next={everyone:!!a.everyone,admins:!!a.admins,groups:[...(a.groups||[])]};if(key==='everyone')return {everyone:on,admins:on,groups:on?groups.map(g=>g.id):[]};if(next.everyone){next.everyone=false;next.admins=true;next.groups=groups.map(g=>g.id);}if(key==='admins')next.admins=on;else next.groups=on?[...new Set([...next.groups,key])]:next.groups.filter(id=>id!==key);return next;},
 matches(a,user){return !!(a.everyone||(a.admins&&user.admin)||(a.groups||[]).includes(user.group));}
};
