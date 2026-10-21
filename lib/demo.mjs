// Fictitious demonstration only. Never used as production statistics.
export function demoState(){
 const disc=[{id:'d0',name:'Mali',type:'c10_central',parent:null},{id:'d1',name:'Koulikoro',type:'c20_region',parent:'d0'},{id:'d2',name:'Kati',type:'c30_district',parent:'d1'},{id:'d3',name:'CSCOM de Kalabancoro',type:'c40_health_area',parent:'d2'},{id:'d4',name:'Zone Kalabancoro',type:'c50_supervision_area',parent:'d3'}];
 const dhis=[{id:'h0',name:'Mali',level:1,parent:null},{id:'h1',name:'Région de Koulikoro',level:2,parent:'h0'},{id:'h2',name:'District de Kati',level:3,parent:'h1'},{id:'h3',name:'Aire de Kalabancoro',level:4,parent:'h2'},{id:'h4',name:'CSCOM Kalabancoro',level:5,parent:'h3'}];
 const names=['N’Golobougou','Sébénikoro','Sanankoroba','Diatoula','Kouralé','Samaya','Farada'];
 names.forEach((name,i)=>disc.push({id:'d'+(i+5),name:'Site ASC de '+name,type:'c60_chw_site',parent:'d4'}));
 ['NGOLOBOUGOU','Site ASC de Sébénikoro','Site ASC de Sanankoroba','DIATOULA','Kouralé','Kourale','Site ASC de Bamabougou'].forEach((name,i)=>dhis.push({id:'h'+(i+5),name,level:6,parent:i===2?'h2':'h4'}));
 return {snapshot:{disc,dhis,updatedAt:null,dhisLevels:[{name:'National',level:1},{name:'Région',level:2},{name:'District',level:3},{name:'Aire',level:4},{name:'Formation sanitaire',level:5},{name:'Site ASC',level:6}],changes:[],firstSnapshot:true},mappings:[['d0','h0'],['d1','h1'],['d2','h2'],['d3','h4'],['d5','h5'],['d6','h6'],['d7','h7']].map(([discId,dhisId])=>({discId,dhisId})),levels:{c10_central:1,c20_region:2,c30_district:3,c40_health_area:5,c50_supervision_area:null,c60_chw_site:6},audit:[],namePlans:[]};
}
