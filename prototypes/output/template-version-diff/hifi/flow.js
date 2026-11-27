(function () {
  const ic = window.ic;
  const SIZE = { start: [40, 40], end: [40, 40], task: [154, 54], pg: [34, 34], cg: [34, 34], eg: [34, 34] };
  const GW_ICON = {
    pg: '<path d="M17 10v14M10 17h14"/>',
    cg: '<circle cx="17" cy="17" r="5"/>',
    eg: '<path d="M12 12l10 10M22 12l-10 10"/>',
  };

  function box(n) {
    const s = SIZE[n.t];
    return { x: n.x, y: n.y, w: s[0], h: s[1], cx: n.x + s[0] / 2, cy: n.y + s[1] / 2 };
  }

  function anchor(b, side) {
    if (side === 'top') return [b.cx, b.y];
    if (side === 'bottom') return [b.cx, b.y + b.h];
    if (side === 'left') return [b.x, b.cy];
    return [b.x + b.w, b.cy];
  }

  function edgePath(a, b, opt, na, nb) {
    if (opt.d) return opt.d;
    const isGwA = /g$/.test(na.t);
    const isGwB = /g$/.test(nb.t);
    const dy = b.cy - a.cy;
    let fromSide = opt.from || 'right';
    let toSide = opt.to || 'left';
    if (!opt.from && isGwA && Math.abs(dy) > 2) fromSide = dy < 0 ? 'top' : 'bottom';
    if (!opt.to && isGwB && Math.abs(dy) > 2) toSide = dy < 0 ? 'bottom' : 'top';
    const p = anchor(a, fromSide);
    const q = anchor(b, toSide);
    if (fromSide === 'top' || fromSide === 'bottom') {
      return 'M' + p[0] + ' ' + p[1] + ' V' + q[1] + ' H' + q[0];
    }
    if (toSide === 'top' || toSide === 'bottom') {
      return 'M' + p[0] + ' ' + p[1] + ' H' + q[0] + ' V' + q[1];
    }
    if (Math.abs(p[1] - q[1]) < 1) return 'M' + p[0] + ' ' + p[1] + ' H' + q[0];
    const mx = opt.mx !== undefined ? opt.mx : Math.round((p[0] + q[0]) / 2);
    return 'M' + p[0] + ' ' + p[1] + ' H' + mx + ' V' + q[1] + ' H' + q[0];
  }

  function nodeHtml(n) {
    const b = box(n);
    const pos = 'left:' + n.x + 'px;top:' + n.y + 'px;';
    if (n.t === 'start' || n.t === 'end') {
      return '<div class="nd-c ' + (n.cls || '') + '" style="' + pos + (n.style || '') + '">' + (n.t === 'start' ? '开始' : '结束') + (n.extra || '') + '</div>';
    }
    if (SIZE[n.t][0] === 34) {
      return '<div class="gw ' + (n.cls || '') + '" style="' + pos + '"><svg viewBox="0 0 34 34"><path class="dm" d="M17 2L32 17 17 32 2 17z"/>' +
        GW_ICON[n.t] + '</svg>' + (n.label ? '<span class="gw-lb">' + n.label + '</span>' : '') + (n.extra || '') + '</div>';
    }
    const hd = n.hd ? 'background:' + n.hd + ';' : '';
    const st = n.st ? '<span class="st">' + n.st + '</span>' : '';
    return '<div class="nd ' + (n.cls || '') + '" style="' + pos + (n.style || '') + '"><div class="nh" style="' + hd + '">' +
      ic(n.icon || 'task', 's12') + st + '</div><div class="nm">' + n.name + '</div>' + (n.extra || '') + '</div>';
  }

  window.canvasHtml = function (nodes, edges, opts) {
    opts = opts || {};
    const map = {};
    nodes.forEach(function (n) { map[n.id] = n; });
    const colors = {};
    let paths = '';
    (edges || []).forEach(function (e) {
      const o = e[2] || {};
      const na = map[e[0]], nb = map[e[1]];
      const color = o.color || '#979ba5';
      colors[color] = true;
      const id = 'ar' + color.replace('#', '');
      const d = edgePath(box(na), box(nb), o, na, nb);
      paths += '<path d="' + d + '" fill="none" stroke="' + color + '" stroke-width="' + (o.w || 1.2) + '"' +
        (o.dash ? ' stroke-dasharray="5 4"' : '') + (o.op ? ' opacity="' + o.op + '"' : '') + ' marker-end="url(#' + id + ')"/>';
      if (o.label) {
        paths += '<text x="' + o.label[1] + '" y="' + o.label[2] + '" class="elb">' + o.label[0] + '</text>';
      }
    });
    let defs = '';
    Object.keys(colors).forEach(function (c) {
      defs += '<marker id="ar' + c.replace('#', '') + '" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">' +
        '<path d="M0 0.8L7.5 4 0 7.2z" fill="' + c + '"/></marker>';
    });
    const svg = '<svg class="edges" width="' + (opts.w || 2000) + '" height="' + (opts.h || 1200) + '"><defs>' + defs + '</defs>' + paths + '</svg>';
    return svg + nodes.map(nodeHtml).join('');
  };

  // 流程编辑页：子标题栏 + 左侧节点面板 + 画布
  window.renderEditor = function (el, opts) {
    const btns = (opts.saveEnabled ? '<button class="btn primary sm">保存</button>' : '<button class="btn disabled sm">保存</button>') +
      '<button class="btn sm">调试</button>' +
      (opts.publish ? '<button class="btn primary sm">' + ic('send', 's12') + '发布</button>' : '');
    const palette = '<div class="palette">' +
      '<div class="it"><span class="circ">开始</span></div><div class="it"><span class="circ">结束</span></div>' +
      '<div class="it">' + ic('task', 's20') + '</div><div class="it">' + ic('subflow', 's20') + '</div>' +
      '<div class="it">' + ic('gw1', 's20') + '</div><div class="it">' + ic('gw2', 's20') + '</div><div class="it">' + ic('gw3', 's20') + '</div>' +
      '</div>';
    const tools = '<div class="cv-tools">' + ic('map') + '<span class="muted">|</span>' + ic('plus', 's14') + '<span>100%</span>' +
      ic('minus', 's14') + '<span class="muted">|</span>' + ic('zoom') + ic('grid') + ic('eye') + '</div>';
    const varsIc = opts.varsOn ? '<span class="tool-on">' + ic('vars') + '</span>' : ic('vars');
    el.outerHTML = '<div style="flex:1;display:flex;flex-direction:column;min-width:0;position:relative">' +
      '<div class="subhd"><span class="back">' + ic('left', 's14') + '编辑流程</span><span class="tpl">' + opts.tpl + ic('edit', 's12') + '</span>' +
      (opts.versionTag || '') +
      '<span class="tools">' + ic('branch') + ic('code') + varsIc + ic('history') + ic('book') + btns + '</span></div>' +
      '<div class="editor">' + palette + '<div class="canvas">' + tools + canvasHtml(opts.nodes, opts.edges) + (opts.canvasExtra || '') + '</div>' +
      (opts.overlay || '') + '</div></div>';
  };

  // 任务执行页：子标题栏 + 画布（无节点面板）
  window.renderTask = function (el, opts) {
    const tools = '<div class="cv-tools">' + ic('map') + '<span class="muted">|</span>' + ic('plus', 's14') + '<span>100%</span>' +
      ic('minus', 's14') + '<span class="muted">|</span>' + ic('fit') + '</div>';
    el.outerHTML = '<div style="flex:1;display:flex;flex-direction:column;min-width:0;position:relative">' +
      '<div class="subhd"><span class="back">' + ic('left', 's14') + '任务列表</span><span class="tpl">' + opts.name + '</span>' + (opts.status || '') +
      '<span class="tools">' + (opts.actions || '') + '</span></div>' +
      '<div class="editor"><div class="canvas">' + tools + canvasHtml(opts.nodes, opts.edges) + (opts.canvasExtra || '') + '</div>' +
      (opts.overlay || '') + '</div></div>';
  };
})();
