const {createRequire} = require('node:module');
const {pathToFileURL} = require('node:url');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const deps = path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies');
const {chromium} = createRequire(path.join(deps, 'node/node_modules/package.json'))('playwright');
const pageParts = JSON.parse(execFileSync(path.join(deps,'python/python.exe'), ['-c',
  'import json; from proposal_template_preview import template_page_parts_preview; print(json.dumps(template_page_parts_preview("templates/modelo_proposta_goldflex.docx")))'
], {cwd:path.join(root,'..'),encoding:'utf8'}));
const fixture = `import React from 'react'; import {createRoot} from 'react-dom/client';
import {ProposalLivePreview} from '/src/components/ProposalLivePreview.tsx';
import '/src/styles.css';
const props = {
  nodes: [
    {id:'body',type:'MINI_BOX',content:'PROPOSTA COMERCIAL',order:0,text_align:'center',source_part:'word/document.xml'},
    {id:'header',type:'FIXED_TEXT',content:'CABECALHO ORIGINAL DO TEMPLATE',source_part:'word/header1.xml'},
    {id:'footer',type:'FIXED_TEXT',content:'RODAPE ORIGINAL DO TEMPLATE',source_part:'word/footer1.xml'}
  ],
  blockOrder:['body','table'], generatedTable:{id:'table',type:'GENERATED_TABLE',content:'Tabela'},
  items:Array.from({length:50},(_,i)=>({item:String(i+1),descricao:'Cadeira com apoio para os bracos e encosto ajustavel.',quantidade:'1',unidade:'UN',valor_unitario:'40,00',valor_total:'40,00'})),
  commercialTerms:{prazo_entrega:'30 dias',prazo_pagamento:'30 dias',validade_proposta:'60 dias'},
  miniBoxAlignments:{}, columnWidths:{}
};
if (location.search.includes('narrow')) {
  props.tableMetrics = {available_width_twips:8640,body_font_pt:9,header_font_pt:9,horizontal_padding_twips:40,narrow_padding_twips:20,vertical_padding_twips:80};
  props.items = [{item:'2',quantidade:'32',unidade:'UND',descricao:'Cadeira de teste com assento em espuma laminada, estrutura em aco, encosto ajustavel e acabamento pintado em epoxi.',marca:'rftgyh',valor_unitario:'R$ 234,00',valor_total:'R$ 7.488,00'}];
  props.columnWidths = {item:6,quantidade:6,unidade:6,descricao:55,marca:8,valor_unitario:9.5,valor_total:9.5};
}
if (location.search.includes('rich')) props.pagePartsPreview = ${JSON.stringify(pageParts)};
createRoot(document.getElementById('root')).render(React.createElement('div',{className:'proposal-retro'},React.createElement(ProposalLivePreview,props)));`;

