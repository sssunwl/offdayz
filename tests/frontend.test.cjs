const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.join(__dirname,'..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const api=require('../docs/assets/site.js');
const cal=JSON.parse(read('docs/data/holidays.json'));
const pages=['docs/index.html','docs/destinations/index.html','docs/destinations/city.html','docs/seasonal/index.html','docs/places/index.html'];

test('September 3: the next shared window is December 25–27 with both countries represented',()=>{
  const win=api.nextWindow(cal,'2026-09-03');
  assert.deepEqual({from:win.from,to:win.to,len:win.len},{from:'2026-12-25',to:'2026-12-27',len:3});
  assert.ok(win.why.includes('行憲紀念日'));
  assert.ok(win.why.includes('聖誕節'));
  assert.ok(win.why.includes('聖誕節翌日'));
  assert.equal((api.date(win.from)-api.date('2026-09-03'))/api.DAY,113);
});

test('Every returned day is a shared day off, with no makeup working day',()=>{
  for(const start of ['2026-01-01','2026-02-10','2026-04-01','2026-09-03','2026-12-27','2027-01-01']){
    const win=api.nextWindow(cal,start);
    assert.ok(win); assert.ok(win.len>=3); assert.ok(win.why.length);
    for(let d=api.date(win.from);api.iso(d)<=win.to;d=new Date(+d+api.DAY)){
      for(const c of ['TW','HK']){
        const data=cal.years[d.getUTCFullYear()][c],s=api.iso(d);
        assert.ok(!data.workdays.includes(s));
        assert.ok([0,6].includes(d.getUTCDay())||data.holidays.some(h=>h[0]===s&&h[2]!=='half'));
      }
    }
  }
});

test('Ordinary weekends, half-days, gaps, and makeup workdays never create false windows',()=>{
  const sample={years:{2026:{TW:{holidays:[['2026-09-04','A','half']]},HK:{holidays:[['2026-09-04','B']]}}}};
  assert.equal(api.nextWindow(sample,'2026-09-03'),null);
  sample.years[2026].TW.holidays=[['2026-09-04','A']];
  sample.years[2026].TW.workdays=['2026-09-05'];
  assert.equal(api.nextWindow(sample,'2026-09-03'),null);
  sample.years[2026].TW.workdays=[];
  sample.years[2026].TW.holidays=[['2026-09-07','A']];
  assert.equal(api.nextWindow(sample,'2026-09-03'),null);
  assert.equal(api.nextWindow({years:{2026:{TW:{holidays:[]}}}},'2026-09-03'),null);
  assert.equal(api.nextWindow(null),null);
  assert.equal(api.nextWindow(cal,'2028-01-01'),null);
});

test('Year boundaries use both years of data and return maximal continuous runs',()=>{
  const sample={years:{2026:{TW:{holidays:[['2026-12-31','Eve']]},HK:{holidays:[['2026-12-31','Eve']]}},2027:{TW:{holidays:[['2027-01-01','New year']]},HK:{holidays:[['2027-01-01','New year']]}}}};
  assert.deepEqual(api.nextWindow(sample,'2026-12-30'),{from:'2026-12-31',to:'2027-01-03',len:4,why:['Eve','New year']});
});

test('Taiwan/Hong Kong day boundaries do not depend on UTC midnight or the visitor timezone',()=>{
  assert.equal(api.todayISO(new Date('2026-09-02T16:01:00Z')),'2026-09-03');
  assert.equal(api.todayISO(new Date('2026-09-02T15:59:00Z')),'2026-09-02');
});

test('City holiday reminders return three future holidays in the current year',()=>{
  for(const country of ['JP','KR','TW']){
    const list=api.upcomingHolidays(cal,country,'2026-09-03');
    assert.equal(list.length,3);
    assert.ok(list.every(h=>h.date>='2026-09-03'&&h.date<'2027'&&h.days>=1));
  }
  assert.equal(api.upcomingHolidays(cal,'JP','2026-12-30').length,0);
  assert.equal(api.upcomingHolidays(null,'JP').length,0);
  assert.equal(api.upcomingHolidays(cal,'ZZ').length,0);
});

test('Data fetch handles network, HTTP, and JSON errors without throwing',async()=>{
  const original=global.fetch;
  try{
    for(const stub of [async()=>{throw new Error('offline')},async()=>({ok:false}),async()=>({ok:true,json:async()=>{throw new Error('bad JSON')}})]){
      global.fetch=stub; assert.equal(await api.getJSON('/fixture'),null);
    }
    global.fetch=async()=>({ok:true,json:async()=>({ok:1})});
    assert.deepEqual(await api.getJSON('/fixture'),{ok:1});
  }finally{global.fetch=original;}
});

test('All shared pages carry the stylesheet, navigation, footer, waves, and one main landmark',()=>{
  for(const file of pages){
    const html=read(file);
    assert.match(html,/<link rel="stylesheet" href="(?:\.\.\/)?assets\/sosol\.css">/);
    assert.doesNotMatch(html,/:root|--gold|class="sec-ttl"|class="hdr"/);
    assert.equal((html.match(/<main\b/g)||[]).length,1,file);
    assert.equal((html.match(/<\/main>/g)||[]).length,1,file);
    assert.match(html,/class="site-header"/);assert.match(html,/class="site-footer"/);
    assert.match(html,/class="ocean-waves"/);
    assert.match(html,/aria-expanded="false"/);
    assert.match(html,/id="dropNav"[^>]*hidden/);
    const active=file.includes('seasonal')?'seasonal/':file.includes('destinations')?'destinations/':file.includes('places')?'places/':'./';
    assert.match(html,new RegExp('href="[^"\\n]*'+active.replaceAll('.','\\.')+'" aria-current="page"'));
  }
  const home=read(pages[0]);
  for(const id of ['masthead','contents','boardingPass'])assert.match(home,new RegExp('id="'+id+'"'));
  assert.doesNotMatch(home,/flights\.json|hotels\.json|deals\.json|id="(?:deals|hotels)"/);

});

test('Local links, stylesheets and scripts resolve to files under the published docs directory',()=>{
  for(const file of pages){
    const html=read(file).split('<script>')[0];
    for(const m of html.matchAll(/(?:href|src)="([^"]+)"/g)){
      if(/^(?:https?:|data:|#)/.test(m[1]))continue;
      let target=path.resolve(root,path.dirname(file),m[1].split(/[?#]/)[0]);
      if(fs.existsSync(target)&&fs.statSync(target).isDirectory())target=path.join(target,'index.html');
      assert.ok(fs.existsSync(target),file+': '+m[1]);
    }
  }
});

test('Inline page scripts and shared script parse without dependencies',()=>{
  for(const file of pages){
    for(const m of read(file).matchAll(/<script>([\s\S]*?)<\/script>/g))assert.doesNotThrow(()=>new vm.Script(m[1],{filename:file}));
  }
  assert.doesNotThrow(()=>new vm.Script(read('docs/assets/site.js')));
});

test('Both calendar copies agree when the sibling project is available',t=>{
  if(!fs.existsSync(path.join(root,'../SunFamilyTrip/calendar.html')))return t.skip('Standalone checkout: sibling project is not present');
  assert.equal(read('docs/calendar/index.html'),read('../SunFamilyTrip/calendar.html'));
});

// A tiny rendering harness: exercises page logic against the existing JSON shapes
// and failed fetches without introducing a package dependency or changing data.
async function renderPage(file,lookup,search=''){
  const nodes=new Map();
  const node=()=>({innerHTML:'',textContent:'',className:'',hidden:false,options:[],
    classList:{add(){},remove(){},toggle(){}},querySelectorAll:()=>[],appendChild(){},setAttribute(){}});
  const document={title:'',getElementById(id){if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);},
    querySelectorAll:()=>[],querySelector:()=>node(),createElement:()=>node()};
  const context=vm.createContext({document,location:{search},URLSearchParams,Date,console,
    SoSol:{...api,todayISO:()=> '2026-09-03',getJSON:async p=>lookup(p),updateStatus(){}}});
  const script=read(file).match(/<script>([\s\S]*?)<\/script>/)[1];
  await vm.runInContext(script,context);
  return nodes;
}

test('Landing renders city facts, three windows, stamps, boarding pass and six seasonal entries at most',async()=>{
  const lookup=p=>JSON.parse(read('docs/'+p.replace(/^\.\//,'')));
  const nodes=await renderPage('docs/index.html',lookup);
  assert.equal((nodes.get('cityGrid').innerHTML.match(/class="travel-card"/g)||[]).length,8);
  assert.match(nodes.get('cityGrid').innerHTML,/時區|簽證|貨幣|最佳月份/);
  assert.match(nodes.get('nextbox').innerHTML,/2026-12-25 — 2026-12-27/);
  assert.match(nodes.get('nextbox').innerHTML,/BOARDING · 2 PAX/);
  assert.equal((nodes.get('offdayList').innerHTML.match(/class="gate-ticket"/g)||[]).length,3);
  // 封面:下一個連假的 3 個「這次去」章+1 個「先別去」作廢章,章上不寫日期
  const cover=nodes.get('coverStamps').innerHTML;
  assert.equal((cover.match(/class="passport-stamp\b/g)||[]).length,4);
  assert.equal((cover.match(/stamp-void/g)||[]).length,1);
  assert.doesNotMatch(cover,/\d{2}\.\d{2}/);
  assert.ok((nodes.get('eventList').innerHTML.match(/class="toc-row"/g)||[]).length<=6);
  assert.equal(nodes.get('issueDate').textContent,'ISSUE 01 · SEP 2026');
});

test('Landing and seasonal views replace loading content when every fetch fails',async()=>{
  const home=await renderPage('docs/index.html',()=>null);
  for(const id of ['cityGrid','coverStamps','offdayList','placePeek','eventList','nextbox']){
    assert.ok(home.get(id).innerHTML.length,id);assert.doesNotMatch(home.get(id).innerHTML,/載入中|計算中/,id);
  }
  const seasonal=await renderPage('docs/seasonal/index.html',()=>null);
  assert.match(seasonal.get('events-list').innerHTML,/活動資料暫時無法載入/);
});

test('All city JSON shapes render; invalid city keys cause no data request',async()=>{
  for(const key of ['okinawa','ishigaki','miyakojima','tokyo','fukuoka','seoul','busan','taipei']){
    const nodes=await renderPage('docs/destinations/city.html',p=>JSON.parse(read(path.posix.join('docs/destinations',p))),'?key='+key);
    assert.equal((nodes.get('holiday-list').innerHTML.match(/class="hrow-card holiday-row"/g)||[]).length,3,key);
    assert.ok(nodes.get('highlights').innerHTML.length,key);
  }
  for(const key of ['../../secret','__proto__','toString','']){
    const missing=await renderPage('docs/destinations/city.html',()=>{throw new Error('Unexpected fetch');},'?key='+key);
    assert.match(missing.get('main').innerHTML,/找不到這個城市/);
  }
});

function htmlFiles(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(f=>f.isDirectory()?htmlFiles(path.join(dir,f.name)):f.name.endsWith('.html')?[path.join(dir,f.name)]:[]);}
test('Published HTML contains no retired navigation and the old route redirects',()=>{
  for(const file of htmlFiles(path.join(root,'docs')))assert.doesNotMatch(fs.readFileSync(file,'utf8'),/機票・酒店|機酒/,file);
  const redirect=read('docs/deals/index.html');
  assert.match(redirect,/name="robots" content="noindex"/);
  assert.match(redirect,/http-equiv="refresh" content="0;url=\.\.\/"/);
  assert.match(redirect,/<a href="\.\.\/">/);
});
test('All column pages have magazine mastheads and keep external holiday search links',()=>{
  for(const file of htmlFiles(path.join(root,'docs')).filter(p=>/\/(destinations|places|seasonal|offdays)\//.test(p))){
    const html=fs.readFileSync(file,'utf8');
    assert.match(html,/class="column-masthead"/);
    assert.match(html,/assets\/magazine\.css/);
    assert.doesNotMatch(html,/flights\.json|hotels\.json|deals\.json/);
  }
  assert.match(read('docs/offdays/2026-xmas-hk/index.html'),/class="btn btn-primary od-book"/);
});

test('A failed city fetch preserves the other city facts and the boarding pass',async()=>{
  const nodes=await renderPage('docs/index.html',p=>p.includes('seoul.json')?null:JSON.parse(read('docs/'+p.replace(/^\.\//,''))));
  assert.equal((nodes.get('cityGrid').innerHTML.match(/class="travel-card"/g)||[]).length,7);
  assert.match(nodes.get('cityGrid').innerHTML,/SEOUL 城市資料暫時無法載入/);
  assert.match(nodes.get('nextbox').innerHTML,/BOARDING/);
});

test('Seasonal month and category filters retain matching events and show an empty state',async()=>{
  const nodes=new Map();
  const document={getElementById(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:''});return nodes.get(id)},querySelectorAll:()=>[]};
  const seasonal=JSON.parse(read('docs/data/seasonal.json'));
  const context=vm.createContext({document,Date,console,SoSol:{...api,todayISO:()=> '2026-11-12',getJSON:async()=>seasonal}});
  await vm.runInContext(read('docs/seasonal/index.html').match(/<script>([\s\S]*?)<\/script>/)[1],context);
  vm.runInContext('setMonth(0);setCat("全部")',context);
  assert.equal((nodes.get('events-list').innerHTML.match(/<details/g)||[]).length,seasonal.events.length);
  vm.runInContext('setMonth(1);setCat("不存在的分類")',context);
  assert.match(nodes.get('events-list').innerHTML,/此篩選條件暫無活動/);
});

test('Mobile navigation opens, closes on a link, and closes with Escape',()=>{
  const handlers={},listeners={};
  const nav={hidden:true,addEventListener:(k,fn)=>listeners[k]=fn};
  const menu={addEventListener:(k,fn)=>handlers[k]=fn,setAttribute(k,v){this[k]=v},focus(){this.focused=true}};
  const header={contains:()=>true,classList:{toggle(){}}};
  const docHandlers={};
  const document={getElementById:id=>({hdr:header,menuBtn:menu,dropNav:nav}[id]),addEventListener:(k,fn)=>docHandlers[k]=fn};
  vm.runInNewContext(read('docs/assets/site.js'),{document,Intl,Date,matchMedia:()=>({addEventListener(){}}),addEventListener(){},scrollY:0});
  handlers.click();assert.equal(nav.hidden,false);assert.equal(menu['aria-expanded'],'true');
  listeners.click({target:{closest:()=>true}});assert.equal(nav.hidden,true);
  handlers.click();docHandlers.keydown({key:'Escape'});assert.equal(nav.hidden,true);assert.equal(menu.focused,true);
});


test('Boarding destination, masthead dateline, and stamp variants follow the magazine revision',async()=>{
  const lookup=p=>JSON.parse(read('docs/'+p.replace(/^\.\//,'')));
  const first=await renderPage('docs/index.html',lookup);
  const second=await renderPage('docs/index.html',lookup);
  assert.match(first.get('nextbox').innerHTML,/HKG · TPE → <span class="boarding-destination">去哪？<\/span>/);
  assert.doesNotMatch(read('docs/index.html'),/\?\?\?/);
  assert.match(read('docs/index.html'),/<span>EST\. 2026 · OFFDAYZ\.SSSUNI\.COM<\/span>/);
  assert.match(read('docs/index.html'),/<p class="cover-deck">[^<]*<br><i>Off days, well spent\.<\/i><\/p>/);
  const cities=first.get('cityGrid').innerHTML;
  const stamps=[...cities.matchAll(/class="passport-stamp (stamp-\w+) (stamp-\w+)" style="--stamp-rotation:([\d-]+)deg;/g)];
  assert.equal(stamps.length,8);
  const keys=['fukuoka','seoul','taipei','okinawa','tokyo','ishigaki','busan','miyakojima'];
  const countries={'日本':'stamp-japan','韓國':'stamp-korea','台灣':'stamp-taiwan'};
  stamps.forEach((stamp,index)=>{
    assert.equal(stamp[1],countries[lookup('./destinations/data/'+keys[index]+'.json').country]);
    assert.equal(stamp[2],index%2===0?'stamp-round':'stamp-rect');
    assert.ok(Number(stamp[3])>=-12&&Number(stamp[3])<=12);
  });
  assert.equal(new Set(stamps.map(stamp=>stamp[3])).size,8);
  assert.equal(cities,second.get('cityGrid').innerHTML);
  assert.equal(first.get('coverStamps').innerHTML,second.get('coverStamps').innerHTML);
  const css=read('docs/assets/magazine.css');
  for(const [country,token] of [['japan','blue'],['korea','navy'],['taiwan','lagoon']]){
    assert.ok(css.includes('.passport-stamp.stamp-'+country+'{color:var(--'+token+')}'));
  }
});

test('City has no retired loading blocks and all published div tags balance',()=>{
  assert.doesNotMatch(read('docs/destinations/city.html'),/live-flights|live-hotels/);
  for(const file of htmlFiles(path.join(root,'docs'))){
    const html=fs.readFileSync(file,'utf8');
    const openingTags=html.match(/<div\b/gi)||[];
    const closingTags=html.match(/<\/div\s*>/gi)||[];
    assert.equal(openingTags.length,closingTags.length,file);

    // Check the static document in order as well, so matching totals cannot hide stray closing tags.
    const markup=html.replace(/<script\b[^>]*>[\s\S]*?<\/script\s*>/gi,'').replace(/<!--[\s\S]*?-->/g,'');
    let depth=0;
    for(const tag of markup.matchAll(/<\/?div\b[^>]*>/gi)){
      depth+=/^<\//.test(tag[0])?-1:1;
      assert.ok(depth>=0,file+': closing div has no opening tag');
    }
    assert.equal(depth,0,file+': unclosed div');
  }
});

test('Column folios appear in mastheads rather than repeating on section headings',()=>{
  for(const folder of ['destinations','places','seasonal','offdays']){
    for(const file of htmlFiles(path.join(root,'docs',folder))){
      const html=fs.readFileSync(file,'utf8');
      assert.match(html,/<div class="dateline"><span>P\.0[2-5] /,file);
      assert.doesNotMatch(html,/<h2\b[^>]*data-folio=/,file);
    }
  }
});
