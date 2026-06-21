const RUB=n=>n.toLocaleString('ru-RU')+' ₽';
const M=n=>(n/1e6).toLocaleString('ru-RU',{minimumFractionDigits:2,maximumFractionDigits:2})+' млн';
const STG={wait:{c:'wait',l:'Ожидают закупки'},cancel:{c:'cancel',l:'Отмена'},proc:{c:'proc',l:'В закупке'},supp:{c:'supp',l:'В сопровождении'},pay:{c:'pay',l:'В оплате'},done:{c:'ok',l:'Закрыта'},late:{c:'late',l:'Просрочено'}};
const ROUTE=['Создана','В закупке','Сопровожд.','Оплата','Закрыта'];
const SOF={wait:0,proc:1,supp:2,late:2,pay:3,done:4};
const DOCKEYS=['ТТН','М15','УПД','Серт'];const DOCLAB={ТТН:'ТТН',М15:'М-15',УПД:'УПД',Серт:'Серт'};
const pos=(name,qty,unit,price,deliv)=>({name,qty,unit,price,deliv});
const dl=(n,st,when,docs,upd,pay,extra)=>Object.assign({n,st,when,docs,upd,pay},extra||{});

// ===== DATA =====
const parents=[
 {code:'Т-67',title:'Трубопроводный узел №3',mtr:'Трубная продукция',srok:'25.07.26',zagruzka:'02.06.26',sostavitel:'А. Орлова',dept:'Комплектация-1',
  children:[
   {num:'1488',proc:'АП1488',supplier:'ООО «ТехСнаб»',lot:'Лот 1',pubStart:'06.06',pubEnd:'13.06',stage:'supp',days:9,
    contract:'№217-П · 09.06',statusSdelki:'Контракт заключён',statusPostavki:'Частично получена',srokDD:'25.07',plan:'25.07',fakt:'—',
    positions:[pos('Труба ст. 57×3,5 ГОСТ 8732',420,'м',1850,1),pos('Труба ст. 76×4,0 ГОСТ 8732',300,'м',2400,1),pos('Отвод 90° 57×3,5',120,'шт',520,2),pos('Тройник 76×57 равнопроходной',36,'шт',1980,null)],
    dels:[dl(1,'done','получена 14.06',{ТТН:1,М15:1,УПД:1,Серт:1},'УПД-3391','paid',{payDate:'19.06'}),
          dl(2,'done','получена 18.06',{ТТН:1,М15:1,УПД:1,Серт:0},'УПД-3402','await')]},
   {num:'1489',proc:'АП1489',supplier:'АО «Промкомплект»',lot:'Лот 2',pubStart:'06.06',pubEnd:'12.06',stage:'pay',days:5,
    contract:'№219-П · 10.06',statusSdelki:'Контракт заключён',statusPostavki:'Получена',srokDD:'20.07',plan:'18.06',fakt:'17.06',
    positions:[pos('Задвижка клиновая 30с41нж ДУ100',24,'шт',12400,1),pos('Кран шаровой ДУ50',40,'шт',3200,1)],
    dels:[dl(1,'done','получена 17.06',{ТТН:1,М15:1,УПД:1,Серт:1},'УПД-3398','await')]},
   {num:'1490',proc:'АП1490',supplier:'—',lot:'Лот 3',pubStart:'06.06',pubEnd:'19.06',stage:'proc',days:14,statusZakup:'Приём заявок №2',
    positions:[pos('Фланец плоский ДУ100 Ру16',60,'шт',1450,null),pos('Прокладка паронит ДУ100',60,'шт',180,null)],dels:[]}
  ]},
 {code:'Т-70',title:'КИПиА для котельной',mtr:'КИПиА',srok:'19.07.26',zagruzka:'28.05.26',sostavitel:'А. Орлова',dept:'Комплектация-1',
  children:[
   {num:'1491',proc:'АП1491',supplier:'ООО «ЭнергоСбыт»',lot:'Лот 1',pubStart:'02.06',pubEnd:'09.06',stage:'late',days:16,
    contract:'№204-П · 03.06',statusSdelki:'Контракт заключён',statusPostavki:'Просрочена',srokDD:'19.06',plan:'19.06',fakt:'—',
    positions:[pos('Датчик давления Метран-150',18,'шт',24800,1),pos('Термопреобразователь ТСМ',30,'шт',3600,1),pos('Контроллер ОВЕН ПЛК',6,'шт',42000,2)],
    dels:[dl(1,'done','получена 12.06',{ТТН:1,М15:1,УПД:1,Серт:1},'УПД-3370','paid',{payDate:'18.06'}),
          dl(2,'late','просрочена · ETA 19.06',{ТТН:0,М15:0,УПД:0,Серт:0},null,'none')]},
   {num:'1492',proc:'АП1492',supplier:'—',lot:'Лот 2',pubStart:'02.06',pubEnd:'18.06',stage:'proc',days:18,statusZakup:'Тех. оценка · 4 поставщика',
    positions:[pos('Манометр МП-100',40,'шт',1250,null),pos('Клапан регулирующий ДУ50',8,'шт',18500,null)],dels:[]}
  ]},
 {code:'Т-71',title:'Кабельные трассы корпус А',mtr:'Кабельная продукция',srok:'16.07.26',zagruzka:'27.05.26',sostavitel:'Л. Кравцова',dept:'Комплектация-2',
  children:[
   {num:'1493',proc:'АП1493',supplier:'ООО «КабельОпт»',lot:'Лот 1',pubStart:'31.05',pubEnd:'06.06',stage:'pay',days:10,
    contract:'№198-П · 30.05',statusSdelki:'Контракт заключён',statusPostavki:'Получена',srokDD:'16.07',plan:'15.06',fakt:'15.06',
    positions:[pos('Кабель ВВГнг(А)-LS 4×95',800,'м',1840,1),pos('Кабель ВВГнг(А)-LS 3×2,5',1200,'м',210,2),pos('Лоток кабельный 200×80',300,'м',640,2)],
    dels:[dl(1,'done','получена 10.06',{ТТН:1,М15:1,УПД:1,Серт:1},'УПД-3355','late'),
          dl(2,'done','получена 15.06',{ТТН:1,М15:1,УПД:1,Серт:1},'УПД-3389','await')]}
  ]},
 {code:'Т-72',title:'Запорная арматура ДУ100',mtr:'Запорная арматура',srok:'01.08.26',zagruzka:'05.06.26',sostavitel:'В. Седов',dept:'Комплектация-1',
  positions:[pos('Задвижка стальная ДУ100',30,'шт',9800,null),pos('Затвор поворотный ДУ80',24,'шт',4200,null)],children:[]},
 {code:'Т-73',title:'Электрооборудование ЩСУ',mtr:'Электрооборудование',srok:'08.08.26',zagruzka:'18.06.26',sostavitel:'В. Седов',dept:'Комплектация-1',
  positions:[pos('Щит ЩСУ-0,4кВ',2,'компл',285000,null),pos('Автомат ВА47-29 25А',60,'шт',420,null)],children:[]},
 {code:'Т-74',title:'Метизы и крепёж',mtr:'Метизы',srok:'03.08.26',zagruzka:'12.06.26',sostavitel:'А. Орлова',dept:'Комплектация-1',
  positions:[pos('Болт М16×60 оц.',2000,'шт',12,null),pos('Гайка М16 оц.',2000,'шт',5,null),pos('Шайба М16 оц.',4000,'шт',2,null)],children:[]},
 {code:'Т-76',title:'Расходники сварочные',mtr:'Сварочные материалы',srok:'—',zagruzka:'10.06.26',sostavitel:'Л. Кравцова',dept:'Комплектация-2',cancelled:true,
  positions:[pos('Электроды УОНИ 13/55 ⌀4',200,'кг',310,null),pos('Проволока СВ-08Г2С ⌀1,2',150,'кг',180,null)],children:[]},
 {code:'Т-75',title:'Спецодежда зимняя',mtr:'Спецодежда',srok:'27.07.26',zagruzka:'24.05.26',sostavitel:'Л. Кравцова',dept:'Комплектация-2',
  children:[
   {num:'1494',proc:'АП1494',supplier:'ООО «РабПром»',lot:'Лот 1',pubStart:'28.05',pubEnd:'03.06',stage:'supp',days:11,
    contract:'№191-П · 28.05',statusSdelki:'Контракт заключён',statusPostavki:'Частично получена',srokDD:'27.07',plan:'10.06',fakt:'16.06',
    positions:[pos('Костюм утеплённый «Зима»',80,'компл',4900,1),pos('Сапоги утеплённые',80,'пар',2600,null)],
    dels:[dl(1,'done','получена 16.06 (с задержкой)',{ТТН:1,М15:1,УПД:1,Серт:0},'УПД-3386','await',{late:true})]}
  ]},
 {code:'Т-69',title:'Стройматериалы корпус Б',mtr:'Строительные материалы',srok:'22.07.26',zagruzka:'14.05.26',sostavitel:'В. Седов',dept:'Комплектация-1',
  children:[
   {num:'1495',proc:'АП1495',supplier:'ООО «СтройБаза»',lot:'Лот 1',pubStart:'21.05',pubEnd:'27.05',stage:'pay',days:8,
    contract:'№176-П · 20.05',statusSdelki:'Контракт заключён',statusPostavki:'Получена',srokDD:'18.07',plan:'17.06',fakt:'17.06',
    positions:[pos('Цемент М500 (50 кг)',400,'меш',390,1),pos('Арматура А500С d12',5000,'м',58,1)],
    dels:[dl(1,'done','получена 17.06',{ТТН:1,М15:1,УПД:1,Серт:1},'УПД-3392','await')]},
   {num:'1496',proc:'АП1496',supplier:'ООО «ЦементТорг»',lot:'Лот 2',pubStart:'22.05',pubEnd:'28.05',stage:'late',days:15,
    contract:'№178-П · 21.05',statusSdelki:'Контракт заключён',statusPostavki:'Просрочена',srokDD:'21.06',plan:'21.06',fakt:'—',
    positions:[pos('Бетон М300 товарный',60,'м³',6200,1)],
    dels:[dl(1,'late','просрочена · ETA 19.06',{ТТН:0,М15:0,УПД:0,Серт:0},null,'none')]}
  ]}
];
// helpers
const posSum=p=>p.qty*p.price;
const childSum=c=>c.positions.reduce((s,p)=>s+posSum(p),0);
const childDonePos=c=>c.positions.filter(p=>{if(p.deliv===null)return false;const d=c.dels.find(x=>x.n===p.deliv);return d&&d.st==='done';}).length;
const childTotalPos=c=>c.positions.length;
function findChild(num){for(const p of parents)for(const c of (p.children||[]))if(c.num===num)return{p,c};return null;}
const allChildren=()=>{const a=[];parents.forEach(p=>(p.children||[]).forEach(c=>a.push({p,c})));return a;};
function overduePct(c){const t=c.positions.length;if(!t)return 0;let late=0;c.positions.forEach(p=>{if(p.deliv!==null){const d=c.dels.find(x=>x.n===p.deliv);if(d&&(d.st==='late'||d.late))late++;}});return Math.round(late/t*100);}
function docsAgg(c){const r={};DOCKEYS.forEach(k=>{r[k]=c.dels.length?c.dels.every(d=>d.docs[k]):false;});return r;}

