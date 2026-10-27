<?php
/** Read-only CLI inventory. No file names, paths, contents or identifiers are exported. */
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
ini_set('display_errors','0');
try{
 require dirname(__DIR__).'/private/app.php';require dirname(__DIR__).'/private/collab/core.php';require dirname(__DIR__).'/private/collab/files.php';
 $root=cc_storage();$tracked=[];$report=['tracked'=>0,'bytes'=>0,'missing_or_corrupt'=>0,'invalid_metadata'=>0,'unreferenced'=>0];
 foreach(crm_query('SELECT storage_key,size_bytes,checksum FROM nd_cc_files')->fetchAll() as $r){$report['tracked']++;if(!preg_match('/^[a-f0-9]{64}$/D',$r['storage_key'])){$report['invalid_metadata']++;continue;}$tracked[$r['storage_key']]=true;
  try{cc_file_path($r);}catch(CrmFailure $e){$report['missing_or_corrupt']++;}}
 foreach(new DirectoryIterator($root) as $entry){if($entry->isDot()||$entry->getFilename()==='.quota.lock')continue;if($entry->isLink()||!$entry->isFile()){$report['invalid_metadata']++;continue;}$report['bytes']+=$entry->getSize();if(!isset($tracked[$entry->getFilename()]))$report['unreferenced']++;}
 echo json_encode($report),PHP_EOL;exit($report['missing_or_corrupt']||$report['invalid_metadata']||$report['unreferenced']?1:0);
}catch(Throwable $e){fwrite(STDERR,"Private storage inventory unavailable. No files changed.\n");exit(1);}
