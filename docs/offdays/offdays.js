// 放假去哪：出發地切換（總表）＋請假方案切換（窗口頁）
(function () {
  var KEY = 'offdays-home';
  var toggle = document.querySelector('.od-toggle');
  if (toggle) {
    var show = function (home) {
      toggle.querySelectorAll('button').forEach(function (b) { b.classList.toggle('on', b.dataset.home === home); });
      document.querySelectorAll('[data-home]').forEach(function (el) {
        if (el.tagName !== 'BUTTON') el.hidden = el.dataset.home !== home;
      });
      try { localStorage.setItem(KEY, home); } catch (e) {}
    };
    var saved = null;
    try { saved = localStorage.getItem(KEY); } catch (e) {}
    show(saved === 'tw' ? 'tw' : 'hk');
    toggle.addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (b) show(b.dataset.home);
    });
  }

  // 請假方案：把查機票／查酒店連結換成那段日期
  var leaves = document.querySelectorAll('.od-leaves .od-leave');
  if (!leaves.length) return;
  var fmt = function (s) { var p = s.split('-'); return +p[1] + '/' + +p[2]; };
  var apply = function (start, end) {
    document.querySelectorAll('.od-book').forEach(function (a) {
      var u = new URL(a.href);
      if (a.dataset.kind === 'flight') {
        var q = u.searchParams.get('q') || '';
        u.searchParams.set('q', q.replace(/on \d{4}-\d{2}-\d{2} through \d{4}-\d{2}-\d{2}/, 'on ' + start + ' through ' + end));
        a.textContent = '查機票 ' + fmt(start) + '–' + fmt(end);
      } else {
        u.searchParams.set('checkin', start);
        u.searchParams.set('checkout', end);
      }
      a.href = u.toString();
    });
  };
  leaves.forEach(function (b) {
    b.addEventListener('click', function () {
      leaves.forEach(function (x) { x.classList.toggle('on', x === b); });
      apply(b.dataset.start, b.dataset.end);
    });
  });
})();
