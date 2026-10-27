// Madam CEO – Voices inbox. Paste this into Extensions → Apps Script of a new Google Sheet.
// 1) Change KEY below to a long random text (the same value goes in the COMMUNITY_KEY secret).
// 2) Deploy → New deployment → Web app → Execute as: Me · Who has access: Anyone → Deploy.
const KEY = 'CHANGE-ME-TO-A-LONG-RANDOM-TEXT';
const SHEET = 'Submissions';
const HEAD = ['id','received','lang','topic','title','story','name','role','country','email','status','note'];

function sheet_() {
  const ss = SpreadsheetApp.getActive();
  let sh = ss.getSheetByName(SHEET);
  if (!sh) { sh = ss.insertSheet(SHEET); sh.appendRow(HEAD); sh.setFrozenRows(1); }
  return sh;
}
function clean_(v, n) {  // trims and blocks spreadsheet formulas
  let s = String(v || '').trim().slice(0, n);
  if (/^[=+\-@]/.test(s)) s = "'" + s;
  return s;
}
function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  const p = (e && e.parameter) || {};
  if (p.website) return out_({ok: true});                       // spam trap
  const story = String(p.story || '').trim();
  if (story.length < 200 || story.length > 8000 || p.consent !== 'yes') return out_({ok: false});
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    sheet_().appendRow([Utilities.getUuid().slice(0, 8), new Date().toISOString(), clean_(p.lang, 2),
      clean_(p.topic, 20), clean_(p.title, 140), clean_(story, 8000), clean_(p.name, 60),
      clean_(p.role, 80), clean_(p.country, 60), clean_(p.email, 120), '', '']);
  } finally { lock.releaseLock(); }
  return out_({ok: true});
}

function doGet(e) {
  const p = (e && e.parameter) || {};
  if (p.key !== KEY) return out_({error: 'forbidden'});
  const sh = sheet_();
  const rows = sh.getDataRange().getValues();
  rows.shift();
  if (p.action === 'mark') {
    for (let i = 0; i < rows.length; i++) {
      if (String(rows[i][0]) === p.id) {
        sh.getRange(i + 2, 11, 1, 2).setValues([[clean_(p.status, 40), clean_(p.note, 300)]]);
        return out_({ok: true});
      }
    }
    return out_({ok: false});
  }
  // Emails are NOT sent out: they stay in this sheet.
  const items = rows.filter(r => r[0] && (!r[10] || String(r[10]).indexOf('shortlist') === 0))
    .map(r => ({id: String(r[0]), received: r[1], lang: r[2], topic: r[3], title: r[4], story: r[5],
                name: r[6], role: r[7], country: r[8], status: String(r[10] || '')}));
  return out_({items: items});
}
