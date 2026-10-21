// Minimal client-side filtering. No dependencies.
(function(){
  var cards=[].slice.call(document.querySelectorAll('#cards .card'));
  if(!cards.length) return;
  var q=document.getElementById('q'), tour=document.getElementById('tour'),
      count=document.getElementById('count'), empty=document.getElementById('empty');
  var method='', hidePast=false;
  var params=new URLSearchParams(location.search);
  if(params.get('method')){
    method=params.get('method');
    [].forEach.call(document.querySelectorAll('[data-filter="method"]'),function(b){
      b.classList.toggle('on', b.dataset.value===method);
    });
  }
  function sync(){
    var term=(q.value||'').toLowerCase().trim();
    var t=tour.value, shown=0;
    cards.forEach(function(c){
      var ok=true;
      if(method && c.dataset.method!==method) ok=false;
      if(hidePast && c.dataset.past==='true') ok=false;
      if(t && c.dataset.tournament!==t) ok=false;
      if(term && (c.dataset.text||'').toLowerCase().indexOf(term)===-1) ok=false;
      c.style.display=ok?'':'none';
      if(ok) shown++;
    });
    if(count) count.textContent=shown+' of '+cards.length+' fixtures';
    if(empty) empty.hidden=shown!==0;
  }
  [].forEach.call(document.querySelectorAll('[data-filter="method"]'),function(b){
    b.addEventListener('click',function(){
      method=b.dataset.value;
      [].forEach.call(document.querySelectorAll('[data-filter="method"]'),
        function(x){x.classList.toggle('on',x===b);});
      sync();
    });
  });
  [].forEach.call(document.querySelectorAll('[data-filter="past"]'),function(b){
    b.addEventListener('click',function(){
      hidePast=!hidePast; b.classList.toggle('on',hidePast); sync();
    });
  });
  if(q) q.addEventListener('input',sync);
  if(tour) tour.addEventListener('change',sync);
  sync();
})();