// ===== DASHBOARD widgets =====
const seg=(on,total)=>`<div class="seg">${Array.from({length:total},(_,i)=>`<span class="${i<on?'on':''}"></span>`).join('')}</div>`;
const meters=[
 {l:'В закупке',c:'var(--proc)',v:2,on:2,t:14,s:'на ЭТП'},
 {l:'В сопровождении',c:'var(--supp)',v:4,on:4,t:14,s:'<b>'+M(13520000)+' ₽</b>'},
 {l:'Поставки в срок',c:'var(--ok)',v:'87',u:'%',on:12,t:14,s:'34 / 39 поставок'},
 {l:'Просрочено',c:'var(--late)',v:3,on:3,t:14,s:'<b>'+M(2090000)+' ₽</b>'},
 {l:'УПД в оплате',c:'var(--pay)',v:5,on:5,t:14,s:'<b>'+M(6260000)+' ₽</b>'},
 {l:'УПД просрочено',c:'var(--late)',v:1,on:1,t:14,s:'<b>'+M(1520000)+' ₽</b>'}
];
function rMeters(){document.getElementById('meters').innerHTML=meters.map(m=>`<div class="meter" style="--c:${m.c}"><div class="ml"><i></i>${m.l}</div><div class="mv">${m.v}${m.u?`<em>${m.u}</em>`:''}</div>${seg(m.on,m.t)}<div class="ms">${m.s}</div></div>`).join('');}
function counts(){const c={wait:0,proc:0,supp:0,pay:0,done:0};parents.forEach(p=>{if(!(p.children||[]).length&&!p.cancelled)c.wait++;if(p.cancelled)c.wait++;});c.wait=parents.filter(p=>!(p.children||[]).length).length;allChildren().forEach(({c:ch})=>{if(ch.stage==='proc')c.proc++;else if(ch.stage==='supp'||ch.stage==='late')c.supp++;else if(ch.stage==='pay')c.pay++;else if(ch.stage==='done')c.done++;});return c;}
function rFlow(){const c=counts();const f=[{c:'var(--wait)',l:'Ожидает',n:c.wait},{c:'var(--proc)',l:'В закупке',n:c.proc},{c:'var(--supp)',l:'Сопровождение',n:c.supp,s:'поставщики'},{c:'var(--pay)',l:'В оплате',n:c.pay,s:'УПД'},{c:'var(--ok)',l:'Закрыта',n:c.done}];
 document.getElementById('flowrail').innerHTML=f.map(s=>`<div class="fstage" style="--c:${s.c}" onclick="go('${s.l==='В закупке'?'zakup':s.l==='Сопровождение'?'soprov':s.l==='Ожидает'?'kompl':s.l==='В оплате'?'pay':'dash'}')"><div class="ft"><i></i><span>${s.l}</span></div><div class="fn">${s.n}</div><div class="fs">${s.s||'&nbsp;'}</div></div>`).join('');}
