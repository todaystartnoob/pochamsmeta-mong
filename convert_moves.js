// Run: node convert_moves.js
const fs = require('fs');

const raw = fs.readFileSync('포켓몬챔피언스_기술.json', 'utf8');
const src = JSON.parse(raw);

// 1. Build MOVE_DATA array
const moveData = src.moves.map(m => {
  const entry = {
    name: m.name,
    type: m.type,
    category: m.category,
    power: m.power ?? null,
    accuracy: m.accuracy ?? null,
    pp: m.pp,
  };
  if (m.tags && m.tags.length > 0) entry.tags = m.tags;
  if (m['타수'] && m['타수'] > 1) entry.hits = m['타수'];
  return entry;
});

// 2. Build MOVE_DESCS object
const moveDescs = {};
for (const m of src.moves) {
  if (m.desc) moveDescs[m.name] = m.desc;
}

// 3. Build MULTI_HIT_COUNT from hits field
const multiHit = {};
for (const m of src.moves) {
  if (m['타수'] && m['타수'] > 1) multiHit[m.name] = m['타수'];
}

// 4. Update data.js: replace MOVE_DATA section
const dataJs = fs.readFileSync('data.js', 'utf8').replace(/^﻿/, ''); // strip BOM
const moveIdx = dataJs.indexOf('const MOVE_DATA=');
const pokemonSection = moveIdx > 0 ? dataJs.substring(0, moveIdx).trimEnd() : dataJs.trimEnd();
const newDataJs = pokemonSection + '\n' + `const MOVE_DATA=${JSON.stringify(moveData)};`;
fs.writeFileSync('data.js', newDataJs, 'utf8');
console.log(`data.js: MOVE_DATA updated with ${moveData.length} moves`);

// 5. Write move-descs.js
const descsJs = 'const MOVE_DESCS=' + JSON.stringify(moveDescs, null, 2) + ';';
fs.writeFileSync('move-descs.js', descsJs, 'utf8');
console.log(`move-descs.js: ${Object.keys(moveDescs).length} descriptions`);

// 6. Print new MULTI_HIT_COUNT for copy-paste into index.html
const multiEntries = Object.entries(multiHit).map(([k,v]) => `'${k}':${v}`).join(',');
console.log(`\nNew MULTI_HIT_COUNT:\n{${multiEntries}}`);
fs.writeFileSync('multi_hit_count.txt', `const MULTI_HIT_COUNT = {\n  ${multiEntries.replace(/,/g,',\n  ')}\n};`, 'utf8');
console.log('multi_hit_count.txt written');
