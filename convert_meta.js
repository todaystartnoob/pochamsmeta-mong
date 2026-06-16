// Run: node convert_meta.js
// data/*.json → meta-usage-data.js + meta-usage-sets.js
const fs = require('fs');
const path = require('path');

const DATA = path.join(__dirname, 'data');

// index.json 에서 시즌 파일 목록 읽기
const idx = JSON.parse(fs.readFileSync(path.join(DATA, 'index.json'), 'utf8'));
const files = idx.files; // e.g. ["champions_s1_single.json", "champions_s1_double.json"]

const usageOut  = {};
const setsOut   = {};

for (const fname of files) {
  const m = fname.match(/champions_s(\d+)_(single|double)\.json$/);
  if (!m) continue;
  const season = m[1], rule = m[2];
  const key = `s${season}_${rule}`;

  // ── meta-usage-data.js: usage + 메타 정보 (teams 제외 — 너무 큼) ──
  const usage = JSON.parse(fs.readFileSync(path.join(DATA, fname), 'utf8'));
  usageOut[key] = {
    season:        usage.season,
    season_number: usage.season_number,
    rule:          usage.rule,
    updated_at:    usage.updated_at,
    team_count:    usage.team_count,
    usage:         usage.usage,
    teams:         usage.teams,
  };

  // ── meta-usage-sets.js: 샘플 기술/노력치 등 ──
  const setsFile = path.join(DATA, `champions_s${season}_${rule}_sets.json`);
  if (fs.existsSync(setsFile)) {
    setsOut[key] = JSON.parse(fs.readFileSync(setsFile, 'utf8'));
  }
}

fs.writeFileSync('meta-usage-data.js', `const META_USAGE_DATA = ${JSON.stringify(usageOut, null, 2)};\n`, 'utf8');
console.log('meta-usage-data.js 생성 완료');

fs.writeFileSync('meta-usage-sets.js', `const META_SETS_DATA = ${JSON.stringify(setsOut, null, 2)};\n`, 'utf8');
console.log('meta-usage-sets.js 생성 완료');

// 변경 내용 요약
for (const key of Object.keys(setsOut)) {
  const d = setsOut[key];
  console.log(`  [${key}] 포켓몬 ${d.pokemon?.length || 0}종`);
}
