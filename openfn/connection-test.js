// OpenFn HTTP adaptor. Only reads the registry and reports a TEST event.
// Never reads indicators and never connects to DHIS2.
fn(async state => {
  const config=state.configuration;
  if(!config?.registryURL||!config.mappingToken||!config.auditToken)throw Error('REGISTRY_CREDENTIAL_REQUIRED');
  const response=await get(config.registryURL+'/api/interop/mappings',{headers:{Authorization:'Bearer '+config.mappingToken}})(state);
  const manifest=response.data;
  if(!manifest?.version||!manifest.mappings?.length)throw Error('EMPTY_MAPPING_MANIFEST');
  const site=manifest.mappings[0],runId='connection-test-'+Date.now();
  await post(config.registryURL+'/api/interop/events',{
    headers:{Authorization:'Bearer '+config.auditToken,'Content-Type':'application/json'},
    body:{eventId:runId+'-site-1',runId,workflow:'registry-connection-test',mappingVersion:manifest.version,
      period:new Date().toISOString().slice(0,7).replace('-',''),dataset:'CONNECTION_TEST',
      chw_site_id:site.chw_site_id,dhis2_org_unit:site.dhis2_org_unit,
      mode:'test',status:'dry_run',counts:{prepared:0,accepted:0,rejected:0}}
  })(state);
  return {...state,data:{mode:'test',registryConnected:true,mappingVersion:manifest.version,sitesAvailable:manifest.mappings.length,auditReceived:true}};
});