const alerts=[
 {id:'Т-70 · 1491',al:'var(--late)',num:'1491',t:'Поставка №2 (ЭнергоСбыт) — <b>просрочена на 1 день</b>, контроллер ПЛК'},
 {id:'Т-69 · 1496',al:'var(--late)',num:'1496',t:'ЦементТорг — <b>поставка просрочена</b>, документов нет'},
 {id:'Т-71 · 1493',al:'var(--late)',num:'1493',t:'<b>УПД-3355 просрочена к оплате</b> +4 дня · 1,47 млн'},
 {id:'Т-67 · 1488',al:'var(--proc)',num:'1488',t:'УПД-3402 без сертификата — <b>нельзя передать в оплату</b>'}
];
function rAlerts(){document.getElementById('alerts').innerHTML=alerts.map(a=>`<div class="alert" style="--al:${a.al}"><span class="aid mono">${a.id}</span><span class="at">${a.t}</span><button class="ab" onclick="openCard('${a.num}')">Открыть</button></div>`).join('');}
const feed=[{t:'09:42',d:'<b>М. Котов</b> <span>подписал УПД-3398 · Т-67/1489</span>'},{t:'09:18',d:'<b>Закупки</b> <span>разбили Т-67 на 3 поставщика (1488–1490)</span>'},{t:'вчера',d:'<b>Оплата</b> <span>провела 1,29 млн по УПД-3370</span>'},{t:'вчера',d:'<b>Комплектация</b> <span>создала Т-73 · 2 позиции</span>'},{t:'2 дня',d:'<b>Закупки</b> <span>передали Т-71/1493 в сопровождение</span>'}];
function rFeed(){document.getElementById('feed').innerHTML=feed.map(f=>`<div class="fitem"><span class="ft2">${f.t}</span><div>${f.d}</div></div>`).join('');}

// ===== STAGE TABLES =====
function chip(stage){const s=STG[stage];return `<span class="chip ${s.c}"><i></i>${s.l}</span>`;}
function progCell(c){const t=childTotalPos(c),d=childDonePos(c),pc=t?Math.round(d/t*100):0,cls=c.stage==='done'?'done':c.stage==='late'?'late':'';return `<div class="prog ${cls}"><div class="bar"><i style="width:${pc}%"></i></div><span class="pn"><b>${d}</b>/${t}</span></div>`;}
function ovdCell(c){const v=overduePct(c);const cls=v>=50?'b':v>0?'w':'';return `<span class="ovd ${cls}">${v}%</span>`;}
function docsCell(c){const a=docsAgg(c);return `<div class="docsq">${DOCKEYS.map(k=>`<span class="${a[k]?'':'no'}" title="${DOCLAB[k]}">${k==='М15'?'М':k[0]}</span>`).join('')}</div>`;}

function tblAwaiting(list){let h=`<div class="tbl-scroll"><table class="reg"><thead><tr><th>#</th><th>Наименование заявки</th><th>Тип МТР</th><th>Срок поставки</th><th>Дата загрузки</th><th>Составитель</th><th class="c">Позиции</th><th>Статус</th></tr></thead><tbody>`;
 list.forEach((p,i)=>{h+=`<tr onclick="openParentCard('${p.code}')"><td class="num">${i+1}</td><td><span class="parent-tag">${p.code}</span><span class="zname">${p.title}</span></td><td>${p.mtr}</td><td><span class="dt">${p.srok}</span></td><td><span class="dt">${p.zagruzka}</span></td><td>${p.sostavitel}</td><td class="c"><span class="posc">${p.positions.length}</span></td><td>${chip(p.cancelled?'cancel':'wait')}</td></tr>`;});
 return h+`</tbody></table></div>`;}
function tblProc(list){let h=`<div class="tbl-scroll"><table class="reg"><thead><tr><th>#</th><th>Наименование заявки</th><th>Тип МТР</th><th>№ заявки</th><th>№ процедуры</th><th>Поставщик</th><th>Дата загрузки</th><th>Нач. публ.</th><th>Заверш. публ.</th><th class="c">Поз.</th><th>Статус</th></tr></thead><tbody>`;
 list.forEach(({p,c},i)=>{h+=`<tr onclick="openCard('${c.num}')"><td class="num">${i+1}</td><td><span class="parent-tag">${p.code}</span><span class="zname">${p.title}</span></td><td>${p.mtr}</td><td><span class="zaglink">${c.num}</span></td><td><span class="proc-id">${c.proc}</span></td><td><span class="supp-c ${c.supplier==='—'?'empty':''}">${c.supplier==='—'?'не выбран':c.supplier}</span></td><td><span class="dt">${p.zagruzka}</span></td><td><span class="dt">${c.pubStart}</span></td><td><span class="dt">${c.pubEnd}</span></td><td class="c"><span class="posc">${c.positions.length}</span></td><td><span class="chip proc mini"><i></i>${c.statusZakup||'В закупке'}</span></td></tr>`;});
 return h+`</tbody></table></div>`;}
