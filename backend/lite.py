# -*- coding: utf-8 -*-
"""轻量版页面渲染 - 服务端渲染 + 原生 ES5 JS
不依赖 Vue，兼容微信内置浏览器所有内核
首屏内容随 HTML 直接到达，消除白屏
"""
import json
from database import clean_stem


def render_lite_page(question, page, total_pages, stats=None):
    """渲染轻量版 HTML 页面

    Args:
        question: 题目字典 (含 id, stem, type, options, answer, explanation)
        page: 当前页码
        total_pages: 总页数
        stats: 统计数据 (可选)
    Returns:
        完整 HTML 字符串
    """
    qid = question.get("id", 0) if question else 0
    stem = clean_stem(question.get("stem", "")) if question else "暂无题目"
    qtype = question.get("type", "single") if question else "single"
    options = question.get("options", {}) if question else {}
    explanation = question.get("explanation", "") if question else ""
    answer = question.get("answer", []) if question else []

    # 构建首屏选项 HTML（服务端直出，不依赖 JS）
    options_html = _build_options_html(qtype, options)

    # 构建填空题输入框
    if qtype in ("fill_blank", "short_answer"):
        blank_count = len(answer) if isinstance(answer, list) else 1
        options_html = ""
        for i in range(blank_count):
            options_html += (
                '<input type="text" class="opt-input" id="blank_{}" '
                'placeholder="第{}空" autocomplete="off">\n'.format(i + 1, i + 1)
            )

    # 注入数据（JSON 安全转义）
    data_json = json.dumps({
        "page": page,
        "totalPages": total_pages,
        "qid": qid,
        "stem": stem,
        "qtype": qtype,
        "options": options,
        "answer": answer,
        "explanation": explanation,
    }, ensure_ascii=False)

    stats_html = ""
    if stats:
        stats_html = (
            '<span class="stat">总题 {}</span>'
            '<span class="stat">已答 {}</span>'
            '<span class="stat">正确率 {:.0f}%</span>'
        ).format(stats.get("total_questions", 0), stats.get("answered_questions", 0),
                 (stats.get("accuracy", 0) * 100))

    html = _LITE_TEMPLATE.replace("__DATA__", data_json)
    html = html.replace("__STEM__", _escape_html(stem))
    html = html.replace("__OPTIONS__", options_html)
    html = html.replace("__PAGE__", str(page))
    html = html.replace("__TOTAL_PAGES__", str(total_pages))
    html = html.replace("__STATS__", stats_html)
    html = html.replace("__QTYPE_LABEL__", _type_label(qtype))

    return html


def _build_options_html(qtype, options):
    """构建选择题选项 HTML"""
    if not options or not isinstance(options, dict):
        return ""
    html = ""
    for key in sorted(options.keys()):
        val = options[key]
        html += (
            '<div class="opt" data-key="{}" onclick="selectOption(this)">'
            '<span class="opt-key">{}</span>'
            '<span class="opt-val">{}</span>'
            '</div>\n'
        ).format(key, key, _escape_html(str(val)))
    return html


def _type_label(qtype):
    labels = {
        "single": "单选题",
        "multiple": "多选题",
        "true_false": "判断题",
        "fill_blank": "填空题",
        "short_answer": "简答题",
    }
    return labels.get(qtype, qtype)


def _escape_html(text):
    if not text:
        return ""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# ============================================================
