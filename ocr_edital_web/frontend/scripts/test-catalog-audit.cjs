const {createRequire} = require('node:module');
const {pathToFileURL} = require('node:url');
const {execFileSync} = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const deps = path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies');
const {chromium} = createRequire(path.join(deps, 'node/node_modules/package.json'))('playwright');
const result = JSON.parse(execFileSync(path.join(deps, 'python/python.exe'), ['-c', `
import json
from catalog_generator import normalize_items, MANUFACTURER
from catalog_rules import catalog_summary, catalog_policy_summary, repertoire_summary
items=normalize_items([{'numeroItem':n,'descricao':'Cadeira giratoria em tela Mesh, apoio lombar, pistao classe 4','quantidade':1,'unidade':'UN'} for n in (1,2)], 'offline:qa')
print(json.dumps(dict(items=items,metadata={},documents=[],validation=dict(incompletos=0,conflitos=0,avisos=[]),catalog_summary=catalog_summary(items),catalog_policy=catalog_policy_summary(),repertoire=repertoire_summary(),warnings=[],manufacturer=MANUFACTURER)))
`], {cwd:path.join(root,'..'), encoding:'utf8'}));
const fixture = `import React,{useState} from 'react';import {createRoot} from 'react-dom/client';
import {CatalogGeneratorBlock} from '/src/components/CatalogGeneratorBlock.tsx';import '/src/styles.css';
function Fixture(){const [link,setLink]=useState('https://pncp.gov.br/app/editais/12345678000199/2026/1');return React.createElement(CatalogGeneratorBlock,{pncpLink:link,onPncpLinkChange:setLink,templates:[{id:'test',name:'Teste',size:1,updated_at:''}],selectedTemplateId:'test',onSelectedTemplateChange:()=>{}});}
createRoot(document.getElementById('root')).render(React.createElement(Fixture));`;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const metrics = {};

