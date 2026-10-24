"""Permanent Git-readable Actions evidence. Trusted main only, no execution of PR artifacts."""
import datetime,io,json,os,urllib.request,urllib.parse,zipfile
from pathlib import Path
from bridge import Gateway,publish,REPO,API

def deployment_report(gateway,producer):
 if producer.get('head_branch')!='main' or producer.get('head_repository',{}).get('full_name')!=REPO or producer.get('path')!='.github/workflows/deploy.yml':return None
 artifacts=gateway.call('GET','repos/'+REPO+'/actions/runs/'+str(producer['id'])+'/artifacts?per_page=100')
 selected=next((a for a in artifacts.get('data',{}).get('artifacts',[]) if a['name'].startswith('deployment-evidence-') and not a['expired']),None)
 if not selected:return None
 class Redirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,req,fp,code,msg,headers,newurl):
   result=super().redirect_request(req,fp,code,msg,headers,newurl)
   if result and urllib.parse.urlparse(req.full_url).netloc!=urllib.parse.urlparse(newurl).netloc:result.remove_header('Authorization')
   return result
 request=urllib.request.Request(API+'repos/'+REPO+'/actions/artifacts/'+str(selected['id'])+'/zip',headers={'Authorization':'Bearer '+gateway.token})
 with urllib.request.build_opener(Redirect()).open(request,timeout=45) as response:data=response.read(1048577)
 if len(data)>1048576:raise ValueError('oversized_evidence')
 with zipfile.ZipFile(io.BytesIO(data)) as archive:
  if archive.namelist()!=['deployment-report.json'] or archive.getinfo('deployment-report.json').file_size>1048576:raise ValueError('unexpected_evidence_file')
  value=json.loads(archive.read('deployment-report.json'))
 # No raw logs, bodies, configuration values or arbitrary files are exported.
 allowed=['mode','result','rollback_verified','revision','release_id','before','after','after_rollback','preexisting_failures','error','error_type','rollback_error','remote','rollback_remote','preflight','apply','finalize','unhealthy_release','approved_files_retained_without_new_regression']
 return {key:value[key] for key in allowed if key in value}

if __name__=='__main__':
 event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text());producer=event.get('workflow_run',{})
 report={'schema_version':1,'source_sha':os.environ['GITHUB_SHA'],'nonce':'workflow-'+str(producer.get('id')),'run_id':os.environ['GITHUB_RUN_ID'],
  'run_url':'https://github.com/'+REPO+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'production_touched':False,
  'producer':{k:producer.get(k) for k in ['id','name','head_sha','head_branch','event','status','conclusion','html_url','path']}}
 gateway=Gateway()
 try:report['inspection']=gateway.inspect();report['deployment_evidence']=deployment_report(gateway,producer)
 except Exception as error:report['evidence_error_type']=type(error).__name__
 publish(report)
