import re, os

SRC = '/Users/ronald/Downloads/posting_recommendation.html'
OUT_DIR = 'papers/posting-recommendation'
OUT = os.path.join(OUT_DIR, 'index.html')
PDF_HREF = '../../pdf/cai-gautier-wolthoff-2026.pdf'

src = open(SRC, encoding='utf-8').read()
ltx_css = re.search(r'<style type="text/css">.*?</style>', src, re.S).group(0)
mathjax = re.search(r'<script type="text/javascript">.*?</script>', src, re.S).group(0)
article_inner = re.search(r'<article\b[^>]*>(.*)</article>', src, re.S).group(1)

def clean(s): return ' '.join(re.sub(r'<[^>]+>', ' ', s).split())

def _close(html, start, tag):
    """Index just past the close of the `tag` element opened at `start`."""
    depth = 0
    for m in re.finditer(r'<' + tag + r'\b[^>]*>|</' + tag + r'>', html[start:]):
        if m.group(0).startswith('</'):
            depth -= 1
            if depth == 0:
                return start + m.end()
        else:
            depth += 1
    return None

def inline_appendix_proofs(html):
    """Move each appendix proof into a collapsible <details> right after the
    lemma/proposition it proves (replacing the in-text 'See Appendix A.x' stub),
    then drop the now-empty Proofs appendix. The appendix subsection id is kept
    on the <details> so existing '#A1.SSn' links still resolve."""
    # 1. collect appendix proof subsections, keyed by id (A1.SSn)
    proofs = {}
    for m in re.finditer(r'<section id="(A1\.SS\d+)"[^>]*>', html):
        sec = html[m.start():_close(html, m.start(), 'section')]
        h3 = re.search(r'<h3\b[^>]*>(.*?)</h3>', sec, re.S).group(1)
        # drop the leading "A.2" subsection-number tag -> "Proof of Lemma 2"
        title = clean(re.sub(r'<span class="ltx_tag[^"]*">.*?</span>', '', h3, flags=re.S))
        body = sec[sec.index('</h3>') + 5:sec.rindex('</section>')]
        proofs[m.group(1)] = (title, body)

    # 2. replace each "See Appendix A.x" proof stub with the real proof
    edits = []
    for m in re.finditer(r'<div class="ltx_proof">', html):
        end = _close(html, m.start(), 'div')
        ref = re.search(r'href="#(A1\.SS\d+)"', html[m.start():end])
        if ref and ref.group(1) in proofs:
            title, body = proofs[ref.group(1)]
            details = ('<details class="ltx-proof" id="%s">\n'
                       '<summary class="ltx-proof-sum">%s</summary>%s\n</details>'
                       % (ref.group(1), title, body))
            edits.append((m.start(), end, details))

    # 3. drop the whole Proofs appendix (all its content now lives inline)
    ap = re.search(r'<section id="A1"[^>]*>', html)
    if ap:
        edits.append((ap.start(), _close(html, ap.start(), 'section'), ''))

    # 4. apply right-to-left so offsets stay valid
    for start, end, repl in sorted(edits, reverse=True):
        html = html[:start] + repl + html[end:]
    return html

article_inner = inline_appendix_proofs(article_inner)

# ---- TOC list ----
mains = re.findall(r'<section id="(S[1-5]|bib)"[^>]*>\s*<h2[^>]*>(.*?)</h2>', src, re.S)
toc = ['<ol>']
for sid, title in mains:
    toc.append(f'<li><a href="#{sid}">{clean(title)}</a>')
    subs = re.findall(r'<section id="(' + re.escape(sid) + r'\.SS[^"]*)"[^>]*>\s*<h3[^>]*>(.*?)</h3>', src, re.S)
    if subs:
        toc.append('<ol>')
        for ssid, st in subs:
            toc.append(f'<li><a href="#{ssid}">{clean(st)}</a></li>')
        toc.append('</ol>')
    toc.append('</li>')
toc.append('</ol>')
toc_list = '\n'.join(toc)

# ---- sections render as normal headings (no collapsing) ----
new = article_inner

