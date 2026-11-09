const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
test('public homepage has direct contacts and no briefing, payment or account widgets',()=>{
 const html=fs.readFileSync('public/index.html','utf8');
 assert.match(html,/https:\/\/t\.me\/minden2006/);
 assert.match(html,/https:\/\/max\.ru\/u\//);
 assert.doesNotMatch(html,/<form\b|services\.php|customer\.php|payment\.php|ai-widget\.js|analytics\.js/);
});