# HTML 模板（约 5KB，含 CSS + JS，不含题目数据）
# ============================================================
_LITE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>期末刷题（轻量版）</title>
<meta name="format-detection" content="telephone=no">
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f0f2f5;color:#333;padding:10px;max-width:600px;margin:0 auto;line-height:1.6}
.hd{display:flex;justify-content:space-between;align-items:center;padding:8px 0;margin-bottom:8px}
.hd h1{font-size:17px;font-weight:600}
.hd .back{font-size:13px;color:#4f9eff;text-decoration:none}
.tags{display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap}
.tag{font-size:11px;padding:2px 8px;border-radius:10px;background:#e8e8e8;color:#666}
.tag.type{background:#4f9eff;color:#fff}
.counter{font-size:13px;color:#888;margin-bottom:8px}
.card{background:#fff;border-radius:10px;padding:16px;margin-bottom:10px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.stem{font-size:15px;line-height:1.7;margin-bottom:14px;word-break:break-word}
.opts{display:flex;flex-direction:column;gap:8px}
.opt{display:flex;gap:8px;padding:12px;border:1.5px solid #e0e0e0;border-radius:8px;cursor:pointer;font-size:14px;transition:border-color .15s,background .15s}
.opt:active{background:#f5f5f5}
.opt.sel{border-color:#4f9eff;background:#e8f2ff}
.opt.ok{border-color:#2ecc71;background:#e8f8ee}
.opt.no{border-color:#e74c3c;background:#fdeaea}
.opt-key{font-weight:700;min-width:20px;color:#4f9eff}
.opt.ok .opt-key{color:#2ecc71}
.opt.no .opt-key{color:#e74c3c}
.opt-input{width:100%;padding:10px;border:1.5px solid #e0e0e0;border-radius:8px;font-size:14px;margin-bottom:8px;outline:none}
.opt-input:focus{border-color:#4f9eff}
.btns{display:flex;gap:8px;margin-top:14px}
.btn{flex:1;padding:11px;border:none;border-radius:8px;font-size:14px;font-weight:500;cursor:pointer;text-align:center}
.btn-pri{background:#4f9eff;color:#fff}
.btn-out{background:#fff;border:1.5px solid #ddd;color:#666}
.btn:active{opacity:.8}
.btn:disabled{opacity:.5;cursor:not-allowed}
.exp{margin-top:12px;padding:12px;background:#f0f7ff;border-radius:8px;font-size:13px;display:none;border-left:3px solid #4f9eff}
.exp.show{display:block}
.exp .ans{margin-top:6px;color:#2ecc71;font-weight:600}
.nav{display:flex;gap:8px;justify-content:space-between;margin-top:12px;padding-bottom:20px}
.nav .btn{flex:0 0 auto;padding:9px 20px}
.stats{display:flex;gap:12px;font-size:12px;color:#888;justify-content:center;padding:8px 0}
.loading{text-align:center;padding:30px;color:#999;font-size:14px}
.load-anim{display:inline-block;width:16px;height:16px;border:2px solid #ddd;border-top-color:#4f9eff;border-radius:50%;animation:spin .6s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>

<div class="hd">
  <h1>📚 期末刷题</h1>
  <a class="back" href="/">完整版 →</a>
</div>

<div class="tags">
  <span class="tag type">__QTYPE_LABEL__</span>
  <span class="tag">__STATS__</span>
</div>

<div class="counter">第 __PAGE__ / __TOTAL_PAGES__ 题</div>

<div class="card" id="qcard">
  <div class="stem" id="stem">__STEM__</div>
  <div class="opts" id="opts">__OPTIONS__</div>
  <div class="btns" id="btns">
    <button class="btn btn-pri" id="submitBtn" onclick="doSubmit()">提交答案</button>
  </div>
  <div class="exp" id="exp">
    <div id="expText"></div>
    <div class="ans" id="ansText"></div>
  </div>
</div>

<div class="nav">
  <button class="btn btn-out" onclick="goPrev()">← 上一题</button>
  <button class="btn btn-pri" onclick="goNext()">下一题 →</button>
</div>

<script>
// ===== 服务端注入数据 =====
var D=__DATA__;
var selected=[];
var submitted=false;

// ===== 提交答案 =====
function doSubmit(){
  if(submitted)return;
  var ans=getUserAnswer();
  if(ans===null||ans===''||(ans instanceof Array&&ans.length===0)){
    return;
  }
  var btn=document.getElementById('submitBtn');
  btn.textContent='提交中...';
  btn.disabled=true;
  var xhr=new XMLHttpRequest();
  xhr.open('POST','/api/submit',true);
  xhr.setRequestHeader('Content-Type','application/json');
  xhr.onreadystatechange=function(){
    if(xhr.readyState===4){
      btn.disabled=false;
      if(xhr.status===200){
        try{var r=JSON.parse(xhr.responseText);showResult(r,ans);}catch(e){btn.textContent='提交答案';}
      }else{
        btn.textContent='提交答案';
      }
    }
  };
  xhr.send(JSON.stringify({question_id:D.qid,answer:ans}));
}

function getUserAnswer(){
  var t=D.qtype;
  if(t==='fill_blank'||t==='short_answer'){
    var blanks=[];
    var i=1;
    while(true){
      var el=document.getElementById('blank_'+i);
      if(!el)break;
      blanks.push(el.value.trim());
      i++;
    }
    return blanks.length===1?blanks[0]:blanks;
  }
  if(t==='multiple')return selected.slice();
  return selected.length>0?selected[0]:null;
}

// ===== 选择选项 =====
function selectOption(el){
  if(submitted)return;
  var key=el.getAttribute('data-key');
  if(D.qtype==='multiple'){
    var idx=selected.indexOf(key);
    if(idx>=0){selected.splice(idx,1);el.classList.remove('sel');}
    else{selected.push(key);el.classList.add('sel');}
  }else{
    var all=el.parentNode.querySelectorAll('.opt');
    for(var i=0;i<all.length;i++){all[i].classList.remove('sel');}
    el.classList.add('sel');
    selected=[key];
  }
}

// ===== 显示结果 =====
function showResult(res,userAns){
  submitted=true;
  document.getElementById('submitBtn').style.display='none';
  // 标记对错
  if(D.qtype!=='fill_blank'&&D.qtype!=='short_answer'){
    var opts=document.querySelectorAll('.opt');
    var ca=res.correct_answer;
    if(typeof ca==='string')ca=[ca];
    for(var i=0;i<opts.length;i++){
      var k=opts[i].getAttribute('data-key');
      var isCorrect=false;
      for(var j=0;j<ca.length;j++){if(ca[j]===k){isCorrect=true;break;}}
      if(isCorrect)opts[i].classList.add('ok');
      if(selected.indexOf(k)>=0&&!isCorrect)opts[i].classList.add('no');
    }
  }
  // 显示解析
  var exp=document.getElementById('exp');
  document.getElementById('expText').textContent='解析：'+(res.explanation||'暂无');
  var caText=res.correct_answer;
  if(caText instanceof Array)caText=caText.join('、');
  document.getElementById('ansText').textContent='正确答案：'+caText;
  exp.classList.add('show');
  // 添加下一题按钮
  var btns=document.getElementById('btns');
  var nb=document.createElement('button');
  nb.className='btn btn-pri';
  nb.textContent='下一题 →';
  nb.onclick=goNext;
  btns.appendChild(nb);
}

// ===== 翻页 =====
function goNext(){
  if(D.page<D.totalPages)loadQ(D.page+1);
}
function goPrev(){
  if(D.page>1)loadQ(D.page-1);
}

function loadQ(p){
  var card=document.getElementById('qcard');
  card.innerHTML='<div class="loading"><span class="load-anim"></span> 加载中...</div>';
  var xhr=new XMLHttpRequest();
  xhr.open('GET','/api/questions?page='+p+'&page_size=1',true);
  xhr.onreadystatechange=function(){
    if(xhr.readyState===4&&xhr.status===200){
      try{
        var r=JSON.parse(xhr.responseText);
        if(r.items&&r.items.length>0){
          renderQ(r.items[0],p,Math.ceil(r.total/r.page_size));
        }
      }catch(e){}
    }
  };
  xhr.send();
}

function escapeHtml(s){
  if(typeof s!=='string')return String(s);
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function renderQ(q,p,tp){
  D={page:p,totalPages:tp,qid:q.id,stem:q.stem,qtype:q.type,options:q.options||{},answer:q.answer||[],explanation:q.explanation||''};
  selected=[];
  submitted=false;
  document.querySelector('.counter').textContent='第 '+p+' / '+tp+' 题';
  // 更新标签
  var tags=document.querySelector('.tags');
  var tl={'single':'单选题','multiple':'多选题','true_false':'判断题','fill_blank':'填空题','short_answer':'简答题'};
  tags.innerHTML='<span class="tag type">'+escapeHtml(tl[q.type]||q.type)+'</span>';
  // 渲染题干（HTML 转义防 XSS）
  // 重建卡片
  var card=document.getElementById('qcard');
  var oh='';
  if(q.type==='fill_blank'||q.type==='short_answer'){
    var bc=q.answer?q.answer.length:1;
    for(var i=1;i<=bc;i++){
      oh+='<input type="text" class="opt-input" id="blank_'+i+'" placeholder="第'+i+'空" autocomplete="off">';
    }
  }else if(q.options){
    var keys=Object.keys(q.options).sort();
    for(var i=0;i<keys.length;i++){
      oh+='<div class="opt" data-key="'+escapeHtml(keys[i])+'" onclick="selectOption(this)"><span class="opt-key">'+escapeHtml(keys[i])+'</span><span class="opt-val">'+escapeHtml(q.options[keys[i]])+'</span></div>';
    }
  }
  card.innerHTML='<div class="stem" id="stem">'+escapeHtml(q.stem)+'</div><div class="opts" id="opts">'+oh+'</div><div class="btns" id="btns"><button class="btn btn-pri" id="submitBtn" onclick="doSubmit()">提交答案</button></div><div class="exp" id="exp"><div id="expText"></div><div class="ans" id="ansText"></div></div>';
}
</script>
</body>
</html>
"""
