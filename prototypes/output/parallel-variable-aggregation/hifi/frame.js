(function () {
  const ICONS = {
    flow: '<path d="M3 4h10M3 8h10M3 12h6"/>',
    doc: '<rect x="3.5" y="2" width="9" height="12" rx="1"/><path d="M6 6h4M6 9h4"/>',
    bug: '<rect x="4.5" y="5" width="7" height="8" rx="3.5"/><path d="M8 5V3M2.5 8h2M11.5 8h2M3 12l1.5-1M13 12l-1.5-1"/>',
    decision: '<circle cx="4" cy="8" r="1.8"/><circle cx="12" cy="4" r="1.8"/><circle cx="12" cy="12" r="1.8"/><path d="M5.6 7.2l4.8-2.4M5.6 8.8l4.8 2.4"/>',
    gear: '<circle cx="8" cy="8" r="2.2"/><path d="M8 1.8v2M8 12.2v2M1.8 8h2M12.2 8h2M3.6 3.6L5 5M11 11l1.4 1.4M3.6 12.4L5 11M11 5l1.4-1.4"/>',
    puzzle: '<path d="M2.5 5.5h3a1.6 1.6 0 1 1 3.2 0h3v3a1.6 1.6 0 1 1 0 3.2v1.8h-9.2v-2.2a1.6 1.6 0 1 0 0-3.2z"/>',
    key: '<circle cx="5.5" cy="10.5" r="2.5"/><path d="M7.3 8.7L13 3M11 5l1.5 1.5"/>',
    chart: '<path d="M2.5 13.5h11M4.5 11V8M8 11V5M11.5 11V7"/>',
    tag: '<path d="M2.5 2.5h5.5l5.5 5.5-5.5 5.5-5.5-5.5z"/><circle cx="5.5" cy="5.5" r="1"/>',
    search: '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/>',
    down: '<path d="M4 6l4 4 4-4"/>',
    right: '<path d="M6 4l4 4-4 4"/>',
    left: '<path d="M10 3L5 8l5 5"/>',
    folder: '<path d="M1.5 4v8.5h13V5.8H8L6.5 4z"/>',
    grid: '<rect x="2.5" y="2.5" width="4.5" height="4.5"/><rect x="9" y="2.5" width="4.5" height="4.5"/><rect x="2.5" y="9" width="4.5" height="4.5"/><rect x="9" y="9" width="4.5" height="4.5"/>',
    plus: '<path d="M8 3v10M3 8h10"/>',
    edit: '<path d="M3 13l.8-3.2L10.8 2.8l2.4 2.4-7 7z"/>',
    trash: '<path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.7 9h5.6l.7-9"/>',
    grip: '<circle cx="6" cy="4" r=".6"/><circle cx="10" cy="4" r=".6"/><circle cx="6" cy="8" r=".6"/><circle cx="10" cy="8" r=".6"/><circle cx="6" cy="12" r=".6"/><circle cx="10" cy="12" r=".6"/>',
    info: '<circle cx="8" cy="8" r="6.5"/><path d="M8 7.2v4.3M8 4.8v.1"/>',
    warn: '<path d="M8 2l6.5 11.5h-13z"/><path d="M8 6.5v3.3M8 11.7v.1"/>',
    error: '<circle cx="8" cy="8" r="6.5"/><path d="M5.6 5.6l4.8 4.8M10.4 5.6l-4.8 4.8"/>',
    close: '<path d="M4 4l8 8M12 4l-8 8"/>',
    pin: '<path d="M6 2h4l-.6 4.2L12 8.8H4l2.6-2.6z"/><path d="M8 8.8V14"/>',
    ext: '<path d="M9 2.5h4.5V7M13.5 2.5L7.5 8.5M11.5 9.5v4h-9v-9h4"/>',
    download: '<path d="M8 2.5v8M4.5 7L8 10.5 11.5 7M3 13.5h10"/>',
    check: '<path d="M3 8.5l3 3 7-7"/>',
    help: '<circle cx="8" cy="8" r="6.5"/><path d="M6.2 6.2a1.9 1.9 0 1 1 2.6 1.8c-.5.2-.8.6-.8 1.1v.4M8 11.6v.1"/>',
    bell: '<path d="M4 11V7a4 4 0 0 1 8 0v4l1 1.5H3z"/><path d="M6.8 14h2.4"/>',
    fold: '<path d="M2.5 3.5h11M2.5 8h7M2.5 12.5h11M13.5 6.5L11.5 8l2 1.5"/>',
    branch: '<circle cx="4.5" cy="3.5" r="1.5"/><circle cx="4.5" cy="12.5" r="1.5"/><circle cx="11.5" cy="6" r="1.5"/><path d="M4.5 5v6M11.5 7.5c0 2-2 3-7 3.5"/>',
    code: '<path d="M5.5 4.5L2 8l3.5 3.5M10.5 4.5L14 8l-3.5 3.5"/>',
    vars: '<rect x="2" y="3" width="12" height="10" rx="1"/><path d="M5 6.5l2 3M7 6.5l-2 3M9 9.5h2.5"/>',
    history: '<path d="M2.5 8a5.5 5.5 0 1 0 1.6-3.9M2.5 2.5v2.5H5"/><path d="M8 5v3.2l2 1.3"/>',
    book: '<path d="M3 2.5h8.5v11H3z"/><path d="M5.5 5.5h3.5"/>',
    send: '<path d="M2 8l12-5.5L10.5 14 8 9z"/><path d="M8 9l6-6.5"/>',
    task: '<rect x="2.5" y="3.5" width="11" height="9" rx="1"/><path d="M2.5 6h11"/>',
    subflow: '<rect x="2.5" y="3.5" width="11" height="9" rx="1"/><path d="M2.5 6h11M9 9h3v2.5"/>',
    gw1: '<path d="M8 1.8L14.2 8 8 14.2 1.8 8z"/><path d="M6 6l4 4M10 6l-4 4"/>',
    gw2: '<path d="M8 1.8L14.2 8 8 14.2 1.8 8z"/><path d="M5.5 7h5M5.5 9h5"/>',
    gw3: '<path d="M8 1.8L14.2 8 8 14.2 1.8 8z"/><circle cx="8" cy="8" r="2"/>',
    map: '<path d="M2 4l4-1.5 4 1.5 4-1.5v9.5l-4 1.5-4-1.5-4 1.5z"/><path d="M6 2.5v9.5M10 4v9.5"/>',
    zoom: '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14M5 7h4M7 5v4"/>',
    eye: '<path d="M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z"/><circle cx="8" cy="8" r="2"/>',
    star: '<path d="M8 2l1.8 3.8 4.2.5-3.1 2.9.8 4.1L8 11.3l-3.7 2 .8-4.1L2 6.3l4.2-.5z"/>',
    refresh: '<path d="M13 8a5 5 0 1 1-1.5-3.6M13 2.5v3h-3"/>',
    user: '<circle cx="8" cy="5.5" r="2.8"/><path d="M2.5 14c.6-3 2.8-4.5 5.5-4.5s4.9 1.5 5.5 4.5"/>',
    lock: '<rect x="3.5" y="7" width="9" height="6.5" rx="1"/><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2"/>',
    copy: '<rect x="5.5" y="5.5" width="8" height="8" rx="1"/><path d="M10.5 5.5v-3h-8v8h3"/>',
    more: '<circle cx="3.5" cy="8" r=".8"/><circle cx="8" cy="8" r=".8"/><circle cx="12.5" cy="8" r=".8"/>',
    minus: '<path d="M3 8h10"/>',
    fit: '<path d="M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10"/>',
    locate: '<circle cx="8" cy="8" r="4.5"/><path d="M8 1.5v3M8 11.5v3M1.5 8h3M11.5 8h3"/>',
    arrow: '<path d="M2.5 8h10M9 4.5L12.5 8 9 11.5"/>',
    play: '<path d="M5 3l8 5-8 5z"/>',
    pause: '<path d="M5.5 3.5v9M10.5 3.5v9"/>',
    stop: '<rect x="4" y="4" width="8" height="8" rx="1"/>',
    success: '<circle cx="8" cy="8" r="6.5"/><path d="M5 8.2l2.1 2.1L11 6.4"/>',
    skip: '<path d="M3.5 3.5l6 4.5-6 4.5zM11.5 3.5v9"/>',
    list: '<path d="M5.5 4h8M5.5 8h8M5.5 12h8M2.5 4h.1M2.5 8h.1M2.5 12h.1"/>',
  };

  function svg(name, cls) {
    return '<svg class="ic ' + (cls || '') + '" viewBox="0 0 16 16">' + (ICONS[name] || '') + '</svg>';
  }
  window.ic = svg;

  const MENUS = [
    ['流程', 'flow'], ['任务', 'doc'], ['调试任务', 'bug'], ['决策表', 'decision'], ['空间配置', 'gear'],
    ['凭证管理', 'key'], ['运营统计', 'chart'], ['标签管理', 'tag'],
  ];

  function render() {
    document.querySelectorAll('[data-topbar]').forEach(function (el) {
      el.outerHTML =
        '<div class="topbar"><div class="logo"><i>F</i>BKFlow</div>' +
        '<div class="topnav"><a class="on">空间管理</a><a>系统管理</a><a>我的插件</a></div>' +
        '<div class="topright">' + svg('book') + svg('help') +
        '<span class="user">' + svg('user') + 'admin' + svg('down', 's12') + '</span></div></div>';
    });
    document.querySelectorAll('[data-sidenav]').forEach(function (el) {
      const active = el.getAttribute('data-sidenav');
      const items = MENUS.map(function (m) {
        return '<a class="' + (m[0] === active ? 'on' : '') + '">' + svg(m[1]) + m[0] + '</a>';
      }).join('');
      el.outerHTML =
        '<div class="sidenav"><div class="space-sel"><span class="av">蓝</span>蓝鲸运维中心 (100)' + svg('down', 's12') + '</div>' +
        '<div class="menu">' + items + '</div><div class="foot">' + svg('fold') + '</div></div>';
    });
    document.querySelectorAll('[data-ic]').forEach(function (el) {
      el.outerHTML = svg(el.getAttribute('data-ic'), el.getAttribute('class') || '');
    });
  }
  render();
})();
