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
from catalog_generator import normalize_items,MANUFACTURER
from catalog_rules import catalog_summary,catalog_policy_summary,repertoire_summary
items=normalize_items([{'numeroItem':1,'descricao':'Cadeira giratória em tela Mesh, encosto mínimo 56 x 45 x 8 cm, apoio lombar, pistão classe 4. Revestimento tecido poliester gramatura tracao urdume','quantidade':1,'unidade':'UN'}],'https://pncp.gov.br/app/editais/12345678000199/2026/1')
print(json.dumps(dict(items=items,metadata={},documents=[],validation=dict(incompletos=0,conflitos=0,avisos=[]),catalog_summary=catalog_summary(items),catalog_policy=catalog_policy_summary(),repertoire=repertoire_summary(),warnings=[],manufacturer=MANUFACTURER)))
`], {cwd:path.join(root,'..'), encoding:'utf8'}));
const fixture = `import React from 'react';import {createRoot} from 'react-dom/client';
import {CatalogGeneratorBlock} from '/src/components/CatalogGeneratorBlock.tsx';import '/src/styles.css';
createRoot(document.getElementById('root')).render(React.createElement(CatalogGeneratorBlock,{
pncpLink:'https://pncp.gov.br/app/editais/12345678000199/2026/1',onPncpLinkChange:()=>{},
templates:[{id:'test',name:'Teste',size:1,updated_at:''}],selectedTemplateId:'test',onSelectedTemplateChange:()=>{}}));`;
(async()=>{
 const {createServer}=await import(pathToFileURL(path.join(root,'node_modules/vite/dist/node/index.js')));
 const vite=await createServer({root,server:{host:'127.0.0.1',port:5201},plugins:[{
 name:'catalog-library-test',resolveId(id){if(id==='virtual:catalog-test')return '\0catalog-test';},
 load(id){if(id==='\0catalog-test')return fixture;},
 configureServer(server){server.middlewares.use('/__catalog-test',async(_req,res)=>{
 res.setHeader('Content-Type','text/html');res.end(await server.transformIndexHtml('/__catalog-test','<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div><script type="module" src="/@id/virtual:catalog-test"></script></body></html>'));});}}]});
 let browser;
 try{
 await vite.listen();browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const job={id:'a'.repeat(32),pncp_link:'',status:'processing',stage:'analysis',progress:20,stages:[{id:'analysis',label:'Análise'}],result:null,error:''};
 await page.route('**/catalog-generator/jobs',r=>r.fulfill({json:job}));
 await page.route('**/catalog-generator/jobs/'+job.id,r=>r.fulfill({json:{...job,status:'ready',progress:100,result}}));
 await page.goto(vite.resolvedUrls.local[0]+'__catalog-test');
 await page.getByRole('button',{name:'Processar edital',exact:true}).click();
 const summary=page.locator('summary').filter({hasText:'Referências complementares'});
 await summary.click();
 const section=page.locator('details').filter({has:summary});
 assert.equal(await section.locator('li').count(),5);
 assert((await section.innerText()).includes('Não comprova atendimento automaticamente'));
 const output=path.join(root,'../reports/catalog-library');fs.mkdirSync(output,{recursive:true});
 await section.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,'desktop.png')});
 await page.setViewportSize({width:390,height:844});await section.scrollIntoViewIfNeeded();
 await page.screenshot({path:path.join(output,'mobile.png')});
 const box=await section.boundingBox();assert(box.x>=0&&box.x+box.width<=391);
 let requests=0;
 let releaseExport;
 const files=Object.fromEntries(['docx','pdf','xlsx','csv','json'].map(kind=>[kind,{filename:'catalog.'+kind,download_url:'/download/catalog.'+kind}]));
 await page.route('**/catalog-generator/jobs/'+job.id+'/export',async route=>{
   requests++;
   if(requests===1) await new Promise(resolve=>{releaseExport=resolve;});
   if(requests===2) return route.fulfill({status:500,json:{error:'Falha de teste'}});
   await route.fulfill({json:{items:result.items,exports:files}});
 });
 const generate=page.getByRole('button',{name:'Gerar catálogo e auditoria'});
 await generate.click();
 const dialog=page.getByRole('dialog',{name:'Baixar catálogo e auditoria'});
 await dialog.waitFor();
 await dialog.getByRole('status').filter({hasText:'Gerando arquivos'}).waitFor();
 while(!releaseExport) await new Promise(resolve=>setTimeout(resolve,10));
 releaseExport();
 await dialog.getByRole('link',{name:'Catálogo DOCX',exact:true}).waitFor();
 assert.equal(await dialog.getByRole('link').count(),5);
 for(const [kind,file] of Object.entries(files)) assert.equal(await dialog.locator(`a[href="${file.download_url}"][download]`).count(),1,kind);
 await page.screenshot({path:path.join(output,'downloads-mobile.png')});
 const dialogBox=await dialog.boundingBox();assert(dialogBox.x>=0&&dialogBox.x+dialogBox.width<=391);
 await page.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});
 await generate.click();await dialog.waitFor();assert.equal(requests,1,'Reopening must reuse ready files');
 await page.keyboard.press('Escape');
 await page.getByRole('textbox',{name:'Produto do item 1',exact:true}).fill('Cadeira alterada');
 await generate.click();await dialog.getByRole('alert').waitFor();
 assert.equal(await dialog.getByRole('link').count(),0,'No stale downloads after editing');
 await dialog.getByRole('button',{name:'Tentar novamente'}).click();
 await dialog.getByRole('link',{name:'Catálogo PDF',exact:true}).waitFor();
 assert.equal(requests,3);
 await page.setViewportSize({width:1440,height:1000});
 await page.screenshot({path:path.join(output,'downloads-desktop.png')});
 await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'Responder pendências',exact:true}).click();
 const form=page.locator('.catalog-generator-repertoire-form');
 const fields=form.locator('fieldset');
 assert.equal(await fields.count(),result.items[0].perguntas_pendentes.length);
 assert((await fields.count())>0);
 for(let i=0;i<1;i++){
   const field=fields.nth(i);
   assert(await field.getByLabel('Requisito ou pendência').getAttribute('readonly')!==null);
   await field.getByLabel('Atendimento ao requisito').selectOption('atende');
   await field.getByLabel('Especificação atendida pela Goldflex').fill('Configuração especial documentada pelo fabricante');
   await field.getByLabel('Evidência técnica').fill('Ficha técnica revisada, página 2');
 }
 await form.getByRole('checkbox').check();
 await page.setViewportSize({width:390,height:844});
 await fields.first().scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,'pending-mobile.png')});
 let savedItem;
 await page.route('**/catalog-generator/jobs/'+job.id+'/technical-repertoire',async route=>{
   const body=route.request().postDataJSON();
   savedItem=JSON.parse(execFileSync(path.join(deps,'python/python.exe'),['-c',
     'import sys,json; from catalog_rules import apply_user_catalog_repertoire; from server import validate_catalog_technical_repertoire; data=json.load(sys.stdin); record=validate_catalog_technical_repertoire(data["repertorio"]); record["id"]="f"*32; print(json.dumps(apply_user_catalog_repertoire(data["item"],record)))'
   ],{cwd:path.join(root,'..'),encoding:'utf8',env:{...process.env,PYTHONUTF8:'1'},input:JSON.stringify({item:result.items[0],repertorio:body.repertorio})}));
   await route.fulfill({json:{...job,status:'ready',progress:100,result:{...result,items:[savedItem]}}});
 });
 await form.getByRole('button',{name:'Salvar e reavaliar'}).click();await form.waitFor({state:'hidden'});
 assert(savedItem.perguntas_pendentes.length>0,'Unanswered fields must remain pending after a partial save');
 await page.getByRole('button',{name:'Responder pendências',exact:true}).click();
 for(let i=0;i<await fields.count();i++){
   const field=fields.nth(i);
   await field.getByLabel('Atendimento ao requisito').selectOption('atende');
   await field.getByLabel('Especificação atendida pela Goldflex').fill('Configuração especial documentada pelo fabricante');
   await field.getByLabel('Evidência técnica').fill('Ficha técnica revisada, página 2');
 }
 await form.getByRole('button',{name:'Salvar e reavaliar'}).click();await form.waitFor({state:'hidden'});
 assert.equal(savedItem.perguntas_pendentes.length,0);
 assert.equal(savedItem.observacao_repertorio.status,'evidencia_completa');
 assert.equal(savedItem.analise_aderencia.declaracao_atendimento_automatica,false);
 await page.getByRole('button',{name:'Editar régua técnica'}).waitFor();
 assert.deepEqual(errors,[]);console.log('PASS: real Block 7 references, backend retrieval, desktop/mobile, no browser errors.');
 }finally{if(browser)await browser.close();await vite.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
