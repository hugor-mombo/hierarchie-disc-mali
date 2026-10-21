export const ROLES=['viewer','editor','reviewer','admin'];
export function can(role,permission){return ({read:ROLES,edit:['editor','reviewer','admin'],review:['reviewer','admin'],execute:['admin'],users:['admin']})[permission]?.includes(role)||false;}
