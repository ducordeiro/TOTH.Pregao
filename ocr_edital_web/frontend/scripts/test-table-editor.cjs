const { createRequire } = require('node:module');
const { pathToFileURL } = require('node:url');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const runtime = process.env.CODEX_NODE_MODULES || path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const { chromium } = createRequire(path.join(runtime, 'package.json'))('playwright');
const root = path.resolve(__dirname, '..');
const output = path.resolve(root, '../reports/table-editor');
const fixture = `
import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ProposalColumnModal } from '/src/components/ProposalColumnModal.tsx';
import { ProposalLivePreview } from '/src/components/ProposalLivePreview.tsx';
import '/src/styles.css';
const initial = [
 {item:'1',quantidade:'2',unidade:'UND',descricao:'Cadeira com apoio para os braços',marca:'Goldflex',valor_unitario:'R$ 10,00',valor_total:'R$ 20,00'},
 {item:'2',quantidade:'1',unidade:'UND',descricao:'Mesa de escritório',marca:'Goldflex',valor_unitario:'R$ 50,00',valor_total:'R$ 50,00'},
];
function Harness() {
 const [items,setItems]=useState(initial),[layout,setLayout]=useState(null),[open,setOpen]=useState(true),[widths,setWidths]=useState({});
 return React.createElement('div',{className:'proposal-retro'},
 React.createElement('button',{onClick:()=>setOpen(true)},'Abrir editor'),
 React.createElement(ProposalLivePreview,{nodes:[],blockOrder:['table'],generatedTable:{id:'table',type:'GENERATED_TABLE',content:'Tabela gerada'},items,
 commercialTerms:{prazo_entrega:'30 dias',prazo_pagamento:'30 dias',validade_proposta:'60 dias'},
 miniBoxAlignments:{},columnWidths:widths,tableLayout:layout}),
 open && React.createElement(ProposalColumnModal,{items,column:null,layout,widths,onClose:()=>setOpen(false),onSave:(next,config,nextWidths)=>{
 setItems(next);setLayout(config);setWidths(nextWidths);setOpen(false);window.savedTable={items:next,layout:config,widths:nextWidths};
 }}));
}
createRoot(document.getElementById('root')).render(React.createElement(Harness));
`;

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const { createServer } = await import(pathToFileURL(path.join(root, 'node_modules/vite/dist/node/index.js')));
  const vite = await createServer({ root, server: { host: '127.0.0.1', port: 5199 }, plugins: [{
    name: 'table-editor-test-fixture',
    resolveId(id) { if (id === 'virtual:table-editor-test') return '\0virtual:table-editor-test'; },
    load(id) { if (id === '\0virtual:table-editor-test') return fixture; },
    configureServer(server) { server.middlewares.use('/__table-editor-test', async (_req,res) => {
      res.setHeader('Content-Type','text/html');
      res.end(await server.transformIndexHtml('/__table-editor-test','<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"/></head><body><div id="root"></div><script type="module" src="/@id/virtual:table-editor-test"></script></body></html>'));
    }); },
  }] });
  let browser;
  try {
    await vite.listen();
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors=[];page.on('pageerror', e=>errors.push(e.message));
    await page.goto(vite.resolvedUrls.local[0] + '__table-editor-test');
    const dialog=page.getByRole('dialog');
    await dialog.getByRole('heading',{name:'Editar tabela',exact:true}).waitFor();
    const firstColumn = dialog.locator('col').first();
    const originalWidth = await firstColumn.evaluate(el=>el.getBoundingClientRect().width);
    const handle = dialog.getByRole('button',{name:/Redimensionar colunas/}).first();
    await handle.press('ArrowRight');
    assert((await firstColumn.evaluate(el=>el.getBoundingClientRect().width)) > originalWidth);
    await page.screenshot({path:path.join(output,'desktop.png')});
    const description=dialog.getByRole('textbox',{name:'DESCRIÇÃO, linha 1',exact:true});
    await description.fill('Mudança descartada');
    await dialog.getByRole('button',{name:'Cancelar',exact:true}).click();
    assert.equal(await dialog.count(),0);
    await page.getByRole('button',{name:'Abrir editor'}).click();
    assert(Math.abs((await firstColumn.evaluate(el=>el.getBoundingClientRect().width))-originalWidth)<1);
    const grip = await handle.boundingBox();
    await page.mouse.move(grip.x+grip.width/2,grip.y+grip.height/2);
    await page.mouse.down();
    await page.mouse.move(grip.x+grip.width/2+30,grip.y+grip.height/2,{steps:8});
    await page.mouse.up();
    assert((await firstColumn.evaluate(el=>el.getBoundingClientRect().width)) > originalWidth+10);
    await dialog.getByRole('button',{name:'Salvar',exact:true}).click();
    assert.equal(await page.locator('.proposal-live-preview .proposal-column-resizer').count(),0);
    const resized = await page.evaluate(()=>window.savedTable.widths.item);
    await page.getByRole('button',{name:'Abrir editor'}).click();
    assert((await firstColumn.evaluate(el=>el.getBoundingClientRect().width)) > originalWidth+10);
    await dialog.getByRole('button',{name:'Restaurar largura das colunas',exact:true}).click();
    assert(Math.abs((await firstColumn.evaluate(el=>el.getBoundingClientRect().width))-originalWidth)<1);
    assert(resized>0);
    assert.equal(await description.inputValue(),'Cadeira com apoio para os braços');
    await description.fill('Cadeira editada');
    await dialog.getByRole('textbox',{name:'Título da coluna 4',exact:true}).fill('Produto');
    await dialog.getByRole('textbox',{name:'QTD, linha 1',exact:true}).fill('3abc');
    assert.equal(await dialog.getByRole('textbox',{name:'QTD, linha 1',exact:true}).inputValue(),'3');
    await dialog.getByRole('button',{name:'Adicionar coluna',exact:true}).click();
    await dialog.getByRole('textbox',{name:'Título da coluna 8',exact:true}).fill('Modelo');
    await dialog.getByRole('textbox',{name:'Modelo, linha 1',exact:true}).fill('GF-01');
    await dialog.getByRole('button',{name:'Adicionar coluna',exact:true}).click();
    await dialog.getByRole('textbox',{name:'Título da coluna 9',exact:true}).fill('Garantia');
    await dialog.getByRole('textbox',{name:'Garantia, linha 1',exact:true}).fill('12 meses');
    await dialog.getByRole('button',{name:'Remover coluna',exact:true}).click();
    await dialog.getByRole('button',{name:'Remover coluna 5: MARCA',exact:true}).click();
    await dialog.getByRole('button',{name:'Salvar',exact:true}).click();
    const saved=await page.evaluate(()=>window.savedTable);
    assert.equal(saved.items[0].descricao,'Cadeira editada');
    assert.equal(saved.items[0].valor_total,'R$ 30,00');
    assert.equal(saved.layout.columns.length,8);
    assert(!saved.layout.columns.some(c=>c.key==='marca'));
    assert.equal(await page.locator('.proposal-replica-table th').filter({hasText:'Garantia'}).count(),1);
    await page.getByRole('button',{name:'Abrir editor'}).click();
    assert.equal(await dialog.getByRole('textbox',{name:'Modelo, linha 1',exact:true}).inputValue(),'GF-01');
    await dialog.getByRole('button',{name:'Remover coluna',exact:true}).click();
    await page.screenshot({path:path.join(output,'remove-column.png')});
    await dialog.getByRole('button',{name:'Cancelar',exact:true}).click();
    await page.setViewportSize({width:390,height:844});
    await page.getByRole('button',{name:'Abrir editor'}).click();
    await dialog.getByRole('button',{name:'Salvar',exact:true}).scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(output,'mobile.png')});
    const bounds=await dialog.boundingBox();assert(bounds.x>=0 && bounds.x+bounds.width<=391);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false);
    await dialog.getByRole('button',{name:'Remover coluna',exact:true}).click();
    const target=dialog.getByRole('button',{name:/^Remover coluna \d+:/}).first();
    for(let count=8;count>1;count--){ await target.click(); if(count>2) await dialog.getByRole('button',{name:'Remover coluna',exact:true}).click(); }
    assert(await dialog.getByRole('button',{name:'Remover coluna',exact:true}).isDisabled());
    await dialog.getByRole('button',{name:'Cancelar',exact:true}).click();
    assert.deepEqual(errors,[]);
    console.log('PASS: cancel/save, edited cells and headers, numeric totals, multiple columns, removal, reopen, desktop/mobile.');
  } finally { if(browser) await browser.close(); await vite.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
