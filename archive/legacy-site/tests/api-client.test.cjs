const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function client(reply) {
 const context = {window:{},fetch:async()=>reply,AbortController,setTimeout,clearTimeout};
 vm.runInNewContext(fs.readFileSync('public/api-client.js','utf8'), context);
 return context.window.NeuroAPI;
}
const valid = d => d.ok === true && Number.isSafeInteger(d.lead_id) && d.lead_id > 0;
const response = (status,type,data) => ({status,ok:status>=200&&status<300,headers:{get:()=>type},json:async()=>{if(data==='MALFORMED')throw new SyntaxError('secret');return data;}});
for (const [name,r] of [
 ['HTML 200',response(200,'text/html','html')],['HTML 201',response(201,'text/html','html')],
 ['malformed JSON',response(201,'application/json','MALFORMED')],['unrelated JSON',response(201,'application/json',{hello:true})],
 ['false result',response(201,'application/json',{ok:false,lead_id:1})],['missing id',response(201,'application/json',{ok:true})],
 ['wrong status',response(200,'application/json',{ok:true,lead_id:1})],['server failure',response(503,'application/json',{ok:true,lead_id:1})]
]) test('reject '+name,async()=>assert.rejects(client(r).request('leads',{},valid,201)));
test('accept explicit persisted lead',async()=>assert.equal((await client(response(201,'application/json; charset=utf-8',{ok:true,lead_id:3})).request('leads',{},valid,201)).lead_id,3));
test('hide internal server details',async()=>{
 await assert.rejects(client(response(503,'application/json',{detail:'SQL password=secret /private/config.php'})).request('leads'),e=>!e.message.includes('secret')&&!e.message.includes('SQL')&&e.status===503);
});
test('timeout becomes Russian retry error',async()=>{
 const context={window:{},AbortController,setTimeout,clearTimeout,fetch:(_,o)=>new Promise((resolve,reject)=>o.signal.addEventListener('abort',()=>reject(new Error('internal stack'))))};
 vm.runInNewContext(fs.readFileSync('public/api-client.js','utf8'),context);
 await assert.rejects(context.window.NeuroAPI.request('leads',{},()=>true,200,5),e=>e.code==='timeout'&&!e.message.includes('stack'));
});
test('network failure becomes Russian error',async()=>{
 const context={window:{},AbortController,setTimeout,clearTimeout,fetch:async()=>{throw new Error('private internal path');}};
 vm.runInNewContext(fs.readFileSync('public/api-client.js','utf8'),context);
 await assert.rejects(context.window.NeuroAPI.request('leads'),e=>e.message.includes('Проверьте соединение')&&!e.message.includes('private'));
});
