'use strict';
(()=>{
 const directory=document.querySelector('[data-owner-directory]');if(!directory)return;
 function mark(){let best=-1,matched=[];for(const a of directory.querySelectorAll('a[href]')){a.removeAttribute('aria-current');const u=new URL(a.href),same=u.pathname===location.pathname&&u.search===location.search;if(!same||u.hash&&u.hash!==location.hash)continue;const score=u.hash?2:1;if(score>best){best=score;matched=[];}if(score===best)matched.push(a);}for(const a of matched)a.setAttribute('aria-current','page');}
 mark();window.addEventListener('hashchange',mark);
 const input=directory.querySelector('input[type=search]');input.addEventListener('input',()=>{const words=input.value.toLocaleLowerCase('ru').trim().split(/\s+/).filter(Boolean);let count=0;for(const group of directory.querySelectorAll('.owner-directory-group')){let shown=0;for(const li of group.querySelectorAll('li')){const text=(group.querySelector('summary').textContent+' '+li.textContent).toLocaleLowerCase('ru');li.hidden=!words.every(w=>text.includes(w));if(!li.hidden)shown++;}group.hidden=!shown;group.open=words.length>0&&shown>0;count+=shown;}directory.querySelector('.owner-directory-empty').hidden=count!==0;});
})();
