(function () {
  const ic = window.ic;
  const G = '#2dcb56', R = '#ea3636';

  function t(id, x, y, name, extra) { return Object.assign({ id: id, t: 'task', x: x, y: y, name: name }, extra || {}); }
  function corner(kind, text) { return '<span class="corner ' + kind + '">' + text + '</span>'; }

  // 流程「订单服务发布」。基线 v1.3.0：开始 → 灰度发布 → 旧版通知（下排）→ 全量发布 → 结束
  // 当前草稿：开始 → 审批确认 → 灰度发布 → 灰度验证 → 全量发布 → 结束
  const CANVAS = {
    // 草稿 vs v1.3.0
    overview: function (focus) {
      return {
        nodes: [
          { id: 's', t: 'start', x: 20, y: 127 },
          t('ap', 96, 120, '审批确认', { cls: 'add', extra: corner('add', '新增') }),
          t('gr', 296, 120, '灰度发布', { cls: focus === 'gr' ? 'focus' : 'mod', extra: corner('mod', '修改') }),
          t('vf', 496, 120, '灰度验证', { cls: 'add', extra: corner('add', '新增') }),
          t('fu', 696, 120, '全量发布', { cls: 'mod', extra: corner('mod', '修改') }),
          { id: 'e', t: 'end', x: 896, y: 127 },
          t('old', 496, 270, '旧版通知', { cls: 'del', extra: corner('del', '删除') }),
        ],
        edges: [
          ['s', 'ap', { color: G }], ['ap', 'gr', { color: G }], ['gr', 'vf', { color: G }], ['vf', 'fu', { color: G }], ['fu', 'e'],
          ['s', 'gr', { color: R, dash: true, d: 'M40 127 V76 H373 V120', label: ['连线变化：开始 → 灰度发布（已删除）', 150, 68] }],
          ['gr', 'old', { color: R, dash: true, op: 0.7, d: 'M373 174 V297 H496' }],
          ['old', 'fu', { color: R, dash: true, op: 0.7, d: 'M650 297 H773 V174' }],
        ],
        w: 960, h: 360,
      };
    },
    // 草稿 vs v1.1.0：v1.1.0 还有「发布前检查」「回滚预案」
    v110: function () {
      return {
        nodes: [
          { id: 's', t: 'start', x: 20, y: 127 },
          t('ap', 96, 120, '审批确认', { cls: 'add', extra: corner('add', '新增') }),
          t('gr', 296, 120, '灰度发布', { cls: 'mod', extra: corner('mod', '修改') }),
          t('vf', 496, 120, '灰度验证', { cls: 'add', extra: corner('add', '新增') }),
          t('fu', 696, 120, '全量发布', { cls: 'mod', extra: corner('mod', '修改') }),
          { id: 'e', t: 'end', x: 896, y: 127 },
          t('pre', 96, 270, '发布前检查', { cls: 'del', extra: corner('del', '删除') }),
          t('old', 496, 270, '旧版通知', { cls: 'del', extra: corner('del', '删除') }),
          t('rb', 846, 270, '回滚预案', { cls: 'del', extra: corner('del', '删除') }),
        ],
        edges: [
          ['s', 'ap', { color: G }], ['ap', 'gr', { color: G }], ['gr', 'vf', { color: G }], ['vf', 'fu', { color: G }],
          ['fu', 'e', { color: G, label: ['连线变化', 812, 138] }],
          ['s', 'pre', { color: R, dash: true, op: 0.7, d: 'M40 167 V297 H96' }],
          ['pre', 'gr', { color: R, dash: true, op: 0.7, d: 'M250 297 H340 V174' }],
          ['gr', 'old', { color: R, dash: true, op: 0.7, d: 'M406 174 V297 H496' }],
          ['old', 'fu', { color: R, dash: true, op: 0.7, d: 'M650 297 H740 V174' }],
          ['fu', 'rb', { color: R, dash: true, op: 0.7, d: 'M806 174 V297 H846' }],
          ['rb', 'e', { color: R, dash: true, op: 0.7, d: 'M916 270 V167' }],
        ],
        w: 1010, h: 360,
      };
    },
    // 假设：草稿只把「旧版通知」挪到了主干上
    layoutOnly: function () {
      return {
        nodes: [
          { id: 's', t: 'start', x: 20, y: 127 },
          t('gr', 196, 120, '灰度发布'),
          t('ghost', 446, 270, '旧版通知', { cls: 'ghost' }),
          t('old', 446, 120, '旧版通知', { cls: 'moved', extra: corner('mv', '位置变化') }),
          t('fu', 696, 120, '全量发布'),
          { id: 'e', t: 'end', x: 896, y: 127 },
        ],
        edges: [
          ['s', 'gr'], ['gr', 'old', { color: '#699df4', w: 1.6 }], ['old', 'fu', { color: '#699df4', w: 1.6 }], ['fu', 'e'],
          ['ghost', 'old', { color: '#979ba5', dash: true, d: 'M523 270 V180' }],
        ],
        w: 960, h: 360,
      };
    },
    // 首次发布：只有草稿
    firstDraft: function () {
      return {
        nodes: [
          { id: 's', t: 'start', x: 20, y: 127 }, t('ap', 96, 120, '审批确认'), t('gr', 296, 120, '灰度发布'),
          t('vf', 496, 120, '灰度验证'), t('fu', 696, 120, '全量发布'), { id: 'e', t: 'end', x: 896, y: 127 },
        ],
        edges: [['s', 'ap'], ['ap', 'gr'], ['gr', 'vf'], ['vf', 'fu'], ['fu', 'e']],
        w: 960, h: 360,
      };
    },
  };
  window.CANVAS = CANVAS;

  window.diffCanvas = function (c, o) {
    o = o || {};
    return '<div class="dcv">' +
      '<div class="zoom"><span>' + ic('plus', 's14') + '</span><span>' + ic('minus', 's14') + '</span><span>' + ic('fit', 's14') + '</span></div>' +
      '<div class="inner" style="transform:translate(' + (o.x || 16) + 'px,' + (o.y || 150) + 'px) scale(' + (o.scale || 0.86) + ')">' + canvasHtml(c.nodes, c.edges, { w: c.w, h: c.h }) + '</div>' +
      (o.legend === false ? '' : '<div class="legend"><span class="lg"><i class="add"></i>新增</span><span class="lg"><i class="del"></i>删除（基线位置）</span>' +
        '<span class="lg"><i class="mod"></i>修改</span><span class="lg"><i class="lnk"></i>连线变化</span></div>') +
      (o.extra || '') + '</div>';
  };

  // 背景：流程编辑页（空间已开启版本管理）
  window.renderBg = function () {
    const c = CANVAS.firstDraft();
    c.nodes.forEach(function (n) { n.y += 100; });
    renderEditor(document.querySelector('[data-editor]'), { tpl: '订单服务发布', saveEnabled: false, publish: true, nodes: c.nodes, edges: c.edges });
  };

  // 发布流程弹窗
  window.releaseDialog = function (o) {
    const crumb = o.crumb
      ? '<span class="crumb">发布流程</span><span class="sep">/</span><span class="cur">' + o.crumb + '</span>'
      : '<span>发布流程</span>';
    const base = o.baseline || '<div class="select"><span class="dark">v1.3.0</span><span class="tag sm">上一发布版</span>' + ic('down', 's12') + '</div>';
    const form =
      '<div class="form rel">' +
      '<div class="fv"><label class="req">版本号</label><div class="prefix"><span class="pre">V</span><div class="input"><span class="dark">' + (o.version || '1.4.0') + '</span></div></div></div>' +
      '<div class="fv"><label>版本描述</label><div class="textarea" style="height:120px">' +
      (o.desc === '' ? '<span class="ph">请输入版本描述</span>' : '<span class="dark">' + (o.desc || '新增审批确认和灰度验证，灰度比例调整为 30%，删除旧版通知') + '</span>') +
      '<span class="cnt">' + (o.descCnt || '31/500') + '</span></div></div>' +
      '<div class="fv rel"><label>对比基线</label>' + base + (o.baseHelp === undefined ? '<div class="help">只能选择已发布的版本，默认为上一发布版。</div>' : o.baseHelp) + (o.dropdown || '') + '</div>' +
      (o.formMk || '') + '</div>';
    const leftFt = o.leftFt !== undefined ? o.leftFt : '<button class="btn">JSON 对比</button>';
    return '<div class="rd">' +
      '<div class="hd">' + crumb + '<span class="x">' + ic('close', 's14') + '</span></div>' +
      '<div class="bd">' + form + '<div class="panel">' + o.panel + '</div></div>' +
      '<div class="ft">' + leftFt + '<span class="ml-auto rel"><button class="btn primary">发布</button>' + (o.pubMk || '') + '</span><button class="btn">取消发布</button></div>' +
      '</div>';
  };

  window.clistHtml = function (groups, foot, search) {
    const g = groups.map(function (gr) {
      const items = gr.open === false ? '' : gr.items.map(function (it) {
        return '<div class="ci ' + (it.on ? 'on' : '') + '"><span class="dot ' + it.dot + '"></span><span class="nowrap">' + it.name + '</span>' +
          '<span class="sub">' + (it.sub || '') + '</span>' + (it.go ? '<span class="go">' + ic('right', 's12') + '</span>' : '') + '</div>';
      }).join('');
      return '<div class="cgrp"><div class="gh">' + ic(gr.open === false ? 'right' : 'down', 's12') + gr.name + '<span class="cnt">' + gr.cnt + '</span></div>' + items + '</div>';
    }).join('');
    return '<div class="clist"><div class="srch"><div class="input">' + ic('search', 's14') +
      (search ? '<span class="dark">' + search + '</span>' : '<span class="ph">搜索节点名或参数名</span>') + '</div></div>' + g +
      (foot ? '<div class="foot">' + foot + '</div>' : '') + '</div>';
  };

  window.summaryBar = function (base, stats, extra) {
    return '<div class="pnl-hd"><span class="ttl">版本差异</span>' +
      '<span class="muted">' + base + ' <span style="margin:0 4px">→</span> 当前草稿（2026-09-24 14:32 由 admin 保存）</span>' +
      '<span class="ml-auto row gap8">' + stats + '</span>' + (extra || '') + '</div>';
  };
})();
