// Run: node convert_items.js
const fs = require('fs');

const raw = fs.readFileSync('포켓몬챔피언스_도구.json', 'utf8');
const src = JSON.parse(raw);

// 1. items-data.js: const ITEM_DATA=[...]
const itemData = src.items.map(it => {
  const e = {
    name: it.name,
    category: it.category,
    effect: it.effect,
    fling: it.fling ?? null,
    champions: it.champions === true,
  };
  if (it.sprite) e.sprite = it.sprite;
  return e;
});
fs.writeFileSync('items-data.js', `const ITEM_DATA=${JSON.stringify(itemData)};`, 'utf8');
console.log(`items-data.js: ${itemData.length} items`);

// 2. pochams-items.js: POCHAMS_ITEM_NAMES Set (champions=true 인 것만)
const champNames = src.items.filter(it => it.champions === true).map(it => it.name).sort();
const setLines = champNames.map(n => `  "${n}",`).join('\n');
fs.writeFileSync('pochams-items.js', `const POCHAMS_ITEM_NAMES = new Set([\n${setLines}\n]);\n`, 'utf8');
console.log(`pochams-items.js: ${champNames.length} champions items`);
