"""Small native Superset layout builder shared by the new operational boards."""
import json

def board_class(db,Dashboard,Slice,owner,history,publish,reports,uid):
 class Board:
  def __init__(self,key,title,url):
   self.key=key;self.charts={}
   d=db.session.query(Dashboard).filter_by(uuid=uid('dashboard:'+key)).one_or_none()
   if d is None:d=Dashboard(uuid=uid('dashboard:'+key),slug=url);db.session.add(d)
   d.dashboard_title=title;d.owners=[owner];d.created_by=d.changed_by=owner;d.roles=list(history.roles);d.published=publish
   self.dash=d
   self.layout={'DASHBOARD_VERSION_KEY':'v2','ROOT_ID':dict(id='ROOT_ID',type='ROOT',children=['GRID_ID']),
    'GRID_ID':dict(id='GRID_ID',type='GRID',children=['TABS-THEME'],parents=['ROOT_ID']),
    'HEADER_ID':dict(id='HEADER_ID',type='HEADER',meta={'text':title}),
    'TABS-THEME':dict(id='TABS-THEME',type='TABS',children=[],parents=['ROOT_ID','GRID_ID'])}
  def chart(self,key,title,ds,viz='table',**settings):
   c=db.session.query(Slice).filter_by(uuid=uid('chart:'+self.key+':'+key)).one_or_none()
   if c is None:c=Slice(uuid=uid('chart:'+self.key+':'+key));db.session.add(c)
   c.slice_name=title;c.viz_type=viz;c.datasource_type='table';c.datasource_id=ds.id;c.owners=[owner];c.created_by=c.changed_by=owner
   p=dict(datasource=f'{ds.id}__table',viz_type=viz,time_range='previous calendar month',granularity_sqla='reported_month',
    adhoc_filters=[] if key in ['quality','available'] else [dict(expressionType='SQL',clause='WHERE',sqlExpression="mapping_status='Rattaché au répertoire courant'")],extra_form_data={},row_limit=100000)
   p.update(settings);c.params=json.dumps(p,ensure_ascii=False);c.query_context=None;db.session.flush();self.charts[key]=c;return c
  def tab(self,key,title):
   tid='TAB-'+self.key+'-'+key;self.layout['TABS-THEME']['children'].append(tid)
   self.layout[tid]=dict(id=tid,type='TAB',children=[],parents=['ROOT_ID','GRID_ID','TABS-THEME'],meta={'text':title});return tid
  def row(self,tid,key,items,height):
   rid=tid+'-ROW-'+key;parents=['ROOT_ID','GRID_ID','TABS-THEME',tid]
   self.layout[tid]['children'].append(rid);self.layout[rid]=dict(id=rid,type='ROW',children=[],parents=parents,meta={'background':'BACKGROUND_TRANSPARENT'})
   for name,width in items:
    c=self.charts[name];cid=tid+'-CHART-'+name;self.layout[rid]['children'].append(cid)
    self.layout[cid]=dict(id=cid,type='CHART',children=[],parents=parents+[rid],meta=dict(chartId=c.id,sliceName=c.slice_name,uuid=str(c.uuid),width=width,height=height))
  def note(self,tid,key,code,height):
   rid=tid+'-NOTE-'+key;mid=rid+'-MARKDOWN';parents=['ROOT_ID','GRID_ID','TABS-THEME',tid]
   self.layout[tid]['children'].append(rid);self.layout[rid]=dict(id=rid,type='ROW',children=[mid],parents=parents,meta={'background':'BACKGROUND_TRANSPARENT'})
   self.layout[mid]=dict(id=mid,type='MARKDOWN',children=[],parents=parents+[rid],meta={'code':code,'width':12,'height':height})
  def finish(self,filters):
   seen=set()
   def check(node):
    assert node not in seen,node;seen.add(node)
    for child in self.layout[node].get('children',[]):
     assert self.layout[child]['parents'][-1]==node;check(child)
   check('ROOT_ID')
   self.dash.slices=list(self.charts.values());self.dash.position_json=json.dumps(self.layout,ensure_ascii=False)
   self.dash.json_metadata=json.dumps(dict(native_filter_configuration=filters,cross_filters_enabled=False,refresh_frequency=0,
    expanded_slices={},timed_refresh_immune_slices=[],default_filters='{}',chart_configuration={},color_scheme='supersetColors'),ensure_ascii=False)
   self.dash.css='''div:has(> .dragdroppable-column){min-width:0}.dashboard-content{background:#f3f6fb}.dashboard-component-chart-holder{border:1px solid #dce6ef;border-radius:10px}
.dashboard-markdown h2,.dashboard-markdown h3{color:#153854}.dashboard-markdown{color:#334e68}
.dashboard-markdown a{font-weight:600}.dashboard-markdown table{width:100%}.dashboard-markdown th,.dashboard-markdown td{padding:9px 12px;border-bottom:1px solid #e1e8f0}'''
   db.session.flush();reports.append(dict(key=self.key,id=self.dash.id,slug=self.dash.slug,charts={k:c.id for k,c in self.charts.items()}))
 return Board
