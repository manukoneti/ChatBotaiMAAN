/* Local-only Markdown + math renderer. Original messages remain plain text in storage. */
(function () {
  function plain(el, text) {
    el.replaceChildren();
    for (const part of text.split(/(https?:\/\/[^\s<>]+)/g)) {
      if (/^https?:\/\//.test(part)) {
        const a = document.createElement('a');
        a.href = part; a.textContent = part; a.target = '_blank'; a.rel = 'noopener noreferrer';
        el.append(a);
      } else el.append(document.createTextNode(part));
    }
  }
  window.renderMessage = function (el, text, role='assistant') {
    el.classList.toggle('formatted', role === 'assistant');
    if (role !== 'assistant' || !window.marked || !window.DOMPurify || !window.katex) {
      plain(el, text); return;
    }
    const maths = [];
    const prefix = 'math' + Math.random().toString(36).slice(2);
    function token(src, block) {
      const patterns = block
        ? [/^\$\$([\s\S]+?)\$\$(?:\n|$)/, /^\\\[([\s\S]+?)\\\](?:\n|$)/]
        : [/^\$\$([\s\S]+?)\$\$/, /^\\\[([\s\S]+?)\\\]/, /^\\\(([\s\S]+?)\\\)/, /^\$(?!\$)((?:\\.|[^$\n])+?)\$(?![\d$])/];
      for (let i=0; i<patterns.length; i++) {
        const m=src.match(patterns[i]);
        if (m) return {type:block?'mathBlock':'mathInline',raw:m[0],math:m[1].trim(),display:block || i<2};
      }
    }
    function render(t) {
      const id = prefix + maths.length;
      maths.push({id, text:t.math, display:t.display});
      return '<span data-maan-math="'+id+'"></span>';
    }
    try {
      const parser = new marked.Marked({gfm:true,breaks:true,async:false,extensions:[
        {name:'mathBlock',level:'block',start:src=>src.search(/\$\$|\\\[/),tokenizer:src=>token(src,true),renderer:render},
        {name:'mathInline',level:'inline',start:src=>src.search(/\$|\\[([]/),tokenizer:src=>token(src,false),renderer:render}
      ]});
      el.innerHTML = DOMPurify.sanitize(parser.parse(text), {
        ALLOWED_TAGS:['p','br','strong','em','del','blockquote','ul','ol','li','pre','code','h1','h2','h3','h4','h5','h6','hr','table','thead','tbody','tr','th','td','a','span'],
        ALLOWED_ATTR:['href','title','start','data-maan-math'],ALLOW_DATA_ATTR:false
      });
      el.querySelectorAll('a').forEach(a=>{
        const href=a.getAttribute('href') || '';
        if (!/^https?:\/\//i.test(href)) a.removeAttribute('href');
        else {a.target='_blank';a.rel='noopener noreferrer';}
      });
      for (const m of maths) {
        const target=el.querySelector('[data-maan-math="'+m.id+'"]');
        if (!target) continue;
        target.removeAttribute('data-maan-math');
        try {katex.render(m.text,target,{displayMode:m.display,throwOnError:true,trust:false,strict:'ignore',maxExpand:200,maxSize:20,output:'htmlAndMathml'});}
        catch (_) {target.textContent=(m.display?'$$':'$')+m.text+(m.display?'$$':'$');target.className='math-fallback';target.title='This formula could not be formatted.';}
      }
      el.querySelectorAll('table').forEach(table=>{const wrap=document.createElement('div');wrap.className='table-scroll';table.replaceWith(wrap);wrap.append(table);});
    } catch (_) {plain(el,text);}
  };
})();
