// Run: node convert_json_to_data.js
const fs = require('fs');

const raw = fs.readFileSync('포켓몬챔피언스_포켓몬.json', 'utf8');
const src = JSON.parse(raw);

const entries = [];

// Base pokemon - sort by dex
for (const pk of src.pokemon) {
  const e = {
    no: pk.dex,
    name: pk.name,
    H: pk.stats.H,
    A: pk.stats.A,
    B: pk.stats.B,
    C: pk.stats.C,
    D: pk.stats.D,
    S: pk.stats.S,
    type1: pk.types[0] || '',
    type2: pk.types[1] || '',
    inGame: pk.champions === true,
    champions: pk.champions === true,
  };
  entries.push(e);
}

// Forms - sort by dex then name
for (const f of src.forms) {
  const e = {
    no: f.dex,
    name: f.name,
    H: f.stats.H,
    A: f.stats.A,
    B: f.stats.B,
    C: f.stats.C,
    D: f.stats.D,
    S: f.stats.S,
    type1: f.types[0] || '',
    type2: f.types[1] || '',
    inGame: f.champions === true,
    champions: f.champions === true,
    form: f.kind || '',
  };
  entries.push(e);
}

// Sort: by no, then base before forms
entries.sort((a, b) => {
  if (a.no !== b.no) return a.no - b.no;
  // base (no form field) before forms
  const aForm = a.form ? 1 : 0;
  const bForm = b.form ? 1 : 0;
  return aForm - bForm;
});

const json = JSON.stringify(entries);
const out = `const POKEMON_DATA=${json};`;
fs.writeFileSync('data.js', out, 'utf8');
console.log(`Done: ${entries.length} entries (${entries.filter(e=>e.inGame).length} inGame/champions)`);
