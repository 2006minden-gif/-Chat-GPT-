<?php
declare(strict_types=1);
/** Generated package access is enforced even when production scheduling is later disabled. */
function prod_managed_file(array $a,array $file,bool $mutation=false):void{
 if($file['mime']!=='application/json')return;
 if($mutation)crm_fail(409,'Производственный пакет нельзя менять через общий редактор файлов. Используйте точное согласование результата.');
 $p=crm_query("SELECT p.*,d.checksum AS approved_hash FROM nd_prod_packages p LEFT JOIN nd_prod_decisions d ON d.entity='package' AND d.record_id=p.id AND d.decision='approved' WHERE p.file_id=?",[$file['id']])->fetch();
 if(!$p)crm_fail(404,'Запись не найдена.');if($a['type']==='customer'&&($p['state']!=='DELIVERED'||!is_string($p['approved_hash'])||!hash_equals($p['approved_hash'],$file['checksum'])))crm_fail(404,'Запись не найдена.');
}
