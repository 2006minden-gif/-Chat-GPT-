<?php
declare(strict_types=1);
interface AiProviderAdapter {
 public function createTask(array $request):array;
 public function executeAgent(array $request):array;
 public function retrieveTask(string $id):array;
 public function cancelTask(string $id):bool;
 public function validateResponse(array $response):array;
 public function estimateCost(int $tokens):?int;
 public function normalizeProviderError(Throwable $error):string;
}
final class AiProviderFailure extends RuntimeException{public function __construct(public string $category){parent::__construct('AI provider unavailable');}}
function ai_provider_status():string{
 $p=config()['ai_provider']??[];if(($p['enabled']??false)!==true)return 'disabled';
 if(($p['type']??'')!=='mock_http')return empty($p['secret_reference'])?'not_configured':'live_unavailable';
 $u=parse_url($p['endpoint']??'');if((config()['ai_test_mode']??false)!==true||!in_array(parse_url(config()['app_url'],PHP_URL_HOST),['127.0.0.1','localhost','::1'],true)||($u['scheme']??'')!=='http'||($u['host']??'')!=='127.0.0.1'||isset($u['user'])||isset($u['pass'])||isset($u['query'])||isset($u['fragment'])||!in_array($u['path']??'',['','/'],true))return 'live_unavailable';
 $c=config();$day=crm_query('SELECT * FROM nd_ai_budgets WHERE bucket=?',['global:day:'.gmdate('Y-m-d')])->fetch();$month=crm_query('SELECT * FROM nd_ai_budgets WHERE bucket=?',['global:month:'.gmdate('Y-m')])->fetch();if(($day&&((int)$day['calls']>=min(100,max(1,(int)($c['ai_daily_requests']??20)))||(int)$day['tokens']>=min(500000,max(4096,(int)($c['ai_daily_tokens']??50000)))||(int)$day['estimated_micro']>=min(10000000,max(1,(int)($c['ai_daily_estimated_micro']??1000000)))))||($month&&(int)$month['calls']>=min(1000,max(1,(int)($c['ai_monthly_requests']??100)))))return 'budget_exhausted';
 $r=crm_query('SELECT * FROM nd_ai_provider_state WHERE provider_id=1')->fetch();if($r&&$r['blocked_until']&&$r['blocked_until']>gmdate('Y-m-d H:i:s'))return $r['last_error']==='rate_limited'?'rate_limited':'temporarily_unavailable';return 'available_mock';
}
function ai_provider():AiProviderAdapter{$s=ai_provider_status();if($s!=='available_mock')throw new AiProviderFailure($s==='budget_exhausted'?'budget_exhausted':($s==='rate_limited'?'rate_limited':'provider_unavailable'));return new MockHttpAiAdapter();}
/** Explicit test-only transport. No invented Nodul or live API endpoints. */
final class MockHttpAiAdapter implements AiProviderAdapter {
 public function createTask(array $request):array{return $this->executeAgent($request);}
 public function executeAgent(array $request):array{
  $p=config()['ai_provider'];$timeout=max(1,min(15,(int)($p['timeout_seconds']??10)));$ctx=stream_context_create(['http'=>['method'=>'POST','header'=>"Content-Type: application/json\r\nAccept: application/json\r\nX-Correlation-ID: ".$request['correlation_id'],'content'=>ai_json($request),'timeout'=>$timeout,'follow_location'=>0,'ignore_errors'=>true]]);
  $fp=@fopen(rtrim($p['endpoint'],'/').'/','rb',false,$ctx);if(!$fp)throw new AiProviderFailure('timeout');$raw=stream_get_contents($fp,65537);$meta=stream_get_meta_data($fp);fclose($fp);if($meta['timed_out']??false)throw new AiProviderFailure('timeout');$status=0;$json=false;foreach($meta['wrapper_data']??[] as $h){if(preg_match('~^HTTP/\S+ (\d+)~',$h,$m))$status=(int)$m[1];if(preg_match('~^Content-Type:\s*application/json(?:;|$)~i',$h))$json=true;}
  if($status===429)throw new AiProviderFailure('rate_limited');if($status<200||$status>=300)throw new AiProviderFailure('provider_unavailable');if(!$json||!is_string($raw)||strlen($raw)>65536)throw new AiProviderFailure('invalid_output');$r=json_decode($raw,true);if(!is_array($r)||json_last_error()!==JSON_ERROR_NONE)throw new AiProviderFailure('invalid_output');return $this->validateResponse($r);
 }
 public function validateResponse(array $r):array{
  if(($r['status']??'')==='refused')throw new AiProviderFailure('model_refusal');if(($r['status']??'')!=='completed'||!is_string($r['output']??null)||array_diff(array_keys($r),['status','output','usage','model']))throw new AiProviderFailure('invalid_output');
  if(isset($r['usage'])){if(!is_array($r['usage'])||array_diff(array_keys($r['usage']),['input_tokens','output_tokens','actual_micro']))throw new AiProviderFailure('invalid_output');foreach($r['usage'] as $v)if($v!==null&&(!is_int($v)||$v<0||$v>1000000000))throw new AiProviderFailure('invalid_output');}
  if(isset($r['model'])&&(!is_string($r['model'])||strlen($r['model'])>64))throw new AiProviderFailure('invalid_output');return $r;
 }
 public function retrieveTask(string $id):array{throw new AiProviderFailure('async_unsupported');}
 public function cancelTask(string $id):bool{return false;}
 public function estimateCost(int $tokens):?int{$rate=config()['ai_provider']['estimated_micro_per_1000_tokens']??null;if(!is_int($rate)||$rate<0||$rate>1000000)return null;return intdiv($tokens*$rate+999,1000);}
 public function normalizeProviderError(Throwable $error):string{return $error instanceof AiProviderFailure?$error->category:'provider_unavailable';}
}