function tblSupp(list){let h=`<table class="reg fit"><colgroup><col style="width:2.5%"><col style="width:17%"><col style="width:5.5%"><col style="width:6.5%"><col style="width:12.5%"><col style="width:9%"><col style="width:9%"><col style="width:9.5%"><col style="width:9.5%"><col style="width:4.5%"><col style="width:4.5%"><col style="width:4.5%"><col style="width:4.5%"><col style="width:6%"><col style="width:5%"></colgroup><thead><tr><th>#</th><th>Наименование заявки</th><th>№ заявки</th><th>№ процед.</th><th>Поставщик</th><th>Тип МТР</th><th class="r">Сумма дог.</th><th>Статус сделки</th><th>Статус поставки</th><th>Срок ДД</th><th>План</th><th>Факт</th><th class="c">Просроч.</th><th class="c">Док-ты</th><th class="c">Поз.</th></tr></thead><tbody>`;
 list.forEach(({p,c},i)=>{const late=c.stage==='late';h+=`<tr onclick="openCard('${c.num}')"><td class="num">${i+1}</td><td><span class="parent-tag">${p.code}</span><span class="zname">${p.title}</span></td><td><span class="zaglink">${c.num}</span></td><td><span class="proc-id">${c.proc}</span></td><td><span class="supp-c">${c.supplier}</span></td><td>${p.mtr}</td><td class="r"><span class="amt">${RUB(childSum(c))}</span></td><td><span class="chip ${late?'late':'supp'} mini"><i></i>${c.statusSdelki}</span></td><td><span class="chip ${late?'late':c.statusPostavki==='Получена'?'ok':'supp'} mini"><i></i>${c.statusPostavki}</span></td><td><span class="dt ${late?'late':''}">${c.srokDD}</span></td><td><span class="dt">${c.plan}</span></td><td><span class="dt">${c.fakt}</span></td><td class="c">${ovdCell(c)}</td><td class="c">${docsCell(c)}</td><td class="c">${progMini(c)}</td></tr>`;});
 return h+`</tbody></table>`;}

function blockWrap(num,bc,title,eng,count,inner,linkPage,extraBtns){
 return `<div class="block" style="--bc:${bc}"><div class="block-h"><span class="bnum">${num}</span><div><div class="btitle">${title}</div><div class="beng">${eng}</div></div><span class="bcount">${count} заявки</span><span class="sp"></span>${extraBtns||''}${linkPage?`<button class="blink" onclick="go('${linkPage}')">Открыть раздел →</button>`:''}<button class="bexport">↧ Экспорт</button></div>${inner}</div>`;}

/* compact tables for Dashboard (сжатая сводка) */
function tblAwaitingC(list){let h=`<div class="tbl-scroll"><table class="reg"><thead><tr><th>#</th><th>Наименование заявки</th><th>Тип МТР</th><th>Срок поставки</th><th class="c">Поз.</th><th>Статус</th></tr></thead><tbody>`;
 list.forEach((p,i)=>{h+=`<tr onclick="openParentCard('${p.code}')"><td class="num">${i+1}</td><td><span class="parent-tag">${p.code}</span><span class="zname">${p.title}</span></td><td>${p.mtr}</td><td><span class="dt">${p.srok}</span></td><td class="c"><span class="posc">${p.positions.length}</span></td><td>${chip(p.cancelled?'cancel':'wait')}</td></tr>`;});
 return h+`</tbody></table></div>`;}
function tblProcC(list){let h=`<div class="tbl-scroll"><table class="reg"><thead><tr><th>#</th><th>Наименование заявки</th><th>№ заявки</th><th>Поставщик</th><th class="c">Поз.</th><th>Статус</th></tr></thead><tbody>`;
 list.forEach(({p,c},i)=>{h+=`<tr onclick="openCard('${c.num}')"><td class="num">${i+1}</td><td><span class="parent-tag">${p.code}</span><span class="zname">${p.title}</span></td><td><span class="zaglink">${c.num}</span></td><td><span class="supp-c ${c.supplier==='—'?'empty':''}">${c.supplier==='—'?'не выбран':c.supplier}</span></td><td class="c"><span class="posc">${c.positions.length}</span></td><td><span class="chip proc mini"><i></i>${c.statusZakup||'В закупке'}</span></td></tr>`;});
 return h+`</tbody></table></div>`;}
function tblSuppC(list){let h=`<div class="tbl-scroll"><table class="reg"><thead><tr><th>#</th><th>Наименование заявки</th><th>№ заявки</th><th>Поставщик</th><th class="r">Сумма договора</th><th>Статус поставки</th><th class="c">Просроч.</th><th class="c">Прогресс</th></tr></thead><tbody>`;
 list.forEach(({p,c},i)=>{const late=c.stage==='late';h+=`<tr onclick="openCard('${c.num}')"><td class="num">${i+1}</td><td><span class="parent-tag">${p.code}</span><span class="zname">${p.title}</span></td><td><span class="zaglink">${c.num}</span></td><td><span class="supp-c">${c.supplier}</span></td><td class="r"><span class="amt">${RUB(childSum(c))}</span></td><td><span class="chip ${late?'late':c.statusPostavki==='Получена'?'ok':'supp'} mini"><i></i>${c.statusPostavki}</span></td><td class="c">${ovdCell(c)}</td><td class="c">${progCell(c)}</td></tr>`;});
 return h+`</tbody></table></div>`;}

function getAwaiting(){return parents.filter(p=>!(p.children||[]).length);}
function getProc(){return allChildren().filter(x=>x.c.stage==='proc');}
function getSupp(){return allChildren().filter(x=>x.c.stage==='supp'||x.c.stage==='late');}

function rDash(){const a=getAwaiting(),pr=getProc(),su=getSupp();
 document.getElementById('dashTables').innerHTML=
  blockWrap(1,'var(--wait)','Ожидают закупки','Awaiting',a.length,tblAwaitingC(a),'kompl')+
  blockWrap(2,'var(--proc)','В закупке','In procurement',pr.length,tblProcC(pr),'zakup')+
  blockWrap(3,'var(--supp)','В сопровождении','In support',su.length,tblSuppC(su),'soprov');
}
function rPages(){const a=getAwaiting(),pr=getProc(),su=getSupp();
 document.getElementById('komplTable').innerHTML=blockWrap(1,'var(--wait)','Ожидают закупки','Awaiting procurement',a.length,tblAwaiting(a),null,'<button class="badd">+ Заявка</button>');
 document.getElementById('zakupTable').innerHTML=blockWrap(2,'var(--proc)','В закупке','In procurement',pr.length,tblProc(pr),null,'<button class="badd">+ Заявка</button>');
 document.getElementById('soprovTable').innerHTML=blockWrap(3,'var(--supp)','В сопровождении','In support',su.length,tblSupp(su),null,'<button class="badd">+ Отгрузка</button>');
 document.getElementById('cntKompl').textContent=a.length;document.getElementById('cntZakup').textContent=pr.length;document.getElementById('cntSoprov').textContent=su.length;
}

