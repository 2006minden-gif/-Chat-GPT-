'use strict';
window.ndContractEssentials={
 moneyWords(value){
  if(typeof value!=='string'||!/^\d{1,8}(?:\.\d{1,2})?$/.test(value))return '';
  const [whole,fraction='']=value.split('.'),amount=Number(whole),kopeks=fraction.padEnd(2,'0');
  const one=['','один','два','три','четыре','пять','шесть','семь','восемь','девять'],teens=['десять','одиннадцать','двенадцать','тринадцать','четырнадцать','пятнадцать','шестнадцать','семнадцать','восемнадцать','девятнадцать'],tens=['','','двадцать','тридцать','сорок','пятьдесят','шестьдесят','семьдесят','восемьдесят','девяносто'],hundreds=['','сто','двести','триста','четыреста','пятьсот','шестьсот','семьсот','восемьсот','девятьсот'];
  const noun=(n,forms)=>forms[n%100>=11&&n%100<=19?2:n%10===1?0:n%10>=2&&n%10<=4?1:2];
  function group(n,female=false){const words=[hundreds[Math.floor(n/100)]];n%=100;if(n>=10&&n<20)words.push(teens[n-10]);else{words.push(tens[Math.floor(n/10)]);words.push(female&&n%10===1?'одна':female&&n%10===2?'две':one[n%10]);}return words.filter(Boolean).join(' ');}
  const words=[];for(const [divisor,forms,female]of [[1000000,['миллион','миллиона','миллионов'],false],[1000,['тысяча','тысячи','тысяч'],true]]){const n=Math.floor(amount/divisor)%1000;if(n)words.push(group(n,female),noun(n,forms));}if(amount%1000)words.push(group(amount%1000));if(!amount)words.push('ноль');words.push(noun(amount,['рубль','рубля','рублей']),kopeks,noun(Number(kopeks),['копейка','копейки','копеек']));const text=words.join(' ');return text.charAt(0).toUpperCase()+text.slice(1);
 },
 prepare(s,records,templates){
  if(!records?.context)return null;
  const id=Number(records.context.order_id),term=s.terms.find(t=>Number(t.order_id)===id),data=term?JSON.parse(term.data_json):null;
  const values={...(data?.values||{})},source=data?.legacy_fields||s.proposal_source?.fields||{};
  const brief=s.brief_source||{},briefCopy={'project.name':'title','project.purpose':'goal','project.type':'service','spec.functions':'requirements','spec.handover':'deliverables','spec.completion_deadline':'deadline','spec.exclusions':'constraints'};for(const [to,from]of Object.entries(briefCopy))if((!Object.hasOwn(values,to)||(to!=='project.name'&&!values[to]?.trim()))&&typeof brief[from]==='string'&&brief[from].trim())values[to]=brief[from];
  const copy={'spec.functions':'deliverables','spec.exclusions':'exclusions','spec.client_materials':'dependencies','spec.revision_rounds':'revision_rounds','spec.release_sequence':'handover_terms','support.scope':'support_terms','support.defect_procedure':'acceptance_procedure','spec.handover':'handover_terms','spec.dependencies':'licenses','spec.cost_payer':'third_party_costs'};
  for(const [to,from]of Object.entries(copy))if(!values[to]?.trim()&&typeof source[from]==='string'&&source[from].trim())values[to]=source[from];
  if(/^(?:(?:Договорная )?поддержка\s+(?:не включена|не предусмотрена)|Не (?:включена|предусмотрена))/i.test(source.support_terms||''))for(const key of ['support.start_event','support.duration','support.end_calculation','support.end_date','support.scope','support.response_time'])if(!values[key]?.trim())values[key]='Не применяется: поддержка после передачи не включена.';
  const owner=s.owner?JSON.parse(s.owner.data_json):null;if(!values['support.contacts']?.trim()&&owner?.email)values['support.contacts']=owner.email;
  const docs=records.lists.documents.filter(d=>d.separate_pdf),agreement=docs.some(d=>d.kind==='agreement'),kind=agreement&&!docs.some(d=>d.kind==='specification')?'specification':'agreement';
  const template=templates.find(t=>t.kind===kind&&t.state==='APPROVED');const pair=['agreement','specification'].map(kind=>templates.find(t=>t.kind===kind&&t.state==='APPROVED'));const preparePair=pair.every(Boolean)&&!docs.some(d=>['agreement','specification'].includes(d.kind));
  return {values,term,template,pair:preparePair?pair:null,order:id,proposal:data?.proposal_id||records.flow?.proposal_binding_id||'',source};
 },
 layout(fields){
  const criteria=fields.querySelector('[data-contract-field="spec.acceptance_criteria"]');if(criteria)criteria.dataset.simpleCriteria='true';
  const order=['project.name','project.purpose','spec.functions','spec.exclusions','spec.completion_deadline','price.rights_fee','spec.acceptance_criteria','spec.milestones'],primary=new Set(order);
  const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Остальные условия договора и передачи';details.append(summary);details.className='card';
  for(const label of Array.from(fields.children)){const i=label.querySelector('[data-contract-field]');if(i&&!primary.has(i.dataset.contractField))details.append(label);}
  for(const key of order){const label=Array.from(fields.children).find(n=>n.querySelector('[data-contract-field]')?.dataset.contractField===key);if(label)fields.append(label);}
  fields.append(details);
  return details;
 },
 fillMetadata(values,record,source={}){
  // Draft metadata and operational wording only; saved document dates remain unchanged.
  if(!values['price.words']){const words=this.moneyWords(source.price);if(words)values['price.words']=words;}
  const today=new Date().toLocaleDateString('en-CA');const defaults={'contract.date':today,'spec.date':today,'contract.number':record?.label?.split(' — ')[0],'spec.version':'1','spec.version_method':'По номеру редакции и контрольной сумме сохранённого PDF.','spec.ai_scope':'Исполнитель может применять ИИ при подготовке результата и проверяет его перед передачей. Функции ИИ в самом продукте определяются согласованным составом работ.','spec.test_plan':'Проверка переданной версии по сценариям и ожидаемым результатам, перечисленным в этом ТЗ.','spec.ai_controls':'Исполнитель проверяет результат по согласованным сценариям перед передачей.','spec.production_checks':'После размещения проверяются доступность и согласованные сценарии; перед заменой сохраняется возможность восстановления предыдущей версии.'};
  for(const [k,v]of Object.entries(defaults))if((!Object.hasOwn(values,k)||(!['contract.date','spec.date'].includes(k)&&!values[k]?.trim()))&&v)values[k]=v;
 },
 noSupport(fields,values){
  function choice(title,defaults,already){const box=document.createElement('label'),check=document.createElement('input'),previous={};check.type='checkbox';check.checked=already;for(const key of Object.keys(defaults))previous[key]=values[key]||'';box.append(check,document.createTextNode(title));fields.insertBefore(box,fields.querySelector(':scope > details'));check.addEventListener('change',()=>{for(const [key,value]of Object.entries(defaults)){const input=fields.querySelector('[data-contract-field="'+key+'"]');if(input){input.value=check.checked?value:(already?'':previous[key]);input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('nd-reload-schedule'));if(!check.checked)for(let p=input.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;}}});}
  const keys=['support.start_event','support.duration','support.end_calculation','support.end_date','support.scope','support.response_time'];choice('Поддержка после передачи не включена',Object.fromEntries(keys.map(k=>[k,'Не применяется: поддержка после передачи не включена.'])),keys.every(k=>/не включена|не предусмотрена/i.test(values[k]||'')));
  choice('Регулярных внешних расходов нет',{'spec.recurring_costs':'[]','spec.cost_payer':'Не применяется: регулярные внешние расходы не предусмотрены.'},values['spec.recurring_costs']?.trim()==='[]');
 }
};
