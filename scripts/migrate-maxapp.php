<?php
/** CLI-only migration 024. No automatic deploy, credentials or destructive force mode. */
declare(strict_types=1);
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
ini_set('display_errors','0');
$operation=$argv[1] ?? 'status';
if (!in_array($operation,['status','up','down'],true) || count($argv)>2) {
    fwrite(STDERR,"Usage: php scripts/migrate-maxapp.php [status|up|down]\n"); exit(2);
}
$pdo=null;$locked=false;$tablesLocked=false;$exitCode=0;
try {
    $config=require dirname(__DIR__).'/private/config.php';
    if (!is_array($config)) throw new RuntimeException('invalid_configuration');
    $pdo=new PDO('mysql:host='.$config['db_host'].';port='.($config['db_port']??3306).';dbname='.$config['db_name'].';charset=utf8mb4',
        $config['db_user'],$config['db_password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_EMULATE_PREPARES=>false,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);
    $pdo->exec("SET time_zone='+00:00'");
    // ENUM/unsigned validation requires strict mode; do not change a host-wide setting.
    $mode=$pdo->query('SELECT @@SESSION.sql_mode')->fetchColumn();
    if (!preg_match('/\bSTRICT_(TRANS_TABLES|ALL_TABLES)\b/',$mode)){$pdo->exec('SET SESSION sql_mode='.$pdo->quote(($mode!==''?$mode.',':'').'STRICT_TRANS_TABLES'));$mode=$pdo->query('SELECT @@SESSION.sql_mode')->fetchColumn();}
    if (!preg_match('/\bSTRICT_(TRANS_TABLES|ALL_TABLES)\b/',$mode)) throw new RuntimeException('strict_sql_mode_required');
    $version='024_max_identity';$directory=dirname(__DIR__).'/database/migrations/'.$version;
    $up=file_get_contents($directory.'/up.sql');$down=file_get_contents($directory.'/down.sql');
    if ($up===false || $down===false) throw new RuntimeException('migration_files_missing');
    // This version contains only simple CREATE/DROP statements, no routines/DELIMITER/quoted semicolons.
    $split=static function(string $sql):array {
        $sql=preg_replace('/^--[^\n]*$/m','',$sql);
        return array_values(array_filter(array_map('trim',explode(';',$sql))));
    };
    preg_match_all('/CREATE TABLE (nd_[a-z_]+)\s*\(/',$up,$matches);$tables=$matches[1];
    if (count($tables)!==4 || count($split($up))!==4 || count($split($down))!==4) throw new RuntimeException('invalid_migration_manifest');
    $exists=static function(string $table) use ($pdo):bool {
        $q=$pdo->prepare('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=?');$q->execute([$table]);return (bool)$q->fetchColumn();
    };
    $lockName='nd_migrate_'.substr(hash('sha256',$config['db_name']),0,40);
    $q=$pdo->prepare('SELECT GET_LOCK(?,0)');$q->execute([$lockName]);
    if ((int)$q->fetchColumn()!==1) throw new RuntimeException('migration_busy');
    $locked=true;
    $journal=$exists('nd_schema_migrations');
    $row=false;
    if ($journal) {$q=$pdo->prepare('SELECT * FROM nd_schema_migrations WHERE version=?');$q->execute([$version]);$row=$q->fetch();}
    if ($operation==='status') {
        echo json_encode(['version'=>$version,'state'=>$row['state']??'not_applied','completed_steps'=>(int)($row['completed_steps']??0)]),PHP_EOL;
    } else {
        if ($row && ($row['up_checksum']!==hash('sha256',$up) || $row['down_checksum']!==hash('sha256',$down))) throw new RuntimeException('migration_checksum_mismatch');
        if ($journal) {
            $q=$pdo->prepare('SELECT 1 FROM nd_schema_migrations WHERE version>? LIMIT 1');$q->execute([$version]);
            if ($q->fetchColumn()!==false) throw new RuntimeException('newer_migration_applied');
        }
        if ($operation==='up') {
            if (!$journal) throw new RuntimeException('migration_023_required');
            $dependency=$pdo->query("SELECT state,up_checksum,down_checksum FROM nd_schema_migrations WHERE version='023_publication'")->fetch();
            $base=dirname(__DIR__).'/database/migrations/023_publication/';
            if (!$dependency || $dependency['state']!=='applied'
                || $dependency['up_checksum']!==hash_file('sha256',$base.'up.sql')
                || $dependency['down_checksum']!==hash_file('sha256',$base.'down.sql')) throw new RuntimeException('migration_023_required');
            if ($row && $row['state']==='applied') {echo "024 already applied\n";}
            else {
                if ($row) throw new RuntimeException('partial_migration_requires_empty_rollback');
                // Never silently adopt tables from an unmanaged or partial SQL import.
                foreach ($tables as $table) if ($exists($table)) throw new RuntimeException('unmanaged_table_collision');
                foreach (['nd_admin'=>'id,password_hash','nd_leads'=>'id,name,contact,service,idea,status,notes,next_step,created,version,request_key,request_hash,consent,consent_at,policy_version,policy_hash','nd_sessions'=>'token,csrf,expires','nd_limits'=>'bucket,attempts,expires'] as $table=>$columns) {
                    $pdo->query('SELECT '.$columns.' FROM '.$table.' LIMIT 0');
                    $q=$pdo->prepare('SELECT engine FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=?');$q->execute([$table]);
                    if ($q->fetchColumn()!=='InnoDB') throw new RuntimeException('innodb_baseline_required');
                }
                $pdo->exec("CREATE TABLE IF NOT EXISTS nd_schema_migrations (version VARCHAR(64) PRIMARY KEY,up_checksum CHAR(64) NOT NULL,down_checksum CHAR(64) NOT NULL,state ENUM('applying','applied','rolling_back') NOT NULL,completed_steps INT UNSIGNED NOT NULL DEFAULT 0,applied_at DATETIME NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
                $pdo->prepare("INSERT INTO nd_schema_migrations(version,up_checksum,down_checksum,state) VALUES (?,?,?,'applying')")->execute([$version,hash('sha256',$up),hash('sha256',$down)]);
                foreach ($split($up) as $step=>$sql) {
                    $pdo->exec($sql);
                    $pdo->prepare('UPDATE nd_schema_migrations SET completed_steps=? WHERE version=?')->execute([$step+1,$version]);
                }
                $pdo->prepare("UPDATE nd_schema_migrations SET state='applied',applied_at=UTC_TIMESTAMP() WHERE version=?")->execute([$version]);
                echo "024 applied\n";
            }
        } else {
            if (!$row) {
                foreach ($tables as $table) if ($exists($table)) throw new RuntimeException('unmanaged_table_collision');
                echo "024 not applied\n";
            } else {
                $existing=array_values(array_filter($tables,$exists));
                $locks=array_map(static fn($table)=>'`'.$table.'` WRITE',$existing);
                $locks[]='nd_deals READ';$locks[]='nd_tasks READ';$locks[]='nd_cost_rates READ';$locks[]='nd_quotations READ';$locks[]='nd_ai_tasks READ';$locks[]='nd_cc_files READ';$locks[]='nd_ai_artifacts READ';$locks[]='nd_cc_revisions READ';$locks[]='nd_orders READ';$locks[]='nd_customers READ';$locks[]='nd_customer_accounts READ';$locks[]='nd_projects READ';$locks[]='nd_project_stages READ';$locks[]='nd_schema_migrations WRITE';$locks[]='nd_admin READ';$locks[]='nd_leads READ';
                // Prevent concurrent new-model inserts between the empty check and DROP.
                $pdo->exec('LOCK TABLES '.implode(',',$locks));$tablesLocked=true;
                foreach ($existing as $table) if ($pdo->query('SELECT 1 FROM `'.$table.'` LIMIT 1')->fetchColumn()!==false) throw new RuntimeException('rollback_refused_nonempty_auth');
                $pdo->prepare("UPDATE nd_schema_migrations SET state='rolling_back' WHERE version=?")->execute([$version]);
                foreach ($split($down) as $sql) {
                    preg_match('/^DROP TABLE IF EXISTS (nd_[a-z_]+)$/',$sql,$drop);
                    if (!$drop) throw new RuntimeException('invalid_migration_manifest');
                    // MySQL 5.7 disallows DROP of a non-locked missing table even with IF EXISTS.
                    if (in_array($drop[1],$existing,true)) $pdo->exec($sql);
                }
                $pdo->prepare('DELETE FROM nd_schema_migrations WHERE version=?')->execute([$version]);
                echo "024 rolled back; legacy records preserved\n";
            }
        }
    }
} catch (Throwable $e) {
    // No exception messages from PDO/config: these may expose SQL, paths or credentials.
    $code=$e instanceof RuntimeException && !($e instanceof PDOException) ? $e->getMessage() : 'migration_failed';
    $safe=['invalid_configuration','strict_sql_mode_required','migration_files_missing','invalid_migration_manifest','migration_busy','migration_checksum_mismatch','partial_migration_requires_empty_rollback','unmanaged_table_collision','innodb_baseline_required','rollback_refused_nonempty_auth','newer_migration_applied','migration_023_required'];
    if (!in_array($code,$safe,true)) $code='migration_failed';
    fwrite(STDERR,json_encode(['error'=>$code,'type'=>get_class($e),'sqlstate'=>$e instanceof PDOException?(string)$e->getCode():null]).PHP_EOL);
    $exitCode=1;
} finally {
    try {
        if ($tablesLocked && $pdo) $pdo->exec('UNLOCK TABLES');
        if ($locked && $pdo) {$q=$pdo->prepare('SELECT RELEASE_LOCK(?)');$q->execute([$lockName]);}
    } catch (Throwable $cleanupError) {
        fwrite(STDERR,"{\"error\":\"migration_lock_cleanup_failed\"}\n");$exitCode=1;
    }
}

exit($exitCode);
