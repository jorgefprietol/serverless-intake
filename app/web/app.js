let config;
let pending;
const el = id => document.getElementById(id);
async function metrics() {
  const response = await fetch('/api/metrics', {headers: {Authorization: 'Bearer '+el('token').value}});
  if (!response.ok) return;
  const data = await response.json();
  el('count').textContent = data.completed_requests;
  el('latency').textContent = data.p95_ms == null ? '—' : data.p95_ms.toFixed(1)+' ms';
  el('audit').textContent = data.audit_events;
}
function reset() { el('payload').value = JSON.stringify(config.demo, null, 2); }
fetch('/api/config').then(r=>r.json()).then(data=>{
  config=data; el('title').textContent=data.title; document.title=data.title+' · ArepaDev';
  el('description').textContent=data.description; el('backend').textContent=data.backend.toUpperCase(); reset();
}).catch(()=>{ el('description').textContent='No se pudo conectar con el servicio.'; });
el('reset').addEventListener('click',reset);
el('run').addEventListener('click',async()=>{
  el('run').disabled=true; el('status').textContent='Procesando';
  try {
    const payload=JSON.parse(el('payload').value);
    const body=JSON.stringify(payload);
    if (!pending || pending.body!==body) pending={body,key:crypto.randomUUID()};
    const response=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+el('token').value,'Idempotency-Key':pending.key},body});
    const data=await response.json();
    el('output').textContent=JSON.stringify(data,null,2);
    el('status').textContent=response.ok?'Completado':'Revisar entrada';
    if (response.ok) pending=null;
    metrics().catch(()=>{});
  } catch(error) {el('output').textContent=error.message;el('status').textContent='Error';}
  finally {el('run').disabled=false;}
});