# ---- any .eps figure -> svg/png fallback note ----
def eps_fallback(m):
    pre, name, post = m.group(1), m.group(2), m.group(3)
    return (f'<img {pre}src="{name}.svg"{post} '
            f'onerror="if(this.dataset.f!==\'png\'){{this.dataset.f=\'png\';this.src=\'{name}.png\';}}'
            f'else{{this.replaceWith(Object.assign(document.createElement(\'div\'),'
            f'{{className:\'ltx-missing-fig\',textContent:\'[ figure {name} not found \\u2014 add {name}.svg or {name}.png here ]\'}}));}}">')
new = re.sub(r'<img ([^>]*?)src="([^"]+)\.eps"([^>]*?)>', eps_fallback, new)

# ---- JEL codes + keywords -> badges ----
def _badges(items):
    return ''.join('<span class="ltx-badge">%s</span>' % i for i in items)
def _meta_sub(m):
    jel = [c for c in re.split(r'[,\s]+', m.group(1).strip().rstrip('.')) if c]
    kw  = [k.strip() for k in m.group(2).split(',') if k.strip()]
    rows = ''
    if jel: rows += '<div class="ltx-meta-row"><span class="ltx-meta-label">JEL</span>%s</div>' % _badges(jel)
    if kw:  rows += '<div class="ltx-meta-row"><span class="ltx-meta-label">Keywords</span>%s</div>' % _badges(kw)
    return '</p>\n<div class="ltx-meta">%s</div>' % rows
new = re.sub(
    r'(?:\s*<br class="ltx_break">\s*)+JEL classification:\s*([^<]*?)\s*'
    r'<br class="ltx_break">\s*Keywords:\s*([^<]*?)\s*</p>',
    _meta_sub, new, flags=re.S)

bibtex_html = ('<div class="bibtex-box" hidden>\n'
  '<button class="bibtex-copy" type="button">Copy</button>\n'
  '<pre>@unpublished{cai-gautier-wolthoff-2026,\n'
  '  author = {Cai, Xiaoming and Gautier, Pieter and Wolthoff, Ronald},\n'
  '  title  = {Platform-Controlled Search and Distortions in Attention Allocation},\n'
  '  year   = {2026},\n'
  '  note   = {Working paper}\n'
  '}</pre>\n</div>')