(async () => {
  const {createServer} = await import(pathToFileURL(path.join(root, 'node_modules/vite/dist/node/index.js')));
  const vite = await createServer({root,server:{host:'127.0.0.1',port:0},plugins:[{
    name:'proposal-page-parts-fixture',
    resolveId(id) { if(id==='virtual:page-parts.tsx') return '\0page-parts.tsx'; },
    load(id) { if(id==='\0page-parts.tsx') return fixture; },
    configureServer(server) { server.middlewares.use('/__page-parts',async(_req,res)=>{
      res.setHeader('Content-Type','text/html');
      res.end(await server.transformIndexHtml('/__page-parts','<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div><script type="module" src="/@id/virtual:page-parts.tsx"></script></body></html>'));
    }); }
  }]});
  let browser;
  try {
    await vite.listen();
    browser = await chromium.launch({headless:true});
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror',error=>errors.push(error.message));
    const out = path.join(root,'../reports/proposal-page-parts');
    fs.mkdirSync(out,{recursive:true});
    let desktopLines;
    for(const [name,viewport] of [['desktop',{width:1280,height:900}],['mobile',{width:390,height:844}]]) {
      await page.setViewportSize(viewport);
      await page.goto(vite.resolvedUrls.local[0]+'__page-parts');
      await page.locator('.proposal-replica-page').first().waitFor();
      const lines = await page.locator('.proposal-replica-table').first().evaluate(table => {
        const scale = Number(getComputedStyle(table).zoom);
        return Array.from(table.querySelectorAll('th')).map(cell => {
          const range = document.createRange();
          range.selectNodeContents(cell);
          return ({
          text: cell.textContent,
          height: Math.round(cell.getBoundingClientRect().height / scale),
          font: getComputedStyle(cell).fontSize,
          lines: range.getClientRects().length,
        }); });
      });
      if (name === 'desktop') desktopLines = lines;
      else lines.forEach((line, index) => {
        assert.equal(line.lines, desktopLines[index].lines, 'viewport zoom must not change text wrapping');
        assert.equal(line.font, desktopLines[index].font);
        assert.ok(Math.abs(line.height - desktopLines[index].height) <= 2, 'allow pixel rounding, not another text line');
      });
      const pages = await page.locator('.proposal-replica-page').evaluateAll(nodes=>nodes.map(node=>{
        const header=node.querySelector('.proposal-replica-template-header');
        const footer=node.querySelector('.proposal-replica-template-footer');
        const body=node.querySelector('.proposal-replica-body');
        return {header:header.textContent,footer:footer.textContent,body:body.textContent,
          headerBottom:header.getBoundingClientRect().bottom,bodyTop:body.getBoundingClientRect().top,
          bodyBottom:body.getBoundingClientRect().bottom,footerTop:footer.getBoundingClientRect().top,
          footerBottom:footer.getBoundingClientRect().bottom,pageBottom:node.getBoundingClientRect().bottom};
      }));
      await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});
      assert.ok(pages.length>1);
      for(const value of pages) {
        assert.equal(value.header,'CABECALHO ORIGINAL DO TEMPLATE');
        assert.equal(value.footer,'RODAPE ORIGINAL DO TEMPLATE');
        assert.ok(!value.body.includes('ORIGINAL DO TEMPLATE'));
        assert.ok(value.headerBottom<=value.bodyTop);
        assert.ok(value.bodyBottom<=value.footerTop);
        assert.ok(value.footerBottom<value.pageBottom,JSON.stringify(value));
      }
      await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});
      console.log(name+': '+pages.length+' pages, original header/footer present without overlap');
      await page.goto(vite.resolvedUrls.local[0]+'__page-parts?narrow');
      await page.locator('.proposal-replica-table').first().waitFor();
      await page.screenshot({path:path.join(out,name+'-narrow.png'),fullPage:true});
      await page.goto(vite.resolvedUrls.local[0]+'__page-parts?rich');
      const originalHeader=page.getByLabel('Cabeçalho original do template', {exact:true}).first();
      await originalHeader.locator('img').first().waitFor();
      await page.evaluate(()=>document.fonts.ready);
      const details=await originalHeader.evaluate(host=>{
        const root=host.shadowRoot;
        const image=root.querySelector('img');
        const paragraph=Array.from(root.querySelectorAll('p')).find(p=>p.textContent.includes('GOLDFLEX INDUSTRIA'));
        const page=host.closest('.proposal-replica-page').getBoundingClientRect();
        const imgBox=image.getBoundingClientRect(),textBox=paragraph.getBoundingClientRect();
        const lineMap=new Map();
        const walker=document.createTreeWalker(paragraph,NodeFilter.SHOW_TEXT);
        while(walker.nextNode()) {
          const text=walker.currentNode;
          for(let i=0;i<text.textContent.length;i++) {
            const range=document.createRange();range.setStart(text,i);range.setEnd(text,i+1);
            const rect=range.getBoundingClientRect();
            if(!rect.height)continue;
            const key=Math.round(rect.top*10)/10;
            lineMap.set(key,(lineMap.get(key)||'')+text.textContent[i]);
          }
        }
        return {imageLoaded:image.complete&&image.naturalWidth>0,align:getComputedStyle(paragraph).textAlign,
          breaks:paragraph.querySelectorAll('br').length,logoLeft:imgBox.right<=textBox.left,
          pageRight:page.right,textRight:textBox.right,headerText:paragraph.textContent,
          font:getComputedStyle(paragraph.querySelector('span')||paragraph).font,
          physicalParagraphWidth:getComputedStyle(paragraph).width,
          textLines:Array.from(lineMap.values()).map(value=>value.replace(/\s+/g,' ').trim()).filter(Boolean)};
      });
      assert(details.imageLoaded,'Original logo must render');
      assert.equal(details.align,'center','Original paragraph alignment must remain centered');
      assert.equal(details.breaks,3,'Preserve explicit Word line breaks, not guessed categories');
      assert(details.logoLeft,'Logo remains on the left of the company text');
      assert(details.textRight<=details.pageRight+2,'Header must fit the white page');
      assert(details.headerText.includes('licitagoldflex@gmail.com'));
      await page.screenshot({path:path.join(out,name+'-rich.png')});
      const count=await page.locator('.proposal-replica-page').count();
      assert.equal(await page.locator('.proposal-template-page-part img').count(),count,'Logo repeats on every page');
      console.log(name+': original logo, center alignment, line breaks and page bounds verified');
      console.log('Header typography:',details.font,details.physicalParagraphWidth);
      fs.writeFileSync(path.join(out,name+'-header.json'),JSON.stringify(details,null,2));
    }
    assert.deepEqual(errors,[]);
  } finally {
    await browser?.close();
    await vite.close();
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
