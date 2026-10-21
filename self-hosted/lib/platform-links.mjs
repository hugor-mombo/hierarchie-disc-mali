export function discContactURL(base,id){
  if(!base||!id)return null;
  try{const url=new URL(base);if(!['http:','https:'].includes(url.protocol)||url.username||url.password)return null;url.search='';url.hash='';return url.toString().replace(/\/$/,'')+'/#/contacts/'+encodeURIComponent(id);}catch{return null;}
}