// ===== CARD =====
let curRole='soprov',cardOrigin='dash';
const rolesData={kompl:{nm:'А. Орлова',av:'АО'},zakup:{nm:'И. Зуев',av:'ИЗ'},soprov:{nm:'М. Котов',av:'МК'},oplata:{nm:'Е. Лапина',av:'ЕЛ'}};
const roleNames={kompl:'Комплектация',zakup:'Закупки',soprov:'Сопровождение',oplata:'Оплата'};
let curCard={kind:'child',id:'1488'};
function curView(){const a=document.querySelector('.view.active');return a?a.id.replace('view-',''):'dash';}
function openCard(num){const v=curView();if(['dash','kompl','zakup','soprov','pay'].includes(v))cardOrigin=v;curCard={kind:'child',id:num};go('card');}
function openParentCard(code){const v=curView();if(['dash','kompl','zakup','soprov','pay'].includes(v))cardOrigin=v;curCard={kind:'parent',id:code};go('card');}
function acts(role,stage){const sof=SOF[stage];const m={
 kompl:[{t:'Редактировать позиции',d:sof>1},{t:'Дублировать заявку'},{t:'Отменить заявку',d:sof>0}],
 zakup:[{t:'Разместить на ЭТП',d:sof!==1,p:sof===1},{t:'Разбить по поставщикам',d:sof!==1},{t:'Выбрать поставщика',d:sof!==1},{t:'Передать в сопровождение',d:sof!==1}],
 soprov:[{t:'Создать поставку',d:sof!==2,p:sof===2},{t:'Отметить документы',d:sof!==2},{t:'Подписать УПД',d:sof!==2},{t:'Передать в оплату',d:sof!==2}],
 oplata:[{t:'Провести оплату',d:sof<3,p:sof===3},{t:'Закрыть заявку',d:sof<3}]};return m[role];}
function posTable(list){let h=`<table class="postbl"><thead><tr><th>Наименование</th><th class="r">Кол-во</th><th>Ед.</th><th class="r">Цена</th><th class="r">Сумма</th></tr></thead><tbody>`;
 list.forEach(p=>{h+=`<tr><td class="pname">${p.name}</td><td class="r pq">${p.qty.toLocaleString('ru-RU')}</td><td>${p.unit}</td><td class="r pp">${RUB(p.price)}</td><td class="r ps">${RUB(posSum(p))}</td></tr>`;});
 return h+`</tbody></table>`;}
const delChip=(st)=>st==='done'?'<span class="chip ok mini"><i></i>Получена</span>':st==='late'?'<span class="chip late mini"><i></i>Просрочена</span>':'<span class="chip supp mini"><i></i>В поставке</span>';
function progMini(c){const t=childTotalPos(c),d=childDonePos(c);const col=c.stage==='late'?'var(--late)':(d===t&&t>0)?'var(--ok)':'var(--ink)';return `<span class="mono" style="font-size:12px;font-weight:600;color:${col};white-space:nowrap">${d}<span style="color:var(--faint);font-weight:400">/${t}</span></span>`;}
// comments
const esc=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const initials=n=>n.split(/[ .]+/).filter(Boolean).map(s=>s[0]).slice(0,2).join('').toUpperCase();
const comments={
 '1488':[{a:'И. Зуев',r:'Закупки',t:'2 дня назад',txt:'Разбил Т-67 на 3 лота, по трубам по итогам торгов выбрали ТехСнаб.'},{a:'М. Котов',r:'Сопровождение',t:'вчера 14:20',txt:'УПД-3402 пришла без сертификата качества — запросил у поставщика, обещают завтра.'}],
 '1491':[{a:'М. Котов',r:'Сопровождение',t:'сегодня 09:30',txt:'ЭнергоСбыт сдвигает контроллеры ПЛК, уточняю новый срок отгрузки.'}],
 'Т-72':[{a:'В. Седов',r:'Комплектация',t:'3 дня назад',txt:'Срочная заявка под пуск узла, прошу взять в закупку в приоритете.'}]
};
function commentsHTML(id){const list=comments[id]||[];
 return `<div class="dsec-t">Комментарии${list.length?' · '+list.length:''}</div>
  <div class="comments">
   ${list.map(c=>`<div class="cmt"><div class="cmt-av">${initials(c.a)}</div><div class="cmt-b"><div class="cmt-h"><b>${c.a}</b><span class="cmt-r">${c.r}</span><span class="cmt-t">${c.t}</span></div><div class="cmt-x">${esc(c.txt)}</div></div></div>`).join('')||'<div class="cmt-empty">Пока нет комментариев. Будьте первым.</div>'}
   <div class="cmt-new"><div class="cmt-av me">${rolesData[curRole].av}</div><textarea id="cmtInput" placeholder="Комментарий по заявке от лица «${roleNames[curRole]}»…"></textarea><button class="btn primary" onclick="addComment('${id}')">Отправить</button></div>
  </div>`;}
