// Shared by the user and developer pages: API calls, the review grid, approval.
const $ = id => document.getElementById(id);
const st = t => { const e = $('status'); if (e) e.textContent = t || ''; };
let cur = null;
const reportLog = (level, msg) => fetch('/api/log', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ level, msg }) }).catch(() => {});
window.addEventListener('error', e => reportLog('error', `${e.message} (${(e.filename || '').split('/').pop()}:${e.lineno})`));
window.addEventListener('unhandledrejection', e => reportLog('error', 'unhandled promise rejection: ' + (e.reason && e.reason.message || e.reason)));

async function call(url, opt, msg) {
  st(msg || 'working…');
  try {
    const r = await fetch(url, opt);
    if (!r.ok) { let m = await r.text(); try { m = JSON.parse(m).detail || m } catch {} throw new Error(m) }
    return await r.json();
  } catch (e) { st(''); alert(e.message); throw e }
  finally { st('') }
}
const post = (url, msg) => call(url, { method: 'POST' }, msg);

function renderGrid(r) {
  cur = r;
  const tb = $('grid').tBodies[0]; tb.innerHTML = '';
  for (const s of r.slots) {
    const iss = r.issues[s.letter] || [], lc = r.low_conf.includes(s.letter);
    const lvl = iss.some(i => i.level == 'error') ? 'error' : (iss.length || lc ? 'warn' : '');
    const msgs = iss.map(i => i.msg).concat(lc ? ['low OCR confidence'] : []);
    if (r.match && r.match[s.key] === false) msgs.push('(synthetic truth differs)');
    const tr = document.createElement('tr'); tr.className = lvl;
    tr.innerHTML = `<td class="l">${s.letter}</td><td>${s.label}</td><td><input class="v" data-k="${s.key}" value="${r.values[s.key] ?? ''}"></td><td class="msg">${msgs.join('; ')}</td>`;
    tb.appendChild(tr);
  }
  const img = $('img'); img.src = '/api/image/' + r.id; img.hidden = false;
  $('ok').disabled = false; $('plan').hidden = true;
  const n = Object.keys(r.issues).length + r.low_conf.filter(l => !(l in r.issues)).length;
  const sm = $('summary'); if (sm) sm.textContent = n ? `${n} field(s) need your attention (highlighted).` : 'All fields read cleanly. Still check against the image.';
}

async function approve() {
  const values = {};
  document.querySelectorAll('input.v').forEach(i => values[i.dataset.k] = i.value === '' ? null : Number(i.value));
  const r = await call('/api/approve', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ values, original: cur.values }) });
  $('plan').hidden = false;
  $('plan').textContent = `Approved. ${r.corrected.length} field(s) corrected by you: ${r.corrected.join(', ') || 'none'}\nRun type_into_epic.bat (or tools/keystroke_helper.py) to type these into Epic.\n\n` +
    r.plan.map(p => p.slot + ': ' + (p.skip ? '(skip)' : p.text)).join('\n');
}

// Approve the reviewed values and type them into Epic (server drives the keyboard); poll progress until it finishes.
async function transcribe(opts = {}) {
  const values = {}, flagged = [];
  document.querySelectorAll('input.v').forEach(i => values[i.dataset.k] = i.value === '' ? null : Number(i.value));
  document.querySelectorAll('#grid tbody tr.error, #grid tbody tr.warn').forEach(tr => {   // flagged AND left unedited by the reviewer
    const i = tr.querySelector('input.v'), was = cur.values[i.dataset.k];
    if (String(was ?? '') === i.value) flagged.push(tr.querySelector('td.l').textContent);
  });
  $('ok').disabled = true; $('abort').hidden = false; $('plan').hidden = true;
  const stat = t => { $('tstat').textContent = t };
  try {
    await call('/api/transcribe', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ values, original: cur.values, flagged, countdown: opts.countdown ?? 5, dry_run: !!opts.dry_run }) });
    for (;;) {
      const j = await (await fetch('/api/transcribe/status')).json();
      stat(j.message);
      if (j.status !== 'running') {
        if (j.status === 'done' && flagged.length) stat(j.message + ` Fields ${flagged.join(', ')} were flagged and not edited: check them in Epic.`);
        break;
      }
      await new Promise(r => setTimeout(r, 400));
    }
  } finally { $('ok').disabled = false; $('abort').hidden = true }
}
const abortT = () => fetch('/api/transcribe/abort', { method: 'POST' });
