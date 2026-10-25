<?php
declare(strict_types=1);
function cc_threads(array $a):array{
 $where=$a['type']==='customer'?' WHERE p.customer_id=? AND c.status=\'active\'':'';$p=$a['type']==='customer'?[$a['customer_id']]:[];
 $search=$_GET['search']??'';if(!is_string($search)||mb_strlen($search)>100)crm_fail(422,'Слишком длинный поиск.');
 if($search!==''){$where.=($where?' AND ':' WHERE ').'(p.title LIKE ? OR c.name LIKE ?)';array_push($p,'%'.$search.'%','%'.$search.'%');}
 $project=$_GET['project_id']??'';if($project!==''){if(!is_string($project)||!ctype_digit($project))crm_fail(422,'Выберите проект.');$where.=($where?' AND ':' WHERE ').'p.id=?';$p[]=$project;}
 $rows=crm_query('SELECT p.id,p.title,p.customer_id,p.archived_at,c.name AS customer_name FROM nd_projects p JOIN nd_customers c ON c.id=p.customer_id'.$where.' ORDER BY p.id DESC LIMIT 25 OFFSET '.((cc_page()-1)*25),$p)->fetchAll();
 foreach($rows as &$r){$last=crm_query('SELECT id,body,created_at FROM nd_cc_messages WHERE project_id=? ORDER BY id DESC LIMIT 1',[$r['id']])->fetch();$r['last_message']=$last?mb_substr($last['body'],0,100):'';$r['last_at']=$last['created_at']??null;
 $read=crm_query('SELECT last_message_id FROM nd_cc_reads WHERE project_id=? AND actor_type=? AND actor_id=?',[$r['id'],$a['type'],$a['id']])->fetchColumn()?:0;
 $r['unread']=(int)crm_query('SELECT COUNT(*) FROM nd_cc_messages WHERE project_id=? AND id>? AND NOT(actor_type=? AND actor_id=?)',[$r['id'],$read,$a['type'],$a['id']])->fetchColumn();}unset($r);
 return ['ok'=>true,'items'=>$rows,'page'=>cc_page(),'page_size'=>25];
}
function cc_messages(array $a,int $project):array{
 cc_project($a,$project);$rows=crm_query('SELECT id,body,actor_type,created_at FROM nd_cc_messages WHERE project_id=? ORDER BY id DESC LIMIT 30 OFFSET '.((cc_page()-1)*30),[$project])->fetchAll();
 foreach($rows as &$r){$files=crm_query('SELECT f.* FROM nd_cc_files f JOIN nd_cc_message_files mf ON mf.file_id=f.id WHERE mf.message_id=?'.($a['type']==='customer'?" AND f.visibility='customer' AND f.archived_at IS NULL":''),[$r['id']])->fetchAll();$r['files']=array_map('cc_public_file',$files);$r['sender']=$r['actor_type']==='owner'?'НейроДело':'Клиент';}unset($r);
 return ['ok'=>true,'items'=>array_reverse($rows),'page'=>cc_page(),'page_size'=>30];
}
function cc_send(array $a,int $project,array $d):array{
 return cc_mutation($a,'messages/'.$project,$d,function()use($a,$project,$d){cc_project($a,$project,true,true);$text=cc_text($d,'body',5000);$ids=$d['file_ids']??[];if(!is_array($ids))crm_fail(422,'Проверьте вложения.');$files=cc_files_for($a,$project,$ids,true);
 crm_query('INSERT INTO nd_cc_messages(project_id,actor_type,actor_id,body) VALUES (?,?,?,?)',[$project,$a['type'],$a['id'],$text]);$id=(int)db()->lastInsertId();foreach($files as $f)crm_query('INSERT INTO nd_cc_message_files VALUES (?,?)',[$id,$f['id']]);cc_event($a,$project,'message_sent');return ['ok'=>true,'id'=>$id];});
}
function cc_read(array $a,int $project,array $d):array{
 return crm_atomic(function()use($a,$project,$d){cc_project($a,$project);$last=cc_id($d['last_message_id']??null);if(!crm_query('SELECT id FROM nd_cc_messages WHERE project_id=? AND id=?',[$project,$last])->fetchColumn())crm_fail(404,'Запись не найдена.');
 crm_query('INSERT INTO nd_cc_reads(project_id,actor_type,actor_id,last_message_id) VALUES (?,?,?,?) ON DUPLICATE KEY UPDATE last_message_id=GREATEST(last_message_id,VALUES(last_message_id))',[$project,$a['type'],$a['id'],$last]);return ['ok'=>true];});
}