function addComment(id){const t=document.getElementById('cmtInput');const v=(t&&t.value||'').trim();if(!v)return;(comments[id]=comments[id]||[]).push({a:rolesData[curRole].nm,r:roleNames[curRole],t:'только что',txt:v});rCard();}
function rCard(){
 if(curCard.kind==='parent'){const p=parents.find(x=>x.code===curCard.id);
  document.getElementById('cardBody').innerHTML=`<div class="dhead"><div class="crumbs"><span class="pcode">${p.code}</span></div>
   <div class="top"><div><h1 style="font-family:var(--sans);font-size:20px">${p.title}</h1><div class="mt">Тип МТР: <b>${p.mtr}</b> · загрузка ${p.zagruzka} · срок <b>${p.srok}</b> · составитель ${p.sostavitel}</div></div><div class="hsp"></div><div class="htot"><div class="l">Ориентир. сумма</div><div class="v">— ₽</div></div></div>
   <div class="route">${ROUTE.map((l,i)=>`<div class="rnode ${i===0?'cur':''}"><div class="rdot">${i+1}</div><div class="rlab">${l}</div></div>${i<4?'<div class="rseg"></div>':''}`).join('')}</div></div>
   <div class="actbar"><span class="z">Зона — <b>${roleNames[curRole]}</b></span>${acts(curRole,'wait').map(a=>`<button class="btn ${a.p?'primary':''}" ${a.d?'disabled':''}>${a.t}</button>`).join('')}</div>
   <div class="dbody"><div class="empty-state"><b>${p.cancelled?'Заявка отменена':'Заявка ожидает закупки'}</b>${p.cancelled?'Снята с закупки комплектовщиком.':'Закупки ещё не взяли заявку в работу. По итогам торгов она будет разбита на дочерние заявки по поставщикам.'}</div>
   <div class="dsec-t">Позиции заявки · ${p.positions.length}</div>${posTable(p.positions)}${commentsHTML(p.code)}</div>`;return;}
 const {p,c}=findChild(curCard.id);const sof=SOF[c.stage];const total=childSum(c);const dPos=childDonePos(c),tPos=childTotalPos(c),pc=tPos?Math.round(dPos/tPos*100):0;
 const sibs=p.children.map(s=>`<span class="sib ${s.num===c.num?'on':''}" onclick="openCard('${s.num}')">${s.num}</span>`).join('');
 const route=ROUTE.map((l,i)=>{const cls=i<sof?'done':i===sof?'cur':'';return `<div class="rnode ${cls}"><div class="rdot">${i<sof?'✓':i+1}</div><div class="rlab">${l}</div></div>${i<4?`<div class="rseg ${i<sof?'fill':''}"></div>`:''}`;}).join('');
 let body='';
 if(c.stage==='proc'){body=`<div class="empty-state"><b>Идёт закупка</b>${c.statusZakup||'Сбор предложений на ЭТП'}. Поставщик ещё не выбран — поставки появятся после заключения контракта.</div><div class="dsec-t">Планируемые позиции · ${c.positions.length}</div>${posTable(c.positions)}`;}
 else{
   if(c.dels.length){body+='<div class="dsec-t">Поставки и позиции</div>';
     c.dels.forEach(d=>{const dpos=c.positions.filter(x=>x.deliv===d.n);const dsum=dpos.reduce((s,x)=>s+posSum(x),0);
       const docs=DOCKEYS.map(k=>`<span class="doctag ${d.docs[k]?'':'no'}">${DOCLAB[k]}</span>`).join('');
       const upd=d.upd?`<span class="updchip">${d.upd}</span>`:'';
       const payTxt=d.pay==='paid'?'оплачена '+(d.payDate||''):d.pay==='late'?'оплата просрочена':d.upd?'ожидает оплаты':'нет УПД';
       body+=`<div class="delivery"><div class="dl-head"><span class="dn">Поставка №${d.n} ${delChip(d.st)}${d.late?'<span class="chip late mini" style="margin-left:2px"><i></i>с задержкой</span>':''}</span><span class="sp"></span><span class="dw">${d.when}</span><span class="dsum">${RUB(dsum)}</span></div>
         ${posTable(dpos)}<div class="docrow">${docs}${upd}<span class="sp"></span><span class="cellsub mono">${payTxt}</span></div></div>`;});
   }
   const pend=c.positions.filter(x=>x.deliv===null);
   if(pend.length){const psum=pend.reduce((s,x)=>s+posSum(x),0);
     body+=`<div class="dsec-t" style="color:var(--late)">Ещё не поставлено · ожидают отгрузки<span class="sp"></span>${curRole==='soprov'?'<button class="btn sm">+ Создать поставку</button>':''}</div>
     <div class="delivery awaiting"><div class="dl-head aw"><span class="dn">Ожидают отгрузки <span class="bd">${pend.length} поз.</span></span><span class="sp"></span><span class="dsum">${RUB(psum)}</span></div>${posTable(pend)}</div>`;}
 }
 document.getElementById('cardBody').innerHTML=`<div class="dhead">
   <div class="crumbs"><span class="pcode">${p.code}</span> <span class="cellsub">${p.title} →</span> ${sibs}</div>
   <div class="top"><div><h1>${c.num} <small>${c.proc}</small></h1><div class="mt">${c.supplier} · ${c.lot} · контракт ${c.contract||'—'} · тип МТР <b>${p.mtr}</b></div></div><div class="hsp"></div><div class="htot"><div class="l">Сумма договора</div><div class="v">${RUB(total)}</div></div></div>
   <div class="route">${route}</div>
   <div class="dprog"><div class="pbar"><i style="width:${pc}%;background:${c.stage==='late'?'var(--late)':pc===100?'var(--ok)':'var(--supp)'}"></i></div><div class="ptx">Поставлено позиций: <b>${dPos} из ${tPos}</b> · ${pc===100?'все позиции получены':'заявка не закрыта'}</div></div></div>
   <div class="actbar"><span class="z">Зона — <b>${roleNames[curRole]}</b></span>${acts(curRole,c.stage).map(a=>`<button class="btn ${a.p?'primary':''}" ${a.d?'disabled':''}>${a.t}</button>`).join('')}<span class="hsp" style="flex:1"></span><button class="btn ghost">История</button></div>
   <div class="dbody">${body}${commentsHTML(c.num)}</div>`;
}

// ===== PAYMENTS =====
function paymentRecords(){const r=[];parents.forEach(p=>(p.children||[]).forEach(c=>c.dels.forEach(d=>{if(d.upd){const dpos=c.positions.filter(x=>x.deliv===d.n);const amt=dpos.reduce((s,x)=>s+posSum(x),0);r.push({upd:d.upd,pcode:p.code,ptitle:p.title,num:c.num,supplier:c.supplier,deln:d.n,pay:d.pay,payDate:d.payDate,amt,positions:dpos,contract:c.contract,docs:d.docs});}})));return r;}
function payFin(){const recs=paymentRecords();let inv=0,paid=0,out=0,late=0;recs.forEach(r=>{inv+=r.amt;if(r.pay==='paid')paid+=r.amt;else{out+=r.amt;if(r.pay==='late')late+=r.amt;}});let con=0,del=0;allChildren().forEach(({c})=>{con+=childSum(c);c.dels.forEach(d=>{if(d.st==='done')del+=c.positions.filter(x=>x.deliv===d.n).reduce((s,x)=>s+posSum(x),0);});});return{con,del,inv,paid,out,late,recs};}
function rPay(){const f=payFin();
 document.getElementById('payhero').innerHTML=`
  <div class="pcard" style="--c:var(--ink)"><div class="pl">Сумма в работе</div><div class="pv" style="color:var(--ink)">${RUB(f.con)}</div><div class="pvsub">по активным договорам</div></div>
  <div class="pcard" style="--c:var(--ok)"><div class="pl">Оплачено</div><div class="pv">${RUB(f.paid)}</div><div class="pvsub">${M(f.paid)}</div></div>
  <div class="pcard" style="--c:var(--proc)"><div class="pl">К оплате</div><div class="pv">${RUB(f.out)}</div><div class="pvsub">${f.recs.filter(r=>r.pay!=='paid').length} УПД</div></div>
  <div class="pcard" style="--c:var(--late)"><div class="pl">Просрочено</div><div class="pv">${RUB(f.late)}</div><div class="pvsub">требует оплаты</div></div>`;
 const delNoInv=Math.max(0,f.del-f.inv),conNoDel=Math.max(0,f.con-f.del);
 const segs=[['sp-paid',f.paid],['sp-out',f.out],['sp-del',delNoInv],['sp-con',conNoDel]];
 document.getElementById('pbar').innerHTML=segs.map(([cl,v])=>{const w=v/f.con*100;return w>1?`<span class="${cl}" style="width:${w}%">${w>11?M(v):''}</span>`:'';}).join('');
 const q=f.recs.slice().sort((a,b)=>(b.pay==='late')-(a.pay==='late')||(a.pay==='paid')-(b.pay==='paid'));
 document.getElementById('payRegSub').textContent=f.recs.length+' платежей · '+M(f.inv)+' ₽';
 document.getElementById('payBody').innerHTML=q.map(r=>{const age=r.pay==='paid'?('оплачена '+(r.payDate||'')):r.pay==='late'?'просрочено +4 дн':'в очереди';
  return `<tr onclick="openPay('${r.upd}')"><td><span class="updn">${r.upd}</span></td><td><span class="parent-tag">${r.pcode}</span> <span class="mono" style="font-size:12px">${r.num}</span></td><td>${r.supplier}</td><td><span class="cellsub">поставка №${r.deln}</span></td><td><span class="pchip ${r.pay==='paid'?'paid':r.pay}">${r.pay==='paid'?'Оплачена':r.pay==='late'?'Просрочена':'Ожидает оплаты'}</span></td><td class="r"><span class="age" style="color:${r.pay==='late'?'var(--late)':'var(--muted)'}">${age}</span></td><td class="r"><span class="amt">${RUB(r.amt)}</span></td></tr>`;}).join('');
 document.getElementById('payCount').textContent=f.recs.filter(r=>r.pay!=='paid').length;}
