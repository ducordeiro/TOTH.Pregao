const {createRequire} = require('node:module');
const {pathToFileURL} = require('node:url');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const deps = path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies');
const {chromium} = createRequire(path.join(deps, 'node/node_modules/package.json'))('playwright');
const object = 'Aquisição de CADEIRAS, cadeira giratória e roçadeira. <b>Texto original</b>';
const bid = {id:'a'.repeat(32), cnpj:'12345678000199', ano:2026, sequencial:1,
  link:'https://pncp.gov.br/app/editais/12345678000199/2026/1', source:'pncp',
  numeroCompra:'01/2026', orgao:'Prefeitura de Teste', municipio:'Mogi Mirim', uf:'SP',
  objeto:object, itensIndexados:true, itemCount:1};
const detail = {oportunidade:{objeto:object, categorias:[], orgao:bid.orgao,
  unidade:bid.orgao, portal_origem:'PNCP', modalidade:'Pregão', numero_compra:'01/2026',
  link_pncp:bid.link, abertura:'', encerramento:'', valor_total_estimado:100},
  itens:[{numero:'1', lote:'', descricao:'Cadeira giratória; cadeiras. roçadeira',
    quantidade:'1', unidade:'UN', valor_unitario_estimado:100, valor_total_estimado:100}],
  arquivos:[], fontes:{itens:'Banco local', oportunidade:'Banco local', arquivos:'Banco local'}};
const fixture = `import React from 'react';import {createRoot} from 'react-dom/client';
import {SearchBlock} from '/src/components/SearchBlock.tsx';import '/src/styles.css';
createRoot(document.getElementById('root')).render(React.createElement(SearchBlock,{
onUseLink:()=>{},onGenerateProposal:()=>{},onGenerateCatalog:()=>{}}));`;

(async () => {
  const {createServer} = await import(pathToFileURL(path.join(root, 'node_modules/vite/dist/node/index.js')));
  const vite = await createServer({root, server:{host:'127.0.0.1', port:0}, plugins:[{
    name:'keyword-highlight-fixture',
    resolveId(id) { if(id==='virtual:keyword-test') return '\0keyword-test'; },
    load(id) { if(id==='\0keyword-test') return fixture; },
    configureServer(server) { server.middlewares.use('/__keyword-test', async (_req,res) => {
      res.setHeader('Content-Type','text/html');
      res.end(await server.transformIndexHtml('/__keyword-test', '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div><script type="module" src="/@id/virtual:keyword-test"></script></body></html>'));
    }); },
  }]});
  let browser;
  try {
    await vite.listen();
    browser = await chromium.launch({headless:true});
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.route('**/internal/opportunities?**', (route) => route.fulfill({json:{results:[bid], total:1, pagina:1, total_pages:1}}));
    await page.route('**/pncp-search?**', (route) => route.fulfill({json:{results:[], total:0, complete:true, searching:false}}));
    await page.route('**/internal/opportunities/'+bid.id+'?**', (route) => route.fulfill({json:detail}));
    const out = path.join(root, '../reports/keyword-highlight');
    fs.mkdirSync(out, {recursive:true});
    for (const [name, viewport] of [['desktop',{width:1440,height:1000}], ['mobile',{width:390,height:844}]]) {
      await page.setViewportSize(viewport);
      await page.goto(vite.resolvedUrls.local[0]+'__keyword-test');
      const input = page.getByPlaceholder('Ex.: cadeira de rodas; monitor;');
      await input.fill('cadeira');
      await page.getByRole('button',{name:'Buscar contratações',exact:true}).click();
      const cell = page.locator('.description-cell');
      await cell.waitFor();
      assert.equal(await cell.textContent(), object);
      assert.deepEqual(await cell.locator('.search-keyword-hit').allTextContents(), ['CADEIRAS','cadeira']);
      await input.fill('mesa');
      assert.equal(await cell.locator('.search-keyword-hit').count(), 2, 'draft must not change previous search highlights');
      await page.screenshot({path:path.join(out,name+'-results.png'),fullPage:true});
      await page.locator('.search-result-row').click();
      await page.locator('.opportunity-object .search-keyword-hit').first().waitFor();
      assert.equal(await page.locator('.opportunity-object').textContent(), object);
      const styles = await page.locator('.opportunity-item strong .search-keyword-hit').first().evaluate((node) => {
        const hit = getComputedStyle(node), parent = getComputedStyle(node.parentElement);
        return {color:hit.color, size:hit.fontSize, parentSize:parent.fontSize, weight:hit.fontWeight, parentWeight:parent.fontWeight};
      });
      assert.equal(styles.color, 'rgb(0, 229, 255)');
      assert.equal(styles.size, styles.parentSize);
      assert.equal(styles.weight, styles.parentWeight);
      await page.screenshot({path:path.join(out,name+'-detail.png'),fullPage:true});
    }
    assert.deepEqual(errors, []);
    console.log('PASS: desktop/mobile highlights, original text, color/font, detail items and draft isolation');
  } finally {
    await browser?.close();
    await vite.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
