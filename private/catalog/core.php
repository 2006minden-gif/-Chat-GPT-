<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/ai/routes.php';require_once dirname(__DIR__).'/crm/write.php';require_once __DIR__.'/contracts.php';
function cat_installed():bool{return crm_query("SELECT state FROM nd_schema_migrations WHERE version='013_service_ordering'")->fetchColumn()==='applied';}
function cat_gate(bool $requests=false):void{
 if((config()['catalog_enabled']??false)!==true||!cat_installed())crm_fail(503,'Каталог услуг пока не открыт.');
 if($requests&&((config()['catalog_requests_enabled']??false)!==true||(config()['catalog_privacy_approved']??false)!==true||!privacy_settings()['enabled']))crm_fail(503,'Приём брифов закрыт до настройки и одобрения документов.');
}
function cat_requests_open():bool{require_once dirname(__DIR__).'/customer-auth.php';return (config()['catalog_requests_enabled']??false)===true&&(config()['catalog_privacy_approved']??false)===true&&(config()['crm_operations_enabled']??false)===true&&(config()['client_collaboration_enabled']??false)===true&&ca_enabled();}
function cat_actor(bool $customer,bool $write):array{$a=cc_actor($customer,$write);cat_gate($customer);return $a;}
function cat_record(string $type,int $id,bool $lock=false):array{
 $table=match($type){'service'=>'nd_catalog_services','template'=>'nd_catalog_templates','request'=>'nd_catalog_requests','offer'=>'nd_catalog_offers',default=>throw new LogicException('unsupported_catalog_entity')};$r=crm_query('SELECT * FROM '.$table.' WHERE id=?'.($lock?' FOR UPDATE':''),[$id])->fetch();if(!$r)crm_fail(404,'Запись не найдена.');return $r;
}
function cat_version(string $kind,int $id):array{
 $table=$kind==='template'?'nd_catalog_template_versions':'nd_catalog_service_versions';$v=crm_query('SELECT * FROM '.$table.' WHERE id=?',[$id])->fetch();if(!$v)crm_fail(404,'Редакция не найдена.');if(!hash_equals($v['checksum'],hash('sha256',$v['body'])))crm_fail(409,'Редакция не прошла проверку целостности.');$v['data']=json_decode($v['body'],true,512,JSON_THROW_ON_ERROR);return $v;
}
function cat_live(int $version):array{
 $v=cat_version('service',$version);$s=cat_record('service',(int)$v['service_id']);$t=cat_version('template',(int)$v['template_version_id']);$parent=cat_record('template',(int)$t['template_id']);if($s['state']!=='PUBLISHED'||(int)$s['published_revision']!==(int)$v['revision_number']||$parent['state']!=='PUBLISHED'||$t['published_at']===null)crm_fail(409,'Услуга или анкета обновлены либо сняты с публикации. Выберите актуальную услугу.');return ['service'=>$s,'version'=>$v,'template'=>$t];
}
function cat_request(array $a,int $id,bool $lock=false):array{
 $r=cat_record('request',$id,$lock);if($a['type']==='customer'&&(int)$r['customer_id']!==(int)$a['customer_id'])crm_fail(404,'Запись не найдена.');cc_project($a,(int)$r['project_id']);return $r;
}
function cat_package(array $v,string $key):array{foreach($v['data']['packages'] as $p)if($p['id']===$key)return $p;crm_fail(422,'Выберите существующий пакет услуги.');}
function cat_consent(array $d):array{$p=privacy_settings();if(!$p['enabled']||($d['consent']??false)!==true)crm_fail(422,'Нужно отдельное согласие на обработку брифа.');if(($d['policy_version']??null)!==$p['version'])crm_fail(409,'Документы обновились. Прочитайте их и подтвердите согласие заново.');return $p;}
function cat_brief(array $r):array{$b=crm_query('SELECT * FROM nd_catalog_briefs WHERE request_id=? AND revision_number=?',[$r['id'],$r['head_revision']])->fetch();if(!$b)crm_fail(409,'Бриф ещё не отправлен.');if(!hash_equals($b['checksum'],hash('sha256',$b['structured_json'])))crm_fail(409,'Бриф не прошёл проверку целостности.');return $b;}
function cat_files(array $a,int $project,mixed $ids):array{if(!is_array($ids)||!array_is_list($ids))crm_fail(422,'Проверьте список вложений.');$out=[];foreach(cc_files_for($a,$project,$ids) as $f)$out[]=['id'=>(int)$f['id'],'name'=>$f['display_name'],'checksum'=>$f['checksum']];return $out;}
function cat_event(array $a,array $r,string $action):void{cc_event($a,(int)$r['project_id'],'catalog_'.$action);}