CUSTOM_CSS = r'''<style>
/* ---------- layout ---------- */
.ltx_page_main{max-width:var(--rwidth,60rem);margin:0 auto;padding:1.25rem 1.25rem 4rem;background:transparent;font-size:calc(1.0625rem * var(--rscale,1));line-height:var(--rleading,1.7);}
.ltx_document{color:var(--text);}
.ltx_title_document{font-size:1.9rem;line-height:1.25;}
.ltx_para,.ltx_eqn_table,.ltx_equationgroup{overflow-x:auto;}
section.ltx_section,section.ltx_appendix,section.ltx_bibliography{scroll-margin-top:7rem;}

/* ---------- sticky two-row header ---------- */
.site-header{position:sticky;top:0;z-index:8;}
.topbar{position:static;}
.subnav{display:flex;flex-wrap:wrap;align-items:center;gap:.5rem;padding:.5rem 1.25rem;
  background:var(--panel);border-bottom:1px solid var(--border);}
.subnav-sp{flex:1 1 auto;}

/* ---------- buttons ---------- */
.ltx-btn{font:600 .85rem/1 system-ui,sans-serif;cursor:pointer;text-decoration:none;display:inline-flex;
  align-items:center;gap:.35rem;color:var(--accent);background:var(--tag-bg);border:1px solid var(--border);
  border-radius:6px;padding:.45rem .8rem;}
[data-theme="dark"] .ltx-btn{color:var(--link);}
.ltx-btn:hover{color:var(--accent-ink);background:var(--accent);border-color:var(--accent);}
.ltx-btn.primary{color:var(--accent-ink);background:var(--accent);border-color:var(--accent);}
.ltx-btn.primary:hover{filter:brightness(1.1);}

/* ---------- Contents dropdown ---------- */
.subnav-toc{position:relative;}
.subnav-toc>summary{list-style:none;}
.subnav-toc>summary::-webkit-details-marker{display:none;}
.subnav-toc-menu{position:absolute;top:calc(100% + .45rem);left:0;z-index:20;min-width:20rem;max-width:92vw;
  max-height:75vh;overflow:auto;background:var(--bg);border:1px solid var(--border);border-radius:10px;
  box-shadow:0 10px 28px rgba(0,0,0,.18);padding:.6rem .9rem;font-size:.92rem;}
.subnav-toc:not([open]) .subnav-toc-menu{display:none;}
.subnav-toc-menu ol{list-style:none;margin:.2rem 0;padding-left:.3rem;}
.subnav-toc-menu ol ol{padding-left:1rem;font-size:.96em;}
.subnav-toc-menu li{margin:.2rem 0;}
.subnav-toc-menu a{text-decoration:none;color:var(--text);}
.subnav-toc-menu a:hover,.subnav-toc-menu a.active{color:var(--accent);}
[data-theme="dark"] .subnav-toc-menu a:hover,[data-theme="dark"] .subnav-toc-menu a.active{color:var(--link);}

/* ---------- search + text controls ---------- */
.subnav-group{display:inline-flex;gap:.3rem;}
.subnav-search{font:inherit;font-size:.85rem;padding:.42rem .6rem;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);width:9rem;max-width:40vw;}
.subnav-search:focus{outline:2px solid var(--accent);outline-offset:1px;}
.subnav-count{font-size:.78rem;color:var(--muted);min-width:3rem;}
mark.ltx-hit{background:#ffe58a;color:inherit;border-radius:2px;padding:0 .05em;}
mark.ltx-hit.current{background:#ff9f1a;}
[data-theme="dark"] mark.ltx-hit{background:#7a5d00;color:#fff;}
[data-theme="dark"] mark.ltx-hit.current{background:#c07a00;}
.subnav-gear{position:relative;}
.subnav-gear>summary{list-style:none;}
.subnav-gear>summary::-webkit-details-marker{display:none;}
.subnav-gear-menu{position:absolute;top:calc(100% + .45rem);right:0;z-index:20;min-width:15rem;max-width:92vw;
  background:var(--bg);border:1px solid var(--border);border-radius:10px;box-shadow:0 10px 28px rgba(0,0,0,.18);padding:.55rem .7rem;}
.subnav-gear:not([open]) .subnav-gear-menu{display:none;}
.gear-row{display:flex;align-items:center;gap:.4rem;margin:.4rem 0;}
.gear-row .gear-label{flex:1 1 auto;font-size:.85rem;color:var(--muted);}
.subnav-gear-menu .ltx-btn{padding:.3rem .6rem;min-width:2rem;justify-content:center;}
.gear-row.gear-reset{justify-content:flex-end;margin-top:.55rem;}

/* ---------- BibTeX ---------- */
.bibtex-box{margin:0 0 1.25rem;}

/* ---------- JEL / keyword badges ---------- */
.ltx-meta{display:flex;flex-direction:column;gap:.5rem;margin:1.1rem 0 .4rem;}
.ltx-meta-row{display:flex;flex-wrap:wrap;align-items:center;gap:.4rem;}
.ltx-meta-label{font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;font-weight:700;color:var(--muted);min-width:5rem;}
.ltx-badge{font-size:.82rem;font-weight:600;color:var(--accent);background:var(--tag-bg);border:1px solid var(--border);border-radius:999px;padding:.2rem .7rem;}
[data-theme="dark"] .ltx-badge{color:var(--link);}

/* ---------- theorem-like environments (partial box) ---------- */
.ltx_theorem{margin:1.4rem 0;padding:.85rem 1.1rem .85rem 1.15rem;background:var(--panel);
  border:1px solid var(--border);border-left:4px solid var(--accent);border-radius:8px;}
.ltx_theorem .ltx_title_theorem{color:var(--accent);}
[data-theme="dark"] .ltx_theorem .ltx_title_theorem{color:var(--link);}
.ltx_theorem .ltx_para:last-child .ltx_p:last-child,
.ltx_theorem > .ltx_para:last-child{margin-bottom:0;}
/* per-type accent so results vs. assumptions are distinguishable */
.ltx_theorem_assumption{border-left-color:#b8860b;}
.ltx_theorem_assumption .ltx_title_theorem{color:#b8860b;}
.ltx_theorem_definition{border-left-color:#7a4fb0;}
.ltx_theorem_definition .ltx_title_theorem{color:#7a4fb0;}
[data-theme="dark"] .ltx_theorem_assumption{border-left-color:#e0b24d;}
[data-theme="dark"] .ltx_theorem_assumption .ltx_title_theorem{color:#e0b24d;}
[data-theme="dark"] .ltx_theorem_definition{border-left-color:#b794e6;}
[data-theme="dark"] .ltx_theorem_definition .ltx_title_theorem{color:#b794e6;}
/* proofs: boxed, but lighter than statements so they read as subordinate */
.ltx_proof{margin:1rem 0 1.2rem;padding:.7rem 1rem;background:var(--bg);
  border:1px solid var(--border);border-left:4px solid var(--muted);border-radius:8px;}
.ltx_proof .ltx_title_proof{color:var(--muted);}
.ltx_proof > .ltx_para:last-child .ltx_p:last-child{margin-bottom:0;}

/* ---------- author block (override LaTeXML 1-line popup) ---------- */
.ltx_authors{text-align:center;margin:.6rem 0 1.4rem;display:flex;flex-wrap:wrap;justify-content:center;gap:.4rem 2rem;}
.ltx_author_before,.ltx_author_after{display:none !important;}
.ltx_creator.ltx_role_author{display:inline-block;vertical-align:top;margin:.3rem 0;max-width:20rem;}
.ltx_personname{display:block;font-weight:600;font-size:1.05rem;}
.ltx_authors_1line .ltx_author_notes{display:block;font-size:.84rem;color:var(--muted);line-height:1.45;margin-top:.15rem;}
.ltx_authors_1line .ltx_author_notes:before{content:none !important;}
.ltx_authors_1line .ltx_author_notes span{display:inline !important;}
.ltx_authors_1line .ltx_author_notes:hover span{display:inline !important;position:static !important;
  background:none !important;border:0 !important;box-shadow:none !important;}
.ltx_authors_1line .ltx_author_notes .ltx_ref.ltx_href{white-space:nowrap;}
.ltx_dates{text-align:center;color:var(--muted);}

/* ---------- back to top ---------- */
#to-top{position:fixed;right:1.1rem;bottom:1.1rem;width:2.6rem;height:2.6rem;border-radius:50%;
  border:1px solid var(--border);background:var(--accent);color:var(--accent-ink);font-size:1.1rem;cursor:pointer;
  opacity:0;pointer-events:none;transition:opacity .2s;box-shadow:0 4px 14px rgba(0,0,0,.18);}
#to-top.show{opacity:.9;pointer-events:auto;} #to-top:hover{opacity:1;}

/* ---------- dark-mode figures + footnotes + misc ---------- */
[data-theme="dark"] figure.ltx_figure,[data-theme="dark"] figure.ltx_table{background:#fff;border-radius:10px;padding:1rem;}
[data-theme="dark"] figure.ltx_table .ltx_text,[data-theme="dark"] figure.ltx_figure .ltx_text{color:#1d2530;}
[data-theme="dark"] [class*="ltx_border"]{border-color:#9aa6b4 !important;}
.ltx-missing-fig{border:1px dashed var(--border);border-radius:8px;padding:1.2rem;color:var(--muted);font-size:.92rem;text-align:center;}
.ltx_ref{color:var(--link);} .ltx_ref:hover{color:var(--accent);}
[data-theme="dark"] .ltx_ref:hover{color:#aecdff;}
.ltx_note_content{max-width:min(32rem,90vw);}
[data-theme="dark"] .ltx_note_content{background:var(--panel);color:var(--text);border-color:var(--border);}
.ltx_note.ltx-note-open .ltx_note_content{display:block;position:absolute;z-index:20;}

/* ---------- collapsible inline proofs ---------- */
details.ltx-proof{margin:.6rem 0 1.1rem;background:var(--bg);border:1px solid var(--border);
  border-left:4px solid var(--muted);border-radius:8px;padding:.5rem 1rem;scroll-margin-top:7rem;}
details.ltx-proof>summary{list-style:none;cursor:pointer;display:flex;align-items:baseline;gap:.45rem;
  font-style:italic;font-weight:600;color:var(--accent);padding:.15rem 0;}
details.ltx-proof>summary::-webkit-details-marker{display:none;}
details.ltx-proof>summary::before{content:"\25B8";font-size:.8em;line-height:1;flex:0 0 auto;
  transition:transform .15s ease;}
details.ltx-proof[open]>summary::before{transform:rotate(90deg);}
details.ltx-proof>summary:hover{text-decoration:underline;}
[data-theme="dark"] details.ltx-proof>summary{color:var(--link);}

@media (max-width:600px){ .ltx_title_document{font-size:1.5rem;} }
@media print{
  .site-header,.bibtex-box,#to-top{display:none !important;}
  details.ltx-proof>summary::before{display:none;}
  a{color:inherit;}
}
</style>'''

