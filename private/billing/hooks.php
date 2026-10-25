<?php
declare(strict_types=1);
require_once __DIR__.'/core.php';require_once __DIR__.'/notifications.php';
function bill_hook_event(string $key,string $template,string $entity,int $id,int $customer,bool $essential=true):void{
 bill_gate();bill_emit($key,$template,$entity,$id,$customer,$essential);
}
function bill_collaboration_event(int $event,int $project,string $action,int $customer,array $context=[]):void{
 if($action==='message_sent')bill_hook_event('activity:'.$event,'new_message','projects',$project,$customer,false);
 elseif($action==='submitted')bill_hook_event('activity:'.$event,in_array($context['document_kind']??'',['deliverable','final','milestone'],true)?'new_deliverable':'awaiting_approval','projects',$project,$customer);
 elseif($action==='decision_recorded')bill_hook_event('activity:'.$event,($context['decision']??'')==='changes_requested'?'changes_requested':'document_approved','projects',$project,$customer);
}
