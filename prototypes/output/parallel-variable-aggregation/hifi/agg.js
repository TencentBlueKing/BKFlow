(function () {
  const ic = window.ic;

  function t(id, x, y, name, extra) { return Object.assign({ id: id, t: 'task', x: x, y: y, name: name }, extra || {}); }

  // 同一个流程「多区域资源巡检」在各屏的画布布局
  const FLOWS = {
    two: function (sel) {
      return {
        nodes: [
          { id: 's', t: 'start', x: 24, y: 210 }, { id: 'pg', t: 'pg', x: 96, y: 213 },
          t('a', 160, 120, '华南区资源检查', { cls: sel === 'a' ? 'sel' : '' }),
          t('b', 160, 286, '华北区资源检查', { cls: sel === 'b' ? 'sel' : '' }),
          { id: 'cg', t: 'cg', x: 364, y: 213 },
          t('sum', 436, 203, '汇总通知'), { id: 'eg', t: 'eg', x: 636, y: 213 },
          t('arc', 706, 120, '结果归档'), t('alm', 706, 286, '异常告警'),
          { id: 'e', t: 'end', x: 906, y: 210 },
        ],
        edges: [['s', 'pg'], ['pg', 'a'], ['pg', 'b'], ['a', 'cg'], ['b', 'cg'], ['cg', 'sum'], ['sum', 'eg'],
          ['eg', 'arc'], ['eg', 'alm'], ['arc', 'e'], ['alm', 'e']],
      };
    },
    sameBranch: function () {
      return {
        nodes: [
          { id: 's', t: 'start', x: 24, y: 210 }, { id: 'pg', t: 'pg', x: 96, y: 213 },
          t('a', 160, 120, '华南区资源检查'), t('a2', 350, 120, '华南区配额复核', { cls: 'sel' }),
          t('b', 160, 286, '华北区资源检查'),
          { id: 'cg', t: 'cg', x: 560, y: 213 }, t('sum', 630, 203, '汇总通知'),
          { id: 'e', t: 'end', x: 830, y: 210 },
        ],
        edges: [['s', 'pg'], ['pg', 'a'], ['a', 'a2'], ['pg', 'b'], ['a2', 'cg'], ['b', 'cg'], ['cg', 'sum'], ['sum', 'e']],
      };
    },
    three: function (sel, extra) {
      extra = extra || {};
      return {
        nodes: [
          { id: 's', t: 'start', x: 24, y: 210 }, { id: 'pg', t: 'pg', x: 96, y: 213 },
          t('a', 160, 90, '华南区资源检查', extra.a),
          t('b', 160, 203, '华北区资源检查', Object.assign({ cls: sel === 'b' ? 'sel' : '' }, extra.b)),
          t('c', 160, 316, '华东区资源检查', Object.assign({ cls: sel === 'c' ? 'sel' : '' }, extra.c)),
          { id: 'cg', t: 'cg', x: 364, y: 213 },
          t('sum', 436, 203, '汇总通知', extra.sum), { id: 'eg', t: 'eg', x: 636, y: 213 },
          t('arc', 706, 120, '结果归档', extra.arc), t('alm', 706, 286, '异常告警', extra.alm),
          { id: 'e', t: 'end', x: 906, y: 210, cls: extra.endCls || '' },
        ],
        edges: [['s', 'pg'], ['pg', 'a'], ['pg', 'b'], ['pg', 'c'], ['a', 'cg'], ['b', 'cg'], ['c', 'cg'], ['cg', 'sum'],
          ['sum', 'eg'], ['eg', 'arc'], ['eg', 'alm', { dash: extra.almDash }], ['arc', 'e'], ['alm', 'e', { dash: extra.almDash }]],
      };
    },
    // 删除「华北区资源检查」之后：分支 1 华南、分支 2 华东
    se: function (extra) {
      extra = extra || {};
      return {
        nodes: [
          { id: 's', t: 'start', x: 24, y: 210, cls: extra.sCls || '' }, { id: 'pg', t: 'pg', x: 96, y: 213 },
          t('a', 160, 120, '华南区资源检查', extra.a), t('c', 160, 286, '华东区资源检查', extra.c),
          { id: 'cg', t: 'cg', x: 364, y: 213 },
          t('sum', 436, 203, '汇总通知', extra.sum), { id: 'eg', t: 'eg', x: 636, y: 213 },
          t('arc', 706, 120, '结果归档', extra.arc), t('alm', 706, 286, '异常告警', extra.alm),
          { id: 'e', t: 'end', x: 906, y: 210, cls: extra.endCls || '', style: extra.endStyle || '' },
        ],
        edges: [['s', 'pg'], ['pg', 'a'], ['pg', 'c'], ['a', 'cg'], ['c', 'cg'], ['cg', 'sum'], ['sum', 'eg'],
          ['eg', 'arc'], ['eg', 'alm', { dash: extra.almDash }], ['arc', 'e'], ['alm', 'e', { dash: extra.almDash }]],
      };
    },
  };
  window.FLOWS = FLOWS;

  // 节点配置侧滑（资源巡检插件）
  window.nodeConfig = function (o) {
    const rows = o.outputs.map(function (r) {
      const hooked = r.varKey ? '<div class="hooked"><span class="var">' + r.varKey + '</span>' + (r.varTag || '') +
        '<span class="ed ' + (r.varTag ? '' : 'ml-auto') + '">' + ic('edit', 's12') + '</span></div>' : '';
      return '<tr class="' + (r.rowCls || '') + '"><td class="name">' + r.name + '</td><td><div class="okey"><span>' + r.key + '</span>' + hooked + '</div></td>' +
        '<td class="hk"><span class="hook ' + (r.hook || '') + '">${x}</span>' + (r.mk || '') + '</td></tr>';
    }).join('');
    return '<div class="slider" style="width:' + (o.width || 760) + 'px">' +
      '<div class="hd"><span class="close">' + ic('right', 's14') + '</span>节点配置<span class="ml-auto link" style="font-size:14px">全局变量</span></div>' +
      '<div class="bd" style="padding-top:16px">' +
      '<div class="sec-title">基础信息</div>' +
      '<div class="fh"><label class="req">标准插件</label><div class="ctl row"><div class="input readonly" style="flex:1;border-right:none"><span class="dark">资源巡检</span><span class="tag sm primary">API 插件</span></div>' +
      '<button class="btn" style="border-color:#3a84ff;color:#3a84ff;background:#e1ecff;min-width:0">重选</button></div></div>' +
      '<div class="fh"><label class="req">插件版本</label><div class="ctl"><div class="select"><span class="dark">v2.1.0</span>' + ic('down', 's12') + '</div></div></div>' +
      '<div class="fh"><label class="req">节点名称</label><div class="ctl"><div class="input"><span class="dark">' + o.name + '</span></div></div></div>' +
      '<div class="fh" style="margin-bottom:22px"><label>失败处理</label><div class="ctl row gap24" style="height:32px">' +
      '<span class="check">自动跳过</span><span class="check on">手动跳过</span><span class="check on">手动重试</span><span class="check">超时后自动重试</span></div></div>' +
      '<div class="sec-title">输入参数</div>' +
      '<div class="fh"><label class="req">巡检区域</label><div class="ctl"><div class="select"><span class="dark">' + o.region + '</span>' + ic('down', 's12') + '</div></div></div>' +
      '<div class="fh" style="margin-bottom:22px"><label>检查项</label><div class="ctl"><div class="input"><span class="dark">' + (o.items || 'CPU、内存、磁盘') + '</span></div></div></div>' +
      '<div class="sec-title rel">输出参数' + (o.outMk || '') + '</div>' +
      '<div class="rel"><div class="tb-wrap"><table class="tb"><colgroup><col style="width:150px"><col><col style="width:120px"></colgroup>' +
      '<thead><tr><th>名称</th><th>KEY</th><th>勾选为全局变量</th></tr></thead><tbody>' + rows + '</tbody></table></div>' + (o.tableMk || '') + '</div>' +
      '</div>' +
      '<div class="ft"><button class="btn primary">确定</button><button class="btn">取消</button></div></div>';
  };

  window.stepsHtml = function (states) {
    const names = ['创建方式', '聚合方式', '引用确认'];
    return '<div class="steps">' + names.map(function (n, i) {
      const s = states[i];
      const dot = s === 'done' ? ic('check', 's12') : String(i + 1);
      const line = i < 2 ? '<span class="step-line ' + (states[i + 1] === 'on' || states[i + 1] === 'done' ? 'on' : '') + '"></span>' : '';
      return '<span class="step ' + s + '"><span class="dot">' + dot + '</span>' + n + '</span>' + line;
    }).join('') + '</div>';
  };

  window.varDialog = function (o) {
    return '<div class="dialog" style="width:' + (o.width || 640) + 'px;top:' + (o.top || 110) + 'px">' +
      '<div class="hd">变量配置<span class="x">' + ic('close', 's14') + '</span></div>' +
      '<div class="bd">' + o.body + '</div><div class="ft">' + o.foot + '</div></div>';
  };
})();