SCRIPT = r'''<script>
  var root=document.documentElement;
  (function(){
    var btn=document.getElementById('theme-toggle');
    function paint(){var d=root.getAttribute('data-theme')==='dark';
      btn.textContent=d?'☀':'☾';btn.setAttribute('aria-label',d?'Switch to light mode':'Switch to dark mode');}
    if(btn){paint();btn.addEventListener('click',function(){
      var n=root.getAttribute('data-theme')==='dark'?'light':'dark';
      root.setAttribute('data-theme',n);try{localStorage.setItem('theme',n);}catch(e){}paint();});}
  })();
  function reveal(id){
    if(!id) return; var t=document.getElementById(id); if(!t) return;
    var n=t; while(n){ if(n.tagName==='DETAILS'&&!n.classList.contains('subnav-toc')) n.open=true; n=n.parentElement; }
    t.scrollIntoView();
  }
  window.addEventListener('hashchange',function(){reveal(decodeURIComponent(location.hash.slice(1)));});
  document.addEventListener('click',function(e){
    ['.subnav-toc','.subnav-gear'].forEach(function(sel){var d=document.querySelector(sel);
      if(d&&d.open&&!(e.target.closest&&e.target.closest(sel))) d.open=false;});
    var a=e.target.closest&&e.target.closest('a[href^="#"]');
    if(a){ setTimeout(function(){reveal(decodeURIComponent(location.hash.slice(1)));},0);
      var dd=a.closest('.subnav-toc'); if(dd) setTimeout(function(){dd.open=false;},60); }
    var m=e.target.closest&&e.target.closest('.ltx_note_mark');
    if(m){ var note=m.closest('.ltx_note'); if(note) note.classList.toggle('ltx-note-open'); }
    var bt=e.target.closest&&e.target.closest('.bibtex-toggle');
    if(bt){ var box=document.querySelector('.bibtex-box'); var show=box.hasAttribute('hidden');
      if(show){box.removeAttribute('hidden');}else{box.setAttribute('hidden','');}
      bt.setAttribute('aria-expanded',show?'true':'false'); }
    var bc=e.target.closest&&e.target.closest('.bibtex-copy');
    if(bc&&navigator.clipboard){ var pre=bc.parentNode.querySelector('pre');
      if(pre){navigator.clipboard.writeText(pre.textContent).then(function(){
        var o=bc.textContent;bc.textContent='Copied!';setTimeout(function(){bc.textContent=o;},1500);});} }
  });
  if(location.hash) reveal(decodeURIComponent(location.hash.slice(1)));
  var topBtn=document.getElementById('to-top');
  addEventListener('scroll',function(){topBtn.classList.toggle('show',scrollY>600);},{passive:true});
  topBtn.addEventListener('click',function(){scrollTo({top:0,behavior:'smooth'});});
  (function(){
    var links={}; document.querySelectorAll('.subnav-toc-menu a').forEach(function(a){links[a.getAttribute('href').slice(1)]=a;});
    var ids=Object.keys(links).map(function(id){return document.getElementById(id);}).filter(Boolean);
    if(!('IntersectionObserver'in window)||!ids.length) return;
    var io=new IntersectionObserver(function(es){es.forEach(function(en){ if(en.isIntersecting){
      Object.values(links).forEach(function(a){a.classList.remove('active');});
      var a=links[en.target.id]; if(a) a.classList.add('active'); } });},{rootMargin:'-25% 0px -65% 0px'});
    ids.forEach(function(el){io.observe(el);});
  })();
  // Reading settings: text size, line spacing, width
  (function(){
    function save(k,v){try{localStorage.setItem(k,v);}catch(e){}}
    var scale=parseFloat(localStorage.getItem('paper-rscale'))||1;
    function setScale(v){scale=Math.min(1.6,Math.max(.8,Math.round(v*100)/100));
      root.style.setProperty('--rscale',scale);save('paper-rscale',scale);}
    var lead=parseFloat(localStorage.getItem('paper-rleading'))||1.7;
    function setLead(v){lead=Math.min(2.4,Math.max(1.2,Math.round(v*100)/100));
      root.style.setProperty('--rleading',lead);save('paper-rleading',lead);}
    var w=parseFloat(localStorage.getItem('paper-rwidth'))||60;
    function setW(v){w=Math.min(84,Math.max(40,Math.round(v)));
      root.style.setProperty('--rwidth',w+'rem');save('paper-rwidth',w+'rem');}
    function on(id,fn){var el=document.getElementById(id); if(el)el.addEventListener('click',fn);}
    on('text-smaller',function(){setScale(scale-0.1);});
    on('text-larger',function(){setScale(scale+0.1);});
    on('line-tighter',function(){setLead(lead-0.15);});
    on('line-looser',function(){setLead(lead+0.15);});
    on('width-narrower',function(){setW(w-4);});
    on('width-wider',function(){setW(w+4);});
    on('reading-reset',function(){
      scale=1;lead=1.7;w=60;
      ['paper-rscale','paper-rwidth','paper-rleading'].forEach(function(k){try{localStorage.removeItem(k);}catch(e){}});
      root.style.removeProperty('--rscale');root.style.removeProperty('--rwidth');root.style.removeProperty('--rleading');});
  })();
  // In-page search: highlight matches and open the sections that contain them
  (function(){
    var art=document.querySelector('article.ltx_document');
    var input=document.getElementById('paper-search'), countEl=document.getElementById('search-count');
    if(!art||!input) return;
    var hits=[], cur=-1, timer=null;
    function clearMarks(){
      document.querySelectorAll('mark.ltx-hit').forEach(function(m){
        var p=m.parentNode; p.replaceChild(document.createTextNode(m.textContent),m); p.normalize();});
      hits=[]; cur=-1;
    }
    function skip(node){
      var p=node.parentNode;
      while(p&&p!==art){var t=p.nodeName.toLowerCase();
        if(t==='math'||t==='script'||t==='style'||t==='mark') return true; p=p.parentNode;}
      return false;
    }
    function run(q){
      clearMarks();
      if(!q||q.length<2){countEl.textContent='';return;}
      var esc=q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
      var walker=document.createTreeWalker(art,NodeFilter.SHOW_TEXT,{acceptNode:function(n){
        if(!n.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
        if(skip(n)) return NodeFilter.FILTER_REJECT;
        return new RegExp(esc,'i').test(n.nodeValue)?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_REJECT;}});
      var nodes=[],n; while(n=walker.nextNode()) nodes.push(n);
      nodes.forEach(function(node){
        var rx=new RegExp(esc,'gi'), txt=node.nodeValue, last=0, m, frag=document.createDocumentFragment(), any=false;
        while((m=rx.exec(txt))){
          any=true;
          if(m.index>last) frag.appendChild(document.createTextNode(txt.slice(last,m.index)));
          var mk=document.createElement('mark'); mk.className='ltx-hit'; mk.textContent=m[0];
          frag.appendChild(mk); hits.push(mk); last=rx.lastIndex;
          if(m.index===rx.lastIndex) rx.lastIndex++;
        }
        if(any){ if(last<txt.length) frag.appendChild(document.createTextNode(txt.slice(last)));
          node.parentNode.replaceChild(frag,node); }
      });
      // open any collapsed proofs that contain a hit
      hits.forEach(function(mk){var p=mk.parentNode;
        while(p&&p!==art){ if(p.tagName==='DETAILS'&&!p.classList.contains('subnav-toc')) p.open=true; p=p.parentNode;}});
      countEl.textContent=hits.length?('1/'+hits.length):'0';
      if(hits.length){cur=0;mark(cur);hits[0].scrollIntoView({block:'center'});}
    }
    function mark(i){hits.forEach(function(m){m.classList.remove('current');});
      if(hits[i]){hits[i].classList.add('current');countEl.textContent=(i+1)+'/'+hits.length;}}
    function step(d){if(!hits.length)return;cur=(cur+d+hits.length)%hits.length;mark(cur);
      hits[cur].scrollIntoView({block:'center'});}
    input.addEventListener('input',function(){clearTimeout(timer);var q=input.value;timer=setTimeout(function(){run(q);},200);});
    input.addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();step(e.shiftKey?-1:1);}
      else if(e.key==='Escape'){input.value='';clearMarks();countEl.textContent='';}});
  })();
  // expand inline proofs so they print in full
  addEventListener('beforeprint',function(){
    document.querySelectorAll('details.ltx-proof').forEach(function(d){d.open=true;});});
</script>'''

TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
<title>Platform-Controlled Search and Distortions in Attention Allocation — Ronald Wolthoff</title>
<meta name="description" content="Platform-Controlled Search and Distortions in Attention Allocation — Cai, Gautier &amp; Wolthoff.">
<link rel="icon" href="../../images/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="../../css/style.css">
<script>
  (function(){try{var t=localStorage.getItem('theme');
    if(!t){t=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}
    document.documentElement.setAttribute('data-theme',t);
    var rs=localStorage.getItem('paper-rscale'); if(rs)document.documentElement.style.setProperty('--rscale',rs);
    var rw=localStorage.getItem('paper-rwidth'); if(rw)document.documentElement.style.setProperty('--rwidth',rw);
    var rl=localStorage.getItem('paper-rleading'); if(rl)document.documentElement.style.setProperty('--rleading',rl);
  }catch(e){}})();
</script>
@@LTXCSS@@
@@CUSTOMCSS@@
@@MATHJAX@@
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
<div class="site-header">
  <header class="topbar">
    <a class="brand" href="../../index.html">Ronald Wolthoff</a>
    <nav class="nav">
      <a href="../../index.html#about">About</a>
      <a href="../../index.html#research">Research</a>
      <button id="theme-toggle" type="button" class="theme-toggle" aria-label="Toggle dark mode">&#9790;</button>
    </nav>
  </header>
  <nav class="subnav" aria-label="Paper actions">
    <details class="subnav-toc">
      <summary class="ltx-btn">&#9776; Contents</summary>
      <div class="subnav-toc-menu">
