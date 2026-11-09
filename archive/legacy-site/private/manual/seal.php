<?php
declare(strict_types=1);
function mh_managed_file(array $a,array $f,bool $mutation):bool{
 if(crm_query("SELECT state FROM nd_schema_migrations WHERE version='012_manual_handoff'")->fetchColumn()!=='applied')return false;
 $r=crm_query('SELECT state,approved_by,approved_checksum,checksum FROM nd_manual_results WHERE file_id=?',[$f['id']])->fetch();if(!$r)return false;
 if($mutation)crm_fail(409,'Ручной результат нельзя менять через общий редактор файлов. Нужна новая редакция задания.');
 if($a['type']==='customer'&&($r['state']!=='DELIVERED'||!$r['approved_by']||!is_string($r['approved_checksum'])||!hash_equals($r['checksum'],$r['approved_checksum'])))crm_fail(404,'Запись не найдена.');return true;
}
