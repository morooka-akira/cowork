#!/usr/bin/env node
// notion-import.js — Notion REST API 直接インポートスクリプト
// 使い方: node notion-import.js <batch-dir> [start] [end]
// 例:     node notion-import.js ./tmp/ng10 059 282
// NOTION_API_KEY を .env または環境変数で設定すること
// インポート済みIDは ./imported-ids.txt に追記され、重複スキップに使用される

'use strict';

const https = require('https');
const fs = require('fs');
const path = require('path');

// .env ファイルを読み込む（dotenv不要）
const envPath = path.join(__dirname, '.env');
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, 'utf8').split('\n')) {
    const m = line.match(/^([^=\s#][^=]*)=(.*)$/);
    if (m) process.env[m[1].trim()] = m[2].trim();
  }
}

const API_KEY = process.env.NOTION_API_KEY;
if (!API_KEY) {
  console.error('ERROR: NOTION_API_KEY が未設定です。.env ファイルか環境変数で設定してください。');
  process.exit(1);
}

const DB_ID = '33daf136-accb-8052-83ab-e06a410484cc';
const DELAY_MS = 350; // ~2.8 req/s
const IDS_FILE = path.join(__dirname, 'imported-ids.txt');

// インポート済みIDをファイルからロード
function loadImportedIds() {
  if (!fs.existsSync(IDS_FILE)) return new Set();
  const lines = fs.readFileSync(IDS_FILE, 'utf8').split('\n').map(l => l.trim()).filter(Boolean);
  return new Set(lines);
}

// インポート済みIDをファイルに追記
function recordImportedId(id) {
  fs.appendFileSync(IDS_FILE, id + '\n', 'utf8');
}

// サロゲートペア（絵文字など U+10000+）を除去して長さを制限
function sanitize(s, limit = 2000) {
  if (!s) return '';
  return s.replace(/[\uD800-\uDFFF]/g, '').slice(0, limit);
}

// Notion ページURLからページIDを抽出（ダッシュなし32文字）
function extractPageId(url) {
  const m = (url || '').match(/([a-f0-9]{32})/i);
  return m ? m[1] : null;
}

// batch JSON の properties を Notion REST API 形式に変換
function toNotionProperties(props, listPageId) {
  const p = {};

  p['名前'] = { title: [{ text: { content: sanitize(props['名前'] || '') } }] };

  for (const f of ['recruit-marker-id', '会社/役職', 'プロフィール']) {
    p[f] = { rich_text: [{ text: { content: sanitize(props[f] || '', f === 'プロフィール' ? 500 : 2000) } }] };
  }

  for (const f of ['X', 'GitHub', 'リンク', 'Wantedly', 'Google', 'Facebook', 'LinkedIn']) {
    if (props[f]) p[f] = { url: props[f] };
  }

  p['ステータス'] = { select: { name: props['ステータス'] || 'アプローチ前' } };

  if (listPageId) {
    p['リスト'] = { relation: [{ id: listPageId }] };
  }

  return p;
}

// Notion API POST /v1/pages
function notionPost(body) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const req = https.request({
      hostname: 'api.notion.com',
      path: '/v1/pages',
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${API_KEY}`,
        'Content-Type': 'application/json',
        'Notion-Version': '2022-06-28',
        'Content-Length': Buffer.byteLength(data),
      },
    }, (res) => {
      let raw = '';
      res.on('data', c => raw += c);
      res.on('end', () => resolve({ status: res.statusCode, raw }));
    });
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

// 1候補者を登録（429 リトライあり）
async function createPage(props, listPageId) {
  const body = {
    parent: { database_id: DB_ID },
    properties: toNotionProperties(props, listPageId),
  };

  for (let attempt = 0; attempt < 4; attempt++) {
    const { status, raw } = await notionPost(body);
    if (status === 200 || status === 201) return { ok: true };
    if (status === 429) {
      const wait = Math.pow(2, attempt) * 1500;
      process.stderr.write(`\n  [429] ${wait}ms 待機...\n`);
      await sleep(wait);
      continue;
    }
    let msg = raw;
    try { msg = JSON.parse(raw).message || raw; } catch {}
    return { ok: false, error: `HTTP ${status}: ${msg.slice(0, 120)}` };
  }
  return { ok: false, error: '429 リトライ上限' };
}

// メイン
async function main() {
  const [batchDirArg, startArg, endArg] = process.argv.slice(2);
  if (!batchDirArg) {
    console.error('使い方: node notion-import.js <batch-dir> [start] [end]');
    process.exit(1);
  }

  const batchDir = path.resolve(batchDirArg);
  let files = fs.readdirSync(batchDir)
    .filter(f => /^nb\d+\.json$/.test(f))
    .sort();

  if (startArg || endArg) {
    const start = startArg ? parseInt(startArg, 10) : 0;
    const end = endArg ? parseInt(endArg, 10) : Infinity;
    files = files.filter(f => {
      const n = parseInt(f.match(/nb(\d+)/)[1], 10);
      return n >= start && n <= end;
    });
  }

  if (files.length === 0) {
    console.log('対象ファイルなし');
    return;
  }

  // インポート済みIDをロード
  const importedIds = loadImportedIds();
  console.log(`📂 ${batchDir}`);
  console.log(`📋 対象: ${files.length} ファイル (${files[0]} 〜 ${files[files.length - 1]})`);
  console.log(`🗂  既インポート済みID: ${importedIds.size}件（スキップ対象）`);
  console.log('');

  let totalOk = 0, totalSkip = 0, totalErr = 0;

  for (const file of files) {
    const filePath = path.join(batchDir, file);
    let candidates;
    try {
      candidates = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    } catch (e) {
      console.error(`[${file}] 読み込みエラー: ${e.message}`);
      totalErr++;
      continue;
    }

    let fileOk = 0, fileSkip = 0, fileErr = 0;

    for (let i = 0; i < candidates.length; i++) {
      const { properties: props } = candidates[i];
      const name = props['名前'] || '(名前なし)';
      const rmId = props['recruit-marker-id'] || '';

      // 重複スキップ
      if (rmId && importedIds.has(rmId)) {
        fileSkip++;
        totalSkip++;
        continue;
      }

      let listPageId = null;
      try {
        const urls = JSON.parse(props['リスト'] || '[]');
        if (urls[0]) listPageId = extractPageId(urls[0]);
      } catch {}

      const result = await createPage(props, listPageId);

      if (result.ok) {
        fileOk++;
        totalOk++;
        if (rmId) {
          importedIds.add(rmId);
          recordImportedId(rmId);
        }
        process.stdout.write(`\r  [${file}] ${i + 1}/${candidates.length} - ${name.slice(0, 20).padEnd(20)} | 累計 ${totalOk}件OK `);
      } else {
        fileErr++;
        totalErr++;
        process.stderr.write(`\n  [NG] ${name}: ${result.error}\n`);
      }

      await sleep(DELAY_MS);
    }

    const parts = [`${fileOk}件OK`];
    if (fileSkip > 0) parts.push(`${fileSkip}件スキップ`);
    if (fileErr > 0) parts.push(`${fileErr}件NG`);
    console.log(`\n  → ${parts.join(', ')}`);
    await sleep(DELAY_MS);
  }

  console.log('');
  const summary = [`成功 ${totalOk}件`];
  if (totalSkip > 0) summary.push(`スキップ ${totalSkip}件`);
  if (totalErr > 0) summary.push(`エラー ${totalErr}件`);
  console.log(`✅ 完了: ${summary.join(' / ')}`);
}

main().catch(e => {
  console.error('致命的エラー:', e.message);
  process.exit(1);
});