@@TOC@@
      </div>
    </details>
    <a class="ltx-btn primary" href="@@PDF@@" download>&#8595; PDF</a>
    <button class="ltx-btn bibtex-toggle" type="button" aria-expanded="false">BibTeX</button>
    <a class="ltx-btn" href="../../index.html#research">&#8592; All papers</a>
    <input class="subnav-search" id="paper-search" type="search" placeholder="Search…" aria-label="Search in paper">
    <span class="subnav-count" id="search-count" aria-live="polite"></span>
    <span class="subnav-sp"></span>
    <details class="subnav-gear">
      <summary class="ltx-btn" title="Reading settings" aria-label="Reading settings">&#9881;</summary>
      <div class="subnav-gear-menu">
        <div class="gear-row"><span class="gear-label">Text size</span>
          <button class="ltx-btn" id="text-smaller" type="button" aria-label="Smaller text">&#8722;</button>
          <button class="ltx-btn" id="text-larger" type="button" aria-label="Larger text">+</button></div>
        <div class="gear-row"><span class="gear-label">Line spacing</span>
          <button class="ltx-btn" id="line-tighter" type="button" aria-label="Tighter line spacing">&#8722;</button>
          <button class="ltx-btn" id="line-looser" type="button" aria-label="Looser line spacing">+</button></div>
        <div class="gear-row"><span class="gear-label">Width</span>
          <button class="ltx-btn" id="width-narrower" type="button" aria-label="Narrower">&#8722;</button>
          <button class="ltx-btn" id="width-wider" type="button" aria-label="Wider">+</button></div>
        <div class="gear-row gear-reset"><button class="ltx-btn" id="reading-reset" type="button">Reset</button></div>
      </div>
    </details>
  </nav>
</div>
<div class="ltx_page_main" id="main">
<div class="ltx_page_content">
@@BIBTEX@@
<article class="ltx_document ltx_authors_1line">
@@BODY@@
</article>
</div>
</div>
<button id="to-top" type="button" aria-label="Back to top" title="Back to top">&#8593;</button>
@@SCRIPT@@
</body>
</html>
'''

page = (TEMPLATE
        .replace('@@LTXCSS@@', ltx_css)
        .replace('@@CUSTOMCSS@@', CUSTOM_CSS)
        .replace('@@MATHJAX@@', mathjax)
        .replace('@@TOC@@', toc_list)
        .replace('@@PDF@@', PDF_HREF)
        .replace('@@BIBTEX@@', bibtex_html)
        .replace('@@BODY@@', new)
        .replace('@@SCRIPT@@', SCRIPT))

os.makedirs(OUT_DIR, exist_ok=True)
open(OUT, 'w', encoding='utf-8').write(page)
print('OK sections=%d size=%dKB' % (len(mains), len(page)//1024))