(async () => {
  const {createServer} = await import(pathToFileURL(path.join(root,'node_modules/vite/dist/node/index.js')));
  const vite = await createServer({root, server:{host:'127.0.0.1', port:0}, plugins:[{
    name:'catalog-audit-test', resolveId(id){if(id==='virtual:catalog-audit.tsx')return '\0catalog-audit.tsx';},
    load(id){if(id==='\0catalog-audit.tsx')return fixture;},
    configureServer(server){server.middlewares.use('/__catalog-audit', async (_req,res)=>{
      res.setHeader('Content-Type','text/html');res.end(await server.transformIndexHtml('/__catalog-audit','<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div><script type="module" src="/@id/virtual:catalog-audit.tsx"></script></body></html>'));
    });}
  }]});
  let browser;
  try {
    await vite.listen(); browser = await chromium.launch({headless:true});
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[]; page.on('pageerror', error=>errors.push(error.message));
    const job={id:'b'.repeat(32),status:'processing',stage:'analysis',progress:20,stages:[{id:'analysis',label:'Analise'}],result:null,error:''};
    let mode='slow', calls=0, active=0, peak=0, delivered=0;
    let payload=result;
    await page.route('**/catalog-generator/jobs',route=>route.fulfill({json:job}));
    await page.route('**/catalog-generator/jobs/'+job.id,async route=>{
      calls++; active++; peak=Math.max(peak,active);
      try {
        if(mode==='slow' || mode==='cancel') await delay(2400);
        if(mode==='recover' && calls===1) return await route.fulfill({status:503,json:{error:'Falha simulada'}});
        delivered=performance.now();
        await route.fulfill({json:{...job,status:'ready',progress:100,result:payload}});
      } catch(error) { if(!/closed|disposed|intercept|Invalid|aborted/i.test(String(error))) throw error; }
      finally { active--; }
    });
    const start = async () => {
      calls=0; peak=0;
      await page.goto(vite.resolvedUrls.local[0]+'__catalog-audit');
      await page.getByRole('button',{name:'Processar edital',exact:true}).click();
    };
    await start();
    await page.getByRole('textbox',{name:'Produto do item 1',exact:true}).waitFor();
    assert.equal(peak,1,'Slow polling must never overlap requests');
    assert.equal(calls,1,'Do not enqueue redundant polls while a request is pending');
    metrics.slow_poll_peak=peak;
    mode='recover'; await start();
    await page.getByText('Falha simulada',{exact:true}).waitFor();
    await page.getByRole('textbox',{name:'Produto do item 1',exact:true}).waitFor();
    assert.equal(await page.getByText('Falha simulada',{exact:true}).count(),0,'A recovered poll must clear its previous error');
    let releaseSave;
    await page.route('**/catalog-generator/jobs/'+job.id+'/technical-repertoire',async route=>{
      await new Promise(resolve=>{releaseSave=resolve;});
      await route.fulfill({json:{...job,status:'ready',result}});
    });
    const ownQuantity=page.getByRole('textbox',{name:'Quantidade do item 1',exact:true});
    const otherProduct=page.getByRole('textbox',{name:'Produto do item 2',exact:true});
    await ownQuantity.fill('99'); await otherProduct.fill('Edicao local preservada');
    await page.getByRole('button',{name:'Responder pendências',exact:true}).first().click();
    const form=page.locator('.catalog-generator-repertoire-form');
    const field=form.locator('fieldset').first();
    await field.getByLabel('Atendimento ao requisito').selectOption('atende');
    await field.getByLabel('Especificação atendida pela Goldflex').fill('Configuracao documentada');
    await field.getByLabel('Evidência técnica').fill('Ficha de teste, pagina 2');
    await form.getByRole('button',{name:'Salvar e reavaliar'}).click();
    while(!releaseSave) await delay(10);
    assert(await ownQuantity.isDisabled(),'Cannot edit item inputs while repertoire is being saved');
    releaseSave(); await form.waitFor({state:'hidden'});
    assert.equal(await ownQuantity.inputValue(),'99','Saving repertoire preserves edited quantity');
    assert.equal(await otherProduct.inputValue(),'Edicao local preservada','Saving item 1 preserves edited item 2');
    mode='cancel'; await start();
    while(!active) await delay(10);
    await page.getByRole('textbox',{name:'Link do edital no PNCP',exact:true}).fill('https://pncp.gov.br/app/editais/12345678000199/2026/2');
    await delay(2600);
    assert.equal(await page.getByRole('textbox',{name:'Produto do item 1',exact:true}).count(),0,'Stale analysis must not reappear after changing the link');
    mode='fast';
    payload={...result,items:Array.from({length:50},(_,i)=>({...result.items[0],id:'qa-'+i,numero:String(i+1)}))};
    await start();
    await page.getByRole('textbox',{name:'Produto do item 50',exact:true}).waitFor();
    metrics.render_50_items_ms=+(performance.now()-delivered).toFixed(2);
    const edits=[];
    await page.getByRole('textbox',{name:'Produto do item 1',exact:true}).scrollIntoViewIfNeeded();
    await page.getByRole('textbox',{name:'Produto do item 1',exact:true}).fill('Aquecimento da edicao');
    for(let i=0;i<10;i++) {
      const before=performance.now();
      await page.getByRole('textbox',{name:'Produto do item 1',exact:true}).fill('Cadeira revisada '+i);
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      edits.push(performance.now()-before);
    }
    metrics.edit_50_items_p95_ms=+edits.sort((a,b)=>a-b)[9].toFixed(2);
    metrics.edit_samples_ms=edits.map(value=>+value.toFixed(2));
    const output=path.join(root,'../reports/catalog-audit'); fs.mkdirSync(output,{recursive:true});
    await page.screenshot({path:path.join(output,'desktop.png')});
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(output,'mobile.png')});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'No horizontal page overflow on mobile');
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(output,'browser.json'),JSON.stringify(metrics,null,2));
    console.log('PASS Block 7: polling, recovery, edit preservation, cancellation, 50 items, mobile.',metrics);
  } finally { if(browser) await browser.close(); await vite.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
