const https = require('https');
const fs = require('fs');
const path = require('path');

// .env 読み込み
const envPath = path.join(__dirname, '.env');
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, 'utf8').split('\n')) {
    const m = line.match(/^([^=\s#][^=]*)=(.*)$/);
    if (m) process.env[m[1].trim()] = m[2].trim();
  }
}

const API_KEY = process.env.NOTION_API_KEY;
console.log('TOKEN prefix:', API_KEY ? API_KEY.slice(0, 12) + '...' : 'MISSING');

const req = https.request({
  hostname: 'api.notion.com',
  path: '/v1/databases/33daf136accb805283abe06a410484cc',
  headers: {
    'Authorization': 'Bearer ' + API_KEY,
    'Notion-Version': '2022-06-28',
  },
}, res => {
  let d = '';
  res.on('data', c => d += c);
  res.on('end', () => {
    const body = JSON.parse(d);
    console.log('STATUS:', res.statusCode);
    console.log('MESSAGE:', body.message || body.title || 'OK');
  });
});
req.on('error', e => console.error('ERROR:', e.message));
req.end();
