/*
 * サイト内検索。search-index.json（_automation/build_search.py が作る）を読み、
 * 入力された語を題名・病院名・本文から部分一致で探す。サーバー側の処理は無い。
 *
 * 日本語は分かち書きされないので、語に区切らず文字列として探す。空白で区切った語は
 * すべて含む記事だけを出す。全角と半角、大文字と小文字は区別しない。
 */
(function () {
  'use strict';

  var PAGE_SIZE = 20;        // 1度に出す件数
  var SNIPPET_BEFORE = 30;   // 一致した位置の手前に出す文字数
  var SNIPPET_LENGTH = 120;  // 抜粋の長さ
  var MAX_TERMS = 10;

  // 索引とリンク先は、このスクリプトの置き場所から決める。ホスト名を書き込むと、
  // 別のホストで配信する確認用のプレビューで動かなくなる。
  var searchDir = new URL('.', document.currentScript.src);
  var siteRoot = new URL('..', searchDir);

  var statusEl = document.getElementById('site-search-status');
  var resultsEl = document.getElementById('site-search-results');
  var moreEl = document.getElementById('site-search-more');
  if (!statusEl || !resultsEl || !moreEl) return;

  function fold(s) {
    return s.normalize('NFKC').toLowerCase();
  }

  function parseTerms(query) {
    var seen = {};
    return fold(query).split(/\s+/).filter(function (t) {
      if (!t || seen[t]) return false;
      seen[t] = true;
      return true;
    }).slice(0, MAX_TERMS);
  }

  function countOccurrences(text, term, limit) {
    var n = 0;
    var at = text.indexOf(term);
    while (at >= 0 && n < limit) {
      n++;
      at = text.indexOf(term, at + term.length);
    }
    return n;
  }

  // 抜粋と強調は同じ位置を指すので、表示用と照合用の長さが揃っている必要がある。
  // 小文字にすると長さが変わる文字がごく一部にある。そのときは照合用をそのまま表示に使う。
  function prepare(doc) {
    var body = doc.b.normalize('NFKC');
    var lower = body.toLowerCase();
    return {
      doc: doc,
      title: fold(doc.t),
      hospital: fold(doc.h),
      body: lower.length === body.length ? body : lower,
      lower: lower
    };
  }

  function search(entries, terms) {
    var hits = [];
    entries.forEach(function (e) {
      var score = 0;
      var first = -1;
      for (var i = 0; i < terms.length; i++) {
        var term = terms[i];
        var inTitle = e.title.indexOf(term) >= 0;
        var inHospital = e.hospital.indexOf(term) >= 0;
        var at = e.lower.indexOf(term);
        if (!inTitle && !inHospital && at < 0) return;
        score += (inTitle ? 10 : 0) + (inHospital ? 5 : 0) + countOccurrences(e.lower, term, 5);
        if (at >= 0 && (first < 0 || at < first)) first = at;
      }
      hits.push({ entry: e, score: score, first: first });
    });
    // 題名や病院名で一致したものを先に、同点なら新しい記事を先に。
    hits.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      return a.entry.doc.d < b.entry.doc.d ? 1 : (a.entry.doc.d > b.entry.doc.d ? -1 : 0);
    });
    return hits;
  }

  function isLowSurrogate(code) { return code >= 0xdc00 && code <= 0xdfff; }
  function isHighSurrogate(code) { return code >= 0xd800 && code <= 0xdbff; }

  function snippetRange(entry, first) {
    var len = entry.body.length;
    var start = first > SNIPPET_BEFORE ? first - SNIPPET_BEFORE : 0;
    var end = Math.min(len, start + SNIPPET_LENGTH);
    // サロゲートペアの途中で切ると文字が壊れる。
    if (start > 0 && isLowSurrogate(entry.body.charCodeAt(start))) start++;
    if (end < len && isHighSurrogate(entry.body.charCodeAt(end - 1))) end--;
    return { start: start, end: end };
  }

  // 抜粋の中で語に一致する範囲。重なりはつなげる。
  function highlightRanges(lower, terms) {
    var ranges = [];
    terms.forEach(function (term) {
      var at = lower.indexOf(term);
      while (at >= 0) {
        ranges.push([at, at + term.length]);
        at = lower.indexOf(term, at + term.length);
      }
    });
    ranges.sort(function (a, b) { return a[0] - b[0]; });
    var merged = [];
    ranges.forEach(function (r) {
      var last = merged[merged.length - 1];
      if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
      else merged.push(r);
    });
    return merged;
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function renderSnippet(entry, first, terms) {
    var range = snippetRange(entry, first);
    var text = entry.body.slice(range.start, range.end);
    var lower = entry.lower.slice(range.start, range.end);
    var p = el('p', 'site-search-snippet');
    var pos = 0;
    if (range.start > 0) p.appendChild(document.createTextNode('…'));
    highlightRanges(lower, terms).forEach(function (r) {
      if (r[0] > pos) p.appendChild(document.createTextNode(text.slice(pos, r[0])));
      p.appendChild(el('mark', '', text.slice(r[0], r[1])));
      pos = r[1];
    });
    if (pos < text.length) p.appendChild(document.createTextNode(text.slice(pos)));
    if (range.end < entry.body.length) p.appendChild(document.createTextNode('…'));
    return p;
  }

  // 日付・病院名・題名の並びと色は、記事一覧のカードに合わせる。
  function renderHit(hit, terms) {
    var doc = hit.entry.doc;
    var article = el('article', 'site-search-hit');
    var meta = el('ul', 'site-search-meta');

    var date = el('li', 'date');
    date.appendChild(el('i', 'fa fa-clock-o'));
    date.appendChild(document.createTextNode(' ' + doc.d.replace(/-/g, '.')));
    meta.appendChild(date);

    if (doc.h) {
      var cat = el('li', 'cat');
      cat.appendChild(el('i', 'fa fa-folder'));
      cat.appendChild(document.createTextNode(' '));
      if (doc.c) {
        var catLink = el('a', '', doc.h);
        catLink.href = new URL('category/' + doc.c + '/', siteRoot).href;
        cat.appendChild(catLink);
      } else {
        cat.appendChild(document.createTextNode(doc.h));
      }
      meta.appendChild(cat);
    }
    article.appendChild(meta);

    var heading = el('h2', 'site-search-title');
    var link = el('a', '', doc.t);
    link.href = new URL(encodeURIComponent(doc.s) + '/', siteRoot).href;
    heading.appendChild(link);
    article.appendChild(heading);

    if (hit.entry.body) article.appendChild(renderSnippet(hit.entry, hit.first, terms));
    return article;
  }

  function setStatus(text, extra) {
    statusEl.textContent = text;
    if (extra) statusEl.appendChild(extra);
  }

  function hospitalIndexHint() {
    var span = el('span', 'site-search-hint');
    span.appendChild(document.createTextNode('語を短くするか、別の語でお試しください。病院名からは'));
    var link = el('a', '', '病院一覧');
    link.href = new URL('hospital-info/', siteRoot).href;
    span.appendChild(link);
    span.appendChild(document.createTextNode('でも探せます。'));
    return span;
  }

  function show(hits, terms, query) {
    var shown = 0;
    function showMore() {
      var next = hits.slice(shown, shown + PAGE_SIZE);
      next.forEach(function (hit) { resultsEl.appendChild(renderHit(hit, terms)); });
      shown += next.length;
      moreEl.hidden = shown >= hits.length;
      if (!moreEl.hidden) {
        moreEl.textContent = 'さらに表示（残り ' + (hits.length - shown) + ' 件）';
      }
    }
    resultsEl.textContent = '';
    if (!hits.length) {
      moreEl.hidden = true;
      setStatus('「' + query + '」に一致する記事は見つかりませんでした。', hospitalIndexHint());
      return;
    }
    setStatus('「' + query + '」の検索結果: ' + hits.length + ' 件');
    moreEl.onclick = showMore;
    showMore();
  }

  var query = (new URLSearchParams(window.location.search).get('q') || '').trim();
  // 結果ページの入力欄とサイドバーの入力欄に、検索した語を残す。
  Array.prototype.forEach.call(document.querySelectorAll('input[name="q"]'), function (input) {
    input.value = query;
  });

  var terms = parseTerms(query);
  if (!terms.length) {
    setStatus('検索する語を入力してください。空白で区切ると、すべての語を含む記事を探します。');
    return;
  }

  document.title = '「' + query + '」の検索結果 | ' + document.title.split(' | ').pop();
  setStatus('検索しています…');

  fetch(new URL('search-index.json', searchDir).href)
    .then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    })
    .then(function (docs) {
      show(search(docs.map(prepare), terms), terms, query);
    })
    .catch(function () {
      setStatus('検索用のデータを読み込めませんでした。時間をおいてもう一度お試しください。');
    });
})();