let curPay=null;
function openPay(upd){const r=paymentRecords().find(x=>x.upd===upd);if(!r)return;curPay=r;go('paycard');}
function rPayCard(){const r=curPay;if(!r)return;const docs=DOCKEYS.map(k=>`<span class="doctag ${r.docs[k]?'':'no'}">${DOCLAB[k]}</span>`).join('');const payZone=curRole==='oplata';
 document.getElementById('payCardBody').innerHTML=`<div class="pcd-h"><div class="top"><div><h1>${r.upd}</h1><div class="mt">${r.supplier} · заявка <b>${r.pcode} / ${r.num}</b> · поставка №${r.deln}</div></div><div class="sp"></div><div style="text-align:right"><div style="font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--faint);font-weight:600">Сумма к оплате</div><div class="amt-big" style="color:${r.pay==='late'?'var(--late)':r.pay==='paid'?'var(--ok)':'var(--proc)'}">${RUB(r.amt)}</div></div></div>
   <div style="margin-top:12px"><span class="pchip ${r.pay==='paid'?'paid':r.pay}">${r.pay==='paid'?'Оплачена '+(r.payDate||''):r.pay==='late'?'Оплата просрочена +4 дня':'Ожидает оплаты'}</span></div></div>
   <div class="pcd-meta"><div class="m"><div class="l">Договор</div><div class="v">${r.contract||'—'}</div></div><div class="m"><div class="l">Поставщик</div><div class="v" style="font-family:var(--sans);font-weight:500">${r.supplier}</div></div><div class="m"><div class="l">Связанная поставка</div><div class="v">№${r.deln}</div></div><div class="m"><div class="l">Документы</div><div class="v" style="display:flex;gap:5px;flex-wrap:wrap">${docs}</div></div></div>
   <div class="pcd-body"><div class="actbar" style="background:transparent;border:none;padding:0 0 14px">${payZone?`<button class="btn primary" ${r.pay==='paid'?'disabled':''}>Провести оплату</button><button class="btn">Выгрузить платёжку</button>`:'<span class="z">Оплату проводит отдел <b>Оплата</b></span>'}<button class="btn ghost" onclick="openCard('${r.num}')">К карточке заявки →</button></div>
   <div class="dsec-t">Позиции в составе УПД · ${r.positions.length}</div>${posTable(r.positions)}</div>`;}

// ===== REPORTS =====
let repType='time';
const repDefs=[{k:'time',t:'Время на этапе / зависания'},{k:'sums',t:'Суммы по этапам и поставщикам'},{k:'late',t:'Просрочки: поставки и оплаты'},{k:'people',t:'Сводка по составителям/отделам'}];
function rRepTypes(){document.getElementById('repTypes').innerHTML=repDefs.map(d=>`<div class="rep-opt ${d.k===repType?'on':''}" onclick="repType='${d.k}';rRepTypes();runReport()"><i></i>${d.t}</div>`).join('');}
function dayPill(d){const cls=d>=14?'bad':d>=10?'warn':'';return `<span class="daypill ${cls}">${d} дн.</span>`;}
function runReport(){const out=document.getElementById('repOut');let h='';
 if(repType==='time'){const rows=allChildren().filter(x=>x.c.stage!=='done');
   h=`<div class="rep-out-h"><h2>Время на этапе и зависания</h2><div class="sp"></div><div class="exp"><button>↧ Excel</button><button>↧ PDF</button><button>↧ CSV</button></div></div>
   <div class="rep-kpis"><div class="rep-kpi"><div class="l">Заявок в работе</div><div class="v">${rows.length}</div></div><div class="rep-kpi"><div class="l">Зависли &gt;14 дн.</div><div class="v" style="color:var(--late)">${rows.filter(x=>x.c.days>=14).length}</div></div><div class="rep-kpi"><div class="l">Ср. время на этапе</div><div class="v">${Math.round(rows.reduce((s,x)=>s+x.c.days,0)/rows.length)} дн.</div></div></div>
   <div class="tbl-scroll"><table class="rtbl"><thead><tr><th>Заявка</th><th>№</th><th>Поставщик</th><th>Этап</th><th class="r">Дней на этапе</th><th>Срок поставки</th></tr></thead><tbody>`;
   rows.sort((a,b)=>b.c.days-a.c.days).forEach(({p,c})=>{h+=`<tr><td><span class="parent-tag">${p.code}</span>${p.title}</td><td class="mono">${c.num}</td><td>${c.supplier==='—'?'<span class="cellsub">не выбран</span>':c.supplier}</td><td>${chip(c.stage)}</td><td class="r">${dayPill(c.days)}</td><td class="mono">${c.srokDD||p.srok}</td></tr>`;});
   h+=`</tbody></table></div>`;
 } else if(repType==='sums'){const byStage={proc:0,supp:0,pay:0},cnt={proc:0,supp:0,pay:0};allChildren().forEach(({c})=>{const k=c.stage==='late'?'supp':c.stage;if(byStage[k]!==undefined){byStage[k]+=childSum(c);cnt[k]++;}});
   const bySupp={};allChildren().forEach(({c})=>{if(c.supplier!=='—'){bySupp[c.supplier]=bySupp[c.supplier]||{sum:0,n:0};bySupp[c.supplier].sum+=childSum(c);bySupp[c.supplier].n++;}});const total=byStage.proc+byStage.supp+byStage.pay;
   h=`<div class="rep-out-h"><h2>Суммы по этапам и поставщикам</h2><div class="sp"></div><div class="exp"><button>↧ Excel</button><button>↧ PDF</button><button>↧ CSV</button></div></div>
   <div class="rep-kpis"><div class="rep-kpi"><div class="l">Всего по договорам</div><div class="v">${M(total)}</div></div><div class="rep-kpi"><div class="l">В сопровождении</div><div class="v" style="color:var(--supp)">${M(byStage.supp)}</div></div><div class="rep-kpi"><div class="l">В оплате</div><div class="v" style="color:var(--pay)">${M(byStage.pay)}</div></div></div>
   <div class="tbl-scroll"><table class="rtbl"><thead><tr><th>Этап</th><th class="r">Заявок</th><th class="r">Сумма договоров</th></tr></thead><tbody>
   <tr><td>${chip('proc')}</td><td class="r mono">${cnt.proc}</td><td class="r mono">${byStage.proc?RUB(byStage.proc):'—'}</td></tr>
   <tr><td>${chip('supp')}</td><td class="r mono">${cnt.supp}</td><td class="r mono">${RUB(byStage.supp)}</td></tr>
   <tr><td>${chip('pay')}</td><td class="r mono">${cnt.pay}</td><td class="r mono">${RUB(byStage.pay)}</td></tr>
   </tbody><tfoot><tr><td>Итого</td><td class="r">${cnt.proc+cnt.supp+cnt.pay}</td><td class="r">${RUB(total)}</td></tr></tfoot></table></div>
   <div class="dsec-t" style="padding:0 16px">По поставщикам</div><div class="tbl-scroll"><table class="rtbl"><thead><tr><th>Поставщик</th><th class="r">Заявок</th><th class="r">Сумма</th></tr></thead><tbody>
   ${Object.entries(bySupp).sort((a,b)=>b[1].sum-a[1].sum).map(([s,v])=>`<tr><td>${s}</td><td class="r mono">${v.n}</td><td class="r mono">${RUB(v.sum)}</td></tr>`).join('')}</tbody></table></div>`;
 } else if(repType==='late'){const lateDel=[],latePay=[];allChildren().forEach(({p,c})=>{c.dels.forEach(d=>{if(d.st==='late'||d.late)lateDel.push({p,c,d});if(d.pay==='late')latePay.push({p,c,d});});});
   h=`<div class="rep-out-h"><h2>Просрочки: поставки и оплаты</h2><div class="sp"></div><div class="exp"><button>↧ Excel</button><button>↧ PDF</button><button>↧ CSV</button></div></div>
   <div class="rep-kpis"><div class="rep-kpi"><div class="l">Просроч. поставок</div><div class="v" style="color:var(--late)">${lateDel.length}</div></div><div class="rep-kpi"><div class="l">Просроч. оплат</div><div class="v" style="color:var(--late)">${latePay.length}</div></div></div>
   <div class="dsec-t" style="padding:0 16px">Поставки</div><div class="tbl-scroll"><table class="rtbl"><thead><tr><th>Заявка</th><th>№</th><th>Поставщик</th><th>Поставка</th><th class="r">% позиций</th><th>Срок ДД</th></tr></thead><tbody>
   ${lateDel.map(({p,c,d})=>`<tr><td><span class="parent-tag">${p.code}</span>${p.title}</td><td class="mono">${c.num}</td><td>${c.supplier}</td><td class="mono">№${d.n}${d.late?' (с задержкой)':''}</td><td class="r">${ovdCell(c)}</td><td><span class="dt late">${c.srokDD}</span></td></tr>`).join('')||'<tr><td colspan="6" class="cellsub">нет</td></tr>'}
   </tbody></table></div>
   <div class="dsec-t" style="padding:0 16px">Оплаты</div><div class="tbl-scroll"><table class="rtbl"><thead><tr><th>УПД</th><th>Заявка</th><th>Поставщик</th><th class="r">Сумма</th></tr></thead><tbody>
   ${latePay.map(({p,c,d})=>{const amt=c.positions.filter(x=>x.deliv===d.n).reduce((s,x)=>s+posSum(x),0);return `<tr><td class="mono">${d.upd}</td><td><span class="parent-tag">${p.code}</span>${c.num}</td><td>${c.supplier}</td><td class="r mono" style="color:var(--late)">${RUB(amt)}</td></tr>`;}).join('')||'<tr><td colspan="4" class="cellsub">нет</td></tr>'}
   </tbody></table></div>`;
 } else {const by={};parents.forEach(p=>{const sum=(p.children||[]).reduce((s,c)=>s+childSum(c),0);by[p.sostavitel]=by[p.sostavitel]||{n:0,sub:0,sum:0,dept:p.dept};by[p.sostavitel].n++;by[p.sostavitel].sub+=(p.children||[]).length;by[p.sostavitel].sum+=sum;});
   h=`<div class="rep-out-h"><h2>Сводка по составителям / отделам</h2><div class="sp"></div><div class="exp"><button>↧ Excel</button><button>↧ PDF</button><button>↧ CSV</button></div></div>
   <div class="tbl-scroll"><table class="rtbl"><thead><tr><th>Составитель</th><th>Отдел</th><th class="r">Заявок (Т-)</th><th class="r">Доч. заявок</th><th class="r">Сумма договоров</th></tr></thead><tbody>
   ${Object.entries(by).map(([s,v])=>`<tr><td>${s}</td><td>${v.dept}</td><td class="r mono">${v.n}</td><td class="r mono">${v.sub}</td><td class="r mono">${v.sum?RUB(v.sum):'—'}</td></tr>`).join('')}</tbody></table></div>`;
 }
 out.innerHTML=h;}

// ===== NAV / ROLES =====
function setRole(r){curRole=r;document.getElementById('meRole').textContent=roleNames[r];document.getElementById('meName').textContent=rolesData[r].nm;document.getElementById('meAv').textContent=rolesData[r].av;const v=curView();if(v==='card')rCard();if(v==='paycard')rPayCard();}
function go(v){document.querySelectorAll('.view').forEach(x=>x.classList.remove('active'));document.getElementById('view-'+v).classList.add('active');
 const hl=v==='card'?cardOrigin:v==='paycard'?'pay':v;
 document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.dataset.v===hl));
 if(v==='card')rCard();if(v==='pay')rPay();if(v==='paycard')rPayCard();if(v==='rep'){rRepTypes();runReport();}
 window.scrollTo({top:0,behavior:'smooth'});}

rMeters();rFlow();rAlerts();rFeed();rDash();rPages();rPay();
