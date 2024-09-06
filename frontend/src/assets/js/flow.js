function t (t, e) {
  const n = Object.keys(t);if (Object.getOwnPropertySymbols) {
    let i = Object.getOwnPropertySymbols(t);e && (i = i.filter((e) => Object.getOwnPropertyDescriptor(t, e).enumerable)), n.push.apply(n, i)
  } return n
} function e (e) {
  for (let i = 1;i < arguments.length;i++) {
    var o = null != arguments[i] ? arguments[i] : {};i % 2 ? t(Object(o), !0).forEach((t) => {
      n(e, t, o[t])
    }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(o)) : t(Object(o)).forEach((t) => {
      Object.defineProperty(e, t, Object.getOwnPropertyDescriptor(o, t))
    })
  } return e
} function n (t, e, n) {
  return e in t ? Object.defineProperty(t, e, { value: n, enumerable: !0, configurable: !0, writable: !0 }) : t[e] = n, t
} function i (t, e) {
  return (function (t) {
    if (Array.isArray(t)) return t
  }(t)) || (function (t, e) {
    let n = null == t ? null : 'undefined' !== typeof Symbol && t[Symbol.iterator] || t['@@iterator'];if (null == n) return;let i; let o; const s = []; let r = !0; let a = !1;try {
      for (n = n.call(t);!(r = (i = n.next()).done) && (s.push(i.value), !e || s.length !== e);r = !0);
    } catch (t) {
      a = !0, o = t
    } finally {
      try {
        r || null == n.return || n.return()
      } finally {
        if (a) throw o
      }
    } return s
  }(t, e)) || (function (t, e) {
    if (!t) return;if ('string' === typeof t) return o(t, e);let n = Object.prototype.toString.call(t).slice(8, -1);'Object' === n && t.constructor && (n = t.constructor.name);if ('Map' === n || 'Set' === n) return Array.from(t);if ('Arguments' === n || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return o(t, e)
  }(t, e)) || (function () {
    throw new TypeError('Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.')
  }())
} function o (t, e) {
  (null == e || e > t.length) && (e = t.length);for (var n = 0, i = new Array(e);n < e;n++)i[n] = t[n];return i
} const s = 'undefined' !== typeof globalThis ? globalThis : 'undefined' !== typeof window ? window : 'undefined' !== typeof global ? global : 'undefined' !== typeof self ? self : {};let r; const a = ((function (t, e) {
  (function () {
    void 0 === Math.sgn && (Math.sgn = function (t) {
      return 0 == t ? 0 : t > 0 ? 1 : -1
    });const t = function (t, e) {
      return { x: t.x - e.x, y: t.y - e.y }
    }; const n = function (t, e) {
      return t.x * e.x + t.y * e.y
    }; const i = function (t) {
      return Math.sqrt(t.x * t.x + t.y * t.y)
    }; const o = function (t, e) {
      return { x: t.x * e, y: t.y * e }
    }; const s = Math.pow(2, -65); const r = function (e, n) {
      for (var o = [], s = a(e, n), r = n.length - 1, u = l(s, 2 * r - 1, o, 0), c = t(e, n[0]), h = i(c), p = 0, f = 0;f < u;f++) {
        c = t(e, d(n, r, o[f], null, null));var g = i(c);g < h && (h = g, p = o[f])
      } return c = t(e, n[r]), (g = i(c)) < h && (h = g, p = 1), { location: p, distance: h }
    }; var a = function (e, i) {
      for (var s = i.length - 1, r = 2 * s - 1, a = [], l = [], u = [], c = [], h = [[1, .6, .3, .1], [.4, .6, .6, .4], [.1, .3, .6, 1]], d = 0;d <= s;d++)a[d] = t(i[d], e);for (d = 0;d <= s - 1;d++)l[d] = t(i[d + 1], i[d]), l[d] = o(l[d], 3);for (let p = 0;p <= s - 1;p++) for (let f = 0;f <= s;f++)u[p] || (u[p] = []), u[p][f] = n(l[p], a[f]);for (d = 0;d <= r;d++)c[d] || (c[d] = []), c[d].y = 0, c[d].x = parseFloat(d) / r;for (let g = s, m = s - 1, v = 0;v <= g + m;v++) {
        const y = Math.max(0, v - m); const b = Math.min(v, g);for (d = y;d <= b;d++) {
          const P = v - d;c[d + P].y += u[P][d] * h[P][d]
        }
      } return c
    }; var l = function (t, e, n, i) {
      let o; let s; const r = []; const a = []; const p = []; const f = [];switch (u(t, e)) {
        case 0:return 0;case 1:if (i >= 64) return n[0] = (t[0].x + t[e].x) / 2, 1;if (c(t, e)) return n[0] = h(t, e), 1
      }d(t, e, .5, r, a), o = l(r, e, p, i + 1), s = l(a, e, f, i + 1);for (var g = 0;g < o;g++)n[g] = p[g];for (g = 0;g < s;g++)n[g + o] = f[g];return o + s
    }; var u = function (t, e) {
      let n; let i; let o = 0;n = i = Math.sgn(t[0].y);for (let s = 1;s <= e;s++)(n = Math.sgn(t[s].y)) != i && o++, i = n;return o
    }; var c = function (t, e) {
      let n; let i; let o; let r; let a; let l; let u; let c; let h;r = t[0].y - t[e].y, a = t[e].x - t[0].x, l = t[0].x * t[e].y - t[e].x * t[0].y, c = h = 0;for (let d = 1;d < e;d++) {
        const p = r * t[d].x + a * t[d].y + l;p > c ? c = p : p < h && (h = p)
      } return 0, 1, 0, n = (1 * (l - c) - 0 * (u = a)) * (1 / (0 * u - 1 * r)), i = (1 * (l - h) - 0 * (u = a)) * (1 / (0 * u - 1 * r)), o = Math.min(n, i), Math.max(n, i) - o < s ? 1 : 0
    }; var h = function (t, e) {
      const n = t[e].x - t[0].x; const i = t[e].y - t[0].y; const o = t[0].x - 0;return 0 + 1 * ((n * (t[0].y - 0) - i * o) * (1 / (0 * n - 1 * i)))
    }; var d = function (t, e, n, i, o) {
      for (var s = [[]], r = 0;r <= e;r++)s[0][r] = t[r];for (let a = 1;a <= e;a++) for (r = 0;r <= e - a;r++)s[a] || (s[a] = []), s[a][r] || (s[a][r] = {}), s[a][r].x = (1 - n) * s[a - 1][r].x + n * s[a - 1][r + 1].x, s[a][r].y = (1 - n) * s[a - 1][r].y + n * s[a - 1][r + 1].y;if (null != i) for (r = 0;r <= e;r++)i[r] = s[r][0];if (null != o) for (r = 0;r <= e;r++)o[r] = s[e - r][r];return s[e][0]
    }; const p = {}; const f = function (t, e) {
      for (var n = (function (t) {
          let e = p[t];if (!e) {
            const n = function (t) {
              return function (e) {
                return t
              }
            }; const i = function () {
              return function (t) {
                return t
              }
            }; const o = function () {
              return function (t) {
                return 1 - t
              }
            }; const s = function (t) {
              return function (e) {
                for (var n = 1, i = 0;i < t.length;i++)n *= t[i](e);return n
              }
            };(e = []).push(new function () {
              return function (e) {
                return Math.pow(e, t)
              }
            });for (let r = 1;r < t;r++) {
              for (var a = [new n(t)], l = 0;l < t - r;l++)a.push(new i);for (l = 0;l < r;l++)a.push(new o);e.push(new s(a))
            }e.push(new function () {
              return function (e) {
                return Math.pow(1 - e, t)
              }
            }), p[t] = e
          } return e
        }(t.length - 1)), i = 0, o = 0, s = 0;s < t.length;s++)i += t[s].x * n[s](e), o += t[s].y * n[s](e);return { x: i, y: o }
    }; const g = function (t, e) {
      return Math.sqrt(Math.pow(t.x - e.x, 2) + Math.pow(t.y - e.y, 2))
    }; const m = function (t) {
      return t[0].x === t[1].x && t[0].y === t[1].y
    }; const v = function (t, e, n) {
      if (m(t)) return { point: t[0], location: e };for (var i = f(t, e), o = 0, s = e, r = n > 0 ? 1 : -1, a = null;o < Math.abs(n);)a = f(t, s += .005 * r), o += g(a, i), i = a;return { point: a, location: s }
    }; const y = function (t, e) {
      const n = f(t, e); const i = f(t.slice(0, t.length - 1), e); const o = i.y - n.y; const s = i.x - n.x;return 0 === o ? 1 / 0 : Math.atan(o / s)
    }; const b = function (t, e, n, i, o) {
      const s = i - e; const r = t - n; const a = t * (e - i) + e * (n - t); const l = (function (t) {
        return [P(t, 'x'), P(t, 'y')]
      }(o)); const u = [s * l[0][0] + r * l[1][0], s * l[0][1] + r * l[1][1], s * l[0][2] + r * l[1][2], s * l[0][3] + r * l[1][3] + a]; const c = function (t, e, n, i) {
        let o; let s; const r = e / t; const a = n / t; const l = i / t; const u = (3 * a - Math.pow(r, 2)) / 9; const c = (9 * r * a - 27 * l - 2 * Math.pow(r, 3)) / 54; const h = Math.pow(u, 3) + Math.pow(c, 2); const d = [];if (h >= 0)o = x(c + Math.sqrt(h)) * Math.pow(Math.abs(c + Math.sqrt(h)), 1 / 3), s = x(c - Math.sqrt(h)) * Math.pow(Math.abs(c - Math.sqrt(h)), 1 / 3), d[0] = -r / 3 + (o + s), d[1] = -r / 3 - (o + s) / 2, d[2] = -r / 3 - (o + s) / 2, 0 !== Math.abs(Math.sqrt(3) * (o - s) / 2) && (d[1] = -1, d[2] = -1);else {
          const p = Math.acos(c / Math.sqrt(-Math.pow(u, 3)));d[0] = 2 * Math.sqrt(-u) * Math.cos(p / 3) - r / 3, d[1] = 2 * Math.sqrt(-u) * Math.cos((p + 2 * Math.PI) / 3) - r / 3, d[2] = 2 * Math.sqrt(-u) * Math.cos((p + 4 * Math.PI) / 3) - r / 3
        } for (let f = 0;f < 3;f++)(d[f] < 0 || d[f] > 1) && (d[f] = -1);return d
      }.apply(null, u); const h = [];if (null != c) for (let d = 0;d < 3;d++) {
        var p; const f = c[d]; const g = Math.pow(f, 2); const m = Math.pow(f, 3); const v = [l[0][0] * m + l[0][1] * g + l[0][2] * f + l[0][3], l[1][0] * m + l[1][1] * g + l[1][2] * f + l[1][3]];p = n - t != 0 ? (v[0] - t) / (n - t) : (v[1] - e) / (i - e), f >= 0 && f <= 1 && p >= 0 && p <= 1 && h.push(v)
      } return h
    };function P (t, e) {
      return [-t[0][e] + 3 * t[1][e] + -3 * t[2][e] + t[3][e], 3 * t[0][e] - 6 * t[1][e] + 3 * t[2][e], -3 * t[0][e] + 3 * t[1][e], t[0][e]]
    } function x (t) {
      return t < 0 ? -1 : t > 0 ? 1 : 0
    } const C = this.jsBezier = { distanceFromCurve: r, gradientAtPoint: y, gradientAtPointAlongCurveFrom (t, e, n) {
      const i = v(t, e, n);return i.location > 1 && (i.location = 1), i.location < 0 && (i.location = 0), y(t, i.location)
    }, nearestPointOnCurve (t, e) {
      const n = r(t, e);return { point: d(e, e.length - 1, n.location, null, null), location: n.location }
    }, pointOnCurve: f, pointAlongCurveFrom (t, e, n) {
      return v(t, e, n).point
    }, perpendicularToCurveAt (t, e, n, i) {
      const o = v(t, e, i = null == i ? 0 : i); const s = y(t, o.location); const r = Math.atan(-1 / s); const a = n / 2 * Math.sin(r); const l = n / 2 * Math.cos(r);return [{ x: o.point.x + l, y: o.point.y + a }, { x: o.point.x - l, y: o.point.y - a }]
    }, locationAlongCurveFrom (t, e, n) {
      return v(t, e, n).location
    }, getLength (t) {
      const e = (new Date).getTime();if (m(t)) return 0;for (var n = f(t, 0), i = 0, o = 0, s = null;o < 1;)s = f(t, o += .005), i += g(s, n), n = s;return console.log('length', (new Date).getTime() - e), i
    }, lineIntersection: b, boxIntersection (t, e, n, i, o) {
      const s = [];return s.push.apply(s, b(t, e, t + n, e, o)), s.push.apply(s, b(t + n, e, t + n, e + i, o)), s.push.apply(s, b(t + n, e + i, t, e + i, o)), s.push.apply(s, b(t, e + i, t, e, o)), s
    }, boundingBoxIntersection (t, e) {
      const n = [];return n.push.apply(n, b(t.x, t.y, t.x + t.w, t.y, e)), n.push.apply(n, b(t.x + t.w, t.y, t.x + t.w, t.y + t.h, e)), n.push.apply(n, b(t.x + t.w, t.y + t.h, t.x, t.y + t.h, e)), n.push.apply(n, b(t.x, t.y + t.h, t.x, t.y, e)), n
    }, version: '0.9.0' };e.jsBezier = C
  }).call('undefined' !== typeof window ? window : s), function () {
    const t = this.Biltong = { version: '0.4.0' };e.Biltong = t;const n = function (t) {
      return '[object Array]' === Object.prototype.toString.call(t)
    }; const i = function (t, e, i) {
      return i(t = n(t) ? t : [t.x, t.y], e = n(e) ? e : [e.x, e.y])
    }; const o = t.gradient = function (t, e) {
      return i(t, e, (t, e) => e[0] == t[0] ? e[1] > t[1] ? 1 / 0 : -1 / 0 : e[1] == t[1] ? e[0] > t[0] ? 0 : -0 : (e[1] - t[1]) / (e[0] - t[0]))
    }; const s = (t.normal = function (t, e) {
      return -1 / o(t, e)
    }, t.lineLength = function (t, e) {
      return i(t, e, (t, e) => Math.sqrt(Math.pow(e[1] - t[1], 2) + Math.pow(e[0] - t[0], 2)))
    }, t.quadrant = function (t, e) {
      return i(t, e, (t, e) => e[0] > t[0] ? e[1] > t[1] ? 2 : 1 : e[0] == t[0] ? e[1] > t[1] ? 2 : 1 : e[1] > t[1] ? 3 : 4)
    }); const r = (t.theta = function (t, e) {
      return i(t, e, (t, e) => {
        const n = o(t, e); let i = Math.atan(n); const r = s(t, e);return 4 != r && 3 != r || (i += Math.PI), i < 0 && (i += 2 * Math.PI), i
      })
    }, t.intersects = function (t, e) {
      const n = t.x; const i = t.x + t.w; const o = t.y; const s = t.y + t.h; const r = e.x; const a = e.x + e.w; const l = e.y; const u = e.y + e.h;return n <= r && r <= i && o <= l && l <= s || n <= a && a <= i && o <= l && l <= s || n <= r && r <= i && o <= u && u <= s || n <= a && r <= i && o <= u && u <= s || r <= n && n <= a && l <= o && o <= u || r <= i && i <= a && l <= o && o <= u || r <= n && n <= a && l <= s && s <= u || r <= i && n <= a && l <= s && s <= u
    }, t.encloses = function (t, e, n) {
      const i = t.x; const o = t.x + t.w; const s = t.y; const r = t.y + t.h; const a = e.x; const l = e.x + e.w; const u = e.y; const c = e.y + e.h; const h = function (t, e, i, o) {
        return n ? t <= e && i >= o : t < e && i > o
      };return h(i, a, o, l) && h(s, u, r, c)
    }, [null, [1, -1], [1, 1], [-1, 1], [-1, -1]]); const a = [null, [-1, -1], [-1, 1], [1, 1], [1, -1]];t.pointOnLine = function (t, e, n) {
      const i = o(t, e); const l = s(t, e); const u = n > 0 ? r[l] : a[l]; const c = Math.atan(i); const h = Math.abs(n * Math.sin(c)) * u[1]; const d = Math.abs(n * Math.cos(c)) * u[0];return { x: t.x + d, y: t.y + h }
    }, t.perpendicularLineTo = function (t, e, n) {
      const i = o(t, e); const s = Math.atan(-1 / i); const r = n / 2 * Math.sin(s); const a = n / 2 * Math.cos(s);return [{ x: e.x + a, y: e.y + r }, { x: e.x - a, y: e.y - r }]
    }
  }.call('undefined' !== typeof window ? window : s), function () {
    function t (t, e, n, i, o, s, r, a) {
      return (function () {
        const t = [];return Array.prototype.push.apply(t, arguments), t.item = function (t) {
          return this[t]
        }, t
      }(function (t, e, n, i, o, s, r, a) {
        return new Touch({ target: e, identifier: A(), pageX: n, pageY: i, screenX: o, screenY: s, clientX: r || o, clientY: a || s })
      }.apply(null, arguments)))
    } const n = function (t, e, n) {
      for (let i = (n = n || t.parentNode).querySelectorAll(e), o = 0;o < i.length;o++) if (i[o] === t) return !0;return !1
    }; const i = function (t) {
      return 'string' === typeof t || t.constructor === String ? document.getElementById(t) : t
    }; const o = function (t) {
      return t.srcElement || t.target
    }; const s = function (t, e, n, i) {
      if (i) {
        if (void 0 !== t.path && t.path.indexOf) return { path: t.path, end: t.path.indexOf(n) };const o = { path: [], end: -1 }; var s = function (t) {
          o.path.push(t), t === n ? o.end = o.path.length - 1 : null != t.parentNode && s(t.parentNode)
        };return s(e), o
      } return { path: [e], end: 1 }
    }; const r = function (t, e) {
      for (var n = 0, i = t.length;n < i && t[n] != e;n++);n < t.length && t.splice(n, 1)
    }; let a = 1; const l = function (t, e, n) {
      const i = a++;return t.__ta = t.__ta || {}, t.__ta[e] = t.__ta[e] || {}, t.__ta[e][i] = n, n.__tauid = i, i
    }; const u = function (t, e, i, r) {
      if (null == t) return i;const a = t.split(','); var l = function (r) {
        l.__tauid = i.__tauid;const u = o(r); let c = u; const h = s(r, u, e, null != t);if (-1 != h.end) for (let d = 0;d < h.end;d++) {
          c = h.path[d];for (let p = 0;p < a.length;p++)n(c, a[p], e) && i.apply(c, arguments)
        }
      };return c(i, r, l), l
    }; var c = function (t, e, n) {
      t.__taExtra = t.__taExtra || [], t.__taExtra.push([e, n])
    }; const h = function (t, e, n, i) {
      if (m && y[e]) {
        const o = u(i, t, n, y[e]);S(t, y[e], o, n)
      }'focus' === e && null == t.getAttribute('tabindex') && t.setAttribute('tabindex', '1'), S(t, e, u(i, t, n, e), n)
    }; const d = { tap: { touches: 1, taps: 1 }, dbltap: { touches: 1, taps: 2 }, contextmenu: { touches: 2, taps: 1 } }; const p = function (t, e) {
      return function (i, a, l, u) {
        if ('contextmenu' == a && v)h(i, a, l, u);else {
          if (null == i.__taTapHandler) {
            const c = i.__taTapHandler = { tap: [], dbltap: [], contextmenu: [], down: !1, taps: 0, downSelectors: [] }; const p = function () {
              c.down = !1
            }; const f = function () {
              c.taps = 0
            };h(i, 'mousedown', (r) => {
              for (let a = o(r), l = s(r, a, i, null != u), h = !1, d = 0;d < l.end;d++) {
                if (h) return;a = l.path[d];for (let g = 0;g < c.downSelectors.length;g++) if (null == c.downSelectors[g] || n(a, c.downSelectors[g], i)) {
                  c.down = !0, setTimeout(p, t), setTimeout(f, e), h = !0;break
                }
              }
            }), h(i, 'mouseup', (t) => {
              if (c.down) {
                let e; let r; const a = o(t);c.taps++;const l = E(t);for (const u in d) if (d.hasOwnProperty(u)) {
                  const h = d[u];if (h.touches === l && (1 === h.taps || h.taps === c.taps)) for (let p = 0;p < c[u].length;p++) {
                    r = s(t, a, i, null != c[u][p][1]);for (let f = 0;f < r.end;f++) if (e = r.path[f], null == c[u][p][1] || n(e, c[u][p][1], i)) {
                      c[u][p][0].apply(e, [t]);break
                    }
                  }
                }
              }
            })
          }i.__taTapHandler.downSelectors.push(u), i.__taTapHandler[a].push([l, u]), l.__taUnstore = function () {
            r(i.__taTapHandler[a], l)
          }
        }
      }
    }; const f = function (t, e, n, i) {
      for (const o in n.__tamee[t])n.__tamee[t].hasOwnProperty(o) && n.__tamee[t][o].apply(i, [e])
    }; const g = function () {
      const t = [];return function (e, i, s, r) {
        if (!e.__tamee) {
          e.__tamee = { over: !1, mouseenter: [], mouseexit: [] };const a = function (i) {
            const s = o(i);(null == r && s == e && !e.__tamee.over || n(s, r, e) && (null == s.__tamee || !s.__tamee.over)) && (f('mouseenter', i, e, s), s.__tamee = s.__tamee || {}, s.__tamee.over = !0, t.push(s))
          }; const c = function (i) {
            for (let s = o(i), r = 0;r < t.length;r++)s != t[r] || n(i.relatedTarget || i.toElement, '*', s) || (s.__tamee.over = !1, t.splice(r, 1), f('mouseexit', i, e, s))
          };S(e, 'mouseover', u(r, e, a, 'mouseover'), a), S(e, 'mouseout', u(r, e, c, 'mouseout'), c)
        }s.__taUnstore = function () {
          delete e.__tamee[i][s.__tauid]
        }, l(e, i, s), e.__tamee[i][s.__tauid] = s
      }
    }; var m = 'ontouchstart' in document.documentElement || navigator.maxTouchPoints; var v = 'onmousedown' in document.documentElement; var y = { mousedown: 'touchstart', mouseup: 'touchend', mousemove: 'touchmove' }; const b = (function () {
      let t = -1;if ('Microsoft Internet Explorer' == navigator.appName) {
        const e = navigator.userAgent;null != new RegExp('MSIE ([0-9]{1,}[.0-9]{0,})').exec(e) && (t = parseFloat(RegExp.$1))
      } return t
    }()); const P = b > -1 && b < 9; const x = function (t, e) {
      if (null == t) return [0, 0];const n = j(t); const i = _(n, 0);return [i[`${e}X`], i[`${e}Y`]]
    }; const C = function (t) {
      return null == t ? [0, 0] : P ? [t.clientX + document.documentElement.scrollLeft, t.clientY + document.documentElement.scrollTop] : x(t, 'page')
    }; var _ = function (t, e) {
      return t.item ? t.item(e) : t[e]
    }; var j = function (t) {
      return t.touches && t.touches.length > 0 ? t.touches : t.changedTouches && t.changedTouches.length > 0 ? t.changedTouches : t.targetTouches && t.targetTouches.length > 0 ? t.targetTouches : [t]
    }; var E = function (t) {
      return j(t).length
    }; var S = function (t, e, n, i) {
      if (l(t, e, n), i.__tauid = n.__tauid, t.addEventListener)t.addEventListener(e, n, !1);else if (t.attachEvent) {
        const o = e + n.__tauid;t[`e${o}`] = n, t[o] = function () {
          t[`e${o}`] && t[`e${o}`](window.event)
        }, t.attachEvent(`on${e}`, t[o])
      }
    }; var w = function (t, e, n) {
      null != n && D(t, function () {
        const o = i(this);if ((function (t, e, n) {
          if (t.__ta && t.__ta[e] && delete t.__ta[e][n.__tauid], n.__taExtra) {
            for (let i = 0;i < n.__taExtra.length;i++)w(t, n.__taExtra[i][0], n.__taExtra[i][1]);n.__taExtra.length = 0
          }n.__taUnstore && n.__taUnstore()
        }(o, e, n)), null != n.__tauid) if (o.removeEventListener)o.removeEventListener(e, n, !1), m && y[e] && o.removeEventListener(y[e], n, !1);else if (this.detachEvent) {
          const s = e + n.__tauid;o[s] && o.detachEvent(`on${e}`, o[s]), o[s] = null, o[`e${s}`] = null
        }n.__taTouchProxy && w(t, n.__taTouchProxy[1], n.__taTouchProxy[0])
      })
    }; var D = function (t, e) {
      if (null != t) {
        t = 'undefined' !== typeof Window && 'unknown' !== typeof t.top && t == t.top ? [t] : 'string' !== typeof t && null == t.tagName && null != t.length ? t : 'string' === typeof t ? document.querySelectorAll(t) : [t];for (let n = 0;n < t.length;n++)e.apply(t[n])
      }
    }; var A = function () {
      return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (t) => {
        const e = 16 * Math.random() | 0;return ('x' == t ? e : 3 & e | 8).toString(16)
      })
    };this.Mottle = function (e) {
      const n = (e = e || {}).clickThreshold || 250; const s = e.dblClickThreshold || 450; const a = new g; const l = new p(n, s); const u = e.smartClicks; const c = function (t, e, n, s) {
        null != n && D(t, function () {
          const t = i(this);u && 'click' === e ? (function (t, e, n, i) {
            null == t.__taSmartClicks && (h(t, 'mousedown', (e) => {
              t.__tad = C(e)
            }, i), h(t, 'mouseup', (e) => {
              t.__tau = C(e)
            }, i), h(t, 'click', (e) => {
              if (t.__tad && t.__tau && t.__tad[0] === t.__tau[0] && t.__tad[1] === t.__tau[1]) for (let n = 0;n < t.__taSmartClicks.length;n++)t.__taSmartClicks[n].apply(o(e), [e])
            }, i), t.__taSmartClicks = []);t.__taSmartClicks.push(n), n.__taUnstore = function () {
              r(t.__taSmartClicks, n)
            }
          }(t, 0, n, s)) : 'tap' === e || 'dbltap' === e || 'contextmenu' === e ? l(t, e, n, s) : 'mouseenter' === e || 'mouseexit' == e ? a(t, e, n, s) : h(t, e, n, s)
        })
      };this.remove = function (t) {
        return D(t, function () {
          const t = i(this);if (t.__ta) for (const e in t.__ta) if (t.__ta.hasOwnProperty(e)) for (const n in t.__ta[e])t.__ta[e].hasOwnProperty(n) && w(t, e, t.__ta[e][n]);t.parentNode && t.parentNode.removeChild(t)
        }), this
      }, this.on = function (t, e, n, i) {
        const o = arguments[0]; const s = 4 == arguments.length ? arguments[2] : null; const r = arguments[1]; const a = arguments[arguments.length - 1];return c(o, r, a, s), this
      }, this.off = function (t, e, n) {
        return w(t, e, n), this
      }, this.trigger = function (e, n, o, s) {
        const r = v && ('undefined' === typeof MouseEvent || null == o || o.constructor === MouseEvent); const a = m && !v && y[n] ? y[n] : n; const l = !(m && !v && y[n]); const u = C(o); const c = x(o, 'screen'); const h = (function (t) {
          return x(t, 'client')
        }(o));return D(e, function () {
          let e; const d = i(this);o = o || { screenX: c[0], screenY: c[1], clientX: h[0], clientY: h[1] };const p = function (t) {
            s && (t.payload = s)
          }; const f = { TouchEvent (e) {
            const n = t(window, d, 0, u[0], u[1], c[0], c[1], h[0], h[1]);(e.initTouchEvent || e.initEvent)(a, !0, !0, window, null, c[0], c[1], h[0], h[1], !1, !1, !1, !1, n, n, n, 1, 0)
          }, MouseEvents (t) {
            t.initMouseEvent(a, !0, !0, window, 0, c[0], c[1], h[0], h[1], !1, !1, !1, !1, 1, d)
          } };if (document.createEvent) {
            const g = !l && !r && m && y[n] ? 'TouchEvent' : 'MouseEvents';e = document.createEvent(g), f[g](e), p(e), d.dispatchEvent(e)
          } else document.createEventObject && ((e = document.createEventObject()).eventType = e.eventName = a, e.screenX = c[0], e.screenY = c[1], e.clientX = h[0], e.clientY = h[1], p(e), d.fireEvent(`on${a}`, e))
        }), this
      }
    }, this.Mottle.consume = function (t, e) {
      t.stopPropagation ? t.stopPropagation() : t.returnValue = !1, !e && t.preventDefault && t.preventDefault()
    }, this.Mottle.pageLocation = C, this.Mottle.setForceTouchEvents = function (t) {
      m = t
    }, this.Mottle.setForceMouseEvents = function (t) {
      v = t
    }, this.Mottle.version = '0.8.0', e.Mottle = this.Mottle
  }.call('undefined' === typeof window ? s : window), function () {
    const t = function (t, e, n) {
      return -1 === t.indexOf(e) && (n ? t.unshift(e) : t.push(e), !0)
    }; const n = function (t, e) {
      const n = t.indexOf(e);-1 !== n && t.splice(n, 1)
    }; const i = function (t) {
      return null != t && ('string' === typeof t || t.constructor === String)
    }; const o = function (t, e, n) {
      for (let i = (n = n || t.parentNode).querySelectorAll(e), o = 0;o < i.length;o++) if (i[o] === t) return !0;return !1
    }; const s = function (t, e, n) {
      if (o(e, n, t)) return e;for (let i = e.parentNode;null != i && i !== t;) {
        if (o(i, n, t)) return i;i = i.parentNode
      }
    }; const r = (function () {
      let t = -1;if ('Microsoft Internet Explorer' === navigator.appName) {
        const e = navigator.userAgent;null != new RegExp('MSIE ([0-9]{1,}[.0-9]{0,})').exec(e) && (t = parseFloat(RegExp.$1))
      } return t
    }()); const a = r > -1 && r < 9; const l = 9 === r; const u = function (t) {
      if (a) return [t.clientX + document.documentElement.scrollLeft, t.clientY + document.documentElement.scrollTop];const e = h(t); const n = c(e, 0);return l ? [n.pageX || n.clientX, n.pageY || n.clientY] : [n.pageX, n.pageY]
    }; var c = function (t, e) {
      return t.item ? t.item(e) : t[e]
    }; var h = function (t) {
      return t.touches && t.touches.length > 0 ? t.touches : t.changedTouches && t.changedTouches.length > 0 ? t.changedTouches : t.targetTouches && t.targetTouches.length > 0 ? t.targetTouches : [t]
    }; const d = { delegatedDraggable: 'katavorio-delegated-draggable', draggable: 'katavorio-draggable', droppable: 'katavorio-droppable', drag: 'katavorio-drag', selected: 'katavorio-drag-selected', active: 'katavorio-drag-active', hover: 'katavorio-drag-hover', noSelect: 'katavorio-drag-no-select', ghostProxy: 'katavorio-ghost-proxy', clonedDrag: 'katavorio-clone-drag' }; const p = ['stop', 'start', 'drag', 'drop', 'over', 'out', 'beforeStart']; const f = function () {}; const g = function () {
      return !0
    }; const m = function (t, e, n) {
      for (let i = 0;i < t.length;i++)t[i] != n && e(t[i])
    }; const v = function (t, e, n, i) {
      m(t, (t) => {
        t.setActive(e), e && t.updatePosition(), n && t.setHover(i, e)
      })
    }; const y = function (t, e) {
      if (null != t) {
        t = i(t) || null != t.tagName || null == t.length ? [t] : t;for (let n = 0;n < t.length;n++)e.apply(t[n], [t[n]])
      }
    }; const b = function (t) {
      t.stopPropagation ? (t.stopPropagation(), t.preventDefault()) : t.returnValue = !1
    }; const P = function (t, e, n, i) {
      this.params = e || {}, this.el = t, this.params.addClass(this.el, this._class), this.uuid = E();let o = !0;return this.setEnabled = function (t) {
        o = t
      }, this.isEnabled = function () {
        return o
      }, this.toggleEnabled = function () {
        o = !o
      }, this.setScope = function (t) {
        this.scopes = t ? t.split(/\s+/) : [i]
      }, this.addScope = function (t) {
        const e = {};for (const n in y(this.scopes, (t) => {
          e[t] = !0
        }), y(t ? t.split(/\s+/) : [], (t) => {
          e[t] = !0
        }), this.scopes = [], e) this.scopes.push(n)
      }, this.removeScope = function (t) {
        const e = {};for (const n in y(this.scopes, (t) => {
          e[t] = !0
        }), y(t ? t.split(/\s+/) : [], (t) => {
          delete e[t]
        }), this.scopes = [], e) this.scopes.push(n)
      }, this.toggleScope = function (t) {
        const e = {};for (const n in y(this.scopes, (t) => {
          e[t] = !0
        }), y(t ? t.split(/\s+/) : [], (t) => {
          e[t] ? delete e[t] : e[t] = !0
        }), this.scopes = [], e) this.scopes.push(n)
      }, this.setScope(e.scope), this.k = e.katavorio, e.katavorio
    }; const x = function () {
      return !0
    }; const C = function () {
      return !1
    }; const _ = function (t, e, n, r) {
      this._class = n.draggable;const a = P.apply(this, arguments);this.rightButtonCanDrag = this.params.rightButtonCanDrag;let l; let c; let h; let p; let f; let m; let y = [0, 0]; let _ = null; let j = null; let w = [0, 0]; let D = !1; let A = [0, 0]; const I = !1 !== this.params.consumeStartEvent; let k = this.el; const O = this.params.clone; const M = (this.params.scroll, !1 !== e.multipleDrop); let T = !1; let F = null; const L = []; let N = null; const R = e.ghostProxyParent;if (l = !0 === e.ghostProxy ? x : e.ghostProxy && 'function' === typeof e.ghostProxy ? e.ghostProxy : function (t, e) {
        return !(!N || !N.useGhostProxy) && N.useGhostProxy(t, e)
      }, c = e.makeGhostProxy ? e.makeGhostProxy : function (t) {
        return N && N.makeGhostProxy ? N.makeGhostProxy(t) : t.cloneNode(!0)
      }, e.selector) {
        let G = t.getAttribute('katavorio-draggable');null == G && (G = `${(new Date).getTime()}`, t.setAttribute('katavorio-draggable', G)), L.push(e)
      } let B; const H = e.snapThreshold; const U = function (t, e, n, i, o) {
        const s = e * Math.floor(t[0] / e); const r = s + e; const a = Math.abs(t[0] - s) <= i ? s : Math.abs(r - t[0]) <= i ? r : t[0]; const l = n * Math.floor(t[1] / n); const u = l + n;return [a, Math.abs(t[1] - l) <= o ? l : Math.abs(u - t[1]) <= o ? u : t[1]]
      };this.posses = [], this.posseRoles = {}, this.toGrid = function (t) {
        if (null == this.params.grid) return t;const e = this.params.grid ? this.params.grid[0] / 2 : H || 5; const n = this.params.grid ? this.params.grid[1] / 2 : H || 5;return U(t, this.params.grid[0], this.params.grid[1], e, n)
      }, this.snap = function (t, e) {
        if (null != k) {
          t = t || (this.params.grid ? this.params.grid[0] : 10), e = e || (this.params.grid ? this.params.grid[1] : 10);const n = this.params.getPosition(k); const i = this.params.grid ? this.params.grid[0] / 2 : H; const o = this.params.grid ? this.params.grid[1] / 2 : H; const s = U(n, t, e, i, o);return this.params.setPosition(k, s), s
        }
      }, this.setUseGhostProxy = function (t) {
        l = t ? x : C
      };const X = function (t) {
        return !1 === e.allowNegative ? [Math.max(0, t[0]), Math.max(0, t[1])] : t
      }; const Y = function (t) {
        B = 'function' === typeof t ? t : t ? function (t, e, n, i) {
          return X([Math.max(0, Math.min(n.w - i[0], t[0])), Math.max(0, Math.min(n.h - i[1], t[1]))])
        }.bind(this) : function (t) {
          return X(t)
        }
      }.bind(this);Y('function' === typeof this.params.constrain ? this.params.constrain : this.params.constrain || this.params.containment), this.setConstrain = function (t) {
        Y(t)
      };let $;this.setRevert = function (t) {
        $ = t
      }, this.params.revert && ($ = this.params.revert);let z = {}; const W = this.setFilter = function (e, n) {
        if (e) {
          const s = 'function' === typeof(r = e) ? (r._katavorioId = E(), r._katavorioId) : r;z[s] = [function (n) {
            let s; const r = n.srcElement || n.target;return i(e) ? s = o(r, e, t) : 'function' === typeof e && (s = e(n, t)), s
          }, !1 !== n]
        } let r
      };this.addFilter = W, this.removeFilter = function (t) {
        const e = 'function' === typeof t ? t._katavorioId : t;delete z[e]
      };this.clearAllFilters = function () {
        z = {}
      }, this.canDrag = this.params.canDrag || g;let V; let q = []; const J = [];this.addSelector = function (t) {
        t.selector && L.push(t)
      }, this.downListener = function (t) {
        let e; let i; let r; let l; let c; let h; let p; let f; let g;if (!t.defaultPrevented && ((this.rightButtonCanDrag || 3 !== t.which && 2 !== t.button) && this.isEnabled() && this.canDrag())) if ((function (t) {
          for (const e in z) {
            const n = z[e]; let i = n[0](t);if (n[1] && (i = !i), !i) return !1
          } return !0
        }(t)) && (function (t, e, n) {
          const i = t.srcElement || t.target;return !o(i, n.getInputFilterSelector(), e)
        }(t, this.el, this.k))) {
          if (N = null, F = null, L.length > 0) {
            const m = (function (t, e, n) {
              for (let i = null, r = e.getAttribute('katavorio-draggable'), a = null != r ? `[katavorio-draggable='${r}'] ` : '', l = 0;l < t.length;l++) if (null != (i = s(e, n, a + t[l].selector))) {
                if (t[l].filter) {
                  const u = o(n, t[l].filter, i);if (!0 === t[l].filterExclude && !u || u) return null
                } return [t[l], i]
              } return null
            }(L, this.el, t.target || t.srcElement));if (null != m && (N = m[0], F = m[1]), null == F) return
          } else F = this.el;if (O) if (k = F.cloneNode(!0), this.params.addClass(k, d.clonedDrag), k.setAttribute('id', null), k.style.position = 'absolute', null != this.params.parent) {
            const v = this.params.getPosition(this.el);k.style.left = `${v[0]}px`, k.style.top = `${v[1]}px`, this.params.parent.appendChild(k)
          } else {
            const P = (e = F.getBoundingClientRect(), i = document.body, r = document.documentElement, l = window.pageYOffset || r.scrollTop || i.scrollTop, c = window.pageXOffset || r.scrollLeft || i.scrollLeft, h = r.clientTop || i.clientTop || 0, p = r.clientLeft || i.clientLeft || 0, f = e.top + l - h, g = e.left + c - p, { top: Math.round(f), left: Math.round(g) });k.style.left = `${P.left}px`, k.style.top = `${P.top}px`, document.body.appendChild(k)
          } else k = F;I && b(t), y = u(t), k && k.parentNode && (A = [k.parentNode.scrollLeft, k.parentNode.scrollTop]), this.params.bind(document, 'mousemove', this.moveListener), this.params.bind(document, 'mouseup', this.upListener), a.markSelection(this), a.markPosses(this), this.params.addClass(document.body, n.noSelect), Q('beforeStart', { el: this.el, pos: _, e: t, drag: this })
        } else this.params.consumeFilteredEvents && b(t)
      }.bind(this), this.moveListener = function (t) {
        if (y) {
          if (!D) if (!1 !== Q('start', { el: this.el, pos: _, e: t, drag: this })) {
            if (!y) return;this.mark(!0), D = !0
          } else this.abort();if (y) {
            J.length = 0;const e = u(t); let n = e[0] - y[0]; let i = e[1] - y[1]; const o = this.params.ignoreZoom ? 1 : a.getZoom();k && k.parentNode && (n += k.parentNode.scrollLeft - A[0], i += k.parentNode.scrollTop - A[1]), n /= o, i /= o, this.moveBy(n, i, t), a.updateSelection(n, i, this), a.updatePosses(n, i, this)
          }
        }
      }.bind(this), this.upListener = function (t) {
        y && (y = null, this.params.unbind(document, 'mousemove', this.moveListener), this.params.unbind(document, 'mouseup', this.upListener), this.params.removeClass(document.body, n.noSelect), this.unmark(t), a.unmarkSelection(this, t), a.unmarkPosses(this, t), this.stop(t), a.notifyPosseDragStop(this, t), D = !1, J.length = 0, O ? (k && k.parentNode && k.parentNode.removeChild(k), k = null) : $ && !0 === $(k, this.params.getPosition(k)) && (this.params.setPosition(k, _), Q('revert', k)))
      }.bind(this), this.getFilters = function () {
        return z
      }, this.abort = function () {
        null != y && this.upListener()
      }, this.getDragElement = function (t) {
        return t ? F || this.el : k || this.el
      };const Z = { start: [], drag: [], stop: [], over: [], out: [], beforeStart: [], revert: [] };e.events.start && Z.start.push(e.events.start), e.events.beforeStart && Z.beforeStart.push(e.events.beforeStart), e.events.stop && Z.stop.push(e.events.stop), e.events.drag && Z.drag.push(e.events.drag), e.events.revert && Z.revert.push(e.events.revert), this.on = function (t, e) {
        Z[t] && Z[t].push(e)
      }, this.off = function (t, e) {
        if (Z[t]) {
          for (var n = [], i = 0;i < Z[t].length;i++)Z[t][i] !== e && n.push(Z[t][i]);Z[t] = n
        }
      };let K; var Q = function (t, e) {
        let n = null;if (N && N[t])n = N[t](e);else if (Z[t]) for (let i = 0;i < Z[t].length;i++) try {
          const o = Z[t][i](e);null != o && (n = o)
        } catch (t) {} return n
      };this.notifyStart = function (t) {
        Q('start', { el: this.el, pos: this.params.getPosition(k), e: t, drag: this })
      }, this.stop = function (t, e) {
        if (e || D) {
          const n = []; const i = a.getSelection(); const o = this.params.getPosition(k);if (i.length > 0) for (let s = 0;s < i.length;s++) {
            const r = this.params.getPosition(i[s].el);n.push([i[s].el, { left: r[0], top: r[1] }, i[s]])
          } else n.push([k, { left: o[0], top: o[1] }, this]);Q('stop', { el: k, pos: K || o, finalPos: o, e: t, drag: this, selection: n })
        }
      }, this.mark = function (t) {
        let e;_ = this.params.getPosition(k), j = this.params.getPosition(k, !0), w = [j[0] - _[0], j[1] - _[1]], this.size = this.params.getSize(k), q = a.getMatchingDroppables(this), v(q, !0, !1, this), this.params.addClass(k, this.params.dragClass || n.drag), e = this.params.getConstrainingRectangle ? this.params.getConstrainingRectangle(k) : this.params.getSize(k.parentNode), V = { w: e[0], h: e[1] }, f = 0, m = 0, t && a.notifySelectionDragStart(this)
      }, this.unmark = function (t, i) {
        if (v(q, !1, !0, this), T && l(F, k) ? (K = [k.offsetLeft - f, k.offsetTop - m], k.parentNode.removeChild(k), k = F) : K = null, this.params.removeClass(k, this.params.dragClass || n.drag), q.length = 0, T = !1, !i) {
          J.length > 0 && K && e.setPosition(F, K), J.sort(S);for (let o = 0;o < J.length;o++) {
            if (!0 === J[o].drop(this, t)) break
          }
        }
      }, this.moveBy = function (t, n, i) {
        J.length = 0;const o = this.toGrid([_[0] + t, _[1] + n]); let s = (function (t, e, n, i) {
          return null != N && N.constrain && 'function' === typeof N.constrain ? N.constrain(t, e, n, i) : B(t, e, n, i)
        }(o, k, V, this.size));if (l(this.el, k)) if (o[0] !== s[0] || o[1] !== s[1]) {
          if (!T) {
            const r = c(F);e.addClass(r, d.ghostProxy), R ? (R.appendChild(r), h = e.getPosition(F.parentNode, !0), p = e.getPosition(e.ghostProxyParent, !0), f = h[0] - p[0], m = h[1] - p[1]) : F.parentNode.appendChild(r), k = r, T = !0
          }s = o
        } else T && (k.parentNode.removeChild(k), k = F, T = !1, h = null, p = null, f = 0, m = 0);const a = { x: s[0], y: s[1], w: this.size[0], h: this.size[1] }; const u = { x: a.x + w[0], y: a.y + w[1], w: a.w, h: a.h }; let g = null;this.params.setPosition(k, [s[0] + f, s[1] + m]);for (let v = 0;v < q.length;v++) {
          const y = { x: q[v].pagePosition[0], y: q[v].pagePosition[1], w: q[v].size[0], h: q[v].size[1] };this.params.intersects(u, y) && (M || null == g || g === q[v].el) && q[v].canDrop(this) ? (g || (g = q[v].el), J.push(q[v]), q[v].setHover(this, !0, i)) : q[v].isHover() && q[v].setHover(this, !1, i)
        }Q('drag', { el: this.el, pos: s, e: i, drag: this })
      }, this.destroy = function () {
        this.params.unbind(this.el, 'mousedown', this.downListener), this.params.unbind(document, 'mousemove', this.moveListener), this.params.unbind(document, 'mouseup', this.upListener), this.downListener = null, this.upListener = null, this.moveListener = null
      }, this.params.bind(this.el, 'mousedown', this.downListener), this.params.handle ? W(this.params.handle, !1) : W(this.params.filter, this.params.filterExclude)
    }; const j = function (t, e, n, i) {
      this._class = n.droppable, this.params = e || {}, this.rank = e.rank || 0, this._activeClass = this.params.activeClass || n.active, this._hoverClass = this.params.hoverClass || n.hover, P.apply(this, arguments);let o = !1;this.allowLoopback = !1 !== this.params.allowLoopback, this.setActive = function (t) {
        this.params[t ? 'addClass' : 'removeClass'](this.el, this._activeClass)
      }, this.updatePosition = function () {
        this.position = this.params.getPosition(this.el), this.pagePosition = this.params.getPosition(this.el, !0), this.size = this.params.getSize(this.el)
      }, this.canDrop = this.params.canDrop || function (t) {
        return !0
      }, this.isHover = function () {
        return o
      }, this.setHover = function (t, e, n) {
        (e || null == this.el._katavorioDragHover || this.el._katavorioDragHover === t.el._katavorio) && (this.params[e ? 'addClass' : 'removeClass'](this.el, this._hoverClass), this.el._katavorioDragHover = e ? t.el._katavorio : null, o !== e && this.params.events[e ? 'over' : 'out']({ el: this.el, e: n, drag: t, drop: this }), o = e)
      }, this.drop = function (t, e) {
        return this.params.events.drop({ drag: t, e, drop: this })
      }, this.destroy = function () {
        this._class = null, this._activeClass = null, this._hoverClass = null, o = null
      }
    }; var E = function () {
      return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (t) => {
        const e = 16 * Math.random() | 0;return ('x' === t ? e : 3 & e | 8).toString(16)
      })
    }; var S = function (t, e) {
      return t.rank < e.rank ? 1 : t.rank > e.rank ? -1 : 0
    }; const w = function (t) {
      return null == t ? null : null == (t = 'string' === typeof t || t.constructor === String ? document.getElementById(t) : t) ? null : (t._katavorio = t._katavorio || E(), t)
    };this.Katavorio = function (e) {
      let o = []; let s = {};this._dragsByScope = {}, this._dropsByScope = {};let r = 1; const a = function (t, e) {
        y(t, (t) => {
          for (let n = 0;n < t.scopes.length;n++)e[t.scopes[n]] = e[t.scopes[n]] || [], e[t.scopes[n]].push(t)
        })
      }; const l = function (t, n) {
        let i = 0;return y(t, (t) => {
          for (let o = 0;o < t.scopes.length;o++) if (n[t.scopes[o]]) {
            const s = e.indexOf(n[t.scopes[o]], t);-1 !== s && (n[t.scopes[o]].splice(s, 1), i++)
          }
        }), i > 0
      }; const u = (this.getMatchingDroppables = function (t) {
        for (var e = [], n = {}, i = 0;i < t.scopes.length;i++) {
          const o = this._dropsByScope[t.scopes[i]];if (o) for (let s = 0;s < o.length;s++)!o[s].canDrop(t) || n[o[s].uuid] || !o[s].allowLoopback && o[s].el === t.el || (n[o[s].uuid] = !0, e.push(o[s]))
        } return e.sort(S), e
      }, function (t) {
        t = t || {};let n; const i = { events: {} };for (n in e)i[n] = e[n];for (n in t)i[n] = t[n];for (n = 0;n < p.length;n++)i.events[p[n]] = t[p[n]] || f;return i.katavorio = this, i
      }.bind(this)); const c = function (t, e) {
        for (let n = 0;n < p.length;n++)e[p[n]] && t.on(p[n], e[p[n]])
      }.bind(this); const h = {}; const g = e.css || {}; const v = e.scope || 'katavorio-drag-scope';for (var b in d)h[b] = d[b];for (var b in g)h[b] = g[b];let P = e.inputFilterSelector || 'input,textarea,select,button,option';this.getInputFilterSelector = function () {
        return P
      }, this.setInputFilterSelector = function (t) {
        return P = t, this
      }, this.draggable = function (t, n) {
        const i = [];return y(t, (t) => {
          if (null != (t = w(t))) if (null == t._katavorioDrag) {
            const o = u(n);t._katavorioDrag = new _(t, o, h, v), a(t._katavorioDrag, this._dragsByScope), i.push(t._katavorioDrag), e.addClass(t, o.selector ? h.delegatedDraggable : h.draggable)
          } else c(t._katavorioDrag, n)
        }), i
      }, this.droppable = function (t, n) {
        const i = [];return y(t, (t) => {
          if (null != (t = w(t))) {
            const o = new j(t, u(n), h, v);t._katavorioDrop = t._katavorioDrop || [], t._katavorioDrop.push(o), a(o, this._dropsByScope), i.push(o), e.addClass(t, h.droppable)
          }
        }), i
      }, this.select = function (t) {
        return y(t, function () {
          const t = w(this);t && t._katavorioDrag && (s[t._katavorio] || (o.push(t._katavorioDrag), s[t._katavorio] = [t, o.length - 1], e.addClass(t, h.selected)))
        }), this
      }, this.deselect = function (t) {
        return y(t, function () {
          const t = w(this);if (t && t._katavorio && s[t._katavorio]) {
            for (var n = [], i = 0;i < o.length;i++)o[i].el !== t && n.push(o[i]);o = n, delete s[t._katavorio], e.removeClass(t, h.selected)
          }
        }), this
      }, this.deselectAll = function () {
        for (const t in s) {
          const n = s[t];e.removeClass(n[0], h.selected)
        }o.length = 0, s = {}
      }, this.markSelection = function (t) {
        m(o, (t) => {
          t.mark()
        }, t)
      }, this.markPosses = function (t) {
        t.posses && y(t.posses, (e) => {
          t.posseRoles[e] && A[e] && m(A[e].members, (t) => {
            t.mark()
          }, t)
        })
      }, this.unmarkSelection = function (t, e) {
        m(o, (t) => {
          t.unmark(e)
        }, t)
      }, this.unmarkPosses = function (t, e) {
        t.posses && y(t.posses, (n) => {
          t.posseRoles[n] && A[n] && m(A[n].members, (t) => {
            t.unmark(e, !0)
          }, t)
        })
      }, this.getSelection = function () {
        return o.slice(0)
      }, this.updateSelection = function (t, e, n) {
        m(o, (n) => {
          n.moveBy(t, e)
        }, n)
      };const x = function (t, e) {
        e.posses && y(e.posses, (n) => {
          e.posseRoles[n] && A[n] && m(A[n].members, (e) => {
            t(e)
          }, e)
        })
      };this.updatePosses = function (t, e, n) {
        x((n) => {
          n.moveBy(t, e)
        }, n)
      }, this.notifyPosseDragStop = function (t, e) {
        x((t) => {
          t.stop(e, !0)
        }, t)
      }, this.notifySelectionDragStop = function (t, e) {
        m(o, (t) => {
          t.stop(e, !0)
        }, t)
      }, this.notifySelectionDragStart = function (t, e) {
        m(o, (t) => {
          t.notifyStart(e)
        }, t)
      }, this.setZoom = function (t) {
        r = t
      }, this.getZoom = function () {
        return r
      };const C = function (t, e, n, i) {
        y(t, (t) => {
          l(t, n), t[i](e), a(t, n)
        })
      };y(['set', 'add', 'remove', 'toggle'], (t) => {
        this[`${t}Scope`] = function (e, n) {
          C(e._katavorioDrag, n, this._dragsByScope, `${t}Scope`), C(e._katavorioDrop, n, this._dropsByScope, `${t}Scope`)
        }.bind(this), this[`${t}DragScope`] = function (e, n) {
          C(e.constructor === _ ? e : e._katavorioDrag, n, this._dragsByScope, `${t}Scope`)
        }.bind(this), this[`${t}DropScope`] = function (e, n) {
          C(e.constructor === j ? e : e._katavorioDrop, n, this._dropsByScope, `${t}Scope`)
        }.bind(this)
      }), this.snapToGrid = function (t, e) {
        for (const n in this._dragsByScope)m(this._dragsByScope[n], (n) => {
          n.snap(t, e)
        })
      }, this.getDragsForScope = function (t) {
        return this._dragsByScope[t]
      }, this.getDropsForScope = function (t) {
        return this._dropsByScope[t]
      };const E = function (t, e, n) {
        if ((t = w(t))[e]) {
          const i = o.indexOf(t[e]);i >= 0 && o.splice(i, 1), l(t[e], n) && y(t[e], (t) => {
            t.destroy()
          }), delete t[e]
        }
      }; const D = function (t, e, n, i) {
        (t = w(t))[e] && t[e].off(n, i)
      };this.elementRemoved = function (t) {
        t._katavorioDrag && this.destroyDraggable(t), t._katavorioDrop && this.destroyDroppable(t)
      }, this.destroyDraggable = function (t, e, n) {
        1 === arguments.length ? E(t, '_katavorioDrag', this._dragsByScope) : D(t, '_katavorioDrag', e, n)
      }, this.destroyDroppable = function (t, e, n) {
        1 === arguments.length ? E(t, '_katavorioDrop', this._dropsByScope) : D(t, '_katavorioDrop', e, n)
      }, this.reset = function () {
        this._dragsByScope = {}, this._dropsByScope = {}, o = [], s = {}, A = {}
      };var A = {}; const I = function (e, n, o) {
        let s; const r = i(n) ? n : n.id; const a = !!i(n) || !1 !== n.active; const l = A[r] || (s = { name: r, members: [] }, A[r] = s, s);return y(e, (e) => {
          if (e._katavorioDrag) {
            if (o && null != e._katavorioDrag.posseRoles[l.name]) return;t(l.members, e._katavorioDrag), t(e._katavorioDrag.posses, l.name), e._katavorioDrag.posseRoles[l.name] = a
          }
        }), l
      };this.addToPosse = function (t, e) {
        for (var n = [], i = 1;i < arguments.length;i++)n.push(I(t, arguments[i]));return 1 === n.length ? n[0] : n
      }, this.setPosse = function (t, e) {
        for (var n = [], i = 1;i < arguments.length;i++)n.push(I(t, arguments[i], !0).name);return y(t, (t) => {
          if (t._katavorioDrag) {
            const e = (function (t, e) {
              for (var n = [], i = 0;i < t.length;i++)-1 === e.indexOf(t[i]) && n.push(t[i]);return n
            }(t._katavorioDrag.posses, n));Array.prototype.push.apply([], t._katavorioDrag.posses);for (let i = 0;i < e.length;i++) this.removeFromPosse(t, e[i])
          }
        }), 1 === n.length ? n[0] : n
      }, this.removeFromPosse = function (t, e) {
        if (arguments.length < 2) throw new TypeError('No posse id provided for remove operation');for (let i = 1;i < arguments.length;i++)e = arguments[i], y(t, (t) => {
          if (t._katavorioDrag && t._katavorioDrag.posses) {
            const i = t._katavorioDrag;y(e, (t) => {
              n(A[t].members, i), n(i.posses, t), delete i.posseRoles[t]
            })
          }
        })
      }, this.removeFromAllPosses = function (t) {
        y(t, (t) => {
          if (t._katavorioDrag && t._katavorioDrag.posses) {
            const e = t._katavorioDrag;y(e.posses, (t) => {
              n(A[t].members, e)
            }), e.posses.length = 0, e.posseRoles = {}
          }
        })
      }, this.setPosseState = function (t, e, n) {
        const i = A[e];i && y(t, (t) => {
          t._katavorioDrag && t._katavorioDrag.posses && (t._katavorioDrag.posseRoles[i.name] = n)
        })
      }
    }, this.Katavorio.version = '1.0.0', e.Katavorio = this.Katavorio
  }.call('undefined' !== typeof window ? window : s), function () {
    this.jsPlumbUtil = this.jsPlumbUtil || {};const t = this.jsPlumbUtil;function n (t) {
      return '[object Array]' === Object.prototype.toString.call(t)
    } function i (t) {
      return 'string' === typeof t
    } function o (t) {
      return 'boolean' === typeof t
    } function s (t) {
      return null != t && '[object Object]' === Object.prototype.toString.call(t)
    } function r (t) {
      return '[object Date]' === Object.prototype.toString.call(t)
    } function a (t) {
      return '[object Function]' === Object.prototype.toString.call(t)
    } function l (t) {
      if (i(t)) return `${t}`;if (o(t)) return !!t;if (r(t)) return new Date(t.getTime());if (a(t)) return t;if (n(t)) {
        for (var e = [], u = 0;u < t.length;u++)e.push(l(t[u]));return e
      } if (s(t)) {
        const c = {};for (const h in t)c[h] = l(t[h]);return c
      } return t
    } function u (t, e, r, a) {
      let u; let c; const h = {}; const d = {};for (r = r || [], a = a || [], c = 0;c < r.length;c++)h[r[c]] = !0;for (c = 0;c < a.length;c++)d[a[c]] = !0;const p = l(t);for (c in e) if (null == p[c] || d[c])p[c] = e[c];else if (i(e[c]) || o(e[c]))h[c] ? ((u = []).push.apply(u, n(p[c]) ? p[c] : [p[c]]), u.push.apply(u, o(e[c]) ? e[c] : [e[c]]), p[c] = u) : p[c] = e[c];else if (n(e[c]))u = [], n(p[c]) && u.push.apply(u, p[c]), u.push.apply(u, e[c]), p[c] = u;else if (s(e[c])) for (const f in s(p[c]) || (p[c] = {}), e[c])p[c][f] = e[c][f];return p
    } function c (t, e) {
      if (t) for (let n = 0;n < t.length;n++) if (e(t[n])) return n;return -1
    } function h (t, e) {
      const n = t.indexOf(e);return n > -1 && t.splice(n, 1), -1 !== n
    } function d (t, e, n, i) {
      let o = t[e];return null == o && (o = [], t[e] = o), o[i ? 'unshift' : 'push'](n), o
    }e.jsPlumbUtil = t, t.isArray = n, t.isNumber = function (t) {
      return '[object Number]' === Object.prototype.toString.call(t)
    }, t.isString = i, t.isBoolean = o, t.isNull = function (t) {
      return null == t
    }, t.isObject = s, t.isDate = r, t.isFunction = a, t.isNamedFunction = function (t) {
      return a(t) && null != t.name && t.name.length > 0
    }, t.isEmpty = function (t) {
      for (const e in t) if (t.hasOwnProperty(e)) return !1;return !0
    }, t.clone = l, t.merge = u, t.replace = function (t, e, n) {
      if (null != t) {
        let i = t;return e.replace(/([^\.])+/g, (t, e, o, s) => {
          const r = t.match(/([^\[0-9]+){1}(\[)([0-9+])/); const a = function () {
            return i[r[1]] || (i[r[1]] = [], i[r[1]])
          };if (o + t.length >= s.length)r ? a()[r[3]] = n : i[t] = n;else if (r) {
            const l = a();i = l[r[3]] || (l[r[3]] = {}, l[r[3]])
          } else i = i[t] || (i[t] = {}, i[t]);return ''
        }), t
      }
    }, t.functionChain = function (t, e, n) {
      for (let i = 0;i < n.length;i++) {
        const o = n[i][0][n[i][1]].apply(n[i][0], n[i][2]);if (o === e) return o
      } return t
    }, t.populate = function (t, e, o, r) {
      var l = function (t) {
        if (null != t) {
          if (i(t)) return (function (t) {
            const n = t.match(/(\${.*?})/g);if (null != n) for (let i = 0;i < n.length;i++) {
              const o = e[n[i].substring(2, n[i].length - 1)] || '';null != o && (t = t.replace(n[i], o))
            } return t
          }(t));if (!a(t) || r || null != o && 0 !== (t.name || '').indexOf(o)) {
            if (n(t)) {
              for (var u = [], c = 0;c < t.length;c++)u.push(l(t[c]));return u
            } if (s(t)) {
              const h = {};for (const d in t)h[d] = l(t[d]);return h
            } return t
          } return t(e)
        }
      };return l(t)
    }, t.findWithFunction = c, t.removeWithFunction = function (t, e) {
      const n = c(t, e);return n > -1 && t.splice(n, 1), -1 !== n
    }, t.remove = h, t.addWithFunction = function (t, e, n) {
      -1 === c(t, n) && t.push(e)
    }, t.addToList = d, t.suggest = function (t, e, n) {
      return -1 === t.indexOf(e) && (n ? t.unshift(e) : t.push(e), !0)
    }, t.extend = function (t, e, i) {
      let o;e = n(e) ? e : [e];const s = function (e) {
        for (let n = e.__proto__;null != n;) if (null != n.prototype) {
          for (const i in n.prototype)n.prototype.hasOwnProperty(i) && !t.prototype.hasOwnProperty(i) && (t.prototype[i] = n.prototype[i]);n = n.prototype.__proto__
        } else n = null
      };for (o = 0;o < e.length;o++) {
        for (const r in e[o].prototype)e[o].prototype.hasOwnProperty(r) && !t.prototype.hasOwnProperty(r) && (t.prototype[r] = e[o].prototype[r]);s(e[o])
      } const a = function (t, n) {
        return function () {
          for (o = 0;o < e.length;o++)e[o].prototype[t] && e[o].prototype[t].apply(this, arguments);return n.apply(this, arguments)
        }
      }; const l = function (e) {
        for (const n in e)t.prototype[n] = a(n, e[n])
      };if (arguments.length > 2) for (o = 2;o < arguments.length;o++)l(arguments[o]);return t
    };for (var p = [], f = 0;f < 256;f++)p[f] = (f < 16 ? '0' : '') + f.toString(16);function g () {
      const t = 4294967295 * Math.random() | 0; const e = 4294967295 * Math.random() | 0; const n = 4294967295 * Math.random() | 0; const i = 4294967295 * Math.random() | 0;return `${p[255 & t] + p[t >> 8 & 255] + p[t >> 16 & 255] + p[t >> 24 & 255]}-${p[255 & e]}${p[e >> 8 & 255]}-${p[e >> 16 & 15 | 64]}${p[e >> 24 & 255]}-${p[63 & n | 128]}${p[n >> 8 & 255]}-${p[n >> 16 & 255]}${p[n >> 24 & 255]}${p[255 & i]}${p[i >> 8 & 255]}${p[i >> 16 & 255]}${p[i >> 24 & 255]}`
    } function m () {
      for (let e = [], n = 0;n < arguments.length;n++)e[n] = arguments[n];if (t.logEnabled && 'undefined' !== typeof console) try {
        const i = arguments[arguments.length - 1];console.log(i)
      } catch (t) {}
    }t.uuid = g, t.fastTrim = function (t) {
      if (null == t) return null;for (var e = t.replace(/^\s\s*/, ''), n = /\s/, i = e.length;n.test(e.charAt(--i)););return e.slice(0, i + 1)
    }, t.each = function (t, e) {
      t = null == t.length || 'string' === typeof t ? [t] : t;for (let n = 0;n < t.length;n++)e(t[n])
    }, t.map = function (t, e) {
      for (var n = [], i = 0;i < t.length;i++)n.push(e(t[i]));return n
    }, t.mergeWithParents = function (t, e, n) {
      n = n || 'parent';const i = function (t) {
        return t ? e[t] : null
      }; const o = function (t) {
        return t ? i(t[n]) : null
      }; var s = function (t, e) {
        if (null == t) return e;const n = ['anchor', 'anchors', 'cssClass', 'connector', 'paintStyle', 'hoverPaintStyle', 'endpoint', 'endpoints'];'override' === e.mergeStrategy && Array.prototype.push.apply(n, ['events', 'overlays']);const i = u(t, e, [], n);return s(o(t), i)
      }; var r = function (t) {
        if (null == t) return {};if ('string' === typeof t) return i(t);if (t.length) {
          for (var e = !1, n = 0, o = void 0;!e && n < t.length;)(o = r(t[n])) ? e = !0 : n++;return o
        }
      }; const a = r(t);return a ? s(o(a), a) : {}
    }, t.logEnabled = !0, t.log = m, t.wrap = function (t, e, n) {
      return function () {
        let i = null;try {
          null != e && (i = e.apply(this, arguments))
        } catch (t) {
          m(`jsPlumb function failed : ${t}`)
        } if (null != t && (null == n || i !== n)) try {
          i = t.apply(this, arguments)
        } catch (t) {
          m(`wrapped function failed : ${t}`)
        } return i
      }
    };const v = (function () {
      return function () {
        const t = this;this._listeners = {}, this.eventsSuspended = !1, this.tick = !1, this.eventsToDieOn = { ready: !0 }, this.queue = [], this.bind = function (e, n, i) {
          const o = function (e) {
            d(t._listeners, e, n, i), n.__jsPlumb = n.__jsPlumb || {}, n.__jsPlumb[g()] = e
          };if ('string' === typeof e)o(e);else if (null != e.length) for (let s = 0;s < e.length;s++)o(e[s]);return t
        }, this.fire = function (t, e, n) {
          if (this.tick) this.queue.unshift(arguments);else {
            if (this.tick = !0, !this.eventsSuspended && this._listeners[t]) {
              const i = this._listeners[t].length; let o = 0; let s = !1; let r = null;if (!this.shouldFireEvent || this.shouldFireEvent(t, e, n)) for (;!s && o < i && !1 !== r;) {
                if (this.eventsToDieOn[t]) this._listeners[t][o].apply(this, [e, n]);else try {
                  r = this._listeners[t][o].apply(this, [e, n])
                } catch (e) {
                  m(`jsPlumb: fire failed for event ${t} : ${e}`)
                }o++, null != this._listeners && null != this._listeners[t] || (s = !0)
              }
            } this.tick = !1, this._drain()
          } return this
        }, this._drain = function () {
          const e = t.queue.pop();e && t.fire.apply(t, e)
        }, this.unbind = function (t, e) {
          if (0 === arguments.length) this._listeners = {};else if (1 === arguments.length) {
            if ('string' === typeof t) delete this._listeners[t];else if (t.__jsPlumb) {
              let n = void 0;for (const i in t.__jsPlumb)n = t.__jsPlumb[i], h(this._listeners[n] || [], t)
            }
          } else 2 === arguments.length && h(this._listeners[t] || [], e);return this
        }, this.getListener = function (e) {
          return t._listeners[e]
        }, this.setSuspendEvents = function (e) {
          t.eventsSuspended = e
        }, this.isSuspendEvents = function () {
          return t.eventsSuspended
        }, this.silently = function (e) {
          t.setSuspendEvents(!0);try {
            e()
          } catch (t) {
            m(`Cannot execute silent function ${t}`)
          }t.setSuspendEvents(!1)
        }, this.cleanupListeners = function () {
          for (const e in t._listeners)t._listeners[e] = null
        }
      }
    }());function y (t, e, n) {
      const i = [t[0] - e[0], t[1] - e[1]]; const o = Math.cos(n / 360 * Math.PI * 2); const s = Math.sin(n / 360 * Math.PI * 2);return [i[0] * o - i[1] * s + e[0], i[1] * o + i[0] * s + e[1], o, s]
    }t.EventGenerator = v, t.rotatePoint = y, t.rotateAnchorOrientation = function (t, e) {
      const n = y(t, [0, 0], e);return [Math.round(n[0]), Math.round(n[1])]
    }
  }.call('undefined' !== typeof window ? window : s), function () {
    this.jsPlumbUtil.matchesSelector = function (t, e, n) {
      for (let i = (n = n || t.parentNode).querySelectorAll(e), o = 0;o < i.length;o++) if (i[o] === t) return !0;return !1
    }, this.jsPlumbUtil.consume = function (t, e) {
      t.stopPropagation ? t.stopPropagation() : t.returnValue = !1, !e && t.preventDefault && t.preventDefault()
    }, this.jsPlumbUtil.sizeElement = function (t, e, n, i, o) {
      t && (t.style.height = `${o}px`, t.height = o, t.style.width = `${i}px`, t.width = i, t.style.left = `${e}px`, t.style.top = `${n}px`)
    }
  }.call('undefined' !== typeof window ? window : s), function () {
    const t = { deriveAnchor (t, e, n, i) {
      return { top: ['TopRight', 'TopLeft'], bottom: ['BottomRight', 'BottomLeft'] }[t][e]
    } }; const e = function (t, e) {
      this.count = 0, this.instance = t, this.lists = {}, this.options = e || {}, this.instance.addList = function (t, e) {
        return this.listManager.addList(t, e)
      }, this.instance.removeList = function (t) {
        this.listManager.removeList(t)
      }, this.instance.bind('manageElement', (t) => {
        for (let e = this.instance.getSelector(t.el, '[jtk-scrollable-list]'), n = 0;n < e.length;n++) this.addList(e[n])
      }), this.instance.bind('unmanageElement', function (t) {
        this.removeList(t.el)
      }), this.instance.bind('connection', (t, e) => {
        null == e && (this._maybeUpdateParentList(t.source), this._maybeUpdateParentList(t.target))
      })
    };this.jsPlumbListManager = e, e.prototype = { addList (e, i) {
      const o = this.instance.extend({}, t);this.instance.extend(o, this.options), i = this.instance.extend(o, i || {});const s = [this.instance.getInstanceIndex(), this.count++].join('_');this.lists[s] = new n(this.instance, e, i, s)
    }, removeList (t) {
      const e = this.lists[t._jsPlumbList];e && (e.destroy(), delete this.lists[t._jsPlumbList])
    }, _maybeUpdateParentList (t) {
      for (let e = t.parentNode, n = this.instance.getContainer();null != e && e !== n;) {
        if (null != e._jsPlumbList && null != this.lists[e._jsPlumbList]) return void e._jsPlumbScrollHandler();e = e.parentNode
      }
    } };var n = function (t, e, n, i) {
      function o (t, e, i, o) {
        return n.anchor ? n.anchor : n.deriveAnchor(t, e, i, o)
      } function s (t, e, i, o) {
        return n.deriveEndpoint ? n.deriveEndpoint(t, e, i, o) : n.endpoint ? n.endpoint : i.type
      }e._jsPlumbList = i;const r = function (n) {
        for (var i = t.getSelector(e, '.jtk-managed'), r = t.getId(e), a = 0;a < i.length;a++) {
          if (i[a].offsetTop < e.scrollTop)i[a]._jsPlumbProxies || (i[a]._jsPlumbProxies = i[a]._jsPlumbProxies || [], t.select({ source: i[a] }).each((n) => {
            t.proxyConnection(n, 0, e, r, () => s('top', 0, n.endpoints[0], n), () => o('top', 0, n.endpoints[0], n)), i[a]._jsPlumbProxies.push([n, 0])
          }), t.select({ target: i[a] }).each((n) => {
            t.proxyConnection(n, 1, e, r, () => s('top', 1, n.endpoints[1], n), () => o('top', 1, n.endpoints[1], n)), i[a]._jsPlumbProxies.push([n, 1])
          }));else if (i[a].offsetTop + i[a].offsetHeight > e.scrollTop + e.offsetHeight)i[a]._jsPlumbProxies || (i[a]._jsPlumbProxies = i[a]._jsPlumbProxies || [], t.select({ source: i[a] }).each((n) => {
            t.proxyConnection(n, 0, e, r, () => s('bottom', 0, n.endpoints[0], n), () => o('bottom', 0, n.endpoints[0], n)), i[a]._jsPlumbProxies.push([n, 0])
          }), t.select({ target: i[a] }).each((n) => {
            t.proxyConnection(n, 1, e, r, () => s('bottom', 1, n.endpoints[1], n), () => o('bottom', 1, n.endpoints[1], n)), i[a]._jsPlumbProxies.push([n, 1])
          }));else if (i[a]._jsPlumbProxies) {
            for (let l = 0;l < i[a]._jsPlumbProxies.length;l++)t.unproxyConnection(i[a]._jsPlumbProxies[l][0], i[a]._jsPlumbProxies[l][1], r);delete i[a]._jsPlumbProxies
          }t.revalidate(i[a])
        }!(function (e) {
          for (let n = e.parentNode, i = t.getContainer();null != n && n !== i;) {
            if (t.hasClass(n, 'jtk-managed')) return void t.recalculateOffsets(n);n = n.parentNode
          }
        }(e))
      };t.setAttribute(e, 'jtk-scrollable-list', 'true'), e._jsPlumbScrollHandler = r, t.on(e, 'scroll', r), r(), this.destroy = function () {
        t.off(e, 'scroll', r), delete e._jsPlumbScrollHandler;for (let n = t.getSelector(e, '.jtk-managed'), i = t.getId(e), o = 0;o < n.length;o++) if (n[o]._jsPlumbProxies) {
          for (let s = 0;s < n[o]._jsPlumbProxies.length;s++)t.unproxyConnection(n[o]._jsPlumbProxies[s][0], n[o]._jsPlumbProxies[s][1], i);delete n[o]._jsPlumbProxies
        }
      }
    }
  }.call('undefined' !== typeof window ? window : s), function () {
    const t = this; const n = t.jsPlumbUtil; const i = function (t) {
      if (t._jsPlumb.paintStyle && t._jsPlumb.hoverPaintStyle) {
        const e = {};d.extend(e, t._jsPlumb.paintStyle), d.extend(e, t._jsPlumb.hoverPaintStyle), delete t._jsPlumb.hoverPaintStyle, e.gradient && t._jsPlumb.paintStyle.fill && delete e.gradient, t._jsPlumb.hoverPaintStyle = e
      }
    }; const o = ['tap', 'dbltap', 'click', 'dblclick', 'mouseover', 'mouseout', 'mousemove', 'mousedown', 'mouseup', 'contextmenu']; const s = function (t) {
      return null == t ? null : t.split(' ')
    }; const r = function (t, e, n) {
      for (const i in e)t[i] = n
    }; const a = function (t, e, i) {
      if (t.getDefaultType) {
        const o = t.getTypeDescriptor(); const s = {}; const a = t.getDefaultType(); let l = n.merge({}, a);r(s, a, '__default');for (let u = 0, c = t._jsPlumb.types.length;u < c;u++) {
          const h = t._jsPlumb.types[u];if ('__default' !== h) {
            const d = t._jsPlumb.instance.getType(h, o);if (null != d) {
              const p = ['anchor', 'anchors', 'connector', 'paintStyle', 'hoverPaintStyle', 'endpoint', 'endpoints', 'connectorOverlays', 'connectorStyle', 'connectorHoverStyle', 'endpointStyle', 'endpointHoverStyle']; const f = [];'override' === d.mergeStrategy ? Array.prototype.push.apply(p, ['events', 'overlays', 'cssClass']) : f.push('cssClass'), l = n.merge(l, d, f, p), r(s, d, h)
            }
          }
        }e && (l = n.populate(l, e, '_')), t.applyType(l, i, s), i || t.repaint()
      }
    }; const l = t.jsPlumbUIComponent = function (t) {
      n.EventGenerator.apply(this, arguments);const e = arguments; const i = this.idPrefix + (new Date).getTime();this._jsPlumb = { instance: t._jsPlumb, parameters: t.parameters || {}, paintStyle: null, hoverPaintStyle: null, paintStyleInUse: null, hover: !1, beforeDetach: t.beforeDetach, beforeDrop: t.beforeDrop, overlayPlacements: [], hoverClass: t.hoverClass || t._jsPlumb.Defaults.HoverClass, types: [], typeCache: {} }, this.cacheTypeItem = function (t, e, n) {
        this._jsPlumb.typeCache[n] = this._jsPlumb.typeCache[n] || {}, this._jsPlumb.typeCache[n][t] = e
      }, this.getCachedTypeItem = function (t, e) {
        return this._jsPlumb.typeCache[e] ? this._jsPlumb.typeCache[e][t] : null
      }, this.getId = function () {
        return i
      };const o = t.overlays || []; const s = {};if (this.defaultOverlayKeys) {
        for (var r = 0;r < this.defaultOverlayKeys.length;r++)Array.prototype.push.apply(o, this._jsPlumb.instance.Defaults[this.defaultOverlayKeys[r]] || []);for (r = 0;r < o.length;r++) {
          const a = d.convertToFullOverlaySpec(o[r]);s[a[1].id] = a
        }
      } const l = { overlays: s, parameters: t.parameters || {}, scope: t.scope || this._jsPlumb.instance.getDefaultScope() };if (this.getDefaultType = function () {
        return l
      }, this.appendToDefaultType = function (t) {
        for (const e in t)l[e] = t[e]
      }, t.events) for (const u in t.events) this.bind(u, t.events[u]);this.clone = function () {
        const t = Object.create(this.constructor.prototype);return this.constructor.apply(t, e), t
      }.bind(this), this.isDetachAllowed = function (t) {
        let e = !0;if (this._jsPlumb.beforeDetach) try {
          e = this._jsPlumb.beforeDetach(t)
        } catch (t) {
          n.log('jsPlumb: beforeDetach callback failed', t)
        } return e
      }, this.isDropAllowed = function (t, e, i, o, s, r, a) {
        let l = this._jsPlumb.instance.checkCondition('beforeDrop', { sourceId: t, targetId: e, scope: i, connection: o, dropEndpoint: s, source: r, target: a });if (this._jsPlumb.beforeDrop) try {
          l = this._jsPlumb.beforeDrop({ sourceId: t, targetId: e, scope: i, connection: o, dropEndpoint: s, source: r, target: a })
        } catch (t) {
          n.log('jsPlumb: beforeDrop callback failed', t)
        } return l
      };const c = [];this.setListenerComponent = function (t) {
        for (let e = 0;e < c.length;e++)c[e][3] = t
      }
    }; const u = function (t, e) {
      const n = t._jsPlumb.types[e]; const i = t._jsPlumb.instance.getType(n, t.getTypeDescriptor());null != i && i.cssClass && t.canvas && t._jsPlumb.instance.removeClass(t.canvas, i.cssClass)
    };n.extend(t.jsPlumbUIComponent, n.EventGenerator, { getParameter (t) {
      return this._jsPlumb.parameters[t]
    }, setParameter (t, e) {
      this._jsPlumb.parameters[t] = e
    }, getParameters () {
      return this._jsPlumb.parameters
    }, setParameters (t) {
      this._jsPlumb.parameters = t
    }, getClass () {
      return d.getClass(this.canvas)
    }, hasClass (t) {
      return d.hasClass(this.canvas, t)
    }, addClass (t) {
      d.addClass(this.canvas, t)
    }, removeClass (t) {
      d.removeClass(this.canvas, t)
    }, updateClasses (t, e) {
      d.updateClasses(this.canvas, t, e)
    }, setType (t, e, n) {
      this.clearTypes(), this._jsPlumb.types = s(t) || [], a(this, e, n)
    }, getType () {
      return this._jsPlumb.types
    }, reapplyTypes (t, e) {
      a(this, t, e)
    }, hasType (t) {
      return -1 !== this._jsPlumb.types.indexOf(t)
    }, addType (t, e, n) {
      const i = s(t); let o = !1;if (null != i) {
        for (let r = 0, l = i.length;r < l;r++) this.hasType(i[r]) || (this._jsPlumb.types.push(i[r]), o = !0);o && a(this, e, n)
      }
    }, removeType (t, e, n) {
      const i = s(t); let o = !1; const r = function (t) {
        const e = this._jsPlumb.types.indexOf(t);return -1 !== e && (u(this, e), this._jsPlumb.types.splice(e, 1), !0)
      }.bind(this);if (null != i) {
        for (let l = 0, c = i.length;l < c;l++)o = r(i[l]) || o;o && a(this, e, n)
      }
    }, clearTypes (t, e) {
      for (let n = this._jsPlumb.types.length, i = 0;i < n;i++)u(this, 0), this._jsPlumb.types.splice(0, 1);a(this, t, e)
    }, toggleType (t, e, n) {
      const i = s(t);if (null != i) {
        for (let o = 0, r = i.length;o < r;o++) {
          const l = this._jsPlumb.types.indexOf(i[o]);-1 !== l ? (u(this, l), this._jsPlumb.types.splice(l, 1)) : this._jsPlumb.types.push(i[o])
        }a(this, e, n)
      }
    }, applyType (t, e) {
      if (this.setPaintStyle(t.paintStyle, e), this.setHoverPaintStyle(t.hoverPaintStyle, e), t.parameters) for (const n in t.parameters) this.setParameter(n, t.parameters[n]);this._jsPlumb.paintStyleInUse = this.getPaintStyle()
    }, setPaintStyle (t, e) {
      this._jsPlumb.paintStyle = t, this._jsPlumb.paintStyleInUse = this._jsPlumb.paintStyle, i(this), e || this.repaint()
    }, getPaintStyle () {
      return this._jsPlumb.paintStyle
    }, setHoverPaintStyle (t, e) {
      this._jsPlumb.hoverPaintStyle = t, i(this), e || this.repaint()
    }, getHoverPaintStyle () {
      return this._jsPlumb.hoverPaintStyle
    }, destroy (t) {
      (t || null == this.typeId) && (this.cleanupListeners(), this.clone = null, this._jsPlumb = null)
    }, isHover () {
      return this._jsPlumb.hover
    }, setHover (t, e, n) {
      if (this._jsPlumb && !this._jsPlumb.instance.currentlyDragging && !this._jsPlumb.instance.isHoverSuspended()) {
        this._jsPlumb.hover = t;const i = t ? 'addClass' : 'removeClass';null != this.canvas && (null != this._jsPlumb.instance.hoverClass && this._jsPlumb.instance[i](this.canvas, this._jsPlumb.instance.hoverClass), null != this._jsPlumb.hoverClass && this._jsPlumb.instance[i](this.canvas, this._jsPlumb.hoverClass)), null != this._jsPlumb.hoverPaintStyle && (this._jsPlumb.paintStyleInUse = t ? this._jsPlumb.hoverPaintStyle : this._jsPlumb.paintStyle, this._jsPlumb.instance.isSuspendDrawing() || (n = n || jsPlumbUtil.uuid(), this.repaint({ timestamp: n, recalc: !1 }))), this.getAttachedElements && !e && (function (t, e, n, i) {
          const o = t.getAttachedElements();if (o) for (let s = 0, r = o.length;s < r;s++)i && i === o[s] || o[s].setHover(e, !0, n)
        }(this, t, jsPlumbUtil.uuid(), this))
      }
    } });let c = 0; const h = t.jsPlumbInstance = function (e) {
      this.version = '2.15.6', this.Defaults = { Anchor: 'Bottom', Anchors: [null, null], ConnectionsDetachable: !0, ConnectionOverlays: [], Connector: 'Bezier', Container: null, DoNotThrowErrors: !1, DragOptions: {}, DropOptions: {}, Endpoint: 'Dot', EndpointOverlays: [], Endpoints: [null, null], EndpointStyle: { fill: '#456' }, EndpointStyles: [null, null], EndpointHoverStyle: null, EndpointHoverStyles: [null, null], HoverPaintStyle: null, LabelStyle: { color: 'black' }, ListStyle: {}, LogEnabled: !1, Overlays: [], MaxConnections: 1, PaintStyle: { 'stroke-width': 4, stroke: '#456' }, ReattachConnections: !1, RenderMode: 'svg', Scope: 'jsPlumb_DefaultScope' }, e && d.extend(this.Defaults, e), this.logEnabled = this.Defaults.LogEnabled, this._connectionTypes = {}, this._endpointTypes = {}, n.EventGenerator.apply(this);const i = this; const s = (function () {
        const t = c + 1;return c++, t
      }()); const r = i.bind; const a = {}; let u = 1; const h = function (t) {
        if (null == t) return null;if (3 === t.nodeType || 8 === t.nodeType) return { el: t, text: !0 };const e = i.getElement(t);return { el: e, id: n.isString(t) && null == e ? t : B(e) }
      };for (const p in this.getInstanceIndex = function () {
        return s
      }, this.setZoom = function (t, e) {
        return u = t, i.fire('zoom', u), e && i.repaintEverything(), !0
      }, this.getZoom = function () {
        return u
      }, this.Defaults)a[p] = this.Defaults[p];let f; let g = [];this.unbindContainer = function () {
        if (null != f && g.length > 0) for (let t = 0;t < g.length;t++)i.off(f, g[t][0], g[t][1])
      }, this.setContainer = function (t) {
        this.unbindContainer(), t = this.getElement(t), this.select().each((e) => {
          e.moveParent(t)
        }), this.selectEndpoints().each((e) => {
          e.moveParent(t)
        });const e = f;f = t, g.length = 0;for (var n = { endpointclick: 'endpointClick', endpointdblclick: 'endpointDblClick' }, s = function (t, e, o) {
            const s = e.srcElement || e.target; const r = (s && s.parentNode ? s.parentNode._jsPlumb : null) || (s ? s._jsPlumb : null) || (s && s.parentNode && s.parentNode.parentNode ? s.parentNode.parentNode._jsPlumb : null);if (r) {
              r.fire(t, r, e);const a = o && n[o + t] || t;i.fire(a, r.component || r, e)
            }
          }, r = function (t, e, n) {
            g.push([t, n]), i.on(f, t, e, n)
          }, a = function (t) {
            r(t, '.jtk-connector', (e) => {
              s(t, e)
            }), r(t, '.jtk-endpoint', (e) => {
              s(t, e, 'endpoint')
            }), r(t, '.jtk-overlay', (e) => {
              s(t, e)
            })
          }, l = 0;l < o.length;l++)a(o[l]);for (const u in x) {
          const c = x[u].el;c.parentNode === e && (e.removeChild(c), f.appendChild(c))
        }
      }, this.getContainer = function () {
        return f
      }, this.bind = function (t, e) {
        'ready' === t && v ? e() : r.apply(i, [t, e])
      }, i.importDefaults = function (t) {
        for (const e in t)i.Defaults[e] = t[e];return t.Container && i.setContainer(t.Container), i
      }, i.restoreDefaults = function () {
        return i.Defaults = d.extend({}, a), i
      };let m = null; var v = !1; const y = []; let b = {}; let P = {}; var x = {}; let C = {}; let _ = {}; let j = !1; const E = []; let S = !1; let w = null; let D = this.Defaults.Scope; let A = 1; const I = function () {
        return `${A++}`
      }; const k = function (t, e) {
        f ? f.appendChild(t) : e ? this.getElement(e).appendChild(t) : this.appendToRoot(t)
      }.bind(this); const O = function (t, e, n, o) {
        const s = { c: [], e: [] };if (!S && null != (t = i.getElement(t))) {
          const r = B(t); const a = t.querySelectorAll('.jtk-managed');null == n && (n = jsPlumbUtil.uuid());it({ elId: r, offset: e, recalc: !1, timestamp: n });for (let l = 0;l < a.length;l++)it({ elId: a[l].getAttribute('id'), recalc: !0, timestamp: n });let u = i.router.redraw(r, e, n, null, o);if (Array.prototype.push.apply(s.c, u.c), Array.prototype.push.apply(s.e, u.e), a) for (let c = 0;c < a.length;c++)u = i.router.redraw(a[c].getAttribute('id'), null, n, null, o, !0), Array.prototype.push.apply(s.c, u.c), Array.prototype.push.apply(s.e, u.e)
        } return s
      }; const M = function (t) {
        return P[t]
      }; const T = function (t, e) {
        let o = d.extend({}, t);if (e && d.extend(o, e), o.source && (o.source.endpoint ? o.sourceEndpoint = o.source : o.source = i.getElement(o.source)), o.target && (o.target.endpoint ? o.targetEndpoint = o.target : o.target = i.getElement(o.target)), t.uuids && (o.sourceEndpoint = M(t.uuids[0]), o.targetEndpoint = M(t.uuids[1])), o.sourceEndpoint && o.sourceEndpoint.isFull())n.log(i, 'could not add connection; source endpoint is full');else if (o.targetEndpoint && o.targetEndpoint.isFull())n.log(i, 'could not add connection; target endpoint is full');else {
          if (!o.type && o.sourceEndpoint && (o.type = o.sourceEndpoint.connectionType), o.sourceEndpoint && o.sourceEndpoint.connectorOverlays) {
            o.overlays = o.overlays || [];for (let s = 0, r = o.sourceEndpoint.connectorOverlays.length;s < r;s++)o.overlays.push(o.sourceEndpoint.connectorOverlays[s])
          }o.sourceEndpoint && o.sourceEndpoint.scope && (o.scope = o.sourceEndpoint.scope), !o['pointer-events'] && o.sourceEndpoint && o.sourceEndpoint.connectorPointerEvents && (o['pointer-events'] = o.sourceEndpoint.connectorPointerEvents);const a = function (t, e, n) {
            const s = (function (t, e) {
              const n = d.extend({}, t);for (const i in e)e[i] && (n[i] = e[i]);return n
            }(e, { anchor: o.anchors ? o.anchors[n] : o.anchor, endpoint: o.endpoints ? o.endpoints[n] : o.endpoint, paintStyle: o.endpointStyles ? o.endpointStyles[n] : o.endpointStyle, hoverPaintStyle: o.endpointHoverStyles ? o.endpointHoverStyles[n] : o.endpointHoverStyle }));return i.addEndpoint(t, s)
          }; const l = function (t, e, n, i) {
            if (o[t] && !o[t].endpoint && !o[`${t}Endpoint`] && !o.newConnection) {
              let s = n[B(o[t])];if (s = s ? s[i] : null) {
                if (!s.enabled) return !1;const r = d.extend({}, s.def);delete r.label;const l = null != s.endpoint && s.endpoint._jsPlumb ? s.endpoint : a(o[t], r, e);if (l.isFull()) return !1;o[`${t}Endpoint`] = l, !o.scope && r.scope && (o.scope = r.scope), s.uniqueEndpoint ? s.endpoint ? l.finalEndpoint = s.endpoint : (s.endpoint = l, l.setDeleteOnEmpty(!1)) : l.setDeleteOnEmpty(!0), 0 === e && s.def.connectorOverlays && (o.overlays = o.overlays || [], Array.prototype.push.apply(o.overlays, s.def.connectorOverlays))
              }
            }
          };if (!1 !== l('source', 0, this.sourceEndpointDefinitions, o.type || 'default') && !1 !== l('target', 1, this.targetEndpointDefinitions, o.type || 'default')) return o.sourceEndpoint && o.targetEndpoint && ((function (t, e) {
            for (let n = t.scope.split(/\s/), i = e.scope.split(/\s/), o = 0;o < n.length;o++) for (let s = 0;s < i.length;s++) if (i[s] === n[o]) return !0;return !1
          }(o.sourceEndpoint, o.targetEndpoint)) || (o = null)), o
        }
      }.bind(i); var F = function (t) {
        const e = i.Defaults.ConnectionType || i.getDefaultConnectionType();t._jsPlumb = i, t.newConnection = F, t.newEndpoint = N, t.endpointsByUUID = P, t.endpointsByElement = b, t.finaliseConnection = L, t.id = `con_${I()}`;const n = new e(t);return n.isDetachable() && (n.endpoints[0].initDraggable('_jsPlumbSource'), n.endpoints[1].initDraggable('_jsPlumbTarget')), n
      }; var L = i.finaliseConnection = function (t, e, n, o) {
        if (e = e || {}, t.suspendedEndpoint || y.push(t), t.pending = null, t.endpoints[0].isTemporarySource = !1, !1 !== o && i.router.newConnection(t), O(t.source), !e.doNotFireConnectionEvent && !1 !== e.fireEvent) {
          const s = { connection: t, source: t.source, target: t.target, sourceId: t.sourceId, targetId: t.targetId, sourceEndpoint: t.endpoints[0], targetEndpoint: t.endpoints[1] };i.fire('connection', s, n)
        }
      }; var N = function (t, e) {
        const n = i.Defaults.EndpointType || d.Endpoint; const o = d.extend({}, t);o._jsPlumb = i, o.newConnection = F, o.newEndpoint = N, o.endpointsByUUID = P, o.endpointsByElement = b, o.fireDetachEvent = X, o.elementId = e || B(o.source);const s = new n(o);return s.id = `ep_${I()}`, nt(o.elementId, o.source), d.headless || i.getDragManager().endpointAdded(o.source, e), s
      }; const R = function (t, e, n) {
        const i = b[t];if (i && i.length) for (let o = 0, s = i.length;o < s;o++) {
          for (let r = 0, a = i[o].connections.length;r < a;r++) {
            if (e(i[o].connections[r])) return
          }n && n(i[o])
        }
      }; const G = function (t, e, n) {
        e = 'block' === e;let i = null;n && (i = function (t) {
          t.setVisible(e, !0, !0)
        });const o = h(t);R(o.id, (t) => {
          if (e && n) {
            const i = t.sourceId === o.id ? 1 : 0;t.endpoints[i].isVisible() && t.setVisible(!0)
          } else t.setVisible(e)
        }, i)
      }; var B = function (t, e, o) {
        if (n.isString(t)) return t;if (null == t) return null;let r = i.getAttribute(t, 'id');return r && 'undefined' !== r || (2 === arguments.length && void 0 !== arguments[1] ? r = e : (1 === arguments.length || 3 === arguments.length && !arguments[2]) && (r = `jsPlumb_${s}_${I()}`), o || i.setAttribute(t, 'id', r)), r
      };this.setConnectionBeingDragged = function (t) {
        j = t
      }, this.isConnectionBeingDragged = function () {
        return j
      }, this.getManagedElements = function () {
        return x
      }, this.connectorClass = 'jtk-connector', this.connectorOutlineClass = 'jtk-connector-outline', this.connectedClass = 'jtk-connected', this.hoverClass = 'jtk-hover', this.endpointClass = 'jtk-endpoint', this.endpointConnectedClass = 'jtk-endpoint-connected', this.endpointFullClass = 'jtk-endpoint-full', this.endpointDropAllowedClass = 'jtk-endpoint-drop-allowed', this.endpointDropForbiddenClass = 'jtk-endpoint-drop-forbidden', this.overlayClass = 'jtk-overlay', this.draggingClass = 'jtk-dragging', this.elementDraggingClass = 'jtk-element-dragging', this.sourceElementDraggingClass = 'jtk-source-element-dragging', this.targetElementDraggingClass = 'jtk-target-element-dragging', this.endpointAnchorClassPrefix = 'jtk-endpoint-anchor', this.hoverSourceClass = 'jtk-source-hover', this.hoverTargetClass = 'jtk-target-hover', this.dragSelectClass = 'jtk-drag-select', this.Anchors = {}, this.Connectors = { svg: {} }, this.Endpoints = { svg: {} }, this.Overlays = { svg: {} }, this.ConnectorRenderers = {}, this.SVG = 'svg', this.addEndpoint = function (t, e, o) {
        o = o || {};const s = d.extend({}, o);d.extend(s, e), s.endpoint = s.endpoint || i.Defaults.Endpoint, s.paintStyle = s.paintStyle || i.Defaults.EndpointStyle;for (var r = [], a = n.isArray(t) || null != t.length && !n.isString(t) ? t : [t], l = 0, u = a.length;l < u;l++) {
          s.source = i.getElement(a[l]), et(s.source);const c = B(s.source); const h = N(s, c); const p = nt(c, s.source, null, !S).info.o;n.addToList(b, c, h), S || h.paint({ anchorLoc: h.anchor.compute({ xy: [p.left, p.top], wh: E[c], element: h, timestamp: w, rotation: this.getRotation(c) }), timestamp: w }), r.push(h)
        } return 1 === r.length ? r[0] : r
      }, this.addEndpoints = function (t, e, o) {
        for (var s = [], r = 0, a = e.length;r < a;r++) {
          const l = i.addEndpoint(t, e[r], o);n.isArray(l) ? Array.prototype.push.apply(s, l) : s.push(l)
        } return s
      }, this.animate = function (t, e, o) {
        if (!this.animationSupported) return !1;o = o || {};const s = i.getElement(t); const r = B(s); const a = d.animEvents.step; const l = d.animEvents.complete;o[a] = n.wrap(o[a], () => {
          i.revalidate(r)
        }), o[l] = n.wrap(o[l], () => {
          i.revalidate(r)
        }), i.doAnimate(s, e, o)
      }, this.checkCondition = function (t, e) {
        const o = i.getListener(t); let s = !0;if (o && o.length > 0) {
          const r = Array.prototype.slice.call(arguments, 1);try {
            for (let a = 0, l = o.length;a < l;a++)s = s && o[a].apply(o[a], r)
          } catch (e) {
            n.log(i, `cannot check condition [${t}]${e}`)
          }
        } return s
      }, this.connect = function (t, e) {
        let i; const o = T(t, e);if (o) {
          if (null == o.source && null == o.sourceEndpoint) return void n.log('Cannot establish connection - source does not exist');if (null == o.target && null == o.targetEndpoint) return void n.log('Cannot establish connection - target does not exist');et(o.source), i = F(o), L(i, o)
        } return i
      };const H = [{ el: 'source', elId: 'sourceId', epDefs: 'sourceEndpointDefinitions' }, { el: 'target', elId: 'targetId', epDefs: 'targetEndpointDefinitions' }]; const U = function (t, e, n, i) {
        let o; let s; let r; const a = H[n]; const l = t[a.elId]; const u = (t[a.el], t.endpoints[n]); const c = { index: n, originalSourceId: 0 === n ? l : t.sourceId, newSourceId: t.sourceId, originalTargetId: 1 === n ? l : t.targetId, newTargetId: t.targetId, connection: t };if (e.constructor === d.Endpoint)(o = e).addConnection(t), e = o.element;else if (s = B(e), r = this[a.epDefs][s], s === t[a.elId])o = null;else if (r) for (const h in r) {
          if (!r[h].enabled) return;o = null != r[h].endpoint && r[h].endpoint._jsPlumb ? r[h].endpoint : this.addEndpoint(e, r[h].def), r[h].uniqueEndpoint && (r[h].endpoint = o), o.addConnection(t)
        } else o = t.makeEndpoint(0 === n, e, s);return null != o && (u.detachFromConnection(t), t.endpoints[n] = o, t[a.el] = o.element, t[a.elId] = o.elementId, c[0 === n ? 'newSourceId' : 'newTargetId'] = o.elementId, Y(c), i || t.repaint()), c.element = e, c
      }.bind(this);this.setSource = function (t, e, n) {
        const i = U(t, e, 0, n);this.router.sourceOrTargetChanged(i.originalSourceId, i.newSourceId, t, i.el, 0)
      }, this.setTarget = function (t, e, n) {
        const i = U(t, e, 1, n);this.router.sourceOrTargetChanged(i.originalTargetId, i.newTargetId, t, i.el, 1)
      }, this.deleteEndpoint = function (t, e, n) {
        const o = 'string' === typeof t ? P[t] : t;return o && i.deleteObject({ endpoint: o, dontUpdateHover: e, deleteAttachedObjects: n }), i
      }, this.deleteEveryEndpoint = function () {
        const t = i.setSuspendDrawing(!0);for (const e in b) {
          const n = b[e];if (n && n.length) for (let o = 0, s = n.length;o < s;o++)i.deleteEndpoint(n[o], !0)
        }b = {}, x = {}, P = {}, C = {}, _ = {}, i.router.reset();const r = i.getDragManager();return r && r.reset(), t || i.setSuspendDrawing(!1), i
      };var X = function (t, e, n) {
        const o = i.Defaults.ConnectionType || i.getDefaultConnectionType(); const s = t.constructor === o ? { connection: t, source: t.source, target: t.target, sourceId: t.sourceId, targetId: t.targetId, sourceEndpoint: t.endpoints[0], targetEndpoint: t.endpoints[1] } : t;e && i.fire('connectionDetached', s, n), i.fire('internal.connectionDetached', s, n), i.router.connectionDetached(s)
      }; var Y = i.fireMoveEvent = function (t, e) {
        i.fire('connectionMoved', t, e)
      };this.unregisterEndpoint = function (t) {
        for (const e in t._jsPlumb.uuid && (P[t._jsPlumb.uuid] = null), i.router.deleteEndpoint(t), b) {
          const n = b[e];if (n) {
            for (var o = [], s = 0, r = n.length;s < r;s++)n[s] !== t && o.push(n[s]);b[e] = o
          }b[e].length < 1 && delete b[e]
        }
      };this.deleteConnection = function (t, e) {
        return !(null == t || !(e = e || {}).force && !n.functionChain(!0, !1, [[t.endpoints[0], 'isDetachAllowed', [t]], [t.endpoints[1], 'isDetachAllowed', [t]], [t, 'isDetachAllowed', [t]], [i, 'checkCondition', ['beforeDetach', t]]])) && (t.setHover(!1), X(t, !t.pending && !1 !== e.fireEvent, e.originalEvent), t.endpoints[0].detachFromConnection(t), t.endpoints[1].detachFromConnection(t), n.removeWithFunction(y, (e) => t.id === e.id), t.cleanup(), t.destroy(), !0)
      }, this.deleteEveryConnection = function (t) {
        t = t || {};const e = y.length; let n = 0;return i.batch(() => {
          for (let o = 0;o < e;o++)n += i.deleteConnection(y[0], t) ? 1 : 0
        }), n
      }, this.deleteConnectionsForElement = function (t, e) {
        e = e || {}, t = i.getElement(t);const n = B(t); const o = b[n];if (o && o.length) for (let s = 0, r = o.length;s < r;s++)o[s].deleteEveryConnection(e);return i
      }, this.deleteObject = function (t) {
        const e = { endpoints: {}, connections: {}, endpointCount: 0, connectionCount: 0 }; const o = !1 !== t.deleteAttachedObjects; const s = function (n) {
          null != n && null == e.connections[n.id] && (t.dontUpdateHover || null == n._jsPlumb || n.setHover(!1), e.connections[n.id] = n, e.connectionCount++)
        };for (const r in t.connection ? s(t.connection) : (function (n) {
          if (null != n && null == e.endpoints[n.id] && (t.dontUpdateHover || null == n._jsPlumb || n.setHover(!1), e.endpoints[n.id] = n, e.endpointCount++, o)) for (let i = 0;i < n.connections.length;i++) {
            const r = n.connections[i];s(r)
          }
        }(t.endpoint)), e.connections) {
          var a = e.connections[r];if (a._jsPlumb) {
            n.removeWithFunction(y, (t) => a.id === t.id), X(a, !1 !== t.fireEvent && !a.pending, t.originalEvent);const l = null == t.deleteAttachedObjects ? null : !t.deleteAttachedObjects;a.endpoints[0].detachFromConnection(a, null, l), a.endpoints[1].detachFromConnection(a, null, l), a.cleanup(!0), a.destroy(!0)
          }
        } for (const u in e.endpoints) {
          const c = e.endpoints[u];c._jsPlumb && (i.unregisterEndpoint(c), c.cleanup(!0), c.destroy(!0))
        } return e
      };const $ = function (t, e, n) {
        return function () {
          return (function (t, e, n, i) {
            for (let o = 0, s = t.length;o < s;o++)t[o][e].apply(t[o], n);return i(t)
          }(t, e, arguments, n))
        }
      }; const z = function (t, e) {
        return function () {
          return (function (t, e, n) {
            for (var i = [], o = 0, s = t.length;o < s;o++)i.push([t[o][e].apply(t[o], n), t[o]]);return i
          }(t, e, arguments))
        }
      }; const W = function (t, e) {
        let n = [];if (t) if ('string' === typeof t) {
          if ('*' === t) return t;n.push(t)
        } else if (e)n = t;else if (t.length) for (let i = 0, o = t.length;i < o;i++)n.push(h(t[i]).id);else n.push(h(t).id);return n
      }; const V = function (t, e, n) {
        return '*' === t || (t.length > 0 ? -1 !== t.indexOf(e) : !n)
      };this.getConnections = function (t, e) {
        t ? t.constructor === String && (t = { scope: t }) : t = {};for (var n = t.scope || i.getDefaultScope(), o = W(n, !0), s = W(t.source), r = W(t.target), a = !e && o.length > 1 ? {} : [], l = function (t, n) {
            if (!e && o.length > 1) {
              let i = a[t];null == i && (i = a[t] = []), i.push(n)
            } else a.push(n)
          }, u = 0, c = y.length;u < c;u++) {
          const h = y[u]; const d = h.proxies && h.proxies[0] ? h.proxies[0].originalEp.elementId : h.sourceId; const p = h.proxies && h.proxies[1] ? h.proxies[1].originalEp.elementId : h.targetId;V(o, h.scope) && V(s, d) && V(r, p) && l(h.scope, h)
        } return a
      };const q = function (t, e) {
        return function (n) {
          for (let i = 0, o = t.length;i < o;i++)n(t[i]);return e(t)
        }
      }; const J = function (t) {
        return function (e) {
          return t[e]
        }
      }; const Z = function (t, e) {
        let n; let i; const o = { length: t.length, each: q(t, e), get: J(t) }; const s = ['setHover', 'removeAllOverlays', 'setLabel', 'addClass', 'addOverlay', 'removeOverlay', 'removeOverlays', 'showOverlay', 'hideOverlay', 'showOverlays', 'hideOverlays', 'setPaintStyle', 'setHoverPaintStyle', 'setSuspendEvents', 'setParameter', 'setParameters', 'setVisible', 'repaint', 'addType', 'toggleType', 'removeType', 'removeClass', 'setType', 'bind', 'unbind']; const r = ['getLabel', 'getOverlay', 'isHover', 'getParameter', 'getParameters', 'getPaintStyle', 'getHoverPaintStyle', 'isVisible', 'hasType', 'getType', 'isSuspendEvents'];for (n = 0, i = s.length;n < i;n++)o[s[n]] = $(t, s[n], e);for (n = 0, i = r.length;n < i;n++)o[r[n]] = z(t, r[n]);return o
      }; var K = function (t) {
        const e = Z(t, K);return d.extend(e, { setDetachable: $(t, 'setDetachable', K), setReattach: $(t, 'setReattach', K), setConnector: $(t, 'setConnector', K), delete () {
          for (let e = 0, n = t.length;e < n;e++)i.deleteConnection(t[e])
        }, isDetachable: z(t, 'isDetachable'), isReattach: z(t, 'isReattach') })
      }; var Q = function (t) {
        const e = Z(t, Q);return d.extend(e, { setEnabled: $(t, 'setEnabled', Q), setAnchor: $(t, 'setAnchor', Q), isEnabled: z(t, 'isEnabled'), deleteEveryConnection () {
          for (let e = 0, n = t.length;e < n;e++)t[e].deleteEveryConnection()
        }, delete () {
          for (let e = 0, n = t.length;e < n;e++)i.deleteEndpoint(t[e])
        } })
      };this.select = function (t) {
        return (t = t || {}).scope = t.scope || '*', K(t.connections || i.getConnections(t, !0))
      }, this.selectEndpoints = function (t) {
        (t = t || {}).scope = t.scope || '*';const e = !t.element && !t.source && !t.target; const n = e ? '*' : W(t.element); const i = e ? '*' : W(t.source); const o = e ? '*' : W(t.target); const s = W(t.scope, !0); const r = [];for (const a in b) {
          const l = V(n, a, !0); const u = V(i, a, !0); const c = '*' !== i; const h = V(o, a, !0); const d = '*' !== o;if (l || u || h)t:for (let p = 0, f = b[a].length;p < f;p++) {
            const g = b[a][p];if (V(s, g.scope, !0)) {
              const m = c && i.length > 0 && !g.isSource; const v = d && o.length > 0 && !g.isTarget;if (m || v) continue t;r.push(g)
            }
          }
        } return Q(r)
      }, this.getAllConnections = function () {
        return y
      }, this.getDefaultScope = function () {
        return D
      }, this.getEndpoint = M, this.getEndpoints = function (t) {
        return b[h(t).id] || []
      }, this.getDefaultEndpointType = function () {
        return d.Endpoint
      }, this.getDefaultConnectionType = function () {
        return d.Connection
      }, this.getId = B, this.draw = O, this.info = h, this.appendElement = k;let tt = !1;this.isHoverSuspended = function () {
        return tt
      }, this.setHoverSuspended = function (t) {
        tt = t
      }, this.hide = function (t, e) {
        return G(t, 'none', e), i
      }, this.idstamp = I;var et = function (t) {
        if (!f && t) {
          const e = i.getElement(t);e.offsetParent && i.setContainer(e.offsetParent)
        }
      }; var nt = i.manage = function (t, e, n, o) {
        return x[t] ? o && (x[t].info = it({ elId: t, timestamp: w, recalc: !0 })) : (x[t] = { el: e, endpoints: [], connections: [], rotation: 0 }, x[t].info = it({ elId: t, timestamp: w }), i.addClass(e, 'jtk-managed'), n || i.fire('manageElement', { id: t, info: x[t].info, el: e })), x[t]
      };this.unmanage = function (t) {
        if (x[t]) {
          const e = x[t].el;i.removeClass(e, 'jtk-managed'), delete x[t], i.fire('unmanageElement', { id: t, el: e })
        }
      }, this.rotate = function (t, e, n) {
        return x[t] && (x[t].rotation = e, x[t].el.style.transform = `rotate(${e}deg)`, x[t].el.style.transformOrigin = 'center center', !0 !== n) ? this.revalidate(t) : { c: [], e: [] }
      }, this.getRotation = function (t) {
        return x[t] && x[t].rotation || 0
      };var it = function (t) {
        let e; let n = t.timestamp; const o = t.recalc; const s = t.offset; const r = t.elId;return S && !n && (n = w), !o && n && n === _[r] ? { o: t.offset || C[r], s: E[r] } : (o || !s && null == C[r] ? null != (e = x[r] ? x[r].el : null) && (E[r] = i.getSize(e), C[r] = i.getOffset(e), _[r] = n) : (C[r] = s || C[r], null == E[r] && null != (e = x[r].el) && (E[r] = i.getSize(e)), _[r] = n), C[r] && !C[r].right && (C[r].right = C[r].left + E[r][0], C[r].bottom = C[r].top + E[r][1], C[r].width = E[r][0], C[r].height = E[r][1], C[r].centerx = C[r].left + C[r].width / 2, C[r].centery = C[r].top + C[r].height / 2), { o: C[r], s: E[r] })
      };this.updateOffset = it, this.init = function () {
        v || (i.Defaults.Container && i.setContainer(i.Defaults.Container), i.router = new t.jsPlumb.DefaultRouter(i), i.anchorManager = i.router.anchorManager, v = !0, i.fire('ready', i))
      }.bind(this), this.log = m, this.jsPlumbUIComponent = l, this.makeAnchor = function () {
        let e; const o = function (e, n) {
          if (t.jsPlumb.Anchors[e]) return new t.jsPlumb.Anchors[e](n);if (!i.Defaults.DoNotThrowErrors) throw { msg: `jsPlumb: unknown anchor type '${e}'` }
        };if (0 === arguments.length) return null;const s = arguments[0]; const r = arguments[1]; let a = null;if (s.compute && s.getOrientation) return s;if ('string' === typeof s)a = o(arguments[0], { elementId: r, jsPlumbInstance: i });else if (n.isArray(s)) if (n.isArray(s[0]) || n.isString(s[0]))2 === s.length && n.isObject(s[1]) ? n.isString(s[0]) ? (e = t.jsPlumb.extend({ elementId: r, jsPlumbInstance: i }, s[1]), a = o(s[0], e)) : (e = t.jsPlumb.extend({ elementId: r, jsPlumbInstance: i, anchors: s[0] }, s[1]), a = new t.jsPlumb.DynamicAnchor(e)) : a = new d.DynamicAnchor({ anchors: s, selector: null, elementId: r, jsPlumbInstance: i });else {
          const l = { x: s[0], y: s[1], orientation: s.length >= 4 ? [s[2], s[3]] : [0, 0], offsets: s.length >= 6 ? [s[4], s[5]] : [0, 0], elementId: r, jsPlumbInstance: i, cssClass: 7 === s.length ? s[6] : null };(a = new t.jsPlumb.Anchor(l)).clone = function () {
            return new t.jsPlumb.Anchor(l)
          }
        } return a.id || (a.id = `anchor_${I()}`), a
      }, this.makeAnchors = function (e, o, s) {
        for (var r = [], a = 0, l = e.length;a < l;a++)'string' === typeof e[a] ? r.push(t.jsPlumb.Anchors[e[a]]({ elementId: o, jsPlumbInstance: s })) : n.isArray(e[a]) && r.push(i.makeAnchor(e[a], o, s));return r
      }, this.makeDynamicAnchor = function (e, n) {
        return new t.jsPlumb.DynamicAnchor({ anchors: e, selector: n, elementId: null, jsPlumbInstance: i })
      }, this.targetEndpointDefinitions = {}, this.sourceEndpointDefinitions = {};const ot = function (e, o, s, r, a) {
        const u = new l(o); const c = o._jsPlumb.EndpointDropHandler({ jsPlumb: i, enabled () {
          return e.def.enabled
        }, isFull () {
          const t = i.select({ target: e.id }).length;return e.def.maxConnections > 0 && t >= e.def.maxConnections
        }, element: e.el, elementId: e.id, isSource: r, isTarget: a, addClass (t) {
          i.addClass(e.el, t)
        }, removeClass (t) {
          i.removeClass(e.el, t)
        }, onDrop (t) {
          t.endpoints[0].anchor.locked = !1
        }, isDropAllowed () {
          return u.isDropAllowed.apply(u, arguments)
        }, isRedrop (t) {
          return null != t.suspendedElement && null != t.suspendedEndpoint && t.suspendedEndpoint.element === e.el
        }, getEndpoint (n) {
          let s = e.def.endpoint;if (null == s || null == s._jsPlumb) {
            const r = i.deriveEndpointAndAnchorSpec(n.getType().join(' '), !0); let a = r.endpoints ? t.jsPlumb.extend(o, { endpoint: e.def.def.endpoint || r.endpoints[1] }) : o;r.anchors && (a = t.jsPlumb.extend(a, { anchor: e.def.def.anchor || r.anchors[1] })), (s = i.addEndpoint(e.el, a))._mtNew = !0
          } if (o.uniqueEndpoint && (e.def.endpoint = s), s.setDeleteOnEmpty(!0), n.isDetachable() && s.initDraggable(), null != s.anchor.positionFinder) {
            const l = i.getUIPosition(arguments, i.getZoom()); const u = i.getOffset(e.el); const c = i.getSize(e.el); const h = null == l ? [0, 0] : s.anchor.positionFinder(l, u, c, s.anchor.constructorParams);s.anchor.x = h[0], s.anchor.y = h[1]
          } return s
        }, maybeCleanup (t) {
          t._mtNew && 0 === t.connections.length ? i.deleteObject({ endpoint: t }) : delete t._mtNew
        } }); const h = t.jsPlumb.dragEvents.drop;return s.scope = s.scope || o.scope || i.Defaults.Scope, s[h] = n.wrap(s[h], c, !0), s.rank = o.rank || 0, a && (s[t.jsPlumb.dragEvents.over] = function () {
          return !0
        }), !1 === o.allowLoopback && (s.canDrop = function (t) {
          return t.getDragElement()._jsPlumbRelatedElement !== e.el
        }), i.initDroppable(e.el, s, 'internal'), c
      };this.makeTarget = function (e, n, o) {
        const s = t.jsPlumb.extend({ _jsPlumb: this }, o);t.jsPlumb.extend(s, n);for (var r = s.maxConnections || -1, a = function (e) {
            const n = h(e); const o = n.id; const a = t.jsPlumb.extend({}, s.dropOptions || {}); const l = s.connectionType || 'default';this.targetEndpointDefinitions[o] = this.targetEndpointDefinitions[o] || {}, et(o), n.el._isJsPlumbGroup && null == a.rank && (a.rank = -1);const u = { def: t.jsPlumb.extend({}, s), uniqueEndpoint: s.uniqueEndpoint, maxConnections: r, enabled: !0 };s.createEndpoint && (u.uniqueEndpoint = !0, u.endpoint = i.addEndpoint(e, u.def), u.endpoint.setDeleteOnEmpty(!1)), n.def = u, this.targetEndpointDefinitions[o][l] = u, ot(n, s, a, !0 === s.isSource, !0), n.el._katavorioDrop[n.el._katavorioDrop.length - 1].targetDef = u
          }.bind(this), l = e.length && e.constructor !== String ? e : [e], u = 0, c = l.length;u < c;u++)a(l[u]);return this
      }, this.unmakeTarget = function (t, e) {
        const n = h(t);return i.destroyDroppable(n.el, 'internal'), e || delete this.targetEndpointDefinitions[n.id], this
      }, this.makeSource = function (e, o, s) {
        const r = t.jsPlumb.extend({ _jsPlumb: this }, s);t.jsPlumb.extend(r, o);const a = r.connectionType || 'default'; const l = i.deriveEndpointAndAnchorSpec(a);r.endpoint = r.endpoint || l.endpoints[0], r.anchor = r.anchor || l.anchors[0];for (var c = r.maxConnections || -1, d = r.onMaxConnections, p = function (o) {
            let s = o.id; const l = this.getElement(o.el);this.sourceEndpointDefinitions[s] = this.sourceEndpointDefinitions[s] || {}, et(s);const h = { def: t.jsPlumb.extend({}, r), uniqueEndpoint: r.uniqueEndpoint, maxConnections: c, enabled: !0 };r.createEndpoint && (h.uniqueEndpoint = !0, h.endpoint = i.addEndpoint(e, h.def), h.endpoint.setDeleteOnEmpty(!1)), this.sourceEndpointDefinitions[s][a] = h, o.def = h;const p = t.jsPlumb.dragEvents.stop; const f = t.jsPlumb.dragEvents.drag; const g = t.jsPlumb.extend({}, r.dragOptions || {}); const m = g.drag; const v = g.stop; let y = null; let b = !1;g.scope = g.scope || r.scope, g[f] = n.wrap(g[f], function () {
              m && m.apply(this, arguments), b = !1
            }), g[p] = n.wrap(g[p], function () {
              if (v && v.apply(this, arguments), this.currentlyDragging = !1, null != y._jsPlumb) {
                const t = r.anchor || this.Defaults.Anchor; const e = y.anchor; const n = y.connections[0]; const o = this.makeAnchor(t, s, this); const a = y.element;if (null != o.positionFinder) {
                  const l = i.getOffset(a); const u = this.getSize(a); const c = { left: l.left + e.x * u[0], top: l.top + e.y * u[1] }; const h = o.positionFinder(c, l, u, o.constructorParams);o.x = h[0], o.y = h[1]
                }y.setAnchor(o, !0), y.repaint(), this.repaint(y.elementId), null != n && this.repaint(n.targetId)
              }
            }.bind(this));const P = function (e) {
              if (3 !== e.which && 2 !== e.button) {
                s = this.getId(this.getElement(o.el));const h = this.sourceEndpointDefinitions[s][a];if (h.enabled) {
                  if (r.filter) if (!1 === (n.isString(r.filter) ? (function (t, e, n, i, o) {
                    for (var s = t.target || t.srcElement, r = !1, a = i.getSelector(e, n), l = 0;l < a.length;l++) if (a[l] === s) {
                      r = !0;break
                    } return o ? !r : r
                  }(e, o.el, r.filter, this, r.filterExclude)) : r.filter(e, o.el))) return;const p = this.select({ source: s }).length;if (h.maxConnections >= 0 && p >= h.maxConnections) return d && d({ element: o.el, maxConnections: c }, e), !1;const f = t.jsPlumb.getPositionOnElement(e, l, u); const m = {};t.jsPlumb.extend(m, h.def), m.isTemporarySource = !0, m.anchor = [f[0], f[1], 0, 0], m.dragOptions = g, h.def.scope && (m.scope = h.def.scope), y = this.addEndpoint(s, m), b = !0, y.setDeleteOnEmpty(!0), h.uniqueEndpoint && (h.endpoint ? y.finalEndpoint = h.endpoint : (h.endpoint = y, y.setDeleteOnEmpty(!1)));var v = function () {
                    i.off(y.canvas, 'mouseup', v), i.off(o.el, 'mouseup', v), b && (b = !1, i.deleteEndpoint(y))
                  };i.on(y.canvas, 'mouseup', v), i.on(o.el, 'mouseup', v);const P = {};if (h.def.extract) for (const x in h.def.extract) {
                    const C = (e.srcElement || e.target).getAttribute(x);C && (P[h.def.extract[x]] = C)
                  }i.trigger(y.canvas, 'mousedown', e, P), n.consume(e)
                }
              }
            }.bind(this);this.on(o.el, 'mousedown', P), h.trigger = P, r.filter && (n.isString(r.filter) || n.isFunction(r.filter)) && i.setDragFilter(o.el, r.filter);const x = t.jsPlumb.extend({}, r.dropOptions || {});ot(o, r, x, !0, !0 === r.isTarget)
          }.bind(this), f = e.length && e.constructor !== String ? e : [e], g = 0, m = f.length;g < m;g++)p(h(f[g]));return this
      }, this.unmakeSource = function (t, e, n) {
        const o = h(t);i.destroyDroppable(o.el, 'internal');const s = this.sourceEndpointDefinitions[o.id];if (s) for (const r in s) if (null == e || e === r) {
          const a = s[r].trigger;a && i.off(o.el, 'mousedown', a), n || delete this.sourceEndpointDefinitions[o.id][r]
        } return this
      }, this.unmakeEverySource = function () {
        for (const t in this.sourceEndpointDefinitions)i.unmakeSource(t, null, !0);return this.sourceEndpointDefinitions = {}, this
      };const st = function (t, e, i) {
        e = n.isArray(e) ? e : [e];const o = B(t);i = i || 'default';for (let s = 0;s < e.length;s++) {
          const r = this[e[s]][o];if (r && r[i]) return r[i].def.scope || this.Defaults.Scope
        }
      }.bind(this); const rt = function (t, e, i, o) {
        i = n.isArray(i) ? i : [i];const s = B(t);o = o || 'default';for (let r = 0;r < i.length;r++) {
          const a = this[i[r]][s];a && a[o] && (a[o].def.scope = e)
        }
      }.bind(this);this.getScope = function (t, e) {
        return st(t, ['sourceEndpointDefinitions', 'targetEndpointDefinitions'])
      }, this.getSourceScope = function (t) {
        return st(t, 'sourceEndpointDefinitions')
      }, this.getTargetScope = function (t) {
        return st(t, 'targetEndpointDefinitions')
      }, this.setScope = function (t, e, n) {
        this.setSourceScope(t, e, n), this.setTargetScope(t, e, n)
      }, this.setSourceScope = function (t, e, n) {
        rt(t, e, 'sourceEndpointDefinitions', n), this.setDragScope(t, e)
      }, this.setTargetScope = function (t, e, n) {
        rt(t, e, 'targetEndpointDefinitions', n), this.setDropScope(t, e)
      }, this.unmakeEveryTarget = function () {
        for (const t in this.targetEndpointDefinitions)i.unmakeTarget(t, !0);return this.targetEndpointDefinitions = {}, this
      };const at = function (t, e, o, s, r) {
        let a; let l; let u; const c = 'source' === t ? this.sourceEndpointDefinitions : this.targetEndpointDefinitions;if (r = r || 'default', e.length && !n.isString(e)) {
          a = [];for (let d = 0, p = e.length;d < p;d++)c[(l = h(e[d])).id] && c[l.id][r] && (a[d] = c[l.id][r].enabled, u = s ? !a[d] : o, c[l.id][r].enabled = u, i[u ? 'removeClass' : 'addClass'](l.el, `jtk-${t}-disabled`))
        } else {
          const f = (l = h(e)).id;c[f] && c[f][r] && (a = c[f][r].enabled, u = s ? !a : o, c[f][r].enabled = u, i[u ? 'removeClass' : 'addClass'](l.el, `jtk-${t}-disabled`))
        } return a
      }.bind(this); const lt = function (t, e) {
        if (null != t) {
          if (n.isString(t) || !t.length) return e.apply(this, [t]);if (t.length) return e.apply(this, [t[0]])
        }
      }.bind(this);this.toggleSourceEnabled = function (t, e) {
        return at('source', t, null, !0, e), this.isSourceEnabled(t, e)
      }, this.setSourceEnabled = function (t, e, n) {
        return at('source', t, e, null, n)
      }, this.isSource = function (t, e) {
        return e = e || 'default', lt(t, (t) => {
          const n = this.sourceEndpointDefinitions[h(t).id];return null != n && null != n[e]
        })
      }, this.isSourceEnabled = function (t, e) {
        return e = e || 'default', lt(t, (t) => {
          const n = this.sourceEndpointDefinitions[h(t).id];return n && n[e] && !0 === n[e].enabled
        })
      }, this.toggleTargetEnabled = function (t, e) {
        return at('target', t, null, !0, e), this.isTargetEnabled(t, e)
      }, this.isTarget = function (t, e) {
        return e = e || 'default', lt(t, (t) => {
          const n = this.targetEndpointDefinitions[h(t).id];return null != n && null != n[e]
        })
      }, this.isTargetEnabled = function (t, e) {
        return e = e || 'default', lt(t, (t) => {
          const n = this.targetEndpointDefinitions[h(t).id];return n && n[e] && !0 === n[e].enabled
        })
      }, this.setTargetEnabled = function (t, e, n) {
        return at('target', t, e, null, n)
      }, this.ready = function (t) {
        i.bind('ready', t)
      };this.repaint = function (t, e, n) {
        return (function (t, e) {
          if ('object' === typeof t && t.length) for (let n = 0, o = t.length;n < o;n++)e(t[n]);else e(t);return i
        }(t, (t) => {
          O(t, e, n)
        }))
      }, this.revalidate = function (t, e, n) {
        const o = n ? t : i.getId(t);i.updateOffset({ elId: o, recalc: !0, timestamp: e });const s = i.getDragManager();return s && s.updateOffsets(o), O(t, null, e)
      }, this.repaintEverything = function () {
        let t; const e = jsPlumbUtil.uuid();for (t in b)i.updateOffset({ elId: t, recalc: !0, timestamp: e });for (t in b)O(t, null, e);return this
      }, this.removeAllEndpoints = function (t, e, n) {
        n = n || [];var o = function (t) {
          let s; let r; const a = h(t); const l = b[a.id];if (l) for (n.push(a), s = 0, r = l.length;s < r;s++)i.deleteEndpoint(l[s], !1);if (delete b[a.id], e && a.el && 3 !== a.el.nodeType && 8 !== a.el.nodeType) for (s = 0, r = a.el.childNodes.length;s < r;s++)o(a.el.childNodes[s])
        };return o(t), this
      };const ut = function (t, e) {
        i.removeAllEndpoints(t.id, !0, e);for (var n = i.getDragManager(), o = function (t) {
            n && n.elementRemoved(t.id), i.router.elementRemoved(t.id), i.isSource(t.el) && i.unmakeSource(t.el), i.isTarget(t.el) && i.unmakeTarget(t.el), i.destroyDraggable(t.el), i.destroyDroppable(t.el), delete i.floatingConnections[t.id], delete x[t.id], delete C[t.id], t.el && (i.removeElement(t.el), t.el._jsPlumb = null)
          }, s = 1;s < e.length;s++)o(e[s]);o(t)
      };this.remove = function (t, e) {
        const n = h(t); const o = [];return n.text && n.el.parentNode ? n.el.parentNode.removeChild(n.el) : n.id && i.batch(() => {
          ut(n, o)
        }, !0 === e), i
      }, this.empty = function (t, e) {
        const n = []; var o = function (t, e) {
          const i = h(t);if (i.text)i.el.parentNode.removeChild(i.el);else if (i.el) {
            for (;i.el.childNodes.length > 0;)o(i.el.childNodes[0]);e || ut(i, n)
          }
        };return i.batch(() => {
          o(t, !0)
        }, !1 === e), i
      }, this.reset = function (t) {
        i.silently(() => {
          tt = !1, i.removeAllGroups(), i.removeGroupManager(), i.deleteEveryEndpoint(), t || i.unbind(), this.targetEndpointDefinitions = {}, this.sourceEndpointDefinitions = {}, y.length = 0, this.doReset && this.doReset()
        })
      }, this.destroy = function () {
        this.reset(), f = null, g = null
      };const ct = function (t) {
        t.canvas && t.canvas.parentNode && t.canvas.parentNode.removeChild(t.canvas), t.cleanup(), t.destroy()
      };this.clear = function () {
        i.select().each(ct), i.selectEndpoints().each(ct), b = {}, P = {}
      }, this.setDefaultScope = function (t) {
        return D = t, i
      }, this.deriveEndpointAndAnchorSpec = function (t, e) {
        for (var n = ((e ? '' : 'default ') + t).split(/[\s]/), o = null, s = null, r = null, a = null, l = 0;l < n.length;l++) {
          const u = i.getType(n[l], 'connection');u && (u.endpoints && (o = u.endpoints), u.endpoint && (s = u.endpoint), u.anchors && (a = u.anchors), u.anchor && (r = u.anchor))
        } return { endpoints: o || [s, s], anchors: a || [r, r] }
      }, this.setId = function (t, e, i) {
        let o;n.isString(t) ? o = t : (t = this.getElement(t), o = this.getId(t));const s = this.getConnections({ source: o, scope: '*' }, !0); const r = this.getConnections({ target: o, scope: '*' }, !0);e = `${e}`, i ? t = this.getElement(e) : (t = this.getElement(o), this.setAttribute(t, 'id', e)), b[e] = b[o] || [];for (let a = 0, l = b[e].length;a < l;a++)b[e][a].setElementId(e), b[e][a].setReferenceElement(t);delete b[o], this.sourceEndpointDefinitions[e] = this.sourceEndpointDefinitions[o], delete this.sourceEndpointDefinitions[o], this.targetEndpointDefinitions[e] = this.targetEndpointDefinitions[o], delete this.targetEndpointDefinitions[o], this.router.changeId(o, e);const u = this.getDragManager();u && u.changeId(o, e), x[e] = x[o], delete x[o];const c = function (n, i, o) {
          for (let s = 0, r = n.length;s < r;s++)n[s].endpoints[i].setElementId(e), n[s].endpoints[i].setReferenceElement(t), n[s][`${o}Id`] = e, n[s][o] = t
        };c(s, 0, 'source'), c(r, 1, 'target'), this.repaint(e)
      }, this.setDebugLog = function (t) {
        m = t
      }, this.setSuspendDrawing = function (t, e) {
        const n = S;return S = t, w = t ? (new Date).getTime() : null, e && this.repaintEverything(), n
      }, this.isSuspendDrawing = function () {
        return S
      }, this.getSuspendedAt = function () {
        return w
      }, this.batch = function (t, e) {
        const i = this.isSuspendDrawing();i || this.setSuspendDrawing(!0);try {
          t()
        } catch (t) {
          n.log('Function run while suspended failed', t)
        }i || this.setSuspendDrawing(!1, !e)
      }, this.doWhileSuspended = this.batch, this.getCachedData = function (t) {
        const e = C[t];return e ? { o: e, s: E[t] } : it({ elId: t })
      }, this.show = function (t, e) {
        return G(t, 'block', e), i
      }, this.toggleVisible = function (t, e) {
        let n = null;e && (n = function (t) {
          const e = t.isVisible();t.setVisible(!e)
        }), R(t, (t) => {
          const e = t.isVisible();t.setVisible(!e)
        }, n)
      }, this.addListener = this.bind;const ht = [];this.registerFloatingConnection = function (t, e, i) {
        ht[t.id] = e, n.addToList(b, t.id, i)
      }, this.getFloatingConnectionFor = function (t) {
        return ht[t]
      }, this.listManager = new t.jsPlumbListManager(this, this.Defaults.ListStyle)
    };n.extend(t.jsPlumbInstance, n.EventGenerator, { setAttribute (t, e, n) {
      this.setAttribute(t, e, n)
    }, getAttribute (e, n) {
      return this.getAttribute(t.jsPlumb.getElement(e), n)
    }, convertToFullOverlaySpec (t) {
      return n.isString(t) && (t = [t, {}]), t[1].id = t[1].id || n.uuid(), t
    }, registerConnectionType (e, n) {
      if (this._connectionTypes[e] = t.jsPlumb.extend({}, n), n.overlays) {
        for (var i = {}, o = 0;o < n.overlays.length;o++) {
          const s = this.convertToFullOverlaySpec(n.overlays[o]);i[s[1].id] = s
        } this._connectionTypes[e].overlays = i
      }
    }, registerConnectionTypes (t) {
      for (const e in t) this.registerConnectionType(e, t[e])
    }, registerEndpointType (e, n) {
      if (this._endpointTypes[e] = t.jsPlumb.extend({}, n), n.overlays) {
        for (var i = {}, o = 0;o < n.overlays.length;o++) {
          const s = this.convertToFullOverlaySpec(n.overlays[o]);i[s[1].id] = s
        } this._endpointTypes[e].overlays = i
      }
    }, registerEndpointTypes (t) {
      for (const e in t) this.registerEndpointType(e, t[e])
    }, getType (t, e) {
      return 'connection' === e ? this._connectionTypes[t] : this._endpointTypes[t]
    }, setIdChanged (t, e) {
      this.setId(t, e, !0)
    }, setParent (t, e) {
      const n = this.getElement(t); const i = this.getId(n); const o = this.getElement(e); const s = this.getId(o); const r = this.getDragManager();n.parentNode.removeChild(n), o.appendChild(n), r && r.setParent(n, i, o, s)
    }, extend (t, e, n) {
      let i;if (n) for (i = 0;i < n.length;i++)t[n[i]] = e[n[i]];else for (i in e)t[i] = e[i];return t
    }, floatingConnections: {}, getFloatingAnchorIndex (t) {
      return t.endpoints[0].isFloating() ? 0 : t.endpoints[1].isFloating() ? 1 : -1
    }, proxyConnection (t, e, n, i, o, s) {
      let r; const a = t.endpoints[e].elementId; const l = t.endpoints[e];t.proxies = t.proxies || [], (r = t.proxies[e] ? t.proxies[e].ep : this.addEndpoint(n, { endpoint: o(t, e), anchor: s(t, e), parameters: { isProxyEndpoint: !0 } })).setDeleteOnEmpty(!0), t.proxies[e] = { ep: r, originalEp: l }, 0 === e ? this.router.sourceOrTargetChanged(a, i, t, n, 0) : this.router.sourceOrTargetChanged(a, i, t, n, 1), l.detachFromConnection(t, null, !0), r.connections = [t], t.endpoints[e] = r, l.setVisible(!1), t.setVisible(!0), this.revalidate(n)
    }, unproxyConnection (t, e, n) {
      if (null != t._jsPlumb && null != t.proxies && null != t.proxies[e]) {
        const i = t.proxies[e].originalEp.element; const o = t.proxies[e].originalEp.elementId;t.endpoints[e] = t.proxies[e].originalEp, 0 === e ? this.router.sourceOrTargetChanged(n, o, t, i, 0) : this.router.sourceOrTargetChanged(n, o, t, i, 1), t.proxies[e].ep.detachFromConnection(t, null), t.proxies[e].originalEp.addConnection(t), t.isVisible() && t.proxies[e].originalEp.setVisible(!0), delete t.proxies[e]
      }
    } });var d = new h;t.jsPlumb = d, d.getInstance = function (t, e) {
      const n = new h(t);if (e) for (const i in e)n[i] = e[i];return n.init(), n
    }, d.each = function (t, e) {
      if (null != t) if ('string' === typeof t)e(d.getElement(t));else if (null != t.length) for (let n = 0;n < t.length;n++)e(d.getElement(t[n]));else e(t)
    }, e.jsPlumb = d
  }.call('undefined' !== typeof window ? window : s), function () {
    const t = this; const e = t.jsPlumb; const n = t.jsPlumbUtil;e.OverlayCapableJsPlumbUIComponent = function (e) {
      t.jsPlumbUIComponent.apply(this, arguments), this._jsPlumb.overlays = {}, this._jsPlumb.overlayPositions = {}, e.label && (this.getDefaultType().overlays.__label = ['Label', { label: e.label, location: e.labelLocation || this.defaultLabelLocation || .5, labelStyle: e.labelStyle || this._jsPlumb.instance.Defaults.LabelStyle, id: '__label' }]), this.setListenerComponent = function (t) {
        if (this._jsPlumb) for (const e in this._jsPlumb.overlays) this._jsPlumb.overlays[e].setListenerComponent(t)
      }
    }, e.OverlayCapableJsPlumbUIComponent.applyType = function (t, e) {
      if (e.overlays) {
        let n; const i = {};for (n in e.overlays) {
          const o = t._jsPlumb.overlays[e.overlays[n][1].id];if (o)o.updateFrom(e.overlays[n][1]), i[e.overlays[n][1].id] = !0, o.reattach(t._jsPlumb.instance, t);else {
            let s = t.getCachedTypeItem('overlay', e.overlays[n][1].id);null != s ? (s.reattach(t._jsPlumb.instance, t), s.setVisible(!0), s.updateFrom(e.overlays[n][1]), t._jsPlumb.overlays[s.id] = s) : s = t.addOverlay(e.overlays[n], !0), i[s.id] = !0
          }
        } for (n in t._jsPlumb.overlays)null == i[t._jsPlumb.overlays[n].id] && t.removeOverlay(t._jsPlumb.overlays[n].id, !0)
      }
    }, n.extend(e.OverlayCapableJsPlumbUIComponent, t.jsPlumbUIComponent, { setHover (t, e) {
      if (this._jsPlumb && !this._jsPlumb.instance.isConnectionBeingDragged()) for (const n in this._jsPlumb.overlays) this._jsPlumb.overlays[n][t ? 'addClass' : 'removeClass'](this._jsPlumb.instance.hoverClass)
    }, addOverlay (t, i) {
      const o = (function (t, i) {
        let o = null;if (n.isArray(i)) {
          const s = i[0]; const r = e.extend({ component: t, _jsPlumb: t._jsPlumb.instance }, i[1]);3 === i.length && e.extend(r, i[2]), o = new(e.Overlays[t._jsPlumb.instance.getRenderMode()][s])(r)
        } else o = i.constructor === String ? new(e.Overlays[t._jsPlumb.instance.getRenderMode()][i])({ component: t, _jsPlumb: t._jsPlumb.instance }) : i;return o.id = o.id || n.uuid(), t.cacheTypeItem('overlay', o, o.id), t._jsPlumb.overlays[o.id] = o, o
      }(this, t));if (this.getData && 'Label' === o.type && n.isArray(t)) {
        const s = this.getData(); const r = t[1];if (s) {
          const a = r.labelLocationAttribute || 'labelLocation'; const l = s ? s[a] : null;l && (o.loc = l)
        }
      } return i || this.repaint(), o
    }, getOverlay (t) {
      return this._jsPlumb.overlays[t]
    }, getOverlays () {
      return this._jsPlumb.overlays
    }, hideOverlay (t) {
      const e = this.getOverlay(t);e && e.hide()
    }, hideOverlays () {
      for (const t in this._jsPlumb.overlays) this._jsPlumb.overlays[t].hide()
    }, showOverlay (t) {
      const e = this.getOverlay(t);e && e.show()
    }, showOverlays () {
      for (const t in this._jsPlumb.overlays) this._jsPlumb.overlays[t].show()
    }, removeAllOverlays (t) {
      for (const e in this._jsPlumb.overlays) this._jsPlumb.overlays[e].cleanup && this._jsPlumb.overlays[e].cleanup();this._jsPlumb.overlays = {}, this._jsPlumb.overlayPositions = null, this._jsPlumb.overlayPlacements = {}, t || this.repaint()
    }, removeOverlay (t, e) {
      const n = this._jsPlumb.overlays[t];n && (n.setVisible(!1), !e && n.cleanup && n.cleanup(), delete this._jsPlumb.overlays[t], this._jsPlumb.overlayPositions && delete this._jsPlumb.overlayPositions[t], this._jsPlumb.overlayPlacements && delete this._jsPlumb.overlayPlacements[t])
    }, removeOverlays () {
      for (let t = 0, e = arguments.length;t < e;t++) this.removeOverlay(arguments[t])
    }, moveParent (t) {
      if (this.bgCanvas && (this.bgCanvas.parentNode.removeChild(this.bgCanvas), t.appendChild(this.bgCanvas)), this.canvas && this.canvas.parentNode) for (const e in this.canvas.parentNode.removeChild(this.canvas), t.appendChild(this.canvas), this._jsPlumb.overlays) if (this._jsPlumb.overlays[e].isAppendedAtTopLevel) {
        const n = this._jsPlumb.overlays[e].getElement();n.parentNode.removeChild(n), t.appendChild(n)
      }
    }, getLabel () {
      const t = this.getOverlay('__label');return null != t ? t.getLabel() : null
    }, getLabelOverlay () {
      return this.getOverlay('__label')
    }, setLabel (t) {
      let n = this.getOverlay('__label');n ? t.constructor === String || t.constructor === Function ? n.setLabel(t) : (t.label && n.setLabel(t.label), t.location && n.setLocation(t.location)) : (n = (function (t, n) {
        const i = { cssClass: n.cssClass, labelStyle: t.labelStyle, id: '__label', component: t, _jsPlumb: t._jsPlumb.instance }; const o = e.extend(i, n);return new(e.Overlays[t._jsPlumb.instance.getRenderMode()].Label)(o)
      }(this, t.constructor === String || t.constructor === Function ? { label: t } : t)), this._jsPlumb.overlays.__label = n);this._jsPlumb.instance.isSuspendDrawing() || this.repaint()
    }, cleanup (t) {
      for (const e in this._jsPlumb.overlays) this._jsPlumb.overlays[e].cleanup(t), this._jsPlumb.overlays[e].destroy(t);t && (this._jsPlumb.overlays = {}, this._jsPlumb.overlayPositions = null)
    }, setVisible (t) {
      this[t ? 'showOverlays' : 'hideOverlays']()
    }, setAbsoluteOverlayPosition (t, e) {
      this._jsPlumb.overlayPositions[t.id] = e
    }, getAbsoluteOverlayPosition (t) {
      return this._jsPlumb.overlayPositions ? this._jsPlumb.overlayPositions[t.id] : null
    }, _clazzManip (t, e, n) {
      if (!n) for (const i in this._jsPlumb.overlays) this._jsPlumb.overlays[i][`${t}Class`](e)
    }, addClass (t, e) {
      this._clazzManip('add', t, e)
    }, removeClass (t, e) {
      this._clazzManip('remove', t, e)
    } })
  }.call('undefined' !== typeof window ? window : s), function () {
    const t = this.jsPlumb; const e = this.jsPlumbUtil; const n = ['connectorStyle', 'connectorHoverStyle', 'connectorOverlays', 'connector', 'connectionType', 'connectorClass', 'connectorHoverClass'];t.Endpoint = function (i) {
      const o = i._jsPlumb; const s = i.newConnection; const r = i.newEndpoint;this.idPrefix = '_jsplumb_e_', this.defaultLabelLocation = [.5, .5], this.defaultOverlayKeys = ['Overlays', 'EndpointOverlays'], t.OverlayCapableJsPlumbUIComponent.apply(this, arguments), this.appendToDefaultType({ connectionType: i.connectionType, maxConnections: null == i.maxConnections ? this._jsPlumb.instance.Defaults.MaxConnections : i.maxConnections, paintStyle: i.endpointStyle || i.paintStyle || i.style || this._jsPlumb.instance.Defaults.EndpointStyle || t.Defaults.EndpointStyle, hoverPaintStyle: i.endpointHoverStyle || i.hoverPaintStyle || this._jsPlumb.instance.Defaults.EndpointHoverStyle || t.Defaults.EndpointHoverStyle, connectorStyle: i.connectorStyle, connectorHoverStyle: i.connectorHoverStyle, connectorClass: i.connectorClass, connectorHoverClass: i.connectorHoverClass, connectorOverlays: i.connectorOverlays, connector: i.connector, connectorTooltip: i.connectorTooltip }), this._jsPlumb.enabled = !(!1 === i.enabled), this._jsPlumb.visible = !0, this.element = t.getElement(i.source), this._jsPlumb.uuid = i.uuid, this._jsPlumb.floatingEndpoint = null, this._jsPlumb.uuid && (i.endpointsByUUID[this._jsPlumb.uuid] = this), this.elementId = i.elementId, this.dragProxy = i.dragProxy, this._jsPlumb.connectionCost = i.connectionCost, this._jsPlumb.connectionsDirected = i.connectionsDirected, this._jsPlumb.currentAnchorClass = '', this._jsPlumb.events = {};let a = !0 === i.deleteOnEmpty;this.setDeleteOnEmpty = function (t) {
        a = t
      };const l = function () {
        const e = `${o.endpointAnchorClassPrefix}-${this._jsPlumb.currentAnchorClass}`;this._jsPlumb.currentAnchorClass = this.anchor.getCssClass();const n = o.endpointAnchorClassPrefix + (this._jsPlumb.currentAnchorClass ? `-${this._jsPlumb.currentAnchorClass}` : '');this.removeClass(e), this.addClass(n), t.updateClasses(this.element, n, e)
      }.bind(this);this.prepareAnchor = function (t) {
        const e = this._jsPlumb.instance.makeAnchor(t, this.elementId, o);return e.bind('anchorChanged', (t) => {
          this.fire('anchorChanged', { endpoint: this, anchor: t }), l()
        }), e
      }, this.setPreparedAnchor = function (t, e) {
        return this._jsPlumb.instance.continuousAnchorFactory.clear(this.elementId), this.anchor = t, l(), e || this._jsPlumb.instance.repaint(this.elementId), this
      }, this.setAnchor = function (t, e) {
        const n = this.prepareAnchor(t);return this.setPreparedAnchor(n, e), this
      };const u = function (t) {
        if (this.connections.length > 0) for (let e = 0;e < this.connections.length;e++) this.connections[e].setHover(t, !1);else this.setHover(t)
      }.bind(this);this.bind('mouseover', () => {
        u(!0)
      }), this.bind('mouseout', () => {
        u(!1)
      }), i._transient || this._jsPlumb.instance.router.addEndpoint(this, this.elementId), this.prepareEndpoint = function (n, s) {
        let r; const a = function (e, n) {
          const i = o.getRenderMode();if (t.Endpoints[i][e]) return new t.Endpoints[i][e](n);if (!o.Defaults.DoNotThrowErrors) throw { msg: `jsPlumb: unknown endpoint type '${e}'` }
        }; let l = { _jsPlumb: this._jsPlumb.instance, cssClass: i.cssClass, container: i.container, tooltip: i.tooltip, connectorTooltip: i.connectorTooltip, endpoint: this };return e.isString(n) ? r = a(n, l) : e.isArray(n) ? (l = e.merge(n[1], l), r = a(n[0], l)) : r = n.clone(), r.clone = function () {
          return e.isString(n) ? a(n, l) : e.isArray(n) ? (l = e.merge(n[1], l), a(n[0], l)) : void 0
        }.bind(this), r.typeId = s, r
      }, this.setEndpoint = function (t, e) {
        const n = this.prepareEndpoint(t);this.setPreparedEndpoint(n, !0)
      }, this.setPreparedEndpoint = function (t, e) {
        null != this.endpoint && (this.endpoint.cleanup(), this.endpoint.destroy()), this.endpoint = t, this.type = this.endpoint.type, this.canvas = this.endpoint.canvas
      }, t.extend(this, i, n), this.isSource = i.isSource || !1, this.isTemporarySource = i.isTemporarySource || !1, this.isTarget = i.isTarget || !1, this.connections = i.connections || [], this.connectorPointerEvents = i['connector-pointer-events'], this.scope = i.scope || o.getDefaultScope(), this.timestamp = null, this.reattachConnections = i.reattach || o.Defaults.ReattachConnections, this.connectionsDetachable = o.Defaults.ConnectionsDetachable, !1 !== i.connectionsDetachable && !1 !== i.detachable || (this.connectionsDetachable = !1), this.dragAllowedWhenFull = !1 !== i.dragAllowedWhenFull, i.onMaxConnections && this.bind('maxConnections', i.onMaxConnections), this.addConnection = function (t) {
        this.connections.push(t), this[`${this.connections.length > 0 ? 'add' : 'remove'}Class`](o.endpointConnectedClass), this[`${this.isFull() ? 'add' : 'remove'}Class`](o.endpointFullClass)
      }, this.detachFromConnection = function (t, e, n) {
        (e = null == e ? this.connections.indexOf(t) : e) >= 0 && (this.connections.splice(e, 1), this[`${this.connections.length > 0 ? 'add' : 'remove'}Class`](o.endpointConnectedClass), this[`${this.isFull() ? 'add' : 'remove'}Class`](o.endpointFullClass)), !n && a && 0 === this.connections.length && o.deleteObject({ endpoint: this, fireEvent: !1, deleteAttachedObjects: !0 !== n })
      }, this.deleteEveryConnection = function (t) {
        for (let e = this.connections.length, n = 0;n < e;n++)o.deleteConnection(this.connections[0], t)
      }, this.detachFrom = function (t, e, n) {
        for (var i = [], s = 0;s < this.connections.length;s++) this.connections[s].endpoints[1] !== t && this.connections[s].endpoints[0] !== t || i.push(this.connections[s]);for (let r = 0, a = i.length;r < a;r++)o.deleteConnection(i[0]);return this
      }, this.getElement = function () {
        return this.element
      }, this.setElement = function (n) {
        const s = this._jsPlumb.instance.getId(n); const r = this.elementId;return e.removeWithFunction(i.endpointsByElement[this.elementId], (t) => t.id === this.id), this.element = t.getElement(n), this.elementId = o.getId(this.element), o.router.rehomeEndpoint(this, r, this.element), o.dragManager.endpointAdded(this.element), e.addToList(i.endpointsByElement, s, this), this
      }, this.makeInPlaceCopy = function () {
        const t = this.anchor.getCurrentLocation({ element: this }); const e = this.anchor.getOrientation(this); const n = this.anchor.getCssClass(); const o = { bind () {}, compute () {
          return [t[0], t[1]]
        }, getCurrentLocation () {
          return [t[0], t[1]]
        }, getOrientation () {
          return e
        }, getCssClass () {
          return n
        } };return r({ dropOptions: i.dropOptions, anchor: o, source: this.element, paintStyle: this.getPaintStyle(), endpoint: i.hideOnDrag ? 'Blank' : this.endpoint, _transient: !0, scope: this.scope, reference: this })
      }, this.connectorSelector = function () {
        return this.connections[0]
      }, this.setStyle = this.setPaintStyle, this.paint = function (t) {
        const e = (t = t || {}).timestamp; const n = !(!1 === t.recalc);if (!e || this.timestamp !== e) {
          const i = o.updateOffset({ elId: this.elementId, timestamp: e }); const s = t.offset ? t.offset.o : i.o;if (null != s) {
            let r = t.anchorPoint; const a = t.connectorPaintStyle;if (null == r) {
              const l = t.dimensions || i.s; const u = { xy: [s.left, s.top], wh: l, element: this, timestamp: e };if (n && this.anchor.isDynamic && this.connections.length > 0) {
                const c = (function (t, e) {
                  let n = 0;if (null != e) for (let i = 0;i < t.connections.length;i++) if (t.connections[i].sourceId === e || t.connections[i].targetId === e) {
                    n = i;break
                  } return t.connections[n]
                }(this, t.elementWithPrecedence)); const h = c.endpoints[0] === this ? 1 : 0; const d = 0 === h ? c.sourceId : c.targetId; const p = o.getCachedData(d); const f = p.o; const g = p.s;u.index = 0 === h ? 1 : 0, u.connection = c, u.txy = [f.left, f.top], u.twh = g, u.tElement = c.endpoints[h], u.tRotation = o.getRotation(d)
              } else this.connections.length > 0 && (u.connection = this.connections[0]);u.rotation = o.getRotation(this.elementId), r = this.anchor.compute(u)
            } for (const m in this.endpoint.compute(r, this.anchor.getOrientation(this), this._jsPlumb.paintStyleInUse, a || this.paintStyleInUse), this.endpoint.paint(this._jsPlumb.paintStyleInUse, this.anchor), this.timestamp = e, this._jsPlumb.overlays) if (this._jsPlumb.overlays.hasOwnProperty(m)) {
              const v = this._jsPlumb.overlays[m];v.isVisible() && (this._jsPlumb.overlayPlacements[m] = v.draw(this.endpoint, this._jsPlumb.paintStyleInUse), v.paint(this._jsPlumb.overlayPlacements[m]))
            }
          }
        }
      }, this.getTypeDescriptor = function () {
        return 'endpoint'
      }, this.isVisible = function () {
        return this._jsPlumb.visible
      }, this.repaint = this.paint;let c = !1;this.initDraggable = function () {
        if (!c && t.isDragSupported(this.element)) {
          let n; const a = { id: null, element: null }; let l = null; let u = !1; let h = null; const d = (function (t, e, n) {
            let i = !1;return { drag () {
              if (i) return i = !1, !0;if (e.element) {
                const o = n.getUIPosition(arguments, n.getZoom());null != o && n.setPosition(e.element, o), n.repaint(e.element, o), t.paint({ anchorPoint: t.anchor.getCurrentLocation({ element: t }) })
              }
            }, stopDrag () {
              i = !0
            } }
          }(this, a, o)); let p = i.dragOptions || {}; const f = t.dragEvents.start; const g = t.dragEvents.stop; const m = t.dragEvents.drag; const v = t.dragEvents.beforeStart; const y = function (e) {
            l = this.connectorSelector();let c = !0;this.isEnabled() || (c = !1), null != l || this.isSource || this.isTemporarySource || (c = !1), !this.isSource || !this.isFull() || null != l && this.dragAllowedWhenFull || (c = !1), null == l || l.isDetachable(this) || (this.isFull() ? c = !1 : l = null);let p = o.checkCondition(null == l ? 'beforeDrag' : 'beforeStartDetach', { endpoint: this, source: this.element, sourceId: this.elementId, connection: l });if (!1 === p ? c = !1 : 'object' === typeof p ? t.extend(p, n || {}) : p = n || {}, !1 === c) return o.stopDrag && o.stopDrag(this.canvas), d.stopDrag(), !1;for (let f = 0;f < this.connections.length;f++) this.connections[f].setHover(!1);this.addClass('endpointDrag'), o.setConnectionBeingDragged(!0), l && !this.isFull() && this.isSource && (l = null), o.updateOffset({ elId: this.elementId });const g = this._jsPlumb.instance.getOffset(this.canvas); const m = this.canvas; const v = this._jsPlumb.instance.getSize(this.canvas);!(function (t, e, n, i) {
              const o = e.createElement('div', { position: 'absolute' });e.appendElement(o);const s = e.getId(o);e.setPosition(o, n), o.style.width = `${i[0]}px`, o.style.height = `${i[1]}px`, e.manage(s, o, !0), t.id = s, t.element = o
            }(a, o, g, v)), o.setAttributes(this.canvas, { dragId: a.id, elId: this.elementId });let y = this.dragProxy || this.endpoint;if (null == this.dragProxy && null != this.connectionType) {
              const b = this._jsPlumb.instance.deriveEndpointAndAnchorSpec(this.connectionType);b.endpoints[1] && (y = b.endpoints[1])
            } const P = this._jsPlumb.instance.makeAnchor('Center');P.isFloating = !0, this._jsPlumb.floatingEndpoint = (function (e, n, i, o, s, r, a, l) {
              return a({ paintStyle: e, endpoint: i, anchor: new t.FloatingAnchor({ reference: n, referenceCanvas: o, jsPlumbInstance: r }), source: s, scope: l })
            }(this.getPaintStyle(), P, y, this.canvas, a.element, o, r, this.scope));const x = this._jsPlumb.floatingEndpoint.anchor;if (null == l) this.setHover(!1, !1), (l = s({ sourceEndpoint: this, targetEndpoint: this._jsPlumb.floatingEndpoint, source: this.element, target: a.element, anchors: [this.anchor, this._jsPlumb.floatingEndpoint.anchor], paintStyle: i.connectorStyle, hoverPaintStyle: i.connectorHoverStyle, connector: i.connector, overlays: i.connectorOverlays, type: this.connectionType, cssClass: this.connectorClass, hoverClass: this.connectorHoverClass, scope: i.scope, data: p })).pending = !0, l.addClass(o.draggingClass), this._jsPlumb.floatingEndpoint.addClass(o.draggingClass), this._jsPlumb.floatingEndpoint.anchor = x, o.fire('connectionDrag', l), o.router.newConnection(l);else {
              u = !0, l.setHover(!1);const C = l.endpoints[0].id === this.id ? 0 : 1;this.detachFromConnection(l, null, !0);const _ = o.getDragScope(m);o.setAttribute(this.canvas, 'originalScope', _), o.fire('connectionDrag', l), 0 === C ? (h = [l.source, l.sourceId, m, _], o.router.sourceOrTargetChanged(l.endpoints[C].elementId, a.id, l, a.element, 0)) : (h = [l.target, l.targetId, m, _], o.router.sourceOrTargetChanged(l.endpoints[C].elementId, a.id, l, a.element, 1)), l.suspendedEndpoint = l.endpoints[C], l.suspendedElement = l.endpoints[C].getElement(), l.suspendedElementId = l.endpoints[C].elementId, l.suspendedElementType = 0 === C ? 'source' : 'target', l.suspendedEndpoint.setHover(!1), this._jsPlumb.floatingEndpoint.referenceEndpoint = l.suspendedEndpoint, l.endpoints[C] = this._jsPlumb.floatingEndpoint, l.addClass(o.draggingClass), this._jsPlumb.floatingEndpoint.addClass(o.draggingClass)
            }o.registerFloatingConnection(a, l, this._jsPlumb.floatingEndpoint), o.currentlyDragging = !0
          }.bind(this); const b = function () {
            if (o.setConnectionBeingDragged(!1), l && null != l.endpoints) {
              const t = o.getDropEvent(arguments); const e = o.getFloatingAnchorIndex(l);if (l.endpoints[0 === e ? 1 : 0].anchor.locked = !1, l.removeClass(o.draggingClass), this._jsPlumb && (l.deleteConnectionNow || l.endpoints[e] === this._jsPlumb.floatingEndpoint) && u && l.suspendedEndpoint) {
                0 === e ? (l.floatingElement = l.source, l.floatingId = l.sourceId, l.floatingEndpoint = l.endpoints[0], l.floatingIndex = 0, l.source = h[0], l.sourceId = h[1]) : (l.floatingElement = l.target, l.floatingId = l.targetId, l.floatingEndpoint = l.endpoints[1], l.floatingIndex = 1, l.target = h[0], l.targetId = h[1]);const n = this._jsPlumb.floatingEndpoint;o.setDragScope(h[2], h[3]), l.endpoints[e] = l.suspendedEndpoint, l.isReattach() || l._forceReattach || l._forceDetach || !o.deleteConnection(l, { originalEvent: t }) ? (l.setHover(!1), l._forceDetach = null, l._forceReattach = null, this._jsPlumb.floatingEndpoint.detachFromConnection(l), l.suspendedEndpoint.addConnection(l), 1 === e ? o.router.sourceOrTargetChanged(l.floatingId, l.targetId, l, l.target, e) : o.router.sourceOrTargetChanged(l.floatingId, l.sourceId, l, l.source, e), o.repaint(h[1])) : o.deleteObject({ endpoint: n })
              } this.deleteAfterDragStop ? o.deleteObject({ endpoint: this }) : this._jsPlumb && this.paint({ recalc: !1 }), o.fire('connectionDragStop', l, t), l.pending && o.fire('connectionAborted', l, t), o.currentlyDragging = !1, l.suspendedElement = null, l.suspendedEndpoint = null, l = null
            }a && a.element && o.remove(a.element, !1, !1), this._jsPlumb && (this.canvas.style.visibility = 'visible', this.anchor.locked = !1, this._jsPlumb.floatingEndpoint = null)
          }.bind(this);(p = t.extend({}, p)).scope = this.scope || p.scope, p[v] = e.wrap(p[v], (t) => {
            n = t.e.payload || {}
          }, !1), p[f] = e.wrap(p[f], y, !1), p[m] = e.wrap(p[m], d.drag), p[g] = e.wrap(p[g], b), p.multipleDrop = !1, p.canDrag = function () {
            return this.isSource || this.isTemporarySource || this.connections.length > 0 && !1 !== this.connectionsDetachable
          }.bind(this), o.initDraggable(this.canvas, p, 'internal'), this.canvas._jsPlumbRelatedElement = this.element, c = !0
        }
      };const h = i.endpoint || this._jsPlumb.instance.Defaults.Endpoint || t.Defaults.Endpoint;this.setEndpoint(h, !0);const d = i.anchor ? i.anchor : i.anchors ? i.anchors : o.Defaults.Anchor || 'Top';this.setAnchor(d, !0);const p = ['default', i.type || ''].join(' ');this.addType(p, i.data, !0), this.canvas = this.endpoint.canvas, this.canvas._jsPlumb = this, this.initDraggable();const f = function (n, s, r, a) {
        if (t.isDropSupported(this.element)) {
          let l = i.dropOptions || o.Defaults.DropOptions || t.Defaults.DropOptions;(l = t.extend({}, l)).scope = l.scope || this.scope;const u = t.dragEvents.drop; const c = t.dragEvents.over; const h = t.dragEvents.out; const d = this; const p = o.EndpointDropHandler({ getEndpoint () {
            return d
          }, jsPlumb: o, enabled () {
            return null == r || r.isEnabled()
          }, isFull () {
            return r.isFull()
          }, element: this.element, elementId: this.elementId, isSource: this.isSource, isTarget: this.isTarget, addClass (t) {
            d.addClass(t)
          }, removeClass (t) {
            d.removeClass(t)
          }, isDropAllowed () {
            return d.isDropAllowed.apply(d, arguments)
          }, reference: a, isRedrop (t, e) {
            return t.suspendedEndpoint && e.reference && t.suspendedEndpoint.id === e.reference.id
          } });l[u] = e.wrap(l[u], p, !0), l[c] = e.wrap(l[c], function () {
            const e = t.getDragObject(arguments); const n = o.getAttribute(t.getElement(e), 'dragId'); const i = o.getFloatingConnectionFor(n);if (null != i) {
              const s = o.getFloatingAnchorIndex(i);if (this.isTarget && 0 !== s || i.suspendedEndpoint && this.referenceEndpoint && this.referenceEndpoint.id === i.suspendedEndpoint.id) {
                const r = o.checkCondition('checkDropAllowed', { sourceEndpoint: i.endpoints[s], targetEndpoint: this, connection: i });this[`${r ? 'add' : 'remove'}Class`](o.endpointDropAllowedClass), this[`${r ? 'remove' : 'add'}Class`](o.endpointDropForbiddenClass), i.endpoints[s].anchor.over(this.anchor, this)
              }
            }
          }.bind(this)), l[h] = e.wrap(l[h], function () {
            const e = t.getDragObject(arguments); const n = null == e ? null : o.getAttribute(t.getElement(e), 'dragId'); const i = n ? o.getFloatingConnectionFor(n) : null;if (null != i) {
              const s = o.getFloatingAnchorIndex(i);(this.isTarget && 0 !== s || i.suspendedEndpoint && this.referenceEndpoint && this.referenceEndpoint.id === i.suspendedEndpoint.id) && (this.removeClass(o.endpointDropAllowedClass), this.removeClass(o.endpointDropForbiddenClass), i.endpoints[s].anchor.out())
            }
          }.bind(this)), o.initDroppable(n, l, 'internal', s)
        }
      }.bind(this);return this.anchor.isFloating || f(this.canvas, !(i._transient || this.anchor.isFloating), this, i.reference), this
    }, e.extend(t.Endpoint, t.OverlayCapableJsPlumbUIComponent, { setVisible (t, e, n) {
      if (this._jsPlumb.visible = t, this.canvas && (this.canvas.style.display = t ? 'block' : 'none'), this[t ? 'showOverlays' : 'hideOverlays'](), !e) for (let i = 0;i < this.connections.length;i++) if (this.connections[i].setVisible(t), !n) {
        const o = this === this.connections[i].endpoints[0] ? 1 : 0;1 === this.connections[i].endpoints[o].connections.length && this.connections[i].endpoints[o].setVisible(t, !0, !0)
      }
    }, getAttachedElements () {
      return this.connections
    }, applyType (e, i) {
      this.setPaintStyle(e.endpointStyle || e.paintStyle, i), this.setHoverPaintStyle(e.endpointHoverStyle || e.hoverPaintStyle, i), null != e.maxConnections && (this._jsPlumb.maxConnections = e.maxConnections), e.scope && (this.scope = e.scope), t.extend(this, e, n), null != e.cssClass && this.canvas && this._jsPlumb.instance.addClass(this.canvas, e.cssClass), t.OverlayCapableJsPlumbUIComponent.applyType(this, e)
    }, isEnabled () {
      return this._jsPlumb.enabled
    }, setEnabled (t) {
      this._jsPlumb.enabled = t
    }, cleanup () {
      const e = this._jsPlumb.instance.endpointAnchorClassPrefix + (this._jsPlumb.currentAnchorClass ? `-${this._jsPlumb.currentAnchorClass}` : '');t.removeClass(this.element, e), this.anchor = null, this.endpoint.cleanup(!0), this.endpoint.destroy(), this.endpoint = null, this._jsPlumb.instance.destroyDraggable(this.canvas, 'internal'), this._jsPlumb.instance.destroyDroppable(this.canvas, 'internal')
    }, setHover (t) {
      this.endpoint && this._jsPlumb && !this._jsPlumb.instance.isConnectionBeingDragged() && this.endpoint.setHover(t)
    }, isFull () {
      return 0 === this._jsPlumb.maxConnections || !(this.isFloating() || this._jsPlumb.maxConnections < 0 || this.connections.length < this._jsPlumb.maxConnections)
    }, isFloating () {
      return null != this.anchor && this.anchor.isFloating
    }, isConnectedTo (t) {
      let e = !1;if (t) for (let n = 0;n < this.connections.length;n++) if (this.connections[n].endpoints[1] === t || this.connections[n].endpoints[0] === t) {
        e = !0;break
      } return e
    }, getConnectionCost () {
      return this._jsPlumb.connectionCost
    }, setConnectionCost (t) {
      this._jsPlumb.connectionCost = t
    }, areConnectionsDirected () {
      return this._jsPlumb.connectionsDirected
    }, setConnectionsDirected (t) {
      this._jsPlumb.connectionsDirected = t
    }, setElementId (t) {
      this.elementId = t, this.anchor.elementId = t
    }, setReferenceElement (e) {
      this.element = t.getElement(e)
    }, setDragAllowedWhenFull (t) {
      this.dragAllowedWhenFull = t
    }, equals (t) {
      return this.anchor.equals(t.anchor)
    }, getUuid () {
      return this._jsPlumb.uuid
    }, computeAnchor (t) {
      return this.anchor.compute(t)
    } }), this.jsPlumbInstance.prototype.EndpointDropHandler = function (t) {
      return function (n) {
        const i = t.jsPlumb;t.removeClass(i.endpointDropAllowedClass), t.removeClass(i.endpointDropForbiddenClass);const o = i.getDropEvent(arguments); const s = i.getDragObject(arguments); const r = i.getAttribute(s, 'dragId'); const a = (i.getAttribute(s, 'elId'), i.getAttribute(s, 'originalScope')); const l = i.getFloatingConnectionFor(r);if (null != l) {
          const u = null != l.suspendedEndpoint;if (!u || null != l.suspendedEndpoint._jsPlumb) {
            const c = t.getEndpoint(l);if (null != c) {
              if (t.isRedrop(l, t)) return l._forceReattach = !0, l.setHover(!1), void(t.maybeCleanup && t.maybeCleanup(c));const h = i.getFloatingAnchorIndex(l);if (0 === h && !t.isSource || 1 === h && !t.isTarget)t.maybeCleanup && t.maybeCleanup(c);else {
                t.onDrop && t.onDrop(l), a && i.setDragScope(s, a);const d = t.isFull(n);if (d && c.fire('maxConnections', { endpoint: this, connection: l, maxConnections: c._jsPlumb.maxConnections }, o), !d && t.enabled()) {
                  let p = !0;0 === h ? (l.floatingElement = l.source, l.floatingId = l.sourceId, l.floatingEndpoint = l.endpoints[0], l.floatingIndex = 0, l.source = t.element, l.sourceId = i.getId(t.element)) : (l.floatingElement = l.target, l.floatingId = l.targetId, l.floatingEndpoint = l.endpoints[1], l.floatingIndex = 1, l.target = t.element, l.targetId = i.getId(t.element)), u && l.suspendedEndpoint.id !== c.id && (l.isDetachAllowed(l) && l.endpoints[h].isDetachAllowed(l) && l.suspendedEndpoint.isDetachAllowed(l) && i.checkCondition('beforeDetach', l) || (p = !1));const f = function (n) {
                    l.endpoints[h].detachFromConnection(l), l.suspendedEndpoint && l.suspendedEndpoint.detachFromConnection(l), l.endpoints[h] = c, c.addConnection(l);const s = c.getParameters();for (const r in s)l.setParameter(r, s[r]);if (u) {
                      const a = l.suspendedEndpoint.elementId;i.fireMoveEvent({ index: h, originalSourceId: 0 === h ? a : l.sourceId, newSourceId: 0 === h ? c.elementId : l.sourceId, originalTargetId: 1 === h ? a : l.targetId, newTargetId: 1 === h ? c.elementId : l.targetId, originalSourceEndpoint: 0 === h ? l.suspendedEndpoint : l.endpoints[0], newSourceEndpoint: 0 === h ? c : l.endpoints[0], originalTargetEndpoint: 1 === h ? l.suspendedEndpoint : l.endpoints[1], newTargetEndpoint: 1 === h ? c : l.endpoints[1], connection: l }, o)
                    } else s.draggable && i.initDraggable(this.element, t.dragOptions, 'internal', i);(1 === h ? i.router.sourceOrTargetChanged(l.floatingId, l.targetId, l, l.target, 1) : i.router.sourceOrTargetChanged(l.floatingId, l.sourceId, l, l.source, 0), l.endpoints[0].finalEndpoint) && (l.endpoints[0].detachFromConnection(l), l.endpoints[0] = l.endpoints[0].finalEndpoint, l.endpoints[0].addConnection(l));e.isObject(n) && l.mergeData(n), i.finaliseConnection(l, null, o, !1), l.setHover(!1), i.revalidate(l.endpoints[0].element)
                  }.bind(this);if (p = p && t.isDropAllowed(l.sourceId, l.targetId, l.scope, l, c)) return f(p), !0;l.suspendedEndpoint && (l.endpoints[h] = l.suspendedEndpoint, l.setHover(!1), l._forceDetach = !0, 0 === h ? (l.source = l.suspendedEndpoint.element, l.sourceId = l.suspendedEndpoint.elementId) : (l.target = l.suspendedEndpoint.element, l.targetId = l.suspendedEndpoint.elementId), l.suspendedEndpoint.addConnection(l), 1 === h ? i.router.sourceOrTargetChanged(l.floatingId, l.targetId, l, l.target, 1) : i.router.sourceOrTargetChanged(l.floatingId, l.sourceId, l, l.source, 0), i.repaint(l.sourceId), l._forceDetach = !1)
                }t.maybeCleanup && t.maybeCleanup(c), i.currentlyDragging = !1
              }
            }
          }
        }
      }
    }
  }.call('undefined' !== typeof window ? window : s), function () {
    const t = this; const e = t.jsPlumb; const n = t.jsPlumbUtil; const i = function (t, i, o, s, r) {
      if (e.Connectors[i] = e.Connectors[i] || {}, null == e.Connectors[i][o]) {
        if (null == e.Connectors[o]) {
          if (t.Defaults.DoNotThrowErrors) return null;throw new TypeError(`jsPlumb: unknown connector type '${o}'`)
        }e.Connectors[i][o] = function () {
          e.Connectors[o].apply(this, arguments), e.ConnectorRenderers[i].apply(this, arguments)
        }, n.extend(e.Connectors[i][o], [e.Connectors[o], e.ConnectorRenderers[i]])
      } return new e.Connectors[i][o](s, r)
    }; const o = function (t, e, n) {
      return t ? n.makeAnchor(t, e, n) : null
    }; const s = function (t, e, i, o) {
      null != e && (e._jsPlumbConnections = e._jsPlumbConnections || {}, o ? delete e._jsPlumbConnections[t.id] : e._jsPlumbConnections[t.id] = !0, n.isEmpty(e._jsPlumbConnections) ? i.removeClass(e, i.connectedClass) : i.addClass(e, i.connectedClass))
    };e.Connection = function (t) {
      const i = t.newEndpoint;this.id = t.id, this.connector = null, this.idPrefix = '_jsplumb_c_', this.defaultLabelLocation = .5, this.defaultOverlayKeys = ['Overlays', 'ConnectionOverlays'], this.previousConnection = t.previousConnection, this.source = e.getElement(t.source), this.target = e.getElement(t.target), e.OverlayCapableJsPlumbUIComponent.apply(this, arguments), t.sourceEndpoint ? (this.source = t.sourceEndpoint.getElement(), this.sourceId = t.sourceEndpoint.elementId) : this.sourceId = this._jsPlumb.instance.getId(this.source), t.targetEndpoint ? (this.target = t.targetEndpoint.getElement(), this.targetId = t.targetEndpoint.elementId) : this.targetId = this._jsPlumb.instance.getId(this.target), this.scope = t.scope, this.endpoints = [], this.endpointStyles = [];const o = this._jsPlumb.instance;o.manage(this.sourceId, this.source), o.manage(this.targetId, this.target), this._jsPlumb.visible = !0, this._jsPlumb.params = { cssClass: t.cssClass, container: t.container, 'pointer-events': t['pointer-events'], editorParams: t.editorParams, overlays: t.overlays }, this._jsPlumb.lastPaintedAt = null, this.bind('mouseover', () => {
        this.setHover(!0)
      }), this.bind('mouseout', () => {
        this.setHover(!1)
      }), this.makeEndpoint = function (e, n, s, r, a) {
        return s = s || this._jsPlumb.instance.getId(n), this.prepareEndpoint(o, i, this, r, e ? 0 : 1, t, n, s, a)
      }, t.type && (t.endpoints = t.endpoints || this._jsPlumb.instance.deriveEndpointAndAnchorSpec(t.type).endpoints);const s = this.makeEndpoint(!0, this.source, this.sourceId, t.sourceEndpoint); const r = this.makeEndpoint(!1, this.target, this.targetId, t.targetEndpoint);s && n.addToList(t.endpointsByElement, this.sourceId, s), r && n.addToList(t.endpointsByElement, this.targetId, r), this.scope || (this.scope = this.endpoints[0].scope), null != t.deleteEndpointsOnEmpty && (this.endpoints[0].setDeleteOnEmpty(t.deleteEndpointsOnEmpty), this.endpoints[1].setDeleteOnEmpty(t.deleteEndpointsOnEmpty));let a = o.Defaults.ConnectionsDetachable;!1 === t.detachable && (a = !1), !1 === this.endpoints[0].connectionsDetachable && (a = !1), !1 === this.endpoints[1].connectionsDetachable && (a = !1);const l = t.reattach || this.endpoints[0].reattachConnections || this.endpoints[1].reattachConnections || o.Defaults.ReattachConnections;this.appendToDefaultType({ detachable: a, reattach: l, paintStyle: this.endpoints[0].connectorStyle || this.endpoints[1].connectorStyle || t.paintStyle || o.Defaults.PaintStyle || e.Defaults.PaintStyle, hoverPaintStyle: this.endpoints[0].connectorHoverStyle || this.endpoints[1].connectorHoverStyle || t.hoverPaintStyle || o.Defaults.HoverPaintStyle || e.Defaults.HoverPaintStyle });const u = o.getSuspendedAt();if (!o.isSuspendDrawing()) {
        const c = o.getCachedData(this.sourceId); const h = c.o; const d = c.s; const p = o.getCachedData(this.targetId); const f = p.o; const g = p.s; const m = u || jsPlumbUtil.uuid(); let v = this.endpoints[0].anchor.compute({ xy: [h.left, h.top], wh: d, element: this.endpoints[0], elementId: this.endpoints[0].elementId, txy: [f.left, f.top], twh: g, tElement: this.endpoints[1], timestamp: m, rotation: o.getRotation(this.endpoints[0].elementId) });this.endpoints[0].paint({ anchorLoc: v, timestamp: m }), v = this.endpoints[1].anchor.compute({ xy: [f.left, f.top], wh: g, element: this.endpoints[1], elementId: this.endpoints[1].elementId, txy: [h.left, h.top], twh: d, tElement: this.endpoints[0], timestamp: m, rotation: o.getRotation(this.endpoints[1].elementId) }), this.endpoints[1].paint({ anchorLoc: v, timestamp: m })
      } this.getTypeDescriptor = function () {
        return 'connection'
      }, this.getAttachedElements = function () {
        return this.endpoints
      }, this.isDetachable = function (t) {
        return !1 !== this._jsPlumb.detachable && (null != t ? !0 === t.connectionsDetachable : !0 === this._jsPlumb.detachable)
      }, this.setDetachable = function (t) {
        this._jsPlumb.detachable = !0 === t
      }, this.isReattach = function () {
        return !0 === this._jsPlumb.reattach || !0 === this.endpoints[0].reattachConnections || !0 === this.endpoints[1].reattachConnections
      }, this.setReattach = function (t) {
        this._jsPlumb.reattach = !0 === t
      }, this._jsPlumb.cost = t.cost || this.endpoints[0].getConnectionCost(), this._jsPlumb.directed = t.directed, null == t.directed && (this._jsPlumb.directed = this.endpoints[0].areConnectionsDirected());const y = e.extend({}, this.endpoints[1].getParameters());e.extend(y, this.endpoints[0].getParameters()), e.extend(y, this.getParameters()), this.setParameters(y), this.setConnector(this.endpoints[0].connector || this.endpoints[1].connector || t.connector || o.Defaults.Connector || e.Defaults.Connector, !0);let b = null != t.data && n.isObject(t.data) ? t.data : {};this.getData = function () {
        return b
      }, this.setData = function (t) {
        b = t || {}
      }, this.mergeData = function (t) {
        b = e.extend(b, t)
      };const P = ['default', this.endpoints[0].connectionType, this.endpoints[1].connectionType, t.type].join(' ');/[^\s]/.test(P) && this.addType(P, t.data, !0), this.updateConnectedClass()
    }, n.extend(e.Connection, e.OverlayCapableJsPlumbUIComponent, { applyType (t, n, i) {
      let o = null;null != t.connector && (null == (o = this.getCachedTypeItem('connector', i.connector)) && (o = this.prepareConnector(t.connector, i.connector), this.cacheTypeItem('connector', o, i.connector)), this.setPreparedConnector(o)), null != t.detachable && this.setDetachable(t.detachable), null != t.reattach && this.setReattach(t.reattach), t.scope && (this.scope = t.scope), null != t.cssClass && this.canvas && this._jsPlumb.instance.addClass(this.canvas, t.cssClass);let s = null;t.anchor ? null == (s = this.getCachedTypeItem('anchors', i.anchor)) && (s = [this._jsPlumb.instance.makeAnchor(t.anchor), this._jsPlumb.instance.makeAnchor(t.anchor)], this.cacheTypeItem('anchors', s, i.anchor)) : t.anchors && null == (s = this.getCachedTypeItem('anchors', i.anchors)) && (s = [this._jsPlumb.instance.makeAnchor(t.anchors[0]), this._jsPlumb.instance.makeAnchor(t.anchors[1])], this.cacheTypeItem('anchors', s, i.anchors)), null != s && (this.endpoints[0].anchor = s[0], this.endpoints[1].anchor = s[1], this.endpoints[1].anchor.isDynamic && this._jsPlumb.instance.repaint(this.endpoints[1].elementId)), e.OverlayCapableJsPlumbUIComponent.applyType(this, t)
    }, addClass (t, e) {
      e && (this.endpoints[0].addClass(t), this.endpoints[1].addClass(t), this.suspendedEndpoint && this.suspendedEndpoint.addClass(t)), this.connector && this.connector.addClass(t)
    }, removeClass (t, e) {
      e && (this.endpoints[0].removeClass(t), this.endpoints[1].removeClass(t), this.suspendedEndpoint && this.suspendedEndpoint.removeClass(t)), this.connector && this.connector.removeClass(t)
    }, isVisible () {
      return this._jsPlumb.visible
    }, setVisible (t) {
      this._jsPlumb.visible = t, this.connector && this.connector.setVisible(t), this.repaint()
    }, cleanup () {
      this.updateConnectedClass(!0), this.endpoints = null, this.source = null, this.target = null, null != this.connector && (this.connector.cleanup(!0), this.connector.destroy(!0)), this.connector = null
    }, updateConnectedClass (t) {
      this._jsPlumb && (s(this, this.source, this._jsPlumb.instance, t), s(this, this.target, this._jsPlumb.instance, t))
    }, setHover (e) {
      this.connector && this._jsPlumb && !this._jsPlumb.instance.isConnectionBeingDragged() && (this.connector.setHover(e), t.jsPlumb[e ? 'addClass' : 'removeClass'](this.source, this._jsPlumb.instance.hoverSourceClass), t.jsPlumb[e ? 'addClass' : 'removeClass'](this.target, this._jsPlumb.instance.hoverTargetClass))
    }, getUuids () {
      return [this.endpoints[0].getUuid(), this.endpoints[1].getUuid()]
    }, getCost () {
      return this._jsPlumb ? this._jsPlumb.cost : -1 / 0
    }, setCost (t) {
      this._jsPlumb.cost = t
    }, isDirected () {
      return this._jsPlumb.directed
    }, getConnector () {
      return this.connector
    }, prepareConnector (t, e) {
      let o; const s = { _jsPlumb: this._jsPlumb.instance, cssClass: this._jsPlumb.params.cssClass, container: this._jsPlumb.params.container, 'pointer-events': this._jsPlumb.params['pointer-events'] }; const r = this._jsPlumb.instance.getRenderMode();return n.isString(t) ? o = i(this._jsPlumb.instance, r, t, s, this) : n.isArray(t) && (o = 1 === t.length ? i(this._jsPlumb.instance, r, t[0], s, this) : i(this._jsPlumb.instance, r, t[0], n.merge(t[1], s), this)), null != e && (o.typeId = e), o
    }, setPreparedConnector (t, e, n, i) {
      if (this.connector !== t) {
        let o; let s = '';if (null != this.connector && (s = (o = this.connector).getClass(), this.connector.cleanup(), this.connector.destroy()), this.connector = t, i && this.cacheTypeItem('connector', t, i), this.canvas = this.connector.canvas, this.bgCanvas = this.connector.bgCanvas, this.connector.reattach(this._jsPlumb.instance), this.addClass(s), this.canvas && (this.canvas._jsPlumb = this), this.bgCanvas && (this.bgCanvas._jsPlumb = this), null != o) for (let r = this.getOverlays(), a = 0;a < r.length;a++)r[a].transfer && r[a].transfer(this.connector);n || this.setListenerComponent(this.connector), e || this.repaint()
      }
    }, setConnector (t, e, n, i) {
      const o = this.prepareConnector(t, i);this.setPreparedConnector(o, e, n, i)
    }, paint (t) {
      if (!this._jsPlumb.instance.isSuspendDrawing() && this._jsPlumb.visible) {
        const e = (t = t || {}).timestamp; const n = this.targetId; const i = this.sourceId;if (null == e || e !== this._jsPlumb.lastPaintedAt) {
          const { o } = this._jsPlumb.instance.updateOffset({ elId: i }); const s = this._jsPlumb.instance.updateOffset({ elId: n }).o; const r = this.endpoints[0]; const a = this.endpoints[1]; const l = r.anchor.getCurrentLocation({ xy: [o.left, o.top], wh: [o.width, o.height], element: r, timestamp: e, rotation: this._jsPlumb.instance.getRotation(this.sourceId) }); const u = a.anchor.getCurrentLocation({ xy: [s.left, s.top], wh: [s.width, s.height], element: a, timestamp: e, rotation: this._jsPlumb.instance.getRotation(this.targetId) });this.connector.resetBounds(), this.connector.compute({ sourcePos: l, targetPos: u, sourceOrientation: r.anchor.getOrientation(r), targetOrientation: a.anchor.getOrientation(a), sourceEndpoint: this.endpoints[0], targetEndpoint: this.endpoints[1], 'stroke-width': this._jsPlumb.paintStyleInUse.strokeWidth, sourceInfo: o, targetInfo: s });const c = { minX: 1 / 0, minY: 1 / 0, maxX: -1 / 0, maxY: -1 / 0 };for (const h in this._jsPlumb.overlays) if (this._jsPlumb.overlays.hasOwnProperty(h)) {
            const d = this._jsPlumb.overlays[h];d.isVisible() && (this._jsPlumb.overlayPlacements[h] = d.draw(this.connector, this._jsPlumb.paintStyleInUse, this.getAbsoluteOverlayPosition(d)), c.minX = Math.min(c.minX, this._jsPlumb.overlayPlacements[h].minX), c.maxX = Math.max(c.maxX, this._jsPlumb.overlayPlacements[h].maxX), c.minY = Math.min(c.minY, this._jsPlumb.overlayPlacements[h].minY), c.maxY = Math.max(c.maxY, this._jsPlumb.overlayPlacements[h].maxY))
          } const p = parseFloat(this._jsPlumb.paintStyleInUse.strokeWidth || 1) / 2; const f = parseFloat(this._jsPlumb.paintStyleInUse.strokeWidth || 0); const g = { xmin: Math.min(this.connector.bounds.minX - (p + f), c.minX), ymin: Math.min(this.connector.bounds.minY - (p + f), c.minY), xmax: Math.max(this.connector.bounds.maxX + (p + f), c.maxX), ymax: Math.max(this.connector.bounds.maxY + (p + f), c.maxY) };for (const m in this.connector.paintExtents = g, this.connector.paint(this._jsPlumb.paintStyleInUse, null, g), this._jsPlumb.overlays) if (this._jsPlumb.overlays.hasOwnProperty(m)) {
            const v = this._jsPlumb.overlays[m];v.isVisible() && v.paint(this._jsPlumb.overlayPlacements[m], g)
          }
        } this._jsPlumb.lastPaintedAt = e
      }
    }, repaint (t) {
      const e = jsPlumb.extend(t || {}, {});e.elId = this.sourceId, this.paint(e)
    }, prepareEndpoint (t, n, i, s, r, a, l, u, c) {
      let h;if (s)i.endpoints[r] = s, s.addConnection(i);else {
        a.endpoints || (a.endpoints = [null, null]);const d = c || a.endpoints[r] || a.endpoint || t.Defaults.Endpoints[r] || e.Defaults.Endpoints[r] || t.Defaults.Endpoint || e.Defaults.Endpoint;a.endpointStyles || (a.endpointStyles = [null, null]), a.endpointHoverStyles || (a.endpointHoverStyles = [null, null]);const p = a.endpointStyles[r] || a.endpointStyle || t.Defaults.EndpointStyles[r] || e.Defaults.EndpointStyles[r] || t.Defaults.EndpointStyle || e.Defaults.EndpointStyle;null == p.fill && null != a.paintStyle && (p.fill = a.paintStyle.stroke), null == p.outlineStroke && null != a.paintStyle && (p.outlineStroke = a.paintStyle.outlineStroke), null == p.outlineWidth && null != a.paintStyle && (p.outlineWidth = a.paintStyle.outlineWidth);let f = a.endpointHoverStyles[r] || a.endpointHoverStyle || t.Defaults.EndpointHoverStyles[r] || e.Defaults.EndpointHoverStyles[r] || t.Defaults.EndpointHoverStyle || e.Defaults.EndpointHoverStyle;null != a.hoverPaintStyle && (null == f && (f = {}), null == f.fill && (f.fill = a.hoverPaintStyle.stroke));const g = a.anchors ? a.anchors[r] : a.anchor ? a.anchor : o(t.Defaults.Anchors[r], u, t) || o(e.Defaults.Anchors[r], u, t) || o(t.Defaults.Anchor, u, t) || o(e.Defaults.Anchor, u, t);h = n({ paintStyle: p, hoverPaintStyle: f, endpoint: d, connections: [i], uuid: a.uuids ? a.uuids[r] : null, anchor: g, source: l, scope: a.scope, reattach: a.reattach || t.Defaults.ReattachConnections, detachable: a.detachable || t.Defaults.ConnectionsDetachable }), null == s && h.setDeleteOnEmpty(!0), i.endpoints[r] = h, !1 === a.drawEndpoints && h.setVisible(!1, !0, !0)
      } return h
    }, replaceEndpoint (t, e) {
      const n = this.endpoints[t]; const i = n.elementId; const o = this._jsPlumb.instance.getEndpoints(i); const s = o.indexOf(n); const r = this.makeEndpoint(0 === t, n.element, i, null, e);this.endpoints[t] = r, o.splice(s, 1, r), this._jsPlumb.instance.deleteObject({ endpoint: n, deleteAttachedObjects: !1 }), this._jsPlumb.instance.fire('endpointReplaced', { previous: n, current: r }), this._jsPlumb.instance.router.sourceOrTargetChanged(this.endpoints[1].elementId, this.endpoints[1].elementId, this, this.endpoints[1].element, 1)
    } })
  }.call('undefined' !== typeof window ? window : s), function () {
    const t = this.jsPlumbUtil; const e = this.jsPlumb;e.AnchorManager = function (n) {
      let i = {}; const o = {}; const s = {}; let r = {}; const a = this; let l = {}; const u = n.jsPlumbInstance; const c = {}; const h = function (t, e) {
        return e[0][0] - t[0][0]
      }; const d = function (t, e) {
        return (t[0][0] < 0 ? -Math.PI - t[0][0] : Math.PI - t[0][0]) - (e[0][0] < 0 ? -Math.PI - e[0][0] : Math.PI - e[0][0])
      }; const p = { top: d, right: h, bottom: h, left: d }; const f = function (t, e) {
        const n = u.getCachedData(t); const i = n.s; const r = n.o; const a = function (e, n, i, r, a, l, c) {
          if (r.length > 0) for (let h = (function (t, e, n, i, o, s, r, a) {
              for (var l = [], u = e[o ? 0 : 1] / (i.length + 1), c = 0;c < i.length;c++) {
                let h = (c + 1) * u; const d = s * e[o ? 1 : 0];r && (h = e[o ? 0 : 1] - h);const p = o ? h : d; let f = n.left + p; const g = p / e[0]; const m = o ? d : h; let v = n.top + m; const y = m / e[1];if (0 !== a) {
                  const b = jsPlumbUtil.rotatePoint([f, v], [n.centerx, n.centery], a);f = b[0], v = b[1]
                }l.push([f, v, g, y, i[c][1], i[c][2]])
              } return l
            }(0, n, i, (y = p[e], r.sort(y)), a, l, 'right' === e || 'top' === e, u.getRotation(t))), d = function (t, e) {
              o[t.id] = [e[0], e[1], e[2], e[3]], s[t.id] = c
            }, f = 0;f < h.length;f++) {
            const g = h[f][4]; const m = g.endpoints[0].elementId === t; const v = g.endpoints[1].elementId === t;m && d(g.endpoints[0], h[f]), v && d(g.endpoints[1], h[f])
          } let y
        };a('bottom', i, r, e.bottom, !0, 1, [0, 1]), a('top', i, r, e.top, !0, 0, [0, -1]), a('left', i, r, e.left, !1, 0, [-1, 0]), a('right', i, r, e.right, !1, 1, [1, 0])
      };this.reset = function () {
        i = {}, r = {}, l = {}
      }, this.addFloatingConnection = function (t, e) {
        c[t] = e
      }, this.newConnection = function (n) {
        const i = n.sourceId; const o = n.targetId; const s = n.endpoints; let a = !0; const l = function (l, u, c, h, d) {
          i === o && c.isContinuous && (n._jsPlumb.instance.removeElement(s[1].canvas), a = !1), t.addToList(r, h, [d, u, c.constructor === e.DynamicAnchor])
        };l(0, s[0], s[0].anchor, o, n), a && l(0, s[1], s[1].anchor, i, n)
      };const g = function (e) {
        !(function (e, n) {
          if (e) {
            const i = function (t) {
              return t[4] === n
            };t.removeWithFunction(e.top, i), t.removeWithFunction(e.left, i), t.removeWithFunction(e.bottom, i), t.removeWithFunction(e.right, i)
          }
        }(l[e.elementId], e.id))
      };this.connectionDetached = function (e, n) {
        const i = e.connection || e; const o = e.sourceId; const s = e.targetId; const l = i.endpoints; const u = function (e, n, i, o, s) {
          t.removeWithFunction(r[o], (t) => t[0].id === s.id)
        };u(0, l[1], l[1].anchor, o, i), u(0, l[0], l[0].anchor, s, i), i.floatingId && (u(i.floatingIndex, i.floatingEndpoint, i.floatingEndpoint.anchor, i.floatingId, i), g(i.floatingEndpoint)), g(i.endpoints[0]), g(i.endpoints[1]), n || (a.redraw(i.sourceId), i.targetId !== i.sourceId && a.redraw(i.targetId))
      }, this.addEndpoint = function (e, n) {
        t.addToList(i, n, e)
      }, this.changeId = function (t, e) {
        r[e] = r[t], i[e] = i[t], delete r[t], delete i[t]
      }, this.getConnectionsFor = function (t) {
        return r[t] || []
      }, this.getEndpointsFor = function (t) {
        return i[t] || []
      }, this.deleteEndpoint = function (e) {
        t.removeWithFunction(i[e.elementId], (t) => t.id === e.id), g(e)
      }, this.elementRemoved = function (t) {
        delete c[t], delete i[t], i[t] = []
      };const m = function (e, i, o, s, r, a, l, u, c, h, d, p) {
        let f; let g; let m = -1; const v = s.endpoints[l]; const y = v.id; const b = [1, 0][l]; const P = [[i, o], s, r, a, y]; const x = e[c]; const C = v._continuousAnchorEdge ? e[v._continuousAnchorEdge] : null;if (C) {
          const _ = t.findWithFunction(C, (t) => t[4] === y);if (-1 !== _) for (C.splice(_, 1), f = 0;f < C.length;f++)g = C[f][1], t.addWithFunction(d, g, (t) => t.id === g.id), t.addWithFunction(p, C[f][1].endpoints[l], (t) => t.id === g.endpoints[l].id), t.addWithFunction(p, C[f][1].endpoints[b], (t) => t.id === g.endpoints[b].id)
        } for (f = 0;f < x.length;f++)g = x[f][1], 1 === n.idx && x[f][3] === a && -1 === m && (m = f), t.addWithFunction(d, g, (t) => t.id === g.id), t.addWithFunction(p, x[f][1].endpoints[l], (t) => t.id === g.endpoints[l].id), t.addWithFunction(p, x[f][1].endpoints[b], (t) => t.id === g.endpoints[b].id);const j = u ? -1 !== m ? m : 0 : x.length;x.splice(j, 0, P), v._continuousAnchorEdge = c
      };this.sourceOrTargetChanged = function (n, i, o, s, a) {
        if (0 === a) {
          if (n !== i) {
            o.sourceId = i, o.source = s, t.removeWithFunction(r[n], (t) => t[0].id === o.id);const l = t.findWithFunction(r[o.targetId], (t) => t[0].id === o.id);l > -1 && (r[o.targetId][l][0] = o, r[o.targetId][l][1] = o.endpoints[0], r[o.targetId][l][2] = o.endpoints[0].anchor.constructor === e.DynamicAnchor), t.addToList(r, i, [o, o.endpoints[1], o.endpoints[1].anchor.constructor === e.DynamicAnchor]), o.endpoints[1].anchor.isContinuous && (o.source === o.target ? o._jsPlumb.instance.removeElement(o.endpoints[1].canvas) : null == o.endpoints[1].canvas.parentNode && o._jsPlumb.instance.appendElement(o.endpoints[1].canvas)), o.updateConnectedClass()
          }
        } else if (1 === a) {
          const u = o.endpoints[0].elementId;o.target = s, o.targetId = i;const c = t.findWithFunction(r[u], (t) => t[0].id === o.id); const h = t.findWithFunction(r[n], (t) => t[0].id === o.id);-1 !== c && (r[u][c][0] = o, r[u][c][1] = o.endpoints[1], r[u][c][2] = o.endpoints[1].anchor.constructor === e.DynamicAnchor), h > -1 && (r[n].splice(h, 1), t.addToList(r, i, [o, o.endpoints[0], o.endpoints[0].anchor.constructor === e.DynamicAnchor])), o.updateConnectedClass()
        }
      }, this.rehomeEndpoint = function (t, e, n) {
        const o = i[e] || []; const s = u.getId(n);if (s !== e) {
          const r = o.indexOf(t);if (r > -1) {
            const l = o.splice(r, 1)[0];a.add(l, s)
          }
        } for (let c = 0;c < t.connections.length;c++)t.connections[c].sourceId === e ? a.sourceOrTargetChanged(e, t.elementId, t.connections[c], t.element, 0) : t.connections[c].targetId === e && a.sourceOrTargetChanged(e, t.elementId, t.connections[c], t.element, 1)
      }, this.redraw = function (n, o, s, a, h, d) {
        const p = []; const g = []; const v = [];if (!u.isSuspendDrawing()) {
          const y = i[n] || []; const b = r[n] || [];s = s || jsPlumbUtil.uuid(), a = a || { left: 0, top: 0 }, o && (o = { left: o.left + a.left, top: o.top + a.top });for (var P = u.updateOffset({ elId: n, offset: o, recalc: !1, timestamp: s }), x = {}, C = 0;C < b.length;C++) {
            var _ = b[C][0]; var j = _.sourceId; var E = _.targetId; const S = _.endpoints[0].anchor.isContinuous; const w = _.endpoints[1].anchor.isContinuous;if (S || w) {
              const D = `${j}_${E}`; let A = x[D]; var I = _.sourceId === n ? 1 : 0; const k = u.getRotation(E); const O = u.getRotation(j);S && !l[j] && (l[j] = { top: [], right: [], bottom: [], left: [] }), w && !l[E] && (l[E] = { top: [], right: [], bottom: [], left: [] }), n !== E && u.updateOffset({ elId: E, timestamp: s }), n !== j && u.updateOffset({ elId: j, timestamp: s });const M = u.getCachedData(E); const T = u.getCachedData(j);E === j && (S || w) ? (m(l[j], -Math.PI / 2, 0, _, !1, E, 0, !1, 'top', 0, p, g), m(l[E], -Math.PI / 2, 0, _, !1, j, 1, !1, 'top', 0, p, g)) : (A || (A = this.calculateOrientation(j, E, T.o, M.o, _.endpoints[0].anchor, _.endpoints[1].anchor, _, O, k), x[D] = A), S && m(l[j], A.theta, 0, _, !1, E, 0, !1, A.a[0], 0, p, g), w && m(l[E], A.theta2, -1, _, !0, j, 1, !0, A.a[1], 0, p, g)), S && t.addWithFunction(v, j, (t) => t === j), w && t.addWithFunction(v, E, (t) => t === E), t.addWithFunction(p, _, (t) => t.id === _.id), (S && 0 === I || w && 1 === I) && t.addWithFunction(g, _.endpoints[I], (t) => t.id === _.endpoints[I].id)
            }
          } for (C = 0;C < y.length;C++)0 === y[C].connections.length && y[C].anchor.isContinuous && (l[n] || (l[n] = { top: [], right: [], bottom: [], left: [] }), m(l[n], -Math.PI / 2, 0, { endpoints: [y[C], y[C]], paint () {} }, !1, n, 0, !1, y[C].anchor.getDefaultFace(), 0, p, g), t.addWithFunction(v, n, (t) => t === n));for (C = 0;C < v.length;C++)f(v[C], l[v[C]]);for (C = 0;C < y.length;C++)y[C].paint({ timestamp: s, offset: P, dimensions: P.s, recalc: !0 !== d });for (C = 0;C < g.length;C++) {
            const F = u.getCachedData(g[C].elementId);g[C].paint({ timestamp: null, offset: F, dimensions: F.s })
          } for (C = 0;C < b.length;C++) {
            var L = b[C][1];if (L.anchor.constructor === e.DynamicAnchor) {
              L.paint({ elementWithPrecedence: n, timestamp: s }), t.addWithFunction(p, b[C][0], (t) => t.id === b[C][0].id);for (var N = 0;N < L.connections.length;N++)L.connections[N] !== b[C][0] && t.addWithFunction(p, L.connections[N], (t) => t.id === L.connections[N].id)
            } else t.addWithFunction(p, b[C][0], (t) => t.id === b[C][0].id)
          } const R = c[n];for (R && R.paint({ timestamp: s, recalc: !1, elId: n }), C = 0;C < p.length;C++)p[C].paint({ elId: n, timestamp: null, recalc: !1, clearEdits: h })
        } return { c: p, e: g }
      };const v = function (e) {
        t.EventGenerator.apply(this), this.type = 'Continuous', this.isDynamic = !0, this.isContinuous = !0;for (var n = e.faces || ['top', 'right', 'bottom', 'left'], i = !(!1 === e.clockwise), r = {}, a = { top: 'bottom', right: 'left', left: 'right', bottom: 'top' }, l = { top: 'right', right: 'bottom', left: 'top', bottom: 'left' }, u = { top: 'left', right: 'top', left: 'bottom', bottom: 'right' }, c = i ? l : u, h = i ? u : l, d = e.cssClass || '', p = null, f = null, g = ['left', 'right'], m = ['top', 'bottom'], v = null, y = 0;y < n.length;y++)r[n[y]] = !0;this.getDefaultFace = function () {
          return 0 === n.length ? 'top' : n[0]
        }, this.isRelocatable = function () {
          return !0
        }, this.isSnapOnRelocate = function () {
          return !0
        }, this.verifyEdge = function (t) {
          return r[t] ? t : r[a[t]] ? a[t] : r[c[t]] ? c[t] : r[h[t]] ? h[t] : t
        }, this.isEdgeSupported = function (t) {
          return null == v ? null == f ? !0 === r[t] : f === t : -1 !== v.indexOf(t)
        }, this.setCurrentFace = function (t, e) {
          p = t, e && null != f && (f = p)
        }, this.getCurrentFace = function () {
          return p
        }, this.getSupportedFaces = function () {
          const t = [];for (const e in r)r[e] && t.push(e);return t
        }, this.lock = function () {
          f = p
        }, this.unlock = function () {
          f = null
        }, this.isLocked = function () {
          return null != f
        }, this.lockCurrentAxis = function () {
          null != p && (v = 'left' === p || 'right' === p ? g : m)
        }, this.unlockCurrentAxis = function () {
          v = null
        }, this.compute = function (t) {
          return o[t.element.id] || [0, 0]
        }, this.getCurrentLocation = function (t) {
          return o[t.element.id] || [0, 0]
        }, this.getOrientation = function (t) {
          return s[t.id] || [0, 0]
        }, this.getCssClass = function () {
          return d
        }
      };u.continuousAnchorFactory = { get (t) {
        return new v(t)
      }, clear (t) {
        delete o[t]
      } }
    }, e.AnchorManager.prototype.calculateOrientation = function (t, e, n, i, o, s, r, a, l) {
      const u = ['left', 'top', 'right', 'bottom'];if (t === e) return { orientation: 'identity', a: ['top', 'top'] };const c = Math.atan2(i.centery - n.centery, i.centerx - n.centerx); const h = Math.atan2(n.centery - i.centery, n.centerx - i.centerx); const d = []; const p = {};!(function (t, e) {
        for (let n = 0;n < t.length;n++) if (p[t[n]] = { left: [e[n][0].left, e[n][0].centery], right: [e[n][0].right, e[n][0].centery], top: [e[n][0].centerx, e[n][0].top], bottom: [e[n][0].centerx, e[n][0].bottom] }, 0 !== e[n][1]) for (const i in p[t[n]])p[t[n]][i] = jsPlumbUtil.rotatePoint(p[t[n]][i], [e[n][0].centerx, e[n][0].centery], e[n][1])
      }(['source', 'target'], [[n, a], [i, l]]));for (let f = 0;f < u.length;f++) for (let g = 0;g < u.length;g++)d.push({ source: u[f], target: u[g], dist: Biltong.lineLength(p.source[u[f]], p.target[u[g]]) });d.sort((t, e) => t.dist < e.dist ? -1 : t.dist > e.dist ? 1 : 0);for (var m = d[0].source, v = d[0].target, y = 0;y < d.length && (m = o.isContinuous && o.locked ? o.getCurrentFace() : !o.isContinuous || o.isEdgeSupported(d[y].source) ? d[y].source : null, v = s.isContinuous && s.locked ? s.getCurrentFace() : !s.isContinuous || s.isEdgeSupported(d[y].target) ? d[y].target : null, null == m || null == v);y++);return o.isContinuous && o.setCurrentFace(m), s.isContinuous && s.setCurrentFace(v), { a: [m, v], theta: c, theta2: h }
    }, e.Anchor = function (e) {
      this.x = e.x || 0, this.y = e.y || 0, this.elementId = e.elementId, this.cssClass = e.cssClass || '', this.orientation = e.orientation || [0, 0], this.lastReturnValue = null, this.offsets = e.offsets || [0, 0], this.timestamp = null, this._unrotatedOrientation = [this.orientation[0], this.orientation[1]], this.relocatable = !1 !== e.relocatable, this.snapOnRelocate = !1 !== e.snapOnRelocate, this.locked = !1, t.EventGenerator.apply(this), this.compute = function (t) {
        const e = t.xy; const n = t.wh; const i = t.timestamp;if (i && i === this.timestamp) return this.lastReturnValue;const o = [e[0] + this.x * n[0] + this.offsets[0], e[1] + this.y * n[1] + this.offsets[1], this.x, this.y]; const s = t.rotation;if (null != s && 0 !== s) {
          const r = jsPlumbUtil.rotatePoint(o, [e[0] + n[0] / 2, e[1] + n[1] / 2], s);this.orientation[0] = Math.round(this._unrotatedOrientation[0] * r[2] - this._unrotatedOrientation[1] * r[3]), this.orientation[1] = Math.round(this._unrotatedOrientation[1] * r[2] + this._unrotatedOrientation[0] * r[3]), this.lastReturnValue = [r[0], r[1], this.x, this.y]
        } else this.orientation[0] = this._unrotatedOrientation[0], this.orientation[1] = this._unrotatedOrientation[1], this.lastReturnValue = o;return this.timestamp = i, this.lastReturnValue
      }, this.getCurrentLocation = function (t) {
        return t = t || {}, null == this.lastReturnValue || null != t.timestamp && this.timestamp !== t.timestamp ? this.compute(t) : this.lastReturnValue
      }, this.setPosition = function (t, e, n, i, o) {
        this.locked && !o || (this.x = t, this.y = e, this.orientation = [n, i], this.lastReturnValue = null)
      }
    }, t.extend(e.Anchor, t.EventGenerator, { equals (t) {
      if (!t) return !1;const e = t.getOrientation(); const n = this.getOrientation();return this.x === t.x && this.y === t.y && this.offsets[0] === t.offsets[0] && this.offsets[1] === t.offsets[1] && n[0] === e[0] && n[1] === e[1]
    }, getOrientation () {
      return this.orientation
    }, getCssClass () {
      return this.cssClass
    } }), e.FloatingAnchor = function (t) {
      e.Anchor.apply(this, arguments);const n = t.reference; const i = t.referenceCanvas; const o = e.getSize(i); let s = null; let r = null;this.orientation = null, this.x = 0, this.y = 0, this.isFloating = !0, this.compute = function (t) {
        const e = t.xy; const n = [e[0] + o[0] / 2, e[1] + o[1] / 2];return r = n, n
      }, this.getOrientation = function (t) {
        if (s) return s;const e = n.getOrientation(t);return [0 * Math.abs(e[0]) * -1, 0 * Math.abs(e[1]) * -1]
      }, this.over = function (t, e) {
        s = t.getOrientation(e)
      }, this.out = function () {
        s = null
      }, this.getCurrentLocation = function (t) {
        return null == r ? this.compute(t) : r
      }
    }, t.extend(e.FloatingAnchor, e.Anchor);e.DynamicAnchor = function (t) {
      e.Anchor.apply(this, arguments), this.isDynamic = !0, this.anchors = [], this.elementId = t.elementId, this.jsPlumbInstance = t.jsPlumbInstance;for (let n = 0;n < t.anchors.length;n++) this.anchors[n] = (i = t.anchors[n], o = this.jsPlumbInstance, s = this.elementId, i.constructor === e.Anchor ? i : o.makeAnchor(i, s, o));let i; let o; let s;this.getAnchors = function () {
        return this.anchors
      };let r = this.anchors.length > 0 ? this.anchors[0] : null; let a = r; const l = function (t, e, n, i, o, s, r) {
        let a = i[0] + t.x * o[0]; let l = i[1] + t.y * o[1]; const u = i[0] + o[0] / 2; const c = i[1] + o[1] / 2;if (null != s && 0 !== s) {
          const h = jsPlumbUtil.rotatePoint([a, l], [u, c], s);a = h[0], l = h[1]
        } return Math.sqrt(Math.pow(e - a, 2) + Math.pow(n - l, 2)) + Math.sqrt(Math.pow(u - a, 2) + Math.pow(c - l, 2))
      }; const u = t.selector || function (t, e, n, i, o, s, r) {
        for (var a = n[0] + i[0] / 2, u = n[1] + i[1] / 2, c = -1, h = 1 / 0, d = 0;d < r.length;d++) {
          const p = l(r[d], a, u, t, e, o);p < h && (c = d + 0, h = p)
        } return r[c]
      };this.compute = function (t) {
        const e = t.xy; const n = t.wh; const i = t.txy; const o = t.twh; const s = t.rotation; const l = t.tRotation;return this.timestamp = t.timestamp, this.locked || null == i || null == o ? (this.lastReturnValue = r.compute(t), this.lastReturnValue) : (t.timestamp = null, r = u(e, n, i, o, s, l, this.anchors), this.x = r.x, this.y = r.y, r !== a && this.fire('anchorChanged', r), a = r, this.lastReturnValue = r.compute(t), this.lastReturnValue)
      }, this.getCurrentLocation = function (t) {
        return null != r ? r.getCurrentLocation(t) : null
      }, this.getOrientation = function (t) {
        return null != r ? r.getOrientation(t) : [0, 0]
      }, this.over = function (t, e) {
        null != r && r.over(t, e)
      }, this.out = function () {
        null != r && r.out()
      }, this.setAnchor = function (t) {
        r = t
      }, this.getCssClass = function () {
        return r && r.getCssClass() || ''
      }, this.setAnchorCoordinates = function (t) {
        const e = jsPlumbUtil.findWithFunction(this.anchors, (e) => e.x === t[0] && e.y === t[1]);return -1 !== e && (this.setAnchor(this.anchors[e]), !0)
      }
    }, t.extend(e.DynamicAnchor, e.Anchor);const n = function (t, n, i, o, s, r) {
      e.Anchors[s] = function (e) {
        const a = e.jsPlumbInstance.makeAnchor([t, n, i, o, 0, 0], e.elementId, e.jsPlumbInstance);return a.type = s, r && r(a, e), a
      }
    };n(.5, 0, 0, -1, 'TopCenter'), n(.5, 1, 0, 1, 'BottomCenter'), n(0, .5, -1, 0, 'LeftMiddle'), n(1, .5, 1, 0, 'RightMiddle'), n(.5, 0, 0, -1, 'Top'), n(.5, 1, 0, 1, 'Bottom'), n(0, .5, -1, 0, 'Left'), n(1, .5, 1, 0, 'Right'), n(.5, .5, 0, 0, 'Center'), n(1, 0, 0, -1, 'TopRight'), n(1, 1, 0, 1, 'BottomRight'), n(0, 0, 0, -1, 'TopLeft'), n(0, 1, 0, 1, 'BottomLeft'), e.Defaults.DynamicAnchors = function (t) {
      return t.jsPlumbInstance.makeAnchors(['TopCenter', 'RightMiddle', 'BottomCenter', 'LeftMiddle'], t.elementId, t.jsPlumbInstance)
    }, e.Anchors.AutoDefault = function (t) {
      const n = t.jsPlumbInstance.makeDynamicAnchor(e.Defaults.DynamicAnchors(t));return n.type = 'AutoDefault', n
    };const i = function (t, n) {
      e.Anchors[t] = function (e) {
        const i = e.jsPlumbInstance.makeAnchor(['Continuous', { faces: n }], e.elementId, e.jsPlumbInstance);return i.type = t, i
      }
    };e.Anchors.Continuous = function (t) {
      return t.jsPlumbInstance.continuousAnchorFactory.get(t)
    }, i('ContinuousLeft', ['left']), i('ContinuousTop', ['top']), i('ContinuousBottom', ['bottom']), i('ContinuousRight', ['right']), n(0, 0, 0, 0, 'Assign', (t, e) => {
      const n = e.position || 'Fixed';t.positionFinder = n.constructor === String ? e.jsPlumbInstance.AnchorPositionFinders[n] : n, t.constructorParams = e
    }), this.jsPlumbInstance.prototype.AnchorPositionFinders = { Fixed (t, e, n) {
      return [(t.left - e.left) / n[0], (t.top - e.top) / n[1]]
    }, Grid (t, e, n, i) {
      const o = t.left - e.left; const s = t.top - e.top; const r = n[0] / i.grid[0]; const a = n[1] / i.grid[1]; const l = Math.floor(o / r); const u = Math.floor(s / a);return [(l * r + r / 2) / n[0], (u * a + a / 2) / n[1]]
    } }, e.Anchors.Perimeter = function (t) {
      const e = (t = t || {}).anchorCount || 60; const n = t.shape;if (!n) throw new Error('no shape supplied to Perimeter Anchor type');const i = function () {
        for (var t = 2 * Math.PI / e, n = 0, i = [], o = 0;o < e;o++) {
          const s = .5 + .5 * Math.sin(n); const r = .5 + .5 * Math.cos(n);i.push([s, r, 0, 0]), n += t
        } return i
      }; const o = function (t) {
        for (var n = e / t.length, i = [], o = function (t, o, s, r, a, l, u) {
            for (let c = (s - t) / (n = e * a), h = (r - o) / n, d = 0;d < n;d++)i.push([t + c * d, o + h * d, null == l ? 0 : l, null == u ? 0 : u])
          }, s = 0;s < t.length;s++)o.apply(null, t[s]);return i
      }; const s = function (t) {
        for (var e = [], n = 0;n < t.length;n++)e.push([t[n][0], t[n][1], t[n][2], t[n][3], 1 / t.length, t[n][4], t[n][5]]);return o(e)
      }; const r = function () {
        return s([[0, 0, 1, 0, 0, -1], [1, 0, 1, 1, 1, 0], [1, 1, 0, 1, 0, 1], [0, 1, 0, 0, -1, 0]])
      }; const a = { Circle: i, Ellipse: i, Diamond () {
        return s([[.5, 0, 1, .5], [1, .5, .5, 1], [.5, 1, 0, .5], [0, .5, .5, 0]])
      }, Rectangle: r, Square: r, Triangle () {
        return s([[.5, 0, 1, 1], [1, 1, 0, 1], [0, 1, .5, 0]])
      }, Path (t) {
        for (var e = t.points, n = [], i = 0, s = 0;s < e.length - 1;s++) {
          const r = Math.sqrt(Math.pow(e[s][2] - e[s][0]) + Math.pow(e[s][3] - e[s][1]));i += r, n.push([e[s][0], e[s][1], e[s + 1][0], e[s + 1][1], r])
        } for (let a = 0;a < n.length;a++)n[a][4] = n[a][4] / i;return o(n)
      } };if (!a[n]) throw new Error(`Shape [${n}] is unknown by Perimeter Anchor type`);let l = a[n](t);t.rotation && (l = (function (t, e) {
        for (var n = [], i = e / 180 * Math.PI, o = 0;o < t.length;o++) {
          const s = t[o][0] - .5; const r = t[o][1] - .5;n.push([s * Math.cos(i) - r * Math.sin(i) + .5, s * Math.sin(i) + r * Math.cos(i) + .5, t[o][2], t[o][3]])
        } return n
      }(l, t.rotation)));const u = t.jsPlumbInstance.makeDynamicAnchor(l);return u.type = 'Perimeter', u
    }
  }.call('undefined' !== typeof window ? window : s), function () {
    this.jsPlumbUtil;const t = this.jsPlumb;t.DefaultRouter = function (e) {
      this.jsPlumbInstance = e, this.anchorManager = new t.AnchorManager({ jsPlumbInstance: e }), this.sourceOrTargetChanged = function (t, e, n, i, o) {
        this.anchorManager.sourceOrTargetChanged(t, e, n, i, o)
      }, this.reset = function () {
        this.anchorManager.reset()
      }, this.changeId = function (t, e) {
        this.anchorManager.changeId(t, e)
      }, this.elementRemoved = function (t) {
        this.anchorManager.elementRemoved(t)
      }, this.newConnection = function (t) {
        this.anchorManager.newConnection(t)
      }, this.connectionDetached = function (t, e) {
        this.anchorManager.connectionDetached(t, e)
      }, this.redraw = function (t, e, n, i, o, s) {
        return this.anchorManager.redraw(t, e, n, i, o, s)
      }, this.deleteEndpoint = function (t) {
        this.anchorManager.deleteEndpoint(t)
      }, this.rehomeEndpoint = function (t, e, n) {
        this.anchorManager.rehomeEndpoint(t, e, n)
      }, this.addEndpoint = function (t, e) {
        this.anchorManager.addEndpoint(t, e)
      }
    }
  }.call('undefined' !== typeof window ? window : s), function () {
    const t = this; const e = t.jsPlumb; const n = t.jsPlumbUtil; const i = t.Biltong;e.Segments = { AbstractSegment (t) {
      this.params = t, this.findClosestPointOnPath = function (t, e) {
        return { d: 1 / 0, x: null, y: null, l: null }
      }, this.getBounds = function () {
        return { minX: Math.min(t.x1, t.x2), minY: Math.min(t.y1, t.y2), maxX: Math.max(t.x1, t.x2), maxY: Math.max(t.y1, t.y2) }
      }, this.lineIntersection = function (t, e, n, i) {
        return []
      }, this.boxIntersection = function (t, e, n, i) {
        const o = [];return o.push.apply(o, this.lineIntersection(t, e, t + n, e)), o.push.apply(o, this.lineIntersection(t + n, e, t + n, e + i)), o.push.apply(o, this.lineIntersection(t + n, e + i, t, e + i)), o.push.apply(o, this.lineIntersection(t, e + i, t, e)), o
      }, this.boundingBoxIntersection = function (t) {
        return this.boxIntersection(t.x, t.y, t.w, t.y)
      }
    }, Straight (t) {
      let n; let o; let s; let r; let a; let l; let u;e.Segments.AbstractSegment.apply(this, arguments);this.type = 'Straight', this.getLength = function () {
        return n
      }, this.getGradient = function () {
        return o
      }, this.getCoordinates = function () {
        return { x1: r, y1: l, x2: a, y2: u }
      }, this.setCoordinates = function (t) {
        r = t.x1, l = t.y1, a = t.x2, u = t.y2, n = Math.sqrt(Math.pow(a - r, 2) + Math.pow(u - l, 2)), o = i.gradient({ x: r, y: l }, { x: a, y: u }), s = -1 / o
      }, this.setCoordinates({ x1: t.x1, y1: t.y1, x2: t.x2, y2: t.y2 }), this.getBounds = function () {
        return { minX: Math.min(r, a), minY: Math.min(l, u), maxX: Math.max(r, a), maxY: Math.max(l, u) }
      }, this.pointOnPath = function (t, e) {
        if (0 !== t || e) {
          if (1 !== t || e) {
            const o = e ? t > 0 ? t : n + t : t * n;return i.pointOnLine({ x: r, y: l }, { x: a, y: u }, o)
          } return { x: a, y: u }
        } return { x: r, y: l }
      }, this.gradientAtPoint = function (t) {
        return o
      }, this.pointAlongPathFrom = function (t, e, n) {
        const o = this.pointOnPath(t, n); const s = e <= 0 ? { x: r, y: l } : { x: a, y: u };return e <= 0 && Math.abs(e) > 1 && (e *= -1), i.pointOnLine(o, s, e)
      };const c = function (t, e, n) {
        return n >= Math.min(t, e) && n <= Math.max(t, e)
      }; const h = function (t, e, n) {
        return Math.abs(n - t) < Math.abs(n - e) ? t : e
      };this.findClosestPointOnPath = function (t, e) {
        const d = { d: 1 / 0, x: null, y: null, l: null, x1: r, x2: a, y1: l, y2: u };if (0 === o)d.y = l, d.x = c(r, a, t) ? t : h(r, a, t);else if (o === 1 / 0 || o === -1 / 0)d.x = r, d.y = c(l, u, e) ? e : h(l, u, e);else {
          const p = l - o * r; const f = (e - s * t - p) / (o - s); const g = o * f + p;d.x = c(r, a, f) ? f : h(r, a, f), d.y = c(l, u, g) ? g : h(l, u, g)
        } const m = i.lineLength([d.x, d.y], [r, l]);return d.d = i.lineLength([t, e], [d.x, d.y]), d.l = m / n, d
      };const d = function (t, e, n) {
        return n > e ? e <= t && t <= n : e >= t && t >= n
      };this.lineIntersection = function (t, e, n, s) {
        const c = Math.abs(i.gradient({ x: t, y: e }, { x: n, y: s })); const h = Math.abs(o); const p = h === 1 / 0 ? r : l - h * r; let f = []; const g = c === 1 / 0 ? t : e - c * t;if (c !== h) if (c === 1 / 0 && 0 === h)d(t, r, a) && d(l, e, s) && (f = [t, l]);else if (0 === c && h === 1 / 0)d(e, l, u) && d(r, t, n) && (f = [r, e]);else {
          let m; let v;c === 1 / 0 ? d(m = t, r, a) && d(v = h * t + p, e, s) && (f = [m, v]) : 0 === c ? d(v = e, l, u) && d(m = (e - p) / h, t, n) && (f = [m, v]) : (v = h * (m = (g - p) / (h - c)) + p, d(m, r, a) && d(v, l, u) && (f = [m, v]))
        } return f
      }, this.boxIntersection = function (t, e, n, i) {
        const o = [];return o.push.apply(o, this.lineIntersection(t, e, t + n, e)), o.push.apply(o, this.lineIntersection(t + n, e, t + n, e + i)), o.push.apply(o, this.lineIntersection(t + n, e + i, t, e + i)), o.push.apply(o, this.lineIntersection(t, e + i, t, e)), o
      }, this.boundingBoxIntersection = function (t) {
        return this.boxIntersection(t.x, t.y, t.w, t.h)
      }
    }, Arc (t) {
      e.Segments.AbstractSegment.apply(this, arguments);const n = function (e, n) {
        return i.theta([t.cx, t.cy], [e, n])
      }; const o = 2 * Math.PI;this.radius = t.r, this.anticlockwise = t.ac, this.type = 'Arc', t.startAngle && t.endAngle ? (this.startAngle = t.startAngle, this.endAngle = t.endAngle, this.x1 = t.cx + this.radius * Math.cos(t.startAngle), this.y1 = t.cy + this.radius * Math.sin(t.startAngle), this.x2 = t.cx + this.radius * Math.cos(t.endAngle), this.y2 = t.cy + this.radius * Math.sin(t.endAngle)) : (this.startAngle = n(t.x1, t.y1), this.endAngle = n(t.x2, t.y2), this.x1 = t.x1, this.y1 = t.y1, this.x2 = t.x2, this.y2 = t.y2), this.endAngle < 0 && (this.endAngle += o), this.startAngle < 0 && (this.startAngle += o);const s = this.endAngle < this.startAngle ? this.endAngle + o : this.endAngle;this.sweep = Math.abs(s - this.startAngle), this.anticlockwise && (this.sweep = o - this.sweep);const r = 2 * Math.PI * this.radius; const a = this.sweep / o; const l = r * a;this.getLength = function () {
        return l
      }, this.getBounds = function () {
        return { minX: t.cx - t.r, maxX: t.cx + t.r, minY: t.cy - t.r, maxY: t.cy + t.r }
      };const u = function (t) {
        const e = Math.floor(t); const n = Math.ceil(t);return t - e < 1e-10 ? e : n - t < 1e-10 ? n : t
      };this.pointOnPath = function (e, n) {
        if (0 === e) return { x: this.x1, y: this.y1, theta: this.startAngle };if (1 === e) return { x: this.x2, y: this.y2, theta: this.endAngle };n && (e /= l);const i = (function (t, e) {
          if (t.anticlockwise) {
            const n = t.startAngle < t.endAngle ? t.startAngle + o : t.startAngle;return n - Math.abs(n - t.endAngle) * e
          } const i = t.endAngle < t.startAngle ? t.endAngle + o : t.endAngle; const s = Math.abs(i - t.startAngle);return t.startAngle + s * e
        }(this, e)); const s = t.cx + t.r * Math.cos(i); const r = t.cy + t.r * Math.sin(i);return { x: u(s), y: u(r), theta: i }
      }, this.gradientAtPoint = function (e, n) {
        const o = this.pointOnPath(e, n); let s = i.normal([t.cx, t.cy], [o.x, o.y]);return this.anticlockwise || s !== 1 / 0 && s !== -1 / 0 || (s *= -1), s
      }, this.pointAlongPathFrom = function (e, n, i) {
        const o = this.pointOnPath(e, i); const s = n / r * 2 * Math.PI; const a = this.anticlockwise ? -1 : 1; const l = o.theta + a * s;return { x: t.cx + this.radius * Math.cos(l), y: t.cy + this.radius * Math.sin(l) }
      }
    }, Bezier (n) {
      this.curve = [{ x: n.x1, y: n.y1 }, { x: n.cp1x, y: n.cp1y }, { x: n.cp2x, y: n.cp2y }, { x: n.x2, y: n.y2 }];const i = function (t) {
        const e = { x: 0, y: 0 };if (0 === t) return this.curve[0];const n = this.curve.length - 1;if (1 === t) return this.curve[n];let i = this.curve; const o = 1 - t;if (0 === n) return this.curve[0];if (1 === n) return { x: o * i[0].x + t * i[1].x, y: o * i[0].y + t * i[1].y };if (n < 4) {
          let s; let r; let a; const l = o * o; const u = t * t; let c = 0;return 2 === n ? (i = [i[0], i[1], i[2], e], s = l, r = o * t * 2, a = u) : 3 === n && (s = l * o, r = l * t * 3, a = o * u * 3, c = t * u), { x: s * i[0].x + r * i[1].x + a * i[2].x + c * i[3].x, y: s * i[0].y + r * i[1].y + a * i[2].y + c * i[3].y }
        } return e
      }.bind(this); const o = function () {
        let t;(t = this.curve)[0].x === t[1].x && t[0].y === t[1].y && (this.length = 0);let e; let n; const o = (function (t) {
          const e = [];t--;for (let n = 0;n <= t;n++)e.push(i(n / t));return e
        }(16));this.length = 0;for (let s = 0;s < 15;s++) {
          const r = o[s]; const a = o[s + 1];this.length += (e = r, n = a, Math.sqrt(Math.pow(e.x - n.x, 2) + Math.pow(e.y - n.y, 2)))
        }
      }.bind(this);e.Segments.AbstractSegment.apply(this, arguments);this.bounds = { minX: Math.min(n.x1, n.x2, n.cp1x, n.cp2x), minY: Math.min(n.y1, n.y2, n.cp1y, n.cp2y), maxX: Math.max(n.x1, n.x2, n.cp1x, n.cp2x), maxY: Math.max(n.y1, n.y2, n.cp1y, n.cp2y) }, this.type = 'Bezier', o();const s = function (e, n, i) {
        return i && (n = t.jsBezier.locationAlongCurveFrom(e, n > 0 ? 0 : 1, n)), n
      };this.pointOnPath = function (e, n) {
        return e = s(this.curve, e, n), t.jsBezier.pointOnCurve(this.curve, e)
      }, this.gradientAtPoint = function (e, n) {
        return e = s(this.curve, e, n), t.jsBezier.gradientAtPoint(this.curve, e)
      }, this.pointAlongPathFrom = function (e, n, i) {
        return e = s(this.curve, e, i), t.jsBezier.pointAlongCurveFrom(this.curve, e, n)
      }, this.getLength = function () {
        return this.length
      }, this.getBounds = function () {
        return this.bounds
      }, this.findClosestPointOnPath = function (e, n) {
        const i = t.jsBezier.nearestPointOnCurve({ x: e, y: n }, this.curve);return { d: Math.sqrt(Math.pow(i.point.x - e, 2) + Math.pow(i.point.y - n, 2)), x: i.point.x, y: i.point.y, l: 1 - i.location, s: this }
      }, this.lineIntersection = function (e, n, i, o) {
        return t.jsBezier.lineIntersection(e, n, i, o, this.curve)
      }
    } }, e.SegmentRenderer = { getPath (t, e) {
      return { Straight (e) {
        const n = t.getCoordinates();return `${e ? `M ${n.x1} ${n.y1} ` : ''}L ${n.x2} ${n.y2}`
      }, Bezier (e) {
        const n = t.params;return `${e ? `M ${n.x2} ${n.y2} ` : ''}C ${n.cp2x} ${n.cp2y} ${n.cp1x} ${n.cp1y} ${n.x1} ${n.y1}`
      }, Arc (e) {
        const n = t.params; const i = t.sweep > Math.PI ? 1 : 0; const o = t.anticlockwise ? 0 : 1;return `${e ? `M${t.x1} ${t.y1} ` : ''}A ${t.radius} ${n.r} 0 ${i},${o} ${t.x2} ${t.y2}`
      } }[t.type](e)
    } };const o = function () {
      this.resetBounds = function () {
        this.bounds = { minX: 1 / 0, minY: 1 / 0, maxX: -1 / 0, maxY: -1 / 0 }
      }, this.resetBounds()
    };e.Connectors.AbstractConnector = function (t) {
      o.apply(this, arguments);const s = []; let r = 0; const a = []; const l = []; const u = t.stub || 0; const c = n.isArray(u) ? u[0] : u; const h = n.isArray(u) ? u[1] : u; const d = t.gap || 0; const p = n.isArray(d) ? d[0] : d; const f = n.isArray(d) ? d[1] : d; let g = null; let m = null;this.getPathData = function () {
        for (var t = '', n = 0;n < s.length;n++)t += e.SegmentRenderer.getPath(s[n], 0 === n), t += ' ';return t
      }, this.findSegmentForPoint = function (t, e) {
        for (var n = { d: 1 / 0, s: null, x: null, y: null, l: null }, i = 0;i < s.length;i++) {
          const o = s[i].findClosestPointOnPath(t, e);o.d < n.d && (n.d = o.d, n.l = o.l, n.x = o.x, n.y = o.y, n.s = s[i], n.x1 = o.x1, n.x2 = o.x2, n.y1 = o.y1, n.y2 = o.y2, n.index = i, n.connectorLocation = a[i][0] + o.l * (a[i][1] - a[i][0]))
        } return n
      }, this.lineIntersection = function (t, e, n, i) {
        for (var o = [], r = 0;r < s.length;r++)o.push.apply(o, s[r].lineIntersection(t, e, n, i));return o
      }, this.boxIntersection = function (t, e, n, i) {
        for (var o = [], r = 0;r < s.length;r++)o.push.apply(o, s[r].boxIntersection(t, e, n, i));return o
      }, this.boundingBoxIntersection = function (t) {
        for (var e = [], n = 0;n < s.length;n++)e.push.apply(e, s[n].boundingBoxIntersection(t));return e
      };const v = function (t, e) {
        let n; let i; let o;if (e && (t = t > 0 ? t / r : (r + t) / r), 1 === t)n = s.length - 1, o = 1;else if (0 === t)o = 0, n = 0;else if (t >= .5) {
          for (n = 0, o = 0, i = a.length - 1;i > -1;i--) if (a[i][1] >= t && a[i][0] <= t) {
            n = i, o = (t - a[i][0]) / l[i];break
          }
        } else for (n = a.length - 1, o = 1, i = 0;i < a.length;i++) if (a[i][1] >= t) {
          n = i, o = (t - a[i][0]) / l[i];break
        } return { segment: s[n], proportion: o, index: n }
      };this.setSegments = function (t) {
        g = [], r = 0;for (let e = 0;e < t.length;e++)g.push(t[e]), r += t[e].getLength()
      }, this.getLength = function () {
        return r
      };const y = function (t) {
        this.strokeWidth = t.strokeWidth;const e = i.quadrant(t.sourcePos, t.targetPos); const n = t.targetPos[0] < t.sourcePos[0]; const o = t.targetPos[1] < t.sourcePos[1]; const s = t.strokeWidth || 1; let r = t.sourceEndpoint.anchor.getOrientation(t.sourceEndpoint); let a = t.targetEndpoint.anchor.getOrientation(t.targetEndpoint); const l = n ? t.targetPos[0] : t.sourcePos[0]; const u = o ? t.targetPos[1] : t.sourcePos[1]; const d = Math.abs(t.targetPos[0] - t.sourcePos[0]); const g = Math.abs(t.targetPos[1] - t.sourcePos[1]);if (0 === r[0] && 0 === r[1] || 0 === a[0] && 0 === a[1]) {
          const m = d > g ? 0 : 1; const v = [1, 0][m];a = [], (r = [])[m] = t.sourcePos[m] > t.targetPos[m] ? -1 : 1, a[m] = t.sourcePos[m] > t.targetPos[m] ? 1 : -1, r[v] = 0, a[v] = 0
        } const y = n ? d + p * r[0] : p * r[0]; const b = o ? g + p * r[1] : p * r[1]; const P = n ? f * a[0] : d + f * a[0]; const x = o ? f * a[1] : g + f * a[1]; const C = r[0] * a[0] + r[1] * a[1]; const _ = { sx: y, sy: b, tx: P, ty: x, lw: s, xSpan: Math.abs(P - y), ySpan: Math.abs(x - b), mx: (y + P) / 2, my: (b + x) / 2, so: r, to: a, x: l, y: u, w: d, h: g, segment: e, startStubX: y + r[0] * c, startStubY: b + r[1] * c, endStubX: P + a[0] * h, endStubY: x + a[1] * h, isXGreaterThanStubTimes2: Math.abs(y - P) > c + h, isYGreaterThanStubTimes2: Math.abs(b - x) > c + h, opposite: -1 === C, perpendicular: 0 === C, orthogonal: 1 === C, sourceAxis: 0 === r[0] ? 'y' : 'x', points: [l, u, d, g, y, b, P, x], stubs: [c, h] };return _.anchorOrientation = _.opposite ? 'opposite' : _.orthogonal ? 'orthogonal' : 'perpendicular', _
      };return this.getSegments = function () {
        return s
      }, this.updateBounds = function (t) {
        const e = t.getBounds();this.bounds.minX = Math.min(this.bounds.minX, e.minX), this.bounds.maxX = Math.max(this.bounds.maxX, e.maxX), this.bounds.minY = Math.min(this.bounds.minY, e.minY), this.bounds.maxY = Math.max(this.bounds.maxY, e.maxY)
      }, this.pointOnPath = function (t, e) {
        const n = v(t, e);return n.segment && n.segment.pointOnPath(n.proportion, !1) || [0, 0]
      }, this.gradientAtPoint = function (t, e) {
        const n = v(t, e);return n.segment && n.segment.gradientAtPoint(n.proportion, !1) || 0
      }, this.pointAlongPathFrom = function (t, e, n) {
        const i = v(t, n);return i.segment && i.segment.pointAlongPathFrom(i.proportion, e, !1) || [0, 0]
      }, this.compute = function (t) {
        m = y.call(this, t), r = s.length = a.length = l.length = 0, this._compute(m, t), this.x = m.points[0], this.y = m.points[1], this.w = m.points[2], this.h = m.points[3], this.segment = m.segment, (function () {
          for (let t = 0, e = 0;e < s.length;e++) {
            const n = s[e].getLength();l[e] = n / r, a[e] = [t, t += n / r]
          }
        }())
      }, { addSegment (t, n, i) {
        if (i.x1 !== i.x2 || i.y1 !== i.y2) {
          const o = new e.Segments[n](i);s.push(o), r += o.getLength(), t.updateBounds(o)
        }
      }, prepareCompute: y, sourceStub: c, targetStub: h, maxStub: Math.max(c, h), sourceGap: p, targetGap: f, maxGap: Math.max(p, f) }
    }, n.extend(e.Connectors.AbstractConnector, o), e.Endpoints.AbstractEndpoint = function (t) {
      return o.apply(this, arguments), { compute: this.compute = function (t, e, n, i) {
        const o = this._compute.apply(this, arguments);return this.x = o[0], this.y = o[1], this.w = o[2], this.h = o[3], this.bounds.minX = this.x, this.bounds.minY = this.y, this.bounds.maxX = this.x + this.w, this.bounds.maxY = this.y + this.h, o
      }, cssClass: t.cssClass }
    }, n.extend(e.Endpoints.AbstractEndpoint, o), e.Endpoints.Dot = function (t) {
      this.type = 'Dot';e.Endpoints.AbstractEndpoint.apply(this, arguments);t = t || {}, this.radius = t.radius || 10, this.defaultOffset = .5 * this.radius, this.defaultInnerRadius = this.radius / 3, this._compute = function (t, e, n, i) {
        this.radius = n.radius || this.radius;let o = t[0] - this.radius; let s = t[1] - this.radius; let r = 2 * this.radius; let a = 2 * this.radius;if (n.stroke) {
          const l = n.strokeWidth || 1;o -= l, s -= l, r += 2 * l, a += 2 * l
        } return [o, s, r, a, this.radius]
      }
    }, n.extend(e.Endpoints.Dot, e.Endpoints.AbstractEndpoint), e.Endpoints.Rectangle = function (t) {
      this.type = 'Rectangle';e.Endpoints.AbstractEndpoint.apply(this, arguments);t = t || {}, this.width = t.width || 20, this.height = t.height || 20, this._compute = function (t, e, n, i) {
        const o = n.width || this.width; const s = n.height || this.height;return [t[0] - o / 2, t[1] - s / 2, o, s]
      }
    }, n.extend(e.Endpoints.Rectangle, e.Endpoints.AbstractEndpoint);const s = function (t) {
      e.jsPlumbUIComponent.apply(this, arguments), this._jsPlumb.displayElements = []
    };n.extend(s, e.jsPlumbUIComponent, { getDisplayElements () {
      return this._jsPlumb.displayElements
    }, appendDisplayElement (t) {
      this._jsPlumb.displayElements.push(t)
    } }), e.Endpoints.Image = function (i) {
      this.type = 'Image', s.apply(this, arguments), e.Endpoints.AbstractEndpoint.apply(this, arguments);let o = i.onload; const r = i.src || i.url; const a = i.cssClass ? ` ${i.cssClass}` : '';this._jsPlumb.img = new Image, this._jsPlumb.ready = !1, this._jsPlumb.initialized = !1, this._jsPlumb.deleted = !1, this._jsPlumb.widthToUse = i.width, this._jsPlumb.heightToUse = i.height, this._jsPlumb.endpoint = i.endpoint, this._jsPlumb.img.onload = function () {
        null != this._jsPlumb && (this._jsPlumb.ready = !0, this._jsPlumb.widthToUse = this._jsPlumb.widthToUse || this._jsPlumb.img.width, this._jsPlumb.heightToUse = this._jsPlumb.heightToUse || this._jsPlumb.img.height, o && o(this))
      }.bind(this), this._jsPlumb.endpoint.setImage = function (t, e) {
        const n = t.constructor === String ? t : t.src;o = e, this._jsPlumb.img.src = n, null != this.canvas && this.canvas.setAttribute('src', this._jsPlumb.img.src)
      }.bind(this), this._jsPlumb.endpoint.setImage(r, o), this._compute = function (t, e, n, i) {
        return this.anchorPoint = t, this._jsPlumb.ready ? [t[0] - this._jsPlumb.widthToUse / 2, t[1] - this._jsPlumb.heightToUse / 2, this._jsPlumb.widthToUse, this._jsPlumb.heightToUse] : [0, 0, 0, 0]
      }, this.canvas = e.createElement('img', { position: 'absolute', margin: 0, padding: 0, outline: 0 }, this._jsPlumb.instance.endpointClass + a), this._jsPlumb.widthToUse && this.canvas.setAttribute('width', this._jsPlumb.widthToUse), this._jsPlumb.heightToUse && this.canvas.setAttribute('height', this._jsPlumb.heightToUse), this._jsPlumb.instance.appendElement(this.canvas), this.actuallyPaint = function (t, e, i) {
        if (!this._jsPlumb.deleted) {
          this._jsPlumb.initialized || (this.canvas.setAttribute('src', this._jsPlumb.img.src), this.appendDisplayElement(this.canvas), this._jsPlumb.initialized = !0);const o = this.anchorPoint[0] - this._jsPlumb.widthToUse / 2; const s = this.anchorPoint[1] - this._jsPlumb.heightToUse / 2;n.sizeElement(this.canvas, o, s, this._jsPlumb.widthToUse, this._jsPlumb.heightToUse)
        }
      }, this.paint = function (e, n) {
        null != this._jsPlumb && (this._jsPlumb.ready ? this.actuallyPaint(e, n) : t.setTimeout(() => {
          this.paint(e, n)
        }, 200))
      }
    }, n.extend(e.Endpoints.Image, [s, e.Endpoints.AbstractEndpoint], { cleanup (t) {
      t && (this._jsPlumb.deleted = !0, this.canvas && this.canvas.parentNode.removeChild(this.canvas), this.canvas = null)
    } }), e.Endpoints.Blank = function (t) {
      e.Endpoints.AbstractEndpoint.apply(this, arguments);this.type = 'Blank', s.apply(this, arguments), this._compute = function (t, e, n, i) {
        return [t[0], t[1], 10, 0]
      };const i = t.cssClass ? ` ${t.cssClass}` : '';this.canvas = e.createElement('div', { display: 'block', width: '1px', height: '1px', background: 'transparent', position: 'absolute' }, this._jsPlumb.instance.endpointClass + i), this._jsPlumb.instance.appendElement(this.canvas), this.paint = function (t, e) {
        n.sizeElement(this.canvas, this.x, this.y, this.w, this.h)
      }
    }, n.extend(e.Endpoints.Blank, [e.Endpoints.AbstractEndpoint, s], { cleanup () {
      this.canvas && this.canvas.parentNode && this.canvas.parentNode.removeChild(this.canvas)
    } }), e.Endpoints.Triangle = function (t) {
      this.type = 'Triangle', e.Endpoints.AbstractEndpoint.apply(this, arguments);const n = this;(t = t || {}).width = t.width || 55, t.height = t.height || 55, this.width = t.width, this.height = t.height, this._compute = function (t, e, i, o) {
        const s = i.width || n.width; const r = i.height || n.height;return [t[0] - s / 2, t[1] - r / 2, s, r]
      }
    };const r = e.Overlays.AbstractOverlay = function (t) {
      this.visible = !0, this.isAppendedAtTopLevel = !0, this.component = t.component, this.loc = null == t.location ? .5 : t.location, this.endpointLoc = null == t.endpointLocation ? [.5, .5] : t.endpointLocation, this.visible = !1 !== t.visible
    };r.prototype = { cleanup (t) {
      t && (this.component = null, this.canvas = null, this.endpointLoc = null)
    }, reattach (t, e) {}, setVisible (t) {
      this.visible = t, this.component.repaint()
    }, isVisible () {
      return this.visible
    }, hide () {
      this.setVisible(!1)
    }, show () {
      this.setVisible(!0)
    }, incrementLocation (t) {
      this.loc += t, this.component.repaint()
    }, setLocation (t) {
      this.loc = t, this.component.repaint()
    }, getLocation () {
      return this.loc
    }, updateFrom () {} }, e.Overlays.Arrow = function (t) {
      this.type = 'Arrow', r.apply(this, arguments), this.isAppendedAtTopLevel = !1, t = t || {};const o = this;this.length = t.length || 20, this.width = t.width || 20, this.id = t.id, this.direction = (t.direction || 1) < 0 ? -1 : 1;const s = t.paintStyle || { 'stroke-width': 1 }; const a = t.foldback || .623;this.computeMaxSize = function () {
        return 1.5 * o.width
      }, this.elementCreated = function (n, i) {
        if (this.path = n, t.events) for (const o in t.events)e.on(n, o, t.events[o])
      }, this.draw = function (t, e) {
        let o; let r; let l; let u;if (t.pointAlongPathFrom) {
          if (n.isString(this.loc) || this.loc > 1 || this.loc < 0) {
            const c = parseInt(this.loc, 10); const h = this.loc < 0 ? 1 : 0;o = t.pointAlongPathFrom(h, c, !1), r = t.pointAlongPathFrom(h, c - this.direction * this.length / 2, !1), l = i.pointOnLine(o, r, this.length)
          } else if (1 === this.loc) {
            if (o = t.pointOnPath(this.loc), r = t.pointAlongPathFrom(this.loc, -this.length), l = i.pointOnLine(o, r, this.length), -1 === this.direction) {
              const d = l;l = o, o = d
            }
          } else if (0 === this.loc) {
            if (l = t.pointOnPath(this.loc), r = t.pointAlongPathFrom(this.loc, this.length), o = i.pointOnLine(l, r, this.length), -1 === this.direction) {
              const p = l;l = o, o = p
            }
          } else o = t.pointAlongPathFrom(this.loc, this.direction * this.length / 2), r = t.pointOnPath(this.loc), l = i.pointOnLine(o, r, this.length);const f = { hxy: o, tail: u = i.perpendicularLineTo(o, l, this.width), cxy: i.pointOnLine(o, l, a * this.length) }; const g = s.stroke || e.stroke; const m = s.fill || e.stroke;return { component: t, d: f, 'stroke-width': s.strokeWidth || e.strokeWidth, stroke: g, fill: m, minX: Math.min(o.x, u[0].x, u[1].x), maxX: Math.max(o.x, u[0].x, u[1].x), minY: Math.min(o.y, u[0].y, u[1].y), maxY: Math.max(o.y, u[0].y, u[1].y) }
        } return { component: t, minX: 0, maxX: 0, minY: 0, maxY: 0 }
      }
    }, n.extend(e.Overlays.Arrow, r, { updateFrom (t) {
      this.length = t.length || this.length, this.width = t.width || this.width, this.direction = null != t.direction ? t.direction : this.direction, this.foldback = t.foldback || this.foldback
    }, cleanup () {
      this.path && this.path.parentNode && this.path.parentNode.removeChild(this.path)
    } }), e.Overlays.PlainArrow = function (t) {
      t = t || {};const n = e.extend(t, { foldback: 1 });e.Overlays.Arrow.call(this, n), this.type = 'PlainArrow'
    }, n.extend(e.Overlays.PlainArrow, e.Overlays.Arrow), e.Overlays.Diamond = function (t) {
      const n = (t = t || {}).length || 40; const i = e.extend(t, { length: n / 2, foldback: 2 });e.Overlays.Arrow.call(this, i), this.type = 'Diamond'
    }, n.extend(e.Overlays.Diamond, e.Overlays.Arrow);const a = function (t, e) {
      return (null == t._jsPlumb.cachedDimensions || e) && (t._jsPlumb.cachedDimensions = t.getDimensions()), t._jsPlumb.cachedDimensions
    }; const l = function (t) {
      e.jsPlumbUIComponent.apply(this, arguments), r.apply(this, arguments);const i = this.fire;this.fire = function () {
        i.apply(this, arguments), this.component && this.component.fire.apply(this.component, arguments)
      }, this.detached = !1, this.id = t.id, this._jsPlumb.div = null, this._jsPlumb.initialised = !1, this._jsPlumb.component = t.component, this._jsPlumb.cachedDimensions = null, this._jsPlumb.create = t.create, this._jsPlumb.initiallyInvisible = !1 === t.visible, this.getElement = function () {
        if (null == this._jsPlumb.div) {
          const n = this._jsPlumb.div = e.getElement(this._jsPlumb.create(this._jsPlumb.component));n.style.position = 'absolute', jsPlumb.addClass(n, `${this._jsPlumb.instance.overlayClass} ${this.cssClass ? this.cssClass : t.cssClass ? t.cssClass : ''}`), this._jsPlumb.instance.appendElement(n), this._jsPlumb.instance.getId(n), this.canvas = n;const i = 'translate(-50%, -50%)';n.style.webkitTransform = i, n.style.mozTransform = i, n.style.msTransform = i, n.style.oTransform = i, n.style.transform = i, n._jsPlumb = this, !1 === t.visible && (n.style.display = 'none')
        } return this._jsPlumb.div
      }, this.draw = function (t, e, i) {
        const o = a(this);if (null != o && 2 === o.length) {
          let s = { x: 0, y: 0 };if (i)s = { x: i[0], y: i[1] };else if (t.pointOnPath) {
            let r = this.loc; let l = !1;(n.isString(this.loc) || this.loc < 0 || this.loc > 1) && (r = parseInt(this.loc, 10), l = !0), s = t.pointOnPath(r, l)
          } else {
            const u = this.loc.constructor === Array ? this.loc : this.endpointLoc;s = { x: u[0] * t.w, y: u[1] * t.h }
          } const c = s.x - o[0] / 2; const h = s.y - o[1] / 2;return { component: t, d: { minx: c, miny: h, td: o, cxy: s }, minX: c, maxX: c + o[0], minY: h, maxY: h + o[1] }
        } return { minX: 0, maxX: 0, minY: 0, maxY: 0 }
      }
    };n.extend(l, [e.jsPlumbUIComponent, r], { getDimensions () {
      return [1, 1]
    }, setVisible (t) {
      this._jsPlumb.div && (this._jsPlumb.div.style.display = t ? 'block' : 'none', t && this._jsPlumb.initiallyInvisible && (a(this, !0), this.component.repaint(), this._jsPlumb.initiallyInvisible = !1))
    }, clearCachedDimensions () {
      this._jsPlumb.cachedDimensions = null
    }, cleanup (t) {
      t ? null != this._jsPlumb.div && (this._jsPlumb.div._jsPlumb = null, this._jsPlumb.instance.removeElement(this._jsPlumb.div)) : (this._jsPlumb && this._jsPlumb.div && this._jsPlumb.div.parentNode && this._jsPlumb.div.parentNode.removeChild(this._jsPlumb.div), this.detached = !0)
    }, reattach (t, e) {
      null != this._jsPlumb.div && t.getContainer().appendChild(this._jsPlumb.div), this.detached = !1
    }, computeMaxSize () {
      const t = a(this);return Math.max(t[0], t[1])
    }, paint (t, e) {
      this._jsPlumb.initialised || (this.getElement(), t.component.appendDisplayElement(this._jsPlumb.div), this._jsPlumb.initialised = !0, this.detached && this._jsPlumb.div.parentNode.removeChild(this._jsPlumb.div)), this._jsPlumb.div.style.left = `${t.component.x + t.d.minx}px`, this._jsPlumb.div.style.top = `${t.component.y + t.d.miny}px`
    } }), e.Overlays.Custom = function (t) {
      this.type = 'Custom', l.apply(this, arguments)
    }, n.extend(e.Overlays.Custom, l), e.Overlays.GuideLines = function () {
      const t = this;t.length = 50, t.strokeWidth = 5, this.type = 'GuideLines', r.apply(this, arguments), e.jsPlumbUIComponent.apply(this, arguments), this.draw = function (e, n) {
        const o = e.pointAlongPathFrom(t.loc, t.length / 2); const s = e.pointOnPath(t.loc); const r = i.pointOnLine(o, s, t.length); const a = i.perpendicularLineTo(o, r, 40); const l = i.perpendicularLineTo(r, o, 20);return { connector: e, head: o, tail: r, headLine: l, tailLine: a, minX: Math.min(o.x, r.x, l[0].x, l[1].x), minY: Math.min(o.y, r.y, l[0].y, l[1].y), maxX: Math.max(o.x, r.x, l[0].x, l[1].x), maxY: Math.max(o.y, r.y, l[0].y, l[1].y) }
      }
    }, e.Overlays.Label = function (t) {
      this.labelStyle = t.labelStyle, this.cssClass = null != this.labelStyle ? this.labelStyle.cssClass : null;const n = e.extend({ create () {
        return e.createElement('div')
      } }, t);if (e.Overlays.Custom.call(this, n), this.type = 'Label', this.label = t.label || '', this.labelText = null, this.labelStyle) {
        const i = this.getElement();if (this.labelStyle.font = this.labelStyle.font || '12px sans-serif', i.style.font = this.labelStyle.font, i.style.color = this.labelStyle.color || 'black', this.labelStyle.fill && (i.style.background = this.labelStyle.fill), this.labelStyle.borderWidth > 0) {
          const o = this.labelStyle.borderStyle ? this.labelStyle.borderStyle : 'black';i.style.border = `${this.labelStyle.borderWidth}px solid ${o}`
        } this.labelStyle.padding && (i.style.padding = this.labelStyle.padding)
      }
    }, n.extend(e.Overlays.Label, e.Overlays.Custom, { cleanup (t) {
      t && (this.div = null, this.label = null, this.labelText = null, this.cssClass = null, this.labelStyle = null)
    }, getLabel () {
      return this.label
    }, setLabel (t) {
      this.label = t, this.labelText = null, this.clearCachedDimensions(), this.update(), this.component.repaint()
    }, getDimensions () {
      return this.update(), l.prototype.getDimensions.apply(this, arguments)
    }, update () {
      if ('function' === typeof this.label) {
        const t = this.label(this);this.getElement().innerHTML = t.replace(/\r\n/g, '<br/>')
      } else null == this.labelText && (this.labelText = this.label, this.getElement().innerHTML = this.labelText.replace(/\r\n/g, '<br/>'))
    }, updateFrom (t) {
      null != t.label && this.setLabel(t.label)
    } })
  }.call('undefined' !== typeof window ? window : s), function () {
    const t = this; const e = t.jsPlumbUtil; const n = t.jsPlumbInstance; const i = 'stop'; const o = 'revert'; const s = '_jsPlumbGroup'; const r = 'show'; const a = 'hide'; const l = function (t) {
      const n = {}; const i = {}; const o = {}; const l = this;function u (e, n) {
        for (let i = t.getContainer();;) {
          if (null == e || e === i) return !1;if (e === n) return !0;e = e.parentNode
        }
      } function c (e, n) {
        for (let i = e.getEl().querySelectorAll('.jtk-managed'), o = 0;o < i.length;o++)t[n ? r : a](i[o], !0)
      }t.bind('connection', (n) => {
        const s = t.getGroupFor(n.source); const r = t.getGroupFor(n.target);null != s && null != r && s === r ? (i[n.connection.id] = s, o[n.connection.id] = s) : (null != s && (e.suggest(s.connections.source, n.connection), i[n.connection.id] = s), null != r && (e.suggest(r.connections.target, n.connection), o[n.connection.id] = r))
      }), t.bind('internal.connectionDetached', (t) => {
        !(function (t) {
          delete t.proxies;let n; let s = i[t.id];null != s && (n = function (e) {
            return e.id === t.id
          }, e.removeWithFunction(s.connections.source, n), e.removeWithFunction(s.connections.target, n), delete i[t.id]), null != (s = o[t.id]) && (n = function (e) {
            return e.id === t.id
          }, e.removeWithFunction(s.connections.source, n), e.removeWithFunction(s.connections.target, n), delete o[t.id])
        }(t.connection))
      }), t.bind('connectionMoved', (t) => {
        const e = (0 === t.index ? i : o)[t.connection.id];if (e) {
          const n = e.connections[0 === t.index ? 'source' : 'target']; const s = n.indexOf(t.connection);-1 !== s && n.splice(s, 1)
        }
      }), this.addGroup = function (e) {
        t.addClass(e.getEl(), 'jtk-group-expanded'), n[e.id] = e, e.manager = this, p(e), t.fire('group:add', { group: e })
      }, this.addToGroup = function (e, n, i) {
        if (e = this.getGroup(e)) {
          const o = e.getEl();if (n._isJsPlumbGroup) return;const s = n._jsPlumbGroup;if (s !== e) {
            t.removeFromDragSelection(n);const r = t.getOffset(n, !0); const a = e.collapsed ? t.getOffset(o, !0) : t.getOffset(e.getDragArea(), !0);null != s && (s.remove(n, !1, i, !1, e), l.updateConnectionsForGroup(s)), e.add(n, i);const u = function (t, n) {
              const i = 0 === n ? 1 : 0;t.each((t) => {
                t.setVisible(!1), t.endpoints[i].element._jsPlumbGroup === e ? (t.endpoints[i].setVisible(!1), d(t, i, e)) : (t.endpoints[n].setVisible(!1), h(t, n, e))
              })
            };e.collapsed && (u(t.select({ source: n }), 0), u(t.select({ target: n }), 1));const c = t.getId(n);t.dragManager.setParent(n, c, o, t.getId(o), r);const p = { left: r.left - a.left, top: r.top - a.top };if (t.setPosition(n, p), t.dragManager.revalidateParent(n, c, r), l.updateConnectionsForGroup(e), t.revalidate(c), !i) {
              const f = { group: e, el: n, pos: p };s && (f.sourceGroup = s), t.fire('group:addMember', f)
            }
          }
        }
      }, this.removeFromGroup = function (t, e, n) {
        if (t = this.getGroup(t)) {
          if (t.collapsed) {
            const i = function (n, i) {
              for (let o = 0;o < n.length;o++) {
                const s = n[o];if (s.proxies) for (let r = 0;r < s.proxies.length;r++) if (null != s.proxies[r]) {
                  const a = s.proxies[r].originalEp.element;(a === e || u(a, e)) && d(s, i, t)
                }
              }
            };i(t.connections.source.slice(), 0), i(t.connections.target.slice(), 1)
          }t.remove(e, null, n)
        }
      }, this.getGroup = function (t) {
        let i = t;if (e.isString(t) && null == (i = n[t])) throw new TypeError(`No such group [${t}]`);return i
      }, this.getGroups = function () {
        const t = [];for (const e in n)t.push(n[e]);return t
      }, this.removeGroup = function (e, i, o, s) {
        e = this.getGroup(e), this.expandGroup(e, !0);const r = e[i ? 'removeAll' : 'orphanAll'](o, s);return t.remove(e.getEl()), delete n[e.id], delete t._groups[e.id], t.fire('group:remove', { group: e }), r
      }, this.removeAllGroups = function (t, e, i) {
        for (const o in n) this.removeGroup(n[o], t, e, i)
      };var h = function (e, n, i) {
        const o = e.endpoints[0 === n ? 1 : 0].element;if (!o[s] || o[s].shouldProxy() || !o[s].collapsed) {
          const r = i.getEl(); const a = t.getId(r);t.proxyConnection(e, n, r, a, (t, e) => i.getEndpoint(t, e), (t, e) => i.getAnchor(t, e))
        }
      };this.collapseGroup = function (e) {
        if (null != (e = this.getGroup(e)) && !e.collapsed) {
          const n = e.getEl();if (c(e, !1), e.shouldProxy()) {
            const i = function (t, n) {
              for (let i = 0;i < t.length;i++) {
                const o = t[i];h(o, n, e)
              }
            };i(e.connections.source, 0), i(e.connections.target, 1)
          }e.collapsed = !0, t.removeClass(n, 'jtk-group-expanded'), t.addClass(n, 'jtk-group-collapsed'), t.revalidate(n), t.fire('group:collapse', { group: e })
        }
      };var d = function (e, n, i) {
        t.unproxyConnection(e, n, t.getId(i.getEl()))
      };function p (e) {
        for (var n = e.getMembers().slice(), s = [], r = 0;r < n.length;r++)Array.prototype.push.apply(s, n[r].querySelectorAll('.jtk-managed'));Array.prototype.push.apply(n, s);const a = t.getConnections({ source: n, scope: '*' }, !0); const l = t.getConnections({ target: n, scope: '*' }, !0); const u = {};e.connections.source.length = 0, e.connections.target.length = 0;const c = function (n) {
          for (let s = 0;s < n.length;s++) if (!u[n[s].id]) {
            u[n[s].id] = !0;const r = t.getGroupFor(n[s].source); const a = t.getGroupFor(n[s].target);r === e ? (a !== e && e.connections.source.push(n[s]), i[n[s].id] = e) : a === e && (e.connections.target.push(n[s]), o[n[s].id] = e)
          }
        };c(a), c(l)
      } this.expandGroup = function (e, n) {
        if (null != (e = this.getGroup(e)) && e.collapsed) {
          const i = e.getEl();if (c(e, !0), e.shouldProxy()) {
            const o = function (t, n) {
              for (let i = 0;i < t.length;i++) {
                const o = t[i];d(o, n, e)
              }
            };o(e.connections.source, 0), o(e.connections.target, 1)
          }e.collapsed = !1, t.addClass(i, 'jtk-group-expanded'), t.removeClass(i, 'jtk-group-collapsed'), t.revalidate(i), this.repaintGroup(e), n || t.fire('group:expand', { group: e })
        }
      }, this.repaintGroup = function (e) {
        for (let n = (e = this.getGroup(e)).getMembers(), i = 0;i < n.length;i++)t.revalidate(n[i])
      }, this.updateConnectionsForGroup = p, this.refreshAllGroups = function () {
        for (const e in n)p(n[e]), t.dragManager.updateOffsets(t.getId(n[e].getEl()))
      }
    }; const u = function (n, r) {
      const a = this; const l = r.el;this.getEl = function () {
        return l
      }, this.id = r.id || e.uuid(), l._isJsPlumbGroup = !0;const u = this.getDragArea = function () {
        const t = n.getSelector(l, '[jtk-group-content]');return t && t.length > 0 ? t[0] : l
      }; const c = !0 === r.ghost; const h = c || !0 === r.constrain; const d = !1 !== r.revert; const p = !0 === r.orphan; const f = !0 === r.prune; const g = !0 === r.dropOverride; const m = !1 !== r.proxied; const v = [];if (this.connections = { source: [], target: [], internal: [] }, this.getAnchor = function (t, e) {
        return r.anchor || 'Continuous'
      }, this.getEndpoint = function (t, e) {
        return r.endpoint || ['Dot', { radius: 10 }]
      }, this.collapsed = !1, !1 !== r.draggable) {
        const y = { drag () {
          for (let t = 0;t < v.length;t++)n.draw(v[t])
        }, stop (t) {
          n.fire('groupDragStop', jsPlumb.extend(t, { group: a }))
        }, scope: '_jsPlumbGroupDrag' };r.dragOptions && t.jsPlumb.extend(y, r.dragOptions), n.draggable(r.el, y)
      }!1 !== r.droppable && n.droppable(r.el, { drop (t) {
        const e = t.drag.el;if (!e._isJsPlumbGroup) {
          const i = e._jsPlumbGroup;if (i !== a) {
            if (null != i && i.overrideDrop(e, a)) return;n.getGroupManager().addToGroup(a, e, !1)
          }
        }
      } });const b = function (t, e) {
        for (let n = null == t.nodeType ? t : [t], i = 0;i < n.length;i++)e(n[i])
      };function P (t, e) {
        const i = (function (t) {
          return t.offsetParent
        }(t)); const o = n.getSize(i); const s = n.getSize(t); const r = e[0]; const a = r + s[0]; const l = e[1]; const u = l + s[1];return a > 0 && r < o[0] && u > 0 && l < o[1]
      } function x (t) {
        const e = n.getId(t); const i = n.getOffset(t);return t.parentNode.removeChild(t), n.getContainer().appendChild(t), n.setPosition(t, i), j(t), n.dragManager.clearParent(t, e), [e, i]
      } function C (t) {
        const e = [];function i (t, e, i) {
          let o = null;if (!P(t, [e, i])) {
            const s = t._jsPlumbGroup;f ? n.remove(t) : o = x(t), s.remove(t)
          } return o
        } for (let o = 0;o < t.selection.length;o++)e.push(i(t.selection[o][0], t.selection[o][1].left, t.selection[o][1].top));return 1 === e.length ? e[0] : e
      } function _ (t) {
        const e = n.getId(t);n.revalidate(t), n.dragManager.revalidateParent(t, e)
      } function j (t) {
        t._katavorioDrag && ((f || p) && t._katavorioDrag.off(i, C), f || p || !d || (t._katavorioDrag.off(o, _), t._katavorioDrag.setRevert(null)))
      } function E (t) {
        t._katavorioDrag && ((f || p) && t._katavorioDrag.on(i, C), h && t._katavorioDrag.setConstrain(!0), c && t._katavorioDrag.setUseGhostProxy(!0), f || p || !d || (t._katavorioDrag.on(o, _), t._katavorioDrag.setRevert((t, e) => !P(t, e))))
      } this.overrideDrop = function (t, e) {
        return g && (d || f || p)
      }, this.add = function (t, e) {
        const i = u();b(t, (t) => {
          if (null != t._jsPlumbGroup) {
            if (t._jsPlumbGroup === a) return;t._jsPlumbGroup.remove(t, !0, e, !1)
          }t._jsPlumbGroup = a, v.push(t), n.isAlreadyDraggable(t) && E(t), t.parentNode !== i && i.appendChild(t)
        }), n.getGroupManager().updateConnectionsForGroup(a)
      }, this.remove = function (t, i, o, s, r) {
        b(t, (t) => {
          if (t._jsPlumbGroup === a) {
            if (delete t._jsPlumbGroup, e.removeWithFunction(v, (e) => e === t), i) try {
              a.getDragArea().removeChild(t)
            } catch (t) {
              jsPlumbUtil.log(`Could not remove element from Group ${t}`)
            } if (j(t), !o) {
              const s = { group: a, el: t };r && (s.targetGroup = r), n.fire('group:removeMember', s)
            }
          }
        }), s || n.getGroupManager().updateConnectionsForGroup(a)
      }, this.removeAll = function (t, e) {
        for (let i = 0, o = v.length;i < o;i++) {
          const s = v[0];a.remove(s, t, e, !0), n.remove(s, !0)
        }v.length = 0, n.getGroupManager().updateConnectionsForGroup(a)
      }, this.orphanAll = function () {
        for (var t = {}, e = 0;e < v.length;e++) {
          const n = x(v[e]);t[n[0]] = n[1]
        } return v.length = 0, t
      }, this.getMembers = function () {
        return v
      }, l[s] = this, n.bind('elementDraggable', (t) => {
        t.el._jsPlumbGroup === this && E(t.el)
      }), this.shouldProxy = function () {
        return m
      }, n.getGroupManager().addGroup(this)
    };n.prototype.addGroup = function (t) {
      const e = this;if (e._groups = e._groups || {}, null != e._groups[t.id]) throw new TypeError(`cannot create Group [${t.id}]; a Group with that ID exists`);if (null != t.el[s]) throw new TypeError(`cannot create Group [${t.id}]; the given element is already a Group`);const n = new u(e, t);return e._groups[n.id] = n, t.collapsed && this.collapseGroup(n), n
    }, n.prototype.addToGroup = function (t, e, n) {
      const i = function (e) {
        const i = this.getId(e);this.manage(i, e), this.getGroupManager().addToGroup(t, e, n)
      }.bind(this);if (Array.isArray(e)) for (let o = 0;o < e.length;o++)i(e[o]);else i(e)
    }, n.prototype.removeFromGroup = function (t, e, n) {
      this.getGroupManager().removeFromGroup(t, e, n), this.getContainer().appendChild(e)
    }, n.prototype.removeGroup = function (t, e, n, i) {
      return this.getGroupManager().removeGroup(t, e, n, i)
    }, n.prototype.removeAllGroups = function (t, e, n) {
      this.getGroupManager().removeAllGroups(t, e, n)
    }, n.prototype.getGroup = function (t) {
      return this.getGroupManager().getGroup(t)
    }, n.prototype.getGroups = function () {
      return this.getGroupManager().getGroups()
    }, n.prototype.expandGroup = function (t) {
      this.getGroupManager().expandGroup(t)
    }, n.prototype.collapseGroup = function (t) {
      this.getGroupManager().collapseGroup(t)
    }, n.prototype.repaintGroup = function (t) {
      this.getGroupManager().repaintGroup(t)
    }, n.prototype.toggleGroup = function (t) {
      null != (t = this.getGroupManager().getGroup(t)) && this.getGroupManager()[t.collapsed ? 'expandGroup' : 'collapseGroup'](t)
    }, n.prototype.getGroupManager = function () {
      let t = this._groupManager;return null == t && (t = this._groupManager = new l(this)), t
    }, n.prototype.removeGroupManager = function () {
      delete this._groupManager
    }, n.prototype.getGroupFor = function (t) {
      if (t = this.getElement(t)) {
        for (var e = this.getContainer(), n = !1, i = null;!n;)null == t || t === e ? n = !0 : t[s] ? (i = t[s], n = !0) : t = t.parentNode;return i
      }
    }
  }.call('undefined' !== typeof window ? window : s), function () {
    const t = this.jsPlumb; const e = this.jsPlumbUtil;t.Connectors.Flowchart = function (e) {
      this.type = 'Flowchart', (e = e || {}).stub = null == e.stub ? 30 : e.stub;let n; const i = t.Connectors.AbstractConnector.apply(this, arguments); const o = null == e.midpoint || isNaN(e.midpoint) ? .5 : e.midpoint; const s = !0 === e.alwaysRespectStubs; let r = null; let a = null; const l = null != e.cornerRadius ? e.cornerRadius : 0; const u = (e.loopbackRadius, function (t) {
        return t < 0 ? -1 : 0 === t ? 0 : 1
      }); const c = function (t) {
        return [u(t[2] - t[0]), u(t[3] - t[1])]
      }; const h = function (t, e, n, i) {
        if (r !== e || a !== n) {
          const o = null == r ? i.sx : r; const s = null == a ? i.sy : a; const l = o === e ? 'v' : 'h';r = e, a = n, t.push([o, s, e, n, l])
        }
      }; const d = function (t) {
        return Math.sqrt(Math.pow(t[0] - t[2], 2) + Math.pow(t[1] - t[3], 2))
      }; const p = function (t) {
        const e = [];return e.push.apply(e, t), e
      };this.midpoint = o, this._compute = function (t, e) {
        n = [], r = null, a = null;const u = function () {
          return [t.startStubX, t.startStubY, t.endStubX, t.endStubY]
        }; const f = { perpendicular: u, orthogonal: u, opposite (e) {
          const n = t; const i = 'x' === e ? 0 : 1;return !s && { x () {
            return 1 === n.so[i] && (n.startStubX > n.endStubX && n.tx > n.startStubX || n.sx > n.endStubX && n.tx > n.sx) || -1 === n.so[i] && (n.startStubX < n.endStubX && n.tx < n.startStubX || n.sx < n.endStubX && n.tx < n.sx)
          }, y () {
            return 1 === n.so[i] && (n.startStubY > n.endStubY && n.ty > n.startStubY || n.sy > n.endStubY && n.ty > n.sy) || -1 === n.so[i] && (n.startStubY < n.endStubY && n.ty < n.startStubY || n.sy < n.endStubY && n.ty < n.sy)
          } }[e]() ? { x: [(t.sx + t.tx) / 2, t.startStubY, (t.sx + t.tx) / 2, t.endStubY], y: [t.startStubX, (t.sy + t.ty) / 2, t.endStubX, (t.sy + t.ty) / 2] }[e] : [t.startStubX, t.startStubY, t.endStubX, t.endStubY]
        } }[t.anchorOrientation](t.sourceAxis); const g = 'x' === t.sourceAxis ? 0 : 1; const m = 'x' === t.sourceAxis ? 1 : 0; const v = f[g]; const y = f[m]; const b = f[g + 2]; const P = f[m + 2];h(n, f[0], f[1], t);const x = t.startStubX + (t.endStubX - t.startStubX) * o; const C = t.startStubY + (t.endStubY - t.startStubY) * o; const _ = { x: [0, 1], y: [1, 0] }; const j = { perpendicular (e) {
          const n = t; const i = { x: [[n.startStubX, n.endStubX], null, [n.endStubX, n.startStubX]], y: [[n.startStubY, n.endStubY], null, [n.endStubY, n.startStubY]] }; const o = { x: [[x, n.startStubY], [x, n.endStubY]], y: [[n.startStubX, C], [n.endStubX, C]] }; const s = { x: [[n.endStubX, n.startStubY]], y: [[n.startStubX, n.endStubY]] }; const r = { x: [[n.startStubX, n.endStubY], [n.endStubX, n.endStubY]], y: [[n.endStubX, n.startStubY], [n.endStubX, n.endStubY]] }; const a = { x: [[n.startStubX, C], [n.endStubX, C], [n.endStubX, n.endStubY]], y: [[x, n.startStubY], [x, n.endStubY], [n.endStubX, n.endStubY]] }; const l = { x: [n.startStubY, n.endStubY], y: [n.startStubX, n.endStubX] }; const u = _[e][0]; const c = _[e][1]; const h = n.so[u] + 1; const d = n.to[c] + 1; const p = -1 === n.to[c] && l[e][1] < l[e][0] || 1 === n.to[c] && l[e][1] > l[e][0]; const f = i[e][h][0]; const g = i[e][h][1]; const m = { x: [[[1, 2, 3, 4], null, [2, 1, 4, 3]], null, [[4, 3, 2, 1], null, [3, 4, 1, 2]]], y: [[[3, 2, 1, 4], null, [2, 3, 4, 1]], null, [[4, 1, 2, 3], null, [1, 4, 3, 2]]] }[e][h][d];return n.segment === m[3] || n.segment === m[2] && p ? o[e] : n.segment === m[2] && g < f ? s[e] : n.segment === m[2] && g >= f || n.segment === m[1] && !p ? a[e] : n.segment === m[0] || n.segment === m[1] && p ? r[e] : void 0
        }, orthogonal (e, n, i, o, s) {
          const r = t; const a = { x: -1 === r.so[0] ? Math.min(n, o) : Math.max(n, o), y: -1 === r.so[1] ? Math.min(n, o) : Math.max(n, o) }[e];return { x: [[a, i], [a, s], [o, s]], y: [[i, a], [s, a], [s, o]] }[e]
        }, opposite (n, o, s, r) {
          const a = t; const l = { x: 'y', y: 'x' }[n]; const u = { x: 'height', y: 'width' }[n]; const c = a[`is${n.toUpperCase()}GreaterThanStubTimes2`];if (e.sourceEndpoint.elementId === e.targetEndpoint.elementId) {
            const h = s + (1 - e.sourceEndpoint.anchor[l]) * e.sourceInfo[u] + i.maxStub;return { x: [[o, h], [r, h]], y: [[h, o], [h, r]] }[n]
          } return !c || 1 === a.so[g] && o > r || -1 === a.so[g] && o < r ? { x: [[o, C], [r, C]], y: [[x, o], [x, r]] }[n] : 1 === a.so[g] && o < r || -1 === a.so[g] && o > r ? { x: [[x, a.sy], [x, a.ty]], y: [[a.sx, C], [a.tx, C]] }[n] : void 0
        } }[t.anchorOrientation](t.sourceAxis, v, y, b, P);if (j) for (let E = 0;E < j.length;E++)h(n, j[E][0], j[E][1], t);h(n, f[2], f[3], t), h(n, t.tx, t.ty, t), (function (t, e, n) {
          for (var o, s, r, a = null, u = 0;u < e.length - 1;u++) {
            if (a = a || p(e[u]), o = p(e[u + 1]), s = c(a), r = c(o), l > 0 && a[4] !== o[4]) {
              const h = Math.min(d(a), d(o)); const f = Math.min(l, h / 2);a[2] -= s[0] * f, a[3] -= s[1] * f, o[0] += r[0] * f, o[1] += r[1] * f;const g = s[1] === r[0] && 1 === r[0] || s[1] === r[0] && 0 === r[0] && s[0] !== r[1] || s[1] === r[0] && -1 === r[0]; const m = (o[1] > a[3] ? 1 : -1) == (o[0] > a[2] ? 1 : -1); const v = m && g || !m && !g ? o[0] : a[2]; const y = m && g || !m && !g ? a[3] : o[1];i.addSegment(t, 'Straight', { x1: a[0], y1: a[1], x2: a[2], y2: a[3] }), i.addSegment(t, 'Arc', { r: f, x1: a[2], y1: a[3], x2: o[0], y2: o[1], cx: v, cy: y, ac: g })
            } else {
              const b = a[2] === a[0] ? 0 : a[2] > a[0] ? n.lw / 2 : -n.lw / 2; const P = a[3] === a[1] ? 0 : a[3] > a[1] ? n.lw / 2 : -n.lw / 2;i.addSegment(t, 'Straight', { x1: a[0] - b, y1: a[1] - P, x2: a[2] + b, y2: a[3] + P })
            }a = o
          }null != o && i.addSegment(t, 'Straight', { x1: o[0], y1: o[1], x2: o[2], y2: o[3] })
        }(this, n, t))
      }
    }, e.extend(t.Connectors.Flowchart, t.Connectors.AbstractConnector)
  }.call('undefined' !== typeof window ? window : s), function () {
    const t = this.jsPlumb; const e = this.jsPlumbUtil;t.Connectors.AbstractBezierConnector = function (e) {
      let n; const i = !1 !== (e = e || {}).showLoopback; const o = (e.curviness, e.margin || 5); const s = (e.proximityLimit, e.orientation && 'clockwise' === e.orientation); const r = e.loopbackRadius || 25;return this._compute = function (t, e) {
        const a = e.sourcePos; const l = e.targetPos; let u = Math.abs(a[0] - l[0]); let c = Math.abs(a[1] - l[1]);if (i && e.sourceEndpoint.elementId === e.targetEndpoint.elementId) {
          const h = e.sourcePos[0]; const d = e.sourcePos[1] - o; const p = h; const f = d - r; const g = p - r; const m = f - r;u = 2 * r, c = 2 * r, t.points[0] = g, t.points[1] = m, t.points[2] = u, t.points[3] = c, n.addSegment(this, 'Arc', { loopback: !0, x1: h - g + 4, y1: d - m, startAngle: 0, endAngle: 2 * Math.PI, r, ac: !s, x2: h - g - 4, y2: d - m, cx: p - g, cy: f - m })
        } else this._computeBezier(t, e, a, l, u, c)
      }, n = t.Connectors.AbstractConnector.apply(this, arguments)
    }, e.extend(t.Connectors.AbstractBezierConnector, t.Connectors.AbstractConnector);const n = function (e) {
      e = e || {}, this.type = 'Bezier';const n = t.Connectors.AbstractBezierConnector.apply(this, arguments); const i = e.curviness || 150;this.getCurviness = function () {
        return i
      }, this._findControlPoint = function (t, e, n, o, s, r, a) {
        const l = [];return r[0] !== a[0] || r[1] === a[1] ? (0 === a[0] ? l.push(n[0] < e[0] ? t[0] + 10 : t[0] - 10) : l.push(t[0] + i * a[0]), 0 === a[1] ? l.push(n[1] < e[1] ? t[1] + 10 : t[1] - 10) : l.push(t[1] + i * r[1])) : (0 === r[0] ? l.push(e[0] < n[0] ? t[0] + 10 : t[0] - 10) : l.push(t[0] - i * r[0]), 0 === r[1] ? l.push(e[1] < n[1] ? t[1] + 10 : t[1] - 10) : l.push(t[1] + i * a[1])), l
      }, this._computeBezier = function (t, e, i, o, s, r) {
        let a; let l; const u = i[0] < o[0] ? s : 0; const c = i[1] < o[1] ? r : 0; const h = i[0] < o[0] ? 0 : s; const d = i[1] < o[1] ? 0 : r;a = this._findControlPoint([u, c], i, o, e.sourceEndpoint, e.targetEndpoint, t.so, t.to), l = this._findControlPoint([h, d], o, i, e.targetEndpoint, e.sourceEndpoint, t.to, t.so), n.addSegment(this, 'Bezier', { x1: u, y1: c, x2: h, y2: d, cp1x: a[0], cp1y: a[1], cp2x: l[0], cp2y: l[1] })
      }
    };t.Connectors.Bezier = n, e.extend(n, t.Connectors.AbstractBezierConnector)
  }.call('undefined' !== typeof window ? window : s), function () {
    const t = this.jsPlumb; const e = this.jsPlumbUtil; const n = function (e) {
      e = e || {}, this.type = 'StateMachine';let n; const i = t.Connectors.AbstractBezierConnector.apply(this, arguments); const o = e.curviness || 10; const s = e.margin || 5; const r = e.proximityLimit || 80;e.orientation && e.orientation;this._computeBezier = function (t, e, a, l, u, c) {
        let h = e.sourcePos[0] < e.targetPos[0] ? 0 : u; let d = e.sourcePos[1] < e.targetPos[1] ? 0 : c; let p = e.sourcePos[0] < e.targetPos[0] ? u : 0; let f = e.sourcePos[1] < e.targetPos[1] ? c : 0;0 === e.sourcePos[2] && (h -= s), 1 === e.sourcePos[2] && (h += s), 0 === e.sourcePos[3] && (d -= s), 1 === e.sourcePos[3] && (d += s), 0 === e.targetPos[2] && (p -= s), 1 === e.targetPos[2] && (p += s), 0 === e.targetPos[3] && (f -= s), 1 === e.targetPos[3] && (f += s);let g; let m; let v; let y; let b; let P; let x; let C; const _ = (h + p) / 2; const j = (d + f) / 2; const E = (P = d, C = f, (b = h) <= (x = p) && C <= P ? 1 : b <= x && P <= C ? 2 : x <= b && C >= P ? 3 : 4); const S = Math.sqrt(Math.pow(p - h, 2) + Math.pow(f - d, 2));g = (n = (function (t, e, n, i, o, s, r, a, l) {
          return a <= l ? [t, e] : 1 === n ? i[3] <= 0 && o[3] >= 1 ? [t + (i[2] < .5 ? -1 * s : s), e] : i[2] >= 1 && o[2] <= 0 ? [t, e + (i[3] < .5 ? -1 * r : r)] : [t + -1 * s, e + -1 * r] : 2 === n ? i[3] >= 1 && o[3] <= 0 ? [t + (i[2] < .5 ? -1 * s : s), e] : i[2] >= 1 && o[2] <= 0 ? [t, e + (i[3] < .5 ? -1 * r : r)] : [t + s, e + -1 * r] : 3 === n ? i[3] >= 1 && o[3] <= 0 ? [t + (i[2] < .5 ? -1 * s : s), e] : i[2] <= 0 && o[2] >= 1 ? [t, e + (i[3] < .5 ? -1 * r : r)] : [t + -1 * s, e + -1 * r] : 4 === n ? i[3] <= 0 && o[3] >= 1 ? [t + (i[2] < .5 ? -1 * s : s), e] : i[2] <= 0 && o[2] >= 1 ? [t, e + (i[3] < .5 ? -1 * r : r)] : [t + s, e + -1 * r] : void 0
        }(_, j, E, e.sourcePos, e.targetPos, o, o, S, r)))[0], m = n[0], v = n[1], y = n[1], i.addSegment(this, 'Bezier', { x1: p, y1: f, x2: h, y2: d, cp1x: g, cp1y: v, cp2x: m, cp2y: y })
      }
    };t.Connectors.StateMachine = n, e.extend(n, t.Connectors.AbstractBezierConnector)
  }.call('undefined' !== typeof window ? window : s), function () {
    const t = this.jsPlumb; const e = this.jsPlumbUtil; const n = function (e) {
      this.type = 'Straight';const n = t.Connectors.AbstractConnector.apply(this, arguments);this._compute = function (t, e) {
        n.addSegment(this, 'Straight', { x1: t.sx, y1: t.sy, x2: t.startStubX, y2: t.startStubY }), n.addSegment(this, 'Straight', { x1: t.startStubX, y1: t.startStubY, x2: t.endStubX, y2: t.endStubY }), n.addSegment(this, 'Straight', { x1: t.endStubX, y1: t.endStubY, x2: t.tx, y2: t.ty })
      }
    };t.Connectors.Straight = n, e.extend(n, t.Connectors.AbstractConnector)
  }.call('undefined' !== typeof window ? window : s), function () {
    const t = this.jsPlumb; const e = this.jsPlumbUtil; const n = { 'stroke-linejoin': 'stroke-linejoin', 'stroke-dashoffset': 'stroke-dashoffset', 'stroke-linecap': 'stroke-linecap' }; const i = 'http://www.w3.org/2000/svg'; const o = function (t, e) {
      for (const n in e)t.setAttribute(n, `${e[n]}`)
    }; const s = function (e, n) {
      return (n = n || {}).version = '1.1', n.xmlns = i, t.createElementNS(i, e, null, null, n)
    }; const r = function (t) {
      return `position:absolute;left:${t[0]}px;top:${t[1]}px`
    }; const a = function (t) {
      for (let e = t.querySelectorAll(' defs,linearGradient,radialGradient'), n = 0;n < e.length;n++)e[n].parentNode.removeChild(e[n])
    }; const l = function (t, e, i, o, r) {
      if (e.setAttribute('fill', i.fill ? i.fill : 'none'), e.setAttribute('stroke', i.stroke ? i.stroke : 'none'), i.gradient ? (function (t, e, n, i, o) {
        let r; const l = `jsplumb_gradient_${o._jsPlumb.instance.idstamp()}`;a(t), r = n.gradient.offset ? s('radialGradient', { id: l }) : s('linearGradient', { id: l, gradientUnits: 'userSpaceOnUse' });const u = s('defs');t.appendChild(u), u.appendChild(r);for (let c = 0;c < n.gradient.stops.length;c++) {
          const h = 1 === o.segment || 2 === o.segment ? c : n.gradient.stops.length - 1 - c; const d = n.gradient.stops[h][1]; const p = s('stop', { offset: `${Math.floor(100 * n.gradient.stops[c][0])}%`, 'stop-color': d });r.appendChild(p)
        } const f = n.stroke ? 'stroke' : 'fill';e.setAttribute(f, `url(#${l})`)
      }(t, e, i, 0, r)) : (a(t), e.setAttribute('style', '')), i.strokeWidth && e.setAttribute('stroke-width', i.strokeWidth), i.dashstyle && i.strokeWidth && !i['stroke-dasharray']) {
        const l = -1 === i.dashstyle.indexOf(',') ? ' ' : ','; const u = i.dashstyle.split(l); let c = '';u.forEach((t) => {
          c += Math.floor(t * i.strokeWidth) + l
        }), e.setAttribute('stroke-dasharray', c)
      } else i['stroke-dasharray'] && e.setAttribute('stroke-dasharray', i['stroke-dasharray']);for (const h in n)i[h] && e.setAttribute(n[h], i[h])
    }; const u = function (t, e, n) {
      t.childNodes.length > n ? t.insertBefore(e, t.childNodes[n]) : t.appendChild(e)
    };e.svg = { node: s, attr: o, pos: r };const c = function (n) {
      const i = n.pointerEventsSpec || 'all'; const a = {};t.jsPlumbUIComponent.apply(this, n.originalArgs), this.canvas = null, this.path = null, this.svg = null, this.bgCanvas = null;const l = `${n.cssClass} ${n.originalArgs[0].cssClass || ''}`; const u = { style: '', width: 0, height: 0, 'pointer-events': i, position: 'absolute' };this.svg = s('svg', u), n.useDivWrapper ? (this.canvas = t.createElement('div', { position: 'absolute' }), e.sizeElement(this.canvas, 0, 0, 1, 1), this.canvas.className = l) : (o(this.svg, { class: l }), this.canvas = this.svg), n._jsPlumb.appendElement(this.canvas, n.originalArgs[0].parent), n.useDivWrapper && this.canvas.appendChild(this.svg);const c = [this.canvas];return this.getDisplayElements = function () {
        return c
      }, this.appendDisplayElement = function (t) {
        c.push(t)
      }, this.paint = function (t, i, s) {
        if (null != t) {
          let l; const u = [this.x, this.y]; const c = [this.w, this.h];null != s && (s.xmin < 0 && (u[0] += s.xmin), s.ymin < 0 && (u[1] += s.ymin), c[0] = s.xmax + (s.xmin < 0 ? -s.xmin : 0), c[1] = s.ymax + (s.ymin < 0 ? -s.ymin : 0)), n.useDivWrapper ? (e.sizeElement(this.canvas, u[0], u[1], c[0] > 0 ? c[0] : 1, c[1] > 0 ? c[1] : 1), u[0] = 0, u[1] = 0, l = r([0, 0])) : l = r([u[0], u[1]]), a.paint.apply(this, arguments), o(this.svg, { style: l, width: c[0] || 1, height: c[1] || 1 })
        }
      }, { renderer: a }
    };e.extend(c, t.jsPlumbUIComponent, { cleanup (t) {
      t || null == this.typeId ? (this.canvas && (this.canvas._jsPlumb = null), this.svg && (this.svg._jsPlumb = null), this.bgCanvas && (this.bgCanvas._jsPlumb = null), this.canvas && this.canvas.parentNode && this.canvas.parentNode.removeChild(this.canvas), this.bgCanvas && this.bgCanvas.parentNode && this.canvas.parentNode.removeChild(this.canvas), this.svg = null, this.canvas = null, this.path = null, this.group = null, this._jsPlumb = null) : (this.canvas && this.canvas.parentNode && this.canvas.parentNode.removeChild(this.canvas), this.bgCanvas && this.bgCanvas.parentNode && this.bgCanvas.parentNode.removeChild(this.bgCanvas))
    }, reattach (t) {
      const e = t.getContainer();this.canvas && null == this.canvas.parentNode && e.appendChild(this.canvas), this.bgCanvas && null == this.bgCanvas.parentNode && e.appendChild(this.bgCanvas)
    }, setVisible (t) {
      this.canvas && (this.canvas.style.display = t ? 'block' : 'none')
    } }), t.ConnectorRenderers.svg = function (e) {
      const n = this;c.apply(this, [{ cssClass: e._jsPlumb.connectorClass, originalArgs: arguments, pointerEventsSpec: 'none', _jsPlumb: e._jsPlumb }]).renderer.paint = function (i, r, a) {
        const c = n.getSegments(); const h = [0, 0];if (a.xmin < 0 && (h[0] = -a.xmin), a.ymin < 0 && (h[1] = -a.ymin), c.length > 0) {
          const d = { d: n.getPathData(), transform: `translate(${h[0]},${h[1]})`, 'pointer-events': e['pointer-events'] || 'visibleStroke' }; let p = null;n.x, n.y, n.w, n.h;if (i.outlineStroke) {
            const f = i.outlineWidth || 1; const g = i.strokeWidth + 2 * f;delete(p = t.extend({}, i)).gradient, p.stroke = i.outlineStroke, p.strokeWidth = g, null == n.bgPath ? (n.bgPath = s('path', d), t.addClass(n.bgPath, t.connectorOutlineClass), u(n.svg, n.bgPath, 0)) : o(n.bgPath, d), l(n.svg, n.bgPath, p, 0, n)
          }null == n.path ? (n.path = s('path', d), u(n.svg, n.path, i.outlineStroke ? 1 : 0)) : o(n.path, d), l(n.svg, n.path, i, 0, n)
        }
      }
    }, e.extend(t.ConnectorRenderers.svg, c);const h = t.SvgEndpoint = function (e) {
      c.apply(this, [{ cssClass: e._jsPlumb.endpointClass, originalArgs: arguments, pointerEventsSpec: 'all', useDivWrapper: !0, _jsPlumb: e._jsPlumb }]).renderer.paint = function (e) {
        const n = t.extend({}, e);n.outlineStroke && (n.stroke = n.outlineStroke), null == this.node ? (this.node = this.makeNode(n), this.svg.appendChild(this.node)) : null != this.updateNode && this.updateNode(this.node), l(this.svg, this.node, n, (this.x, this.y, this.w, this.h), this), r(this.node, (this.x, this.y))
      }.bind(this)
    };e.extend(h, c), t.Endpoints.svg.Dot = function () {
      t.Endpoints.Dot.apply(this, arguments), h.apply(this, arguments), this.makeNode = function (t) {
        return s('circle', { cx: this.w / 2, cy: this.h / 2, r: this.radius })
      }, this.updateNode = function (t) {
        o(t, { cx: this.w / 2, cy: this.h / 2, r: this.radius })
      }
    }, e.extend(t.Endpoints.svg.Dot, [t.Endpoints.Dot, h]), t.Endpoints.svg.Rectangle = function () {
      t.Endpoints.Rectangle.apply(this, arguments), h.apply(this, arguments), this.makeNode = function (t) {
        return s('rect', { width: this.w, height: this.h })
      }, this.updateNode = function (t) {
        o(t, { width: this.w, height: this.h })
      }
    }, e.extend(t.Endpoints.svg.Rectangle, [t.Endpoints.Rectangle, h]), t.Endpoints.svg.Image = t.Endpoints.Image, t.Endpoints.svg.Blank = t.Endpoints.Blank, t.Overlays.svg.Label = t.Overlays.Label, t.Overlays.svg.Custom = t.Overlays.Custom;const d = function (e, n) {
      e.apply(this, n), t.jsPlumbUIComponent.apply(this, n), this.isAppendedAtTopLevel = !1, this.path = null, this.paint = function (t, e) {
        if (t.component.svg && e) {
          null == this.path && (this.path = s('path', { 'pointer-events': 'all' }), t.component.svg.appendChild(this.path), this.elementCreated && this.elementCreated(this.path, t.component), this.canvas = t.component.svg);const r = n && 1 === n.length && n[0].cssClass || ''; const a = [0, 0];e.xmin < 0 && (a[0] = -e.xmin), e.ymin < 0 && (a[1] = -e.ymin), o(this.path, { d: i(t.d), class: r, stroke: t.stroke ? t.stroke : null, fill: t.fill ? t.fill : null, transform: `translate(${a[0]},${a[1]})` })
        }
      };var i = function (t) {
        return isNaN(t.cxy.x) || isNaN(t.cxy.y) ? '' : `M${t.hxy.x},${t.hxy.y} L${t.tail[0].x},${t.tail[0].y} L${t.cxy.x},${t.cxy.y} L${t.tail[1].x},${t.tail[1].y} L${t.hxy.x},${t.hxy.y}`
      };this.transfer = function (t) {
        t.canvas && this.path && this.path.parentNode && (this.path.parentNode.removeChild(this.path), t.canvas.appendChild(this.path))
      }
    }; const p = { cleanup (t) {
      null != this.path && (t ? this._jsPlumb.instance.removeElement(this.path) : this.path.parentNode && this.path.parentNode.removeChild(this.path))
    }, reattach (t, e) {
      this.path && e.canvas && e.canvas.appendChild(this.path)
    }, setVisible (t) {
      null != this.path && (this.path.style.display = t ? 'block' : 'none')
    } };e.extend(d, [t.jsPlumbUIComponent, t.Overlays.AbstractOverlay]), t.Overlays.svg.Arrow = function () {
      d.apply(this, [t.Overlays.Arrow, arguments])
    }, e.extend(t.Overlays.svg.Arrow, [t.Overlays.Arrow, d], p), t.Overlays.svg.PlainArrow = function () {
      d.apply(this, [t.Overlays.PlainArrow, arguments])
    }, e.extend(t.Overlays.svg.PlainArrow, [t.Overlays.PlainArrow, d], p), t.Overlays.svg.Diamond = function () {
      d.apply(this, [t.Overlays.Diamond, arguments])
    }, e.extend(t.Overlays.svg.Diamond, [t.Overlays.Diamond, d], p), t.Overlays.svg.GuideLines = function () {
      let e; let n; let i = null; const r = this;t.Overlays.GuideLines.apply(this, arguments), this.paint = function (t, l) {
        null == i && (i = s('path'), t.connector.svg.appendChild(i), r.attachListeners(i, t.connector), r.attachListeners(i, r), e = s('path'), t.connector.svg.appendChild(e), r.attachListeners(e, t.connector), r.attachListeners(e, r), n = s('path'), t.connector.svg.appendChild(n), r.attachListeners(n, t.connector), r.attachListeners(n, r));const u = [0, 0];l.xmin < 0 && (u[0] = -l.xmin), l.ymin < 0 && (u[1] = -l.ymin), o(i, { d: a(t.head, t.tail), stroke: 'red', fill: null, transform: `translate(${u[0]},${u[1]})` }), o(e, { d: a(t.tailLine[0], t.tailLine[1]), stroke: 'blue', fill: null, transform: `translate(${u[0]},${u[1]})` }), o(n, { d: a(t.headLine[0], t.headLine[1]), stroke: 'green', fill: null, transform: `translate(${u[0]},${u[1]})` })
      };var a = function (t, e) {
        return `M ${t.x},${t.y} L${e.x},${e.y}`
      }
    }, e.extend(t.Overlays.svg.GuideLines, t.Overlays.GuideLines)
  }.call('undefined' !== typeof window ? window : s), function () {
    const t = this; const e = t.jsPlumb; const n = t.jsPlumbUtil; const i = t.Katavorio; const o = t.Biltong; const s = function (t, n) {
      const s = `_katavorio_${n = n || 'main'}`; let r = t[s]; const a = t.getEventManager();return r || ((r = new i({ bind: a.on, unbind: a.off, getSize: e.getSize, getConstrainingRectangle (t) {
        return [t.parentNode.scrollWidth, t.parentNode.scrollHeight]
      }, getPosition (e, n) {
        const i = t.getOffset(e, n, e._katavorioDrag ? e.offsetParent : null);return [i.left, i.top]
      }, setPosition (t, e) {
        t.style.left = `${e[0]}px`, t.style.top = `${e[1]}px`
      }, addClass: e.addClass, removeClass: e.removeClass, intersects: o.intersects, indexOf (t, e) {
        return t.indexOf(e)
      }, scope: t.getDefaultScope(), css: { noSelect: t.dragSelectClass, droppable: 'jtk-droppable', draggable: 'jtk-draggable', drag: 'jtk-drag', selected: 'jtk-drag-selected', active: 'jtk-drag-active', hover: 'jtk-drag-hover', ghostProxy: 'jtk-ghost-proxy' } })).setZoom(t.getZoom()), t[s] = r, t.bind('zoom', r.setZoom)), r
    }; const r = function (t, e) {
      if (null == e) return [0, 0];const n = h(e); const i = c(n, 0);return [i[`${t}X`], i[`${t}Y`]]
    }; const a = r.bind(this, 'page'); const l = r.bind(this, 'screen'); const u = r.bind(this, 'client'); var c = function (t, e) {
      return t.item ? t.item(e) : t[e]
    }; var h = function (t) {
      return t.touches && t.touches.length > 0 ? t.touches : t.changedTouches && t.changedTouches.length > 0 ? t.changedTouches : t.targetTouches && t.targetTouches.length > 0 ? t.targetTouches : [t]
    }; const d = function (t) {
      let e = {}; let n = []; let i = {}; let o = {}; const s = {};this.register = function (r) {
        let a; const l = t.getId(r);e[l] || (e[l] = r, n.push(r), i[l] = {});var u = function (e) {
          if (e) for (let n = 0;n < e.childNodes.length;n++) if (3 !== e.childNodes[n].nodeType && 8 !== e.childNodes[n].nodeType) {
            const c = jsPlumb.getElement(e.childNodes[n]); const h = t.getId(e.childNodes[n], null, !0);if (h && o[h] && o[h] > 0) {
              a || (a = t.getOffset(r));const d = t.getOffset(c);i[l][h] = { id: h, offset: { left: d.left - a.left, top: d.top - a.top } }, s[h] = l
            }u(e.childNodes[n])
          }
        };u(r)
      }, this.updateOffsets = function (e, n) {
        if (null != e) {
          n = n || {};let o; const r = jsPlumb.getElement(e); const a = t.getId(r); const l = i[a];if (l) for (const u in l) if (l.hasOwnProperty(u)) {
            const c = jsPlumb.getElement(u); const h = n[u] || t.getOffset(c);if (null == c.offsetParent && null != i[a][u]) continue;o || (o = t.getOffset(r)), i[a][u] = { id: u, offset: { left: h.left - o.left, top: h.top - o.top } }, s[u] = a
          }
        }
      }, this.endpointAdded = function (n, r) {
        r = r || t.getId(n);const a = document.body; let l = n.parentNode;for (o[r] = o[r] ? o[r] + 1 : 1;null != l && l !== a;) {
          const u = t.getId(l, null, !0);if (u && e[u]) {
            const c = t.getOffset(l);if (null == i[u][r]) {
              const h = t.getOffset(n);i[u][r] = { id: r, offset: { left: h.left - c.left, top: h.top - c.top } }, s[r] = u
            } break
          }l = l.parentNode
        }
      }, this.endpointDeleted = function (t) {
        if (o[t.elementId] && (o[t.elementId]--, o[t.elementId] <= 0)) for (const e in i)i.hasOwnProperty(e) && i[e] && (delete i[e][t.elementId], delete s[t.elementId])
      }, this.changeId = function (t, e) {
        i[e] = i[t], i[t] = {}, s[e] = s[t], s[t] = null
      }, this.getElementsForDraggable = function (t) {
        return i[t]
      }, this.elementRemoved = function (t) {
        const e = s[t];e && (i[e] && delete i[e][t], delete s[t])
      }, this.reset = function () {
        e = {}, n = [], i = {}, o = {}
      }, this.dragEnded = function (e) {
        if (null != e.offsetParent) {
          const n = t.getId(e); const i = s[n];i && this.updateOffsets(i)
        }
      }, this.setParent = function (e, n, o, r, a) {
        const l = s[n];i[r] || (i[r] = {});const u = t.getOffset(o); const c = a || t.getOffset(e);l && i[l] && delete i[l][n], i[r][n] = { id: n, offset: { left: c.left - u.left, top: c.top - u.top } }, s[n] = r
      }, this.clearParent = function (t, e) {
        const n = s[e];n && (delete i[n][e], delete s[e])
      }, this.revalidateParent = function (e, n, i) {
        const o = s[n];if (o) {
          const r = {};r[n] = i, this.updateOffsets(o, r), t.revalidate(o)
        }
      }, this.getDragAncestor = function (e) {
        const n = jsPlumb.getElement(e); const i = t.getId(n); const o = s[i];return o ? jsPlumb.getElement(o) : null
      }
    }; const p = function (t, e, i) {
      e = n.fastTrim(e), void 0 !== t.className.baseVal ? t.className.baseVal = e : t.className = e;try {
        const o = t.classList;if (null != o) {
          for (;o.length > 0;)o.remove(o.item(0));for (let s = 0;s < i.length;s++)i[s] && o.add(i[s])
        }
      } catch (t) {
        n.log('JSPLUMB: cannot set class list', t)
      }
    }; const f = function (t) {
      return void 0 === t.className.baseVal ? t.className : t.className.baseVal
    }; const g = function (t, e, i) {
      e = null == e ? [] : n.isArray(e) ? e : e.split(/\s+/), i = null == i ? [] : n.isArray(i) ? i : i.split(/\s+/);const o = f(t).split(/\s+/); const s = function (t, e) {
        for (let n = 0;n < e.length;n++) if (t)-1 === o.indexOf(e[n]) && o.push(e[n]);else {
          const i = o.indexOf(e[n]);-1 !== i && o.splice(i, 1)
        }
      };s(!0, e), s(!1, i), p(t, o.join(' '), o)
    };t.jsPlumb.extend(t.jsPlumbInstance.prototype, { headless: !1, pageLocation: a, screenLocation: l, clientLocation: u, getDragManager () {
      return null == this.dragManager && (this.dragManager = new d(this)), this.dragManager
    }, recalculateOffsets (t) {
      this.getDragManager().updateOffsets(t)
    }, createElement (t, e, n, i) {
      return this.createElementNS(null, t, e, n, i)
    }, createElementNS (t, e, n, i, o) {
      let s; const r = null == t ? document.createElement(e) : document.createElementNS(t, e);for (s in n = n || {})r.style[s] = n[s];for (s in i && (r.className = i), o = o || {})r.setAttribute(s, `${o[s]}`);return r
    }, getAttribute (t, e) {
      return null != t.getAttribute ? t.getAttribute(e) : null
    }, setAttribute (t, e, n) {
      null != t.setAttribute && t.setAttribute(e, n)
    }, setAttributes (t, e) {
      for (const n in e)e.hasOwnProperty(n) && t.setAttribute(n, e[n])
    }, appendToRoot (t) {
      document.body.appendChild(t)
    }, getRenderModes () {
      return ['svg']
    }, getClass: f, addClass (t, e) {
      jsPlumb.each(t, (t) => {
        g(t, e)
      })
    }, hasClass (t, e) {
      return (t = jsPlumb.getElement(t)).classList ? t.classList.contains(e) : -1 !== f(t).indexOf(e)
    }, removeClass (t, e) {
      jsPlumb.each(t, (t) => {
        g(t, null, e)
      })
    }, toggleClass (t, e) {
      jsPlumb.hasClass(t, e) ? jsPlumb.removeClass(t, e) : jsPlumb.addClass(t, e)
    }, updateClasses (t, e, n) {
      jsPlumb.each(t, (t) => {
        g(t, e, n)
      })
    }, setClass (t, e) {
      null != e && jsPlumb.each(t, (t) => {
        p(t, e, e.split(/\s+/))
      })
    }, setPosition (t, e) {
      t.style.left = `${e.left}px`, t.style.top = `${e.top}px`
    }, getPosition (t) {
      const e = function (e) {
        const n = t.style[e];return n ? n.substring(0, n.length - 2) : 0
      };return { left: e('left'), top: e('top') }
    }, getStyle (t, e) {
      return void 0 !== window.getComputedStyle ? getComputedStyle(t, null).getPropertyValue(e) : t.currentStyle[e]
    }, getSelector (t, e) {
      return 1 === arguments.length ? null != t.nodeType ? t : document.querySelectorAll(t) : t.querySelectorAll(e)
    }, getOffset (t, e, n) {
      t = jsPlumb.getElement(t), n = n || this.getContainer();for (var i = { left: t.offsetLeft, top: t.offsetTop }, o = e || null != n && t !== n && t.offsetParent !== n ? t.offsetParent : null, s = function (t) {
        null != t && t !== document.body && (t.scrollTop > 0 || t.scrollLeft > 0) && (i.left -= t.scrollLeft, i.top -= t.scrollTop)
      }.bind(this);null != o;)i.left += o.offsetLeft, i.top += o.offsetTop, s(o), o = e ? o.offsetParent : o.offsetParent === n ? null : o.offsetParent;if (null != n && !e && (n.scrollTop > 0 || n.scrollLeft > 0)) {
        const r = null != t.offsetParent ? this.getStyle(t.offsetParent, 'position') : 'static'; const a = this.getStyle(t, 'position');'absolute' !== a && 'fixed' !== a && 'absolute' !== r && 'fixed' !== r && (i.left -= n.scrollLeft, i.top -= n.scrollTop)
      } return i
    }, getPositionOnElement (t, e, n) {
      const i = void 0 !== e.getBoundingClientRect ? e.getBoundingClientRect() : { left: 0, top: 0, width: 0, height: 0 }; const o = document.body; const s = document.documentElement; const r = window.pageYOffset || s.scrollTop || o.scrollTop; const a = window.pageXOffset || s.scrollLeft || o.scrollLeft; const l = s.clientTop || o.clientTop || 0; const u = s.clientLeft || o.clientLeft || 0; const c = i.top + r - l + 0 * n; const h = i.left + a - u + 0 * n; const d = jsPlumb.pageLocation(t); const p = i.width || e.offsetWidth * n; const f = i.height || e.offsetHeight * n;return [(d[0] - h) / p, (d[1] - c) / f]
    }, getAbsolutePosition (t) {
      const e = function (e) {
        const n = t.style[e];if (n) return parseFloat(n.substring(0, n.length - 2))
      };return [e('left'), e('top')]
    }, setAbsolutePosition (t, e, n, i) {
      n ? this.animate(t, { left: `+=${e[0] - n[0]}`, top: `+=${e[1] - n[1]}` }, i) : (t.style.left = `${e[0]}px`, t.style.top = `${e[1]}px`)
    }, getSize (t) {
      return [t.offsetWidth, t.offsetHeight]
    }, getWidth (t) {
      return t.offsetWidth
    }, getHeight (t) {
      return t.offsetHeight
    }, getRenderMode () {
      return 'svg'
    }, draggable (t, e) {
      let i;return t = n.isArray(t) || null != t.length && !n.isString(t) ? t : [t], Array.prototype.slice.call(t).forEach((t) => {
        (i = this.info(t)).el && this._initDraggableIfNecessary(i.el, !0, e, i.id, !0)
      }), this
    }, snapToGrid (t, e, n) {
      const i = []; const o = function (t) {
        const o = this.info(t);if (null != o.el && o.el._katavorioDrag) {
          const s = o.el._katavorioDrag.snap(e, n);this.revalidate(o.el), i.push([o.el, s])
        }
      }.bind(this);if (1 === arguments.length || 3 === arguments.length)o(t, e, n);else {
        const s = this.getManagedElements();for (const r in s)o(r, arguments[0], arguments[1])
      } return i
    }, initDraggable (t, e, n) {
      s(this, n).draggable(t, e), t._jsPlumbDragOptions = e
    }, destroyDraggable (t, e) {
      s(this, e).destroyDraggable(t), t._jsPlumbDragOptions = null, t._jsPlumbRelatedElement = null
    }, unbindDraggable (t, e, n, i) {
      s(this, i).destroyDraggable(t, e, n)
    }, setDraggable (t, e) {
      return jsPlumb.each(t, (t) => {
        this.isDragSupported(t) && (this._draggableStates[this.getAttribute(t, 'id')] = e, this.setElementDraggable(t, e))
      })
    }, _draggableStates: {}, toggleDraggable (t) {
      let e;return jsPlumb.each(t, (t) => {
        const n = this.getAttribute(t, 'id');return e = !(e = null != this._draggableStates[n] && this._draggableStates[n]), this._draggableStates[n] = e, this.setDraggable(t, e), e
      }), e
    }, _initDraggableIfNecessary (t, e, i, o, s) {
      if (!jsPlumb.headless && (null != e && e && jsPlumb.isDragSupported(t, this))) {
        let r = i || this.Defaults.DragOptions;if (r = jsPlumb.extend({}, r), jsPlumb.isAlreadyDraggable(t, this))i.force && this.initDraggable(t, r);else {
          const a = jsPlumb.dragEvents.drag; const l = jsPlumb.dragEvents.stop; const u = jsPlumb.dragEvents.start;this.manage(o, t), r[u] = n.wrap(r[u], (t) => {
            const e = t.el._jsPlumbDragOptions; let n = !0;return e.canDrag && (n = e.canDrag()), n && (this.setHoverSuspended(!0), this.select({ source: t.el }).addClass(`${this.elementDraggingClass} ${this.sourceElementDraggingClass}`, !0), this.select({ target: t.el }).addClass(`${this.elementDraggingClass} ${this.targetElementDraggingClass}`, !0), this.setConnectionBeingDragged(!0)), n
          }), r[a] = n.wrap(r[a], function (t) {
            const e = this.getUIPosition(arguments, this.getZoom());if (null != e) {
              const n = t.el._jsPlumbDragOptions;this.draw(t.el, e, null, !0), n._dragging && this.addClass(t.el, 'jtk-dragged'), n._dragging = !0
            }
          }.bind(this)), r[l] = n.wrap(r[l], (t) => {
            for (var e, n = t.selection, i = function (n) {
                let i;null != n[1] && (e = this.getUIPosition([{ el: n[2].el, pos: [n[1].left, n[1].top] }]), i = this.draw(n[2].el, e)), null != n[0]._jsPlumbDragOptions && delete n[0]._jsPlumbDragOptions._dragging, this.removeClass(n[0], 'jtk-dragged'), this.select({ source: n[2].el }).removeClass(`${this.elementDraggingClass} ${this.sourceElementDraggingClass}`, !0), this.select({ target: n[2].el }).removeClass(`${this.elementDraggingClass} ${this.targetElementDraggingClass}`, !0), t.e._drawResult = t.e._drawResult || { c: [], e: [], a: [] }, Array.prototype.push.apply(t.e._drawResult.c, i.c), Array.prototype.push.apply(t.e._drawResult.e, i.e), Array.prototype.push.apply(t.e._drawResult.a, i.a), this.getDragManager().dragEnded(n[2].el)
              }.bind(this), o = 0;o < n.length;o++)i(n[o]);this.setHoverSuspended(!1), this.setConnectionBeingDragged(!1)
          });const c = this.getId(t);this._draggableStates[c] = !0;const h = this._draggableStates[c];r.disabled = null != h && !h, this.initDraggable(t, r), this.getDragManager().register(t), s && this.fire('elementDraggable', { el: t, options: r })
        }
      }
    }, animationSupported: !0, getElement (t) {
      return null == t ? null : 'string' === typeof(t = 'string' === typeof t ? t : null == t.tagName && null != t.length && null == t.enctype ? t[0] : t) ? document.getElementById(t) : t
    }, removeElement (t) {
      s(this).elementRemoved(t), this.getEventManager().remove(t)
    }, doAnimate (t, i, o) {
      o = o || {};const s = this.getOffset(t); const r = (function (t, e) {
        const i = function (i) {
          if (null != e[i]) {
            if (n.isString(e[i])) {
              const o = e[i].match(/-=/) ? -1 : 1; const s = e[i].substring(2);return t[i] + o * s
            } return e[i]
          } return t[i]
        };return [i('left'), i('top')]
      }(s, i)); const a = r[0] - s.left; const l = r[1] - s.top; const u = o.duration || 250; const c = u / 15; const h = 15 / u * a; const d = 15 / u * l; let p = 0; var f = setInterval(() => {
        e.setPosition(t, { left: s.left + h * (p + 1), top: s.top + d * (p + 1) }), null != o.step && o.step(p, Math.ceil(c)), ++p >= c && (window.clearInterval(f), null != o.complete && o.complete())
      }, 15)
    }, destroyDroppable (t, e) {
      s(this, e).destroyDroppable(t)
    }, unbindDroppable (t, e, n, i) {
      s(this, i).destroyDroppable(t, e, n)
    }, droppable (t, e) {
      let i;return t = n.isArray(t) || null != t.length && !n.isString(t) ? t : [t], (e = e || {}).allowLoopback = !1, Array.prototype.slice.call(t).forEach((t) => {
        (i = this.info(t)).el && this.initDroppable(i.el, e)
      }), this
    }, initDroppable (t, e, n) {
      s(this, n).droppable(t, e)
    }, isAlreadyDraggable (t) {
      return null != t._katavorioDrag
    }, isDragSupported (t, e) {
      return !0
    }, isDropSupported (t, e) {
      return !0
    }, isElementDraggable (t) {
      return (t = e.getElement(t))._katavorioDrag && t._katavorioDrag.isEnabled()
    }, getDragObject (t) {
      return t[0].drag.getDragElement()
    }, getDragScope (t) {
      return t._katavorioDrag && t._katavorioDrag.scopes.join(' ') || ''
    }, getDropEvent (t) {
      return t[0].e
    }, getUIPosition (t, e) {
      const n = t[0].el;if (null == n.offsetParent) return null;const i = t[0].finalPos || t[0].pos; const o = { left: i[0], top: i[1] };if (n._katavorioDrag && n.offsetParent !== this.getContainer()) {
        const s = this.getOffset(n.offsetParent);o.left += s.left, o.top += s.top
      } return o
    }, setDragFilter (t, e, n) {
      t._katavorioDrag && t._katavorioDrag.setFilter(e, n)
    }, setElementDraggable (t, n) {
      (t = e.getElement(t))._katavorioDrag && t._katavorioDrag.setEnabled(n)
    }, setDragScope (t, e) {
      t._katavorioDrag && t._katavorioDrag.k.setDragScope(t, e)
    }, setDropScope (t, e) {
      t._katavorioDrop && t._katavorioDrop.length > 0 && t._katavorioDrop[0].k.setDropScope(t, e)
    }, addToPosse (t, n) {
      const i = Array.prototype.slice.call(arguments, 1); const o = s(this);e.each(t, (t) => {
        (t = [e.getElement(t)]).push.apply(t, i), o.addToPosse.apply(o, t)
      })
    }, setPosse (t, n) {
      const i = Array.prototype.slice.call(arguments, 1); const o = s(this);e.each(t, (t) => {
        (t = [e.getElement(t)]).push.apply(t, i), o.setPosse.apply(o, t)
      })
    }, removeFromPosse (t, n) {
      const i = Array.prototype.slice.call(arguments, 1); const o = s(this);e.each(t, (t) => {
        (t = [e.getElement(t)]).push.apply(t, i), o.removeFromPosse.apply(o, t)
      })
    }, removeFromAllPosses (t) {
      const n = s(this);e.each(t, (t) => {
        n.removeFromAllPosses(e.getElement(t))
      })
    }, setPosseState (t, n, i) {
      const o = s(this);e.each(t, (t) => {
        o.setPosseState(e.getElement(t), n, i)
      })
    }, dragEvents: { start: 'start', stop: 'stop', drag: 'drag', step: 'step', over: 'over', out: 'out', drop: 'drop', complete: 'complete', beforeStart: 'beforeStart' }, animEvents: { step: 'step', complete: 'complete' }, stopDrag (t) {
      t._katavorioDrag && t._katavorioDrag.abort()
    }, addToDragSelection (t) {
      const e = this.getElement(t);null == e || !e._isJsPlumbGroup && null != e._jsPlumbGroup || s(this).select(t)
    }, removeFromDragSelection (t) {
      s(this).deselect(t)
    }, getDragSelection () {
      return s(this).getSelection()
    }, clearDragSelection () {
      s(this).deselectAll()
    }, trigger (t, e, n, i) {
      this.getEventManager().trigger(t, e, n, i)
    }, doReset () {
      for (const t in this)0 === t.indexOf('_katavorio_') && this[t].reset()
    }, getEventManager () {
      return (n = (e = this)._mottle) || (n = e._mottle = new t.Mottle), n;let e; let n
    }, on (t, e, n) {
      return this.getEventManager().on.apply(this, arguments), this
    }, off (t, e, n) {
      return this.getEventManager().off.apply(this, arguments), this
    } });let m; let v;m = e.init, (v = function () {
      /complete|loaded|interactive/.test(document.readyState) && void 0 !== document.body && null != document.body ? m() : setTimeout(v, 9)
    })()
  }.call('undefined' !== typeof window ? window : s)
}(r = { exports: {} }, r.exports)), r.exports); const l = (a.jsBezier, a.Biltong, a.Mottle, a.Katavorio, a.jsPlumbUtil, a.jsPlumb);const u = function (t, e, n, i, o, s, r, a, l, u) {
  'boolean' !== typeof r && (l = a, a = r, r = !1);let c; const h = 'function' === typeof n ? n.options : n;if (t && t.render && (h.render = t.render, h.staticRenderFns = t.staticRenderFns, h._compiled = !0, o && (h.functional = !0)), i && (h._scopeId = i), s ? (c = function (t) {
    (t = t || this.$vnode && this.$vnode.ssrContext || this.parent && this.parent.$vnode && this.parent.$vnode.ssrContext) || 'undefined' === typeof __VUE_SSR_CONTEXT__ || (t = __VUE_SSR_CONTEXT__), e && e.call(this, l(t)), t && t._registeredComponents && t._registeredComponents.add(s)
  }, h._ssrRegister = c) : e && (c = r ? function () {
    e.call(this, u(this.$root.$options.shadowRoot))
  } : function (t) {
    e.call(this, a(t))
  }), c) if (h.functional) {
    const d = h.render;h.render = function (t, e) {
      return c.call(e), d(t, e)
    }
  } else {
    const p = h.beforeCreate;h.beforeCreate = p ? [].concat(p, c) : [c]
  } return n
}; const c = 'undefined' !== typeof navigator && /msie [6-9]\\b/.test(navigator.userAgent.toLowerCase());const h = document.head || document.getElementsByTagName('head')[0]; const d = {};const p = function (t) {
  return function (t, e) {
    return (function (t, e) {
      const n = c ? e.media || 'default' : t; const i = d[n] || (d[n] = { ids: new Set, styles: [] });if (!i.ids.has(t)) {
        i.ids.add(t);let o = e.source;if (e.map && (o += `\n/*# sourceURL=${e.map.sources[0]} */`, o += `\n/*# sourceMappingURL=data:application/json;base64,${btoa(unescape(encodeURIComponent(JSON.stringify(e.map))))} */`), i.element || (i.element = document.createElement('style'), i.element.type = 'text/css', e.media && i.element.setAttribute('media', e.media), h.appendChild(i.element)), 'styleSheet' in i.element)i.styles.push(o), i.element.styleSheet.cssText = i.styles.filter(Boolean).join('\n');else {
          const s = i.ids.size - 1; const r = document.createTextNode(o); const a = i.element.childNodes;a[s] && i.element.removeChild(a[s]), a.length ? i.element.insertBefore(r, a[s]) : i.element.appendChild(r)
        }
      }
    }(t, e))
  }
}; const f = u({ render () {
  const t = this; const e = t.$createElement;return (t._self._c || e)('div', { staticClass: 'palette-panel' }, [t._t('palette', () => [t._m(0)])], 2)
}, staticRenderFns: [function () {
  const t = this.$createElement; const e = this._self._c || t;return e('ul', { staticClass: 'palette-group' }, [e('li', [e('div', { staticClass: 'palette-default-item startpoint', attrs: { 'data-type': 'startpoint' } })]), e('li', [e('div', { staticClass: 'palette-default-item endpoint', attrs: { 'data-type': 'endpoint' } })]), e('li', [e('div', { staticClass: 'palette-default-item tasknode', attrs: { 'data-type': 'tasknode' } })]), e('li', [e('div', { staticClass: 'palette-default-item gateway', attrs: { 'data-type': 'gateway' } })])])
}] }, (t) => {
  t && t('data-v-09b6e314_0', { source: '.palette-group{margin:0;padding:0;background:#fcfcfc;text-align:center;list-style:none}.palette-group>li{padding:14px 0}.palette-default-item{display:inline-block;width:40px;height:40px;font-size:12px;color:#888;border:1px solid #999;border-radius:2px;cursor:pointer;user-select:none}.palette-default-item:hover{box-shadow:0 0 8px rgba(50,50,50,.3)}.startpoint{border-radius:50%;border:4px solid #6a6c8a}.endpoint{border-radius:50%;background:#6a6c8a}.tasknode{height:30px;border:2px solid #33d0c6}.gateway{width:30px;height:30px;background:#7c68fc;transform:rotate(-45deg)}', map: void 0, media: void 0 })
}, { name: 'PalettePanel', props: ['selector'], data () {
  return {}
} }, void 0, !1, void 0, p, void 0); const g = u({ render () {
  const t = this; const e = t.$createElement; const n = t._self._c || e;return n('div', { staticClass: 'tool-panel' }, t._l(t.tools, (e, i) => n('div', { key: i, class: ['tool-item', e.cls, { actived: 'frameSelect' === e.type && t.isFrameSelecting }], on: { click (n) {
    return t.onToolClick(e)
  } } }, [t._v(`\n        ${t._s(e.name)}\n    `)])), 0)
}, staticRenderFns: [] }, (t) => {
  t && t('data-v-2c518942_0', { source: '.tool-item{display:inline-block;margin-right:10px;user-select:none;cursor:pointer}.tool-item:last-child{margin-right:0}.tool-item.actived{color:#3a84ff}', map: void 0, media: void 0 })
}, { name: 'ToolPanel', props: ['tools', 'isFrameSelecting'], data () {
  return {}
}, methods: { onToolClick (t) {
  this.$emit('onToolClick', t)
} } }, void 0, !1, void 0, p, void 0); const m = u({ render () {
  const t = this.$createElement; const e = this._self._c || t;return e('div', { staticClass: 'bk-flow-location', on: { mousedown: this.onMouseDown, mouseup: this.onMouseUp } }, ['startpoint' === this.node.type ? e('div', { staticClass: 'circle-node startpoint' }) : 'endpoint' === this.node.type ? e('div', { staticClass: 'circle-node endpoint' }) : 'tasknode' === this.node.type ? e('div', { staticClass: 'tasknode' }) : 'gateway' === this.node.type ? e('div', { staticClass: 'gateway' }) : e('div', { staticClass: 'node-default' })])
}, staticRenderFns: [] }, (t) => {
  t && t('data-v-0604134d_0', { source: '.bk-flow-location .circle-node{width:30px;height:30px;border-radius:50%;text-align:center}.bk-flow-location .startpoint{border:4px solid #6a6c8a}.bk-flow-location .endpoint{background:#6a6c8a}.bk-flow-location .tasknode{width:80px;height:50px;border:2px solid #33d0c6}.bk-flow-location .gateway{width:30px;height:30px;background:#7c68fc;transform:rotate(-45deg)}.bk-flow-location .node-default{width:120px;height:80px;line-height:80px;border:1px solid #ccc;border-radius:2px;text-align:center}.bk-flow-location .node-default.selected{border:1px solid #3a84ff}', map: void 0, media: void 0 })
}, { name: 'NodeTemplate', props: { node: { type: Object, default () {
  return {}
} } }, data () {
  return { moveFlag: { x: 0, y: 0, moved: !1 } }
}, methods: { onMouseDown (t) {
  this.moveFlag = { x: t.pageX, y: t.pageY, moved: !1 }, this.$el.addEventListener('mousemove', this.mouseMoveHandler)
}, onMouseUp (t) {
  const e = t.pageX; const n = t.pageY;this.moveFlag.x = e, this.moveFlag.y = n, this.moveFlag.moved ? (console.log('drag event'), this.moveFlag.moved = !1) : console.log('click event'), this.$el.removeEventListener('mousemove', this.mouseMoveHandler)
}, mouseMoveHandler (t) {
  const e = t.pageX; const n = t.pageY;(Math.abs(e - this.moveFlag.x) > 2 || Math.abs(n - this.moveFlag.y) > 2) && (this.moveFlag.moved = !0)
} } }, void 0, !1, void 0, p, void 0);function v (t) {
  return 'touches' in t ? t.touches[0] : t
} const y = { grid: [5, 5] }; const b = { connector: ['Bezier', { curviness: 30 }], paintStyle: { strokeWidth: 2, stroke: '#567567', outlineStroke: 'tranparent', outlineWidth: 6 }, hoverPaintStyle: { fill: 'transparent', stroke: '#3a84ff' } }; const P = { endpoint: 'Dot', connector: ['Flowchart', { stub: [1, 6], alwaysRespectStub: !0, gap: 8, cornerRadius: 2 }], connectorOverlays: [['PlainArrow', { width: 8, length: 6, location: 1, id: 'arrow' }]], paintStyle: { fill: '#3a84ff', radius: 5 }, anchor: ['Left', 'Right', 'Top', 'Bottom'], isSource: !0, isTarget: !0 };function x () {
  for (var t = arguments.length > 0 && void 0 !== arguments[0] ? arguments[0] : '', e = '', n = 0;n < 7;n++)e += Math.floor(65536 * (1 + Math.random())).toString(16)
    .substring(1);return t + e
} const C = { showPalette: { type: Boolean, default: !0 }, showTool: { type: Boolean, default: !0 }, tools: { type: Array, default () {
  return [{ type: 'zoomIn', name: '放大', cls: 'tool-item' }, { type: 'zoomOut', name: '缩小', cls: 'tool-item' }, { type: 'resetPosition', name: '重置', cls: 'tool-item' }]
} }, editable: { type: Boolean, default: !0 }, selector: { type: String, default: 'palette-default-item' }, data: { type: Object, default () {
  return { nodes: [], lines: [] }
} }, nodeOptions: { type: Object, default () {
  return e({}, y)
} }, connectorOptions: { type: Object, default () {
  return e({}, b)
} }, endpointOptions: { type: Object, default () {
  return e({}, P)
} } }; const _ = { mousedown: 'ontouchstart' in document.documentElement ? 'touchstart' : 'mousedown', mousemove: 'ontouchmove' in document.documentElement ? 'touchmove' : 'mousemove', mouseup: 'ontouchend' in document.documentElement ? 'touchend' : 'mouseup' }; const j = u({ render () {
  const t = this; const e = t.$createElement; const n = t._self._c || e;return n('div', { class: ['jsflow', { editable: t.editable }] }, [n('div', { staticClass: 'canvas-area' }, [t.showTool ? n('div', { staticClass: 'tool-panel-wrap' }, [t._t('toolPanel', () => [n('tool-panel', { attrs: { tools: t.tools, 'is-frame-selecting': t.isFrameSelecting }, on: { onToolClick: t.onToolClick } })])], 2) : t._e(), t.showPalette ? n('div', { ref: 'palettePanel', staticClass: 'palette-panel-wrap' }, [t._t('palettePanel', () => [n('palette-panel', { attrs: { selector: t.selector } })])], 2) : t._e(), n('div', { ref: 'canvasFlowWrap', staticClass: 'canvas-flow-wrap', style: t.canvasWrapStyle, on: t._d({}, [t.mousedown, t.onCanvasMouseDown, t.mouseup, t.onCanvasMouseUp]) }, [n('div', { ref: 'canvasFlow', staticClass: 'canvas-flow', attrs: { id: 'canvas-flow' } }, [t._l(t.nodes, (e) => n('div', { key: e.id }, [n('div', { staticClass: 'jsflow-node canvas-node', attrs: { id: e.id }, on: { mouseenter (n) {
    return t.toggleHighLight(e, !0)
  }, mouseleave (n) {
    return t.toggleHighLight(e, !1)
  } } }, [t._t('nodeTemplate', () => [n('node-template', { attrs: { node: e } })], { node: e })], 2)])), n('div', { staticClass: 'reference-line-vertical' }), n('div', { staticClass: 'reference-line-horizontal' })], 2), t.isFrameSelecting ? n('div', { staticClass: 'canvas-frame-selector', style: t.frameSelectorStyle }) : t._e()]), t.showAddingNode ? n('div', { staticClass: 'jsflow-node adding-node', style: t.setNodeInitialPos(t.addingNodeConfig) }, [t._t('nodeTemplate', () => [n('node-template', { attrs: { node: t.addingNodeConfig } })], { node: t.addingNodeConfig })], 2) : t._e()])])
}, staticRenderFns: [] }, (t) => {
  t && t('data-v-23911004_0', { source: '.jsflow{height:100%;border:1px solid #ccc}.jsflow .canvas-area{position:relative;height:100%}.jsflow .tool-panel-wrap{position:absolute;top:20px;left:70px;padding:10px 20px;background:#c4c6cc;opacity:.65;border-radius:4px;z-index:4}.jsflow .palette-panel-wrap{float:left;width:60px;height:100%;border-right:1px solid #ccc}.jsflow .canvas-flow-wrap{position:relative;height:100%;overflow:hidden}.jsflow .canvas-flow{position:relative;min-width:100%;min-height:100%}.jsflow .canvas-frame-selector{position:absolute;border:1px solid #3a84ff;background:rgba(58,132,255,.15)}.jsflow .jsflow-node{position:absolute;user-select:none}.jsflow .jtk-endpoint{z-index:1;cursor:pointer}.jsflow .adding-node{opacity:.8}.jsflow .jtk-endpoint.jtk-dragging{z-index:0}.jsflow .jtk-connector{cursor:pointer}.jsflow .reference-line-vertical{display:none;position:absolute;top:-100000px;bottom:-100000px;left:0;width:2px;background:rgba(30,144,255,.8);z-index:1}.jsflow .reference-line-horizontal{display:none;position:absolute;left:-100000px;right:-100000px;top:0;height:2px;background:rgba(30,144,255,.8);z-index:1}', map: void 0, media: void 0 })
}, { name: 'JsFlow', components: { PalettePanel: f, ToolPanel: g, NodeTemplate: m }, model: { prop: 'data', event: 'change' }, props: C, data () {
  const t = this.data;return e({ nodes: t.nodes, lines: t.lines, canvasGrabbing: !1, isFrameSelecting: !1, frameMoving: null, mouseDownPos: {}, canvasPos: { x: 0, y: 0 }, canvasOffset: { x: 0, y: 0 }, frameSelectorPos: { x: 0, y: 0 }, frameSelectorRect: { width: 0, height: 0 }, selectedNodes: [], showAddingNode: !1, addingNodeConfig: {}, addingNodeRect: {}, canvasRect: {}, paletteRect: {}, zoom: 1, moveTimer: null }, _)
}, computed: { canvasWrapStyle () {
  return { cursor: this.isFrameSelecting ? 'crosshair' : this.canvasGrabbing ? '-webkit-grabbing' : '-webkit-grab' }
}, frameSelectorStyle () {
  return { left: ''.concat(this.frameSelectorPos.x, 'px'), top: ''.concat(this.frameSelectorPos.y, 'px'), width: ''.concat(this.frameSelectorRect.width, 'px'), height: ''.concat(this.frameSelectorRect.height, 'px') }
} }, watch: { 'data.nodes': { handler (t) {
  this.nodes = t
}, deep: !0 }, editable (t) {
  const e = this.$el.querySelectorAll('.canvas-node');this.toggleNodeDraggable(e, t)
} }, mounted () {
  this.initCanvas(), this.registerEvent(), this.renderData(), this.$refs.palettePanel && (this.paletteRect = this.$refs.palettePanel.getBoundingClientRect(), this.registerPaletteEvent())
}, beforeDestroy () {
  this.$refs.palettePanel && this.$refs.palettePanel.removeEventListener(this.mousedown, this.nodeCreateHandler), this.$el.removeEventListener(this.mousemove, this.nodeMovingHandler), document.removeEventListener(this.mouseup, this.nodeMoveEndHandler)
}, methods: { initCanvas () {
  const t = {}; const n = e(e({}, this.endpointOptions), this.connectorOptions);for (const i in n) {
    const o = i[0].toUpperCase();t[''.concat(o).concat(i.slice(1))] = n[i]
  } this.instance = l.getInstance(e({ Container: 'canvas-flow' }, t))
}, registerEvent () {
  const t = this;this.instance.bind('beforeDrag', (e) => !!t.editable && ('function' !== typeof t.$listeners.onBeforeDrag || t.$listeners.onBeforeDrag(e))), this.instance.bind('connectionDrag', (e) => {
    'function' === typeof t.$listeners.onConnectionDrag && t.$emit('onConnectionDrag', e)
  }), this.instance.bind('beforeDrop', (e) => !!t.editable && ('function' !== typeof t.$listeners.onBeforeDrop || t.$listeners.onBeforeDrop(e))), this.instance.bind('connection', (e) => {
    'function' === typeof t.$listeners.onConnection && t.$emit('onConnection', e)
  }), this.instance.bind('connectionDragStop', (e, n) => {
    if (!e.target || !e.target.classList.contains('jsflow-node')) {
      const i = t.getNodeByEvent(n.target);if (i) {
        const o = t.nodes.find((t) => i.id === t.id);if ('function' === typeof t.$listeners.onConnectionDragStop) {
          const s = { id: e.source.id, arrow: e.endpoints[0].anchor.type || e.endpoints[0].anchor.cssClass };t.$emit('onConnectionDragOnNode', s, o.id, n)
        }
      }'function' === typeof t.$listeners.onConnectionDragStop && t.$emit('onConnectionDragStop', e)
    }
  }), this.instance.bind('beforeDetach', (e) => 'function' !== typeof t.$listeners.onBeforeDetach || t.$listeners.onBeforeDetach(e)), this.instance.bind('connectionDetached', (e, n) => {
    const i = t.lines.filter((t) => t.source.id !== e.sourceId && t.target.id !== e.targetId);t.lines = i, 'function' === typeof t.$listeners.onConnectionDetached && t.$emit('onConnectionDetached', e)
  }), this.instance.bind('connectionMoved', (e, n) => {
    'function' === typeof t.$listeners.onConnectionMoved && t.$emit('onConnectionMoved', lines)
  }), this.instance.bind('click', (e, n) => {
    'function' === typeof t.$listeners.onConnectionClick && t.$emit('onConnectionClick', e, n)
  }), this.instance.bind('dblclick', (e, n) => {
    'function' === typeof t.$listeners.onConnectionDbClick && t.$emit('onConnectionDbClick', e, n)
  }), this.instance.bind('endpointClick', (e, n) => {
    'function' === typeof t.$listeners.onEndpointClick && t.$emit('onEndpointClick', e, n)
  }), this.instance.bind('endpointDblClick', (e, n) => {
    'function' === typeof t.$listeners.onEndpointDbClick && t.$emit('onEndpointDbClick', e, n)
  })
}, renderData () {
  const t = this;this.instance.batch(() => {
    t.nodes.forEach((e) => {
      t.initNode(e)
    }), t.lines.forEach((e) => {
      t.createConnector(e, t.connectorOptions)
    })
  })
}, updateCanvas (t) {
  this.removeAllConnector(), this.lines = t.lines, this.nodes = t.nodes, this.renderData()
}, createNode (t) {
  const e = this;('function' !== typeof this.$listeners.onCreateNodeBefore || this.$listeners.onCreateNodeBefore(t)) && (this.nodes.push(t), this.$nextTick(() => {
    e.initNode(t)
  }))
}, initNode (t) {
  const e = document.getElementById(t.id);e.style.left = ''.concat(t.x, 'px'), e.style.top = ''.concat(t.y, 'px'), this.setNodeDraggable(t, this.nodeOptions), this.setNodeEndPoint(t, this.endpointOptions), 'function' === typeof this.$listeners.onCreateNodeAfter && this.$emit('onCreateNodeAfter', t)
}, removeNode (t) {
  const e = this.nodes.findIndex((e) => e.id === t.id);this.nodes.splice(e, 1), this.instance.remove(t.id)
}, setNodeEndPoint (t, n) {
  const i = this; const o = n.anchors || { Top: [.5, 0, 0, -1, 'Top'], Right: [1, .5, 1, 0, 'Right'], Bottom: [.5, 1, 0, 1, 'Bottom'], Left: [0, .5, -1, 0, 'Left'] };Object.keys(o).forEach((s) => {
    const r = o[s]; const a = i.instance.addEndpoint(t.id, e({ anchor: r, uuid: s + t.id }, n));a && a.endpoint.canvas && (a.endpoint.canvas.dataset.pos = s)
  })
}, setNodeDraggable (t, n) {
  if (this.editable) {
    const o = this;this.instance.draggable(t.id, e({ grid: [20, 20], drag (e) {
      const n = o.instance.getDragSelection().map((t) => t.el.id); const i = o.nodes.find((e) => t.id === e.id); const s = Object.assign({}, i);if (o.toggleHighLight(t, !1), 0 === n.length)o.setReferenceLine(t.id, e), o.setBoundaryOffset(e);else if (n.some((e) => e === t.id)) {
        let r;if (!o.frameMoving) {
          let a; let l; const u = Math.min.apply(null, o.selectedNodes.map((t) => t.x)); const c = Math.min.apply(null, o.selectedNodes.map((t) => t.y));o.selectedNodes.some((t) => {
            if (t.x === u) return a = t, !0
          }), o.selectedNodes.some((t) => {
            if (t.y === c) return l = t, !0
          }), o.frameMoving = { left: a, top: l }
        }(null === (r = o.frameMoving.left) || void 0 === r ? void 0 : r.id) === t.id && o.setFrameReferLine()
      } else o.cancelFrameSelectorHandler();o.$emit('onNodeMoving', s, e)
    }, stop (e) {
      let n = -1; const s = i(e.pos, 2); const r = s[0]; const a = s[1]; const l = o.nodes.find((e, i) => {
        if (e.id === t.id) return n = i, !0
      }); const u = Object.assign({}, l, { x: r, y: a });o.nodes.splice(n, 1, u), o.frameMoving = null, o.$emit('onNodeMoveStop', u, e);const c = o.$refs.canvasFlow.querySelector('.reference-line-vertical'); const h = o.$refs.canvasFlow.querySelector('.reference-line-horizontal');c.setAttribute('style', 'display: none; left: 0'), h.setAttribute('style', 'display: none; top: 0'), clearTimeout(this.moveTimer)
    } }, n))
  }
}, setReferenceLine (t, e) {
  const n = this; const o = e.el; const s = o.clientWidth; const r = o.clientHeight; const a = i(e.pos, 2); const l = [a[0] + s / 2, a[1] + r / 2]; const u = this.$refs.canvasFlow.querySelector('.reference-line-vertical'); const c = this.$refs.canvasFlow.querySelector('.reference-line-horizontal');u.setAttribute('style', 'display: none; left: 0'), c.setAttribute('style', 'display: none; top: 0');let h = !1; let d = !1;this.data.nodes.some((e) => {
    if (e.id !== t) {
      const i = n.$refs.canvasFlow.querySelector('#'.concat(e.id)); const o = window.getComputedStyle(i); const s = o.width; const r = o.height; const a = [e.x + Number(s.replace('px', '')) / 2, e.y + Number(r.replace('px', '')) / 2];return h || a[0] !== l[0] || (u.setAttribute('style', 'display: inline-block; left: '.concat(a[0] - 1, 'px;')), h = !0), d || a[1] !== l[1] || (c.setAttribute('style', 'display: inline-block; top: '.concat(a[1] - 1, 'px;')), d = !0), !(!h || !d) || void 0
    }
  })
}, setFrameReferLine () {
  const t = this; const e = this.$refs.canvasFlow.querySelector('#'.concat(this.frameMoving.left.id)); const n = this.$refs.canvasFlow.querySelector('#'.concat(this.frameMoving.top.id)); const i = Number(window.getComputedStyle(e).left.replace('px', '')); const o = Number(window.getComputedStyle(n).top.replace('px', '')); const s = this.$refs.canvasFlow.querySelector('.reference-line-vertical'); const r = this.$refs.canvasFlow.querySelector('.reference-line-horizontal');s.setAttribute('style', 'display: none; left: 0'), r.setAttribute('style', 'display: none; top: 0');let a = !1; let l = !1;this.data.nodes.some((e) => {
    if (!t.selectedNodes.find((t) => t.id === e.id)) {
      const n = [e.x, e.y];return a || n[0] !== i || (s.setAttribute('style', 'display: inline-block; left: '.concat(i, 'px;')), a = !0), l || n[1] !== o || (r.setAttribute('style', 'display: inline-block; top: '.concat(o, 'px;')), l = !0), !(!a || !l) || void 0
    }
  })
}, setBoundaryOffset (t) {
  const e = this.$refs.canvasFlowWrap.getBoundingClientRect(); const n = e.left; const i = e.top; const o = e.width; const s = e.height;t.e.pageX < n && this.intervalMoveCanvas('horizontal', 20), t.e.pageX > n + o && this.intervalMoveCanvas('horizontal', -20), t.e.pageY < i && this.intervalMoveCanvas('vertical', 20), t.e.pageY > i + s && this.intervalMoveCanvas('vertical', -20)
}, intervalMoveCanvas (t, e) {
  const n = this;this.moveTimer && clearTimeout(this.moveTimer), this.moveTimer = setTimeout(() => {
    const i = n.canvasOffset; let o = i.x; let s = i.y;'horizontal' === t ? o += e : s += e, n.setCanvasPosition(o, s), n.moveTimer || n.intervalMoveCanvas(t, e)
  }, 16)
}, setNodePosition (t) {
  const e = document.getElementById(t.id);e.style.left = ''.concat(t.x, 'px'), e.style.top = ''.concat(t.y, 'px'), this.instance.revalidate(e)
}, toggleNodeDraggable (t, e) {
  this.instance.setDraggable(t, e)
}, setNodeInitialPos (t) {
  return { left: ''.concat(t.x, 'px'), top: ''.concat(t.y, 'px'), visibility: t.visible ? 'initial' : 'hidden' }
}, createConnector (t, n) {
  const i = t.options || {};return this.instance.connect({ source: t.source.id, target: t.target.id, uuids: [t.source.arrow + t.source.id, t.target.arrow + t.target.id] }, e(e({}, n), i))
}, setConnector (t, e, n) {
  const i = this;this.instance.getAllConnections().filter((n) => n.sourceId === t && n.targetId === e)
    .forEach((t) => {
      t.setConnector(n), i.endpointOptions && i.endpointOptions.connectorOverlays && i.endpointOptions.connectorOverlays.forEach((e) => {
        t.addOverlay(e)
      })
    })
}, removeConnector (t) {
  const e = this;this.instance.getConnections({ source: t.source.id, target: t.target.id }).forEach((t) => {
    e.instance.deleteConnection(t)
  })
}, removeAllConnector () {
  this.instance.deleteEveryConnection(), this.lines = []
}, getConnectorsByNodeId (t) {
  return this.instance.getAllConnections().filter((e) => e.sourceId === t || e.targetId === t)
}, getNodeByEvent (t) {
  const e = t.parentNode;return !(!e || 'HTML' === e.nodeName) && (e.classList.contains('jsflow-node') ? e : this.getNodeByEvent(e))
}, addLineOverlay (t, e) {
  const n = this;this.instance.getConnections({ source: t.source.id, target: t.target.id }).forEach((t) => {
    t.addOverlay([e.type, { label: e.name, location: e.location, cssClass: e.cls, id: e.id, events: { click (t, e) {
      n.$emit('onOverlayClick', t, e)
    } } }])
  })
}, removeLineOverlay (t, e) {
  this.instance.getConnections({ source: t.source.id, target: t.target.id }).forEach((t) => {
    t.removeOverlay(e)
  })
}, onCanvasMouseDown (t) {
  'touchstart' !== t.type && 0 !== t.button || (t = v(t), this.isFrameSelecting ? this.frameSelectHandler(t) : (this.canvasGrabbing = !0, this.mouseDownPos = { x: t.pageX, y: t.pageY }, this.$refs.canvasFlowWrap.addEventListener(this.mousemove, this.canvasFlowMoveHandler, !1)))
}, canvasFlowMoveHandler (t) {
  t = v(t), this.canvasOffset = { x: this.canvasPos.x + t.pageX - this.mouseDownPos.x, y: this.canvasPos.y + t.pageY - this.mouseDownPos.y }, this.$refs.canvasFlow.style.left = ''.concat(this.canvasOffset.x, 'px'), this.$refs.canvasFlow.style.top = ''.concat(this.canvasOffset.y, 'px'), this.$emit('onCanvasMove', { left: this.canvasOffset.x, top: this.canvasOffset.y })
}, onCanvasMouseUp (t) {
  this.isFrameSelecting ? this.frameSelectEndHandler(t) : (this.canvasGrabbing = !1, this.$refs.canvasFlowWrap.removeEventListener(this.mousemove, this.canvasFlowMoveHandler), this.canvasPos = { x: this.canvasOffset.x, y: this.canvasOffset.y })
}, registerPaletteEvent () {
  this.$refs.palettePanel.addEventListener(this.mousedown, this.nodeCreateHandler, !1)
}, nodeCreateHandler (t) {
  const n = this; const i = (function t (e, n) {
    return 1 === e.nodeType && e.classList.contains(n) ? e : 'HTML' !== e.parentNode.nodeName ? t(e.parentNode, n) : null
  }(t.target, this.selector));if (i) {
    const o = i.dataset.type ? i.dataset.type : ''; const s = {};for (const r in i.dataset) {
      const a = r.match(/(config)(\w*)/);if (a && '' !== a[2]) {
        const l = a[2]; const u = l[0].toLowerCase() + l.slice(1);s[u] = i.dataset[r]
      }
    } this.showAddingNode = !0, this.addingNodeConfig.id = x('node'), this.addingNodeConfig.type = o, this.$nextTick(() => {
      const i = n.$el.querySelector('.adding-node');n.addingNodeRect = i.getBoundingClientRect();const r = n.getAddingNodePos(t);n.addingNodeConfig = e({ id: x('node'), type: o, x: r.x, y: r.y, adding: !0, visible: !1 }, s), n.$el.addEventListener(n.mousemove, n.nodeMovingHandler, !1), document.addEventListener(n.mouseup, n.nodeMoveEndHandler, !1)
    })
  }
}, nodeMovingHandler (t) {
  const e = this.getAddingNodePos(t);this.$set(this.addingNodeConfig, 'x', e.x), this.$set(this.addingNodeConfig, 'y', e.y), this.$set(this.addingNodeConfig, 'visible', !0), 'function' === typeof this.$listeners.onAddNodeMoving && this.$emit('onAddNodeMoving', { type: this.addingNodeConfig.type, x: e.x, y: e.y })
}, nodeMoveEndHandler (t) {
  if (this.$el.removeEventListener(this.mousemove, this.nodeMovingHandler), document.removeEventListener(this.mouseup, this.nodeMoveEndHandler), this.showAddingNode = !1, t.pageX > this.paletteRect.left + this.paletteRect.width) {
    const e = this.addingNodeConfig.x - this.paletteRect.width - this.canvasOffset.x; const n = this.addingNodeConfig.y - this.canvasOffset.y;this.$set(this.addingNodeConfig, 'x', e), this.$set(this.addingNodeConfig, 'y', n), delete this.addingNodeConfig.adding, delete this.addingNodeConfig.visible, this.createNode(this.addingNodeConfig)
  } this.addingNodeConfig = {}, this.addingNodeRect = {}
}, getAddingNodePos (t) {
  return { x: t.pageX - this.paletteRect.left - this.addingNodeRect.width / 2, y: t.pageY - this.paletteRect.top - this.addingNodeRect.height / 2 }
}, toggleHighLight (t) {
  const e = this; const n = !(arguments.length > 1 && void 0 !== arguments[1]) || arguments[1];if (this.editable) {
    const i = document.getElementById(t.id);this.instance.selectEndpoints({ source: i }).each((t) => {
      let i;n ? (i = e.endpointOptions.hoverPaintStyle, t.endpoint.canvas.classList.add('jtk-endpoint-highlight')) : (i = e.endpointOptions.paintStyle, t.endpoint.canvas.classList.remove('jtk-endpoint-highlight')), i && t.setStyle(i)
    })
  }
}, onToolClick (t) {
  'function' === typeof this[t.type] && this[t.type](), this.$emit('onToolClick', t)
}, setZoom (t, e, n) {
  this.instance.setContainer('canvas-flow'), this.$refs.canvasFlow.style.transform = `matrix(${t},0,0,${t},${e},${n})`, this.$refs.canvasFlow.style.transformOrigin = '0 0', this.$refs.canvasFlow.zoom = t, this.zoom = t, this.instance.setZoom(t)
}, zoomIn () {
  const t = arguments.length > 0 && void 0 !== arguments[0] ? arguments[0] : 1.1; const e = arguments.length > 1 && void 0 !== arguments[1] ? arguments[1] : 0; const n = arguments.length > 2 && void 0 !== arguments[2] ? arguments[2] : 0; const i = this.zoom * t; const o = e - e * i; const s = n - n * i;i > 2 || this.setZoom(i, o, s)
}, zoomOut () {
  const t = arguments.length > 0 && void 0 !== arguments[0] ? arguments[0] : .9; const e = arguments.length > 1 && void 0 !== arguments[1] ? arguments[1] : 0; const n = arguments.length > 2 && void 0 !== arguments[2] ? arguments[2] : 0; const i = this.zoom * t; const o = e - e * i; const s = n - n * i;i < .1 || this.setZoom(i, o, s)
}, resetPosition () {
  this.setZoom(1, 0, 0), this.setCanvasPosition(0, 0)
}, setCanvasPosition (t, e) {
  this.canvasOffset = { x: t, y: e }, this.canvasPos = { x: t, y: e }, this.$refs.canvasFlow.style.left = `${this.canvasOffset.x}px`, this.$refs.canvasFlow.style.top = `${this.canvasOffset.y}px`
}, frameSelect () {
  const t = !(arguments.length > 0 && void 0 !== arguments[0]) || arguments[0];this.isFrameSelecting = t
}, onOpenFrameSelect () {
  this.frameSelect()
}, onCloseFrameSelect () {
  this.frameSelect(!1)
}, frameSelectHandler (t) {
  this.canvasRect = this.$refs.canvasFlowWrap.getBoundingClientRect(), this.mouseDownPos = { x: t.clientX - this.canvasRect.left, y: t.clientY - this.canvasRect.top }, this.$refs.canvasFlowWrap.addEventListener(this.mousemove, this.frameSelectMovingHandler, !1)
}, frameSelectMovingHandler (t) {
  const e = t.clientX - this.mouseDownPos.x - this.canvasRect.left; const n = t.clientY - this.mouseDownPos.y - this.canvasRect.top;this.frameSelectorRect = { width: Math.abs(e), height: Math.abs(n) }, this.frameSelectorPos = { x: e > 0 ? this.mouseDownPos.x : this.mouseDownPos.x + e, y: n > 0 ? this.mouseDownPos.y : this.mouseDownPos.y + n }
}, frameSelectEndHandler (t) {
  this.$refs.canvasFlowWrap.removeEventListener(this.mousemove, this.frameSelectMovingHandler), this.$refs.canvasFlowWrap.removeEventListener(this.mouseup, this.frameSelectEndHandler), document.addEventListener(this.mousedown, this.cancelFrameSelectorHandler, { capture: !1, once: !0 });const e = this.getSelectedNodes(); const n = e.map((t) => t.id); const i = this.mouseDownPos; const o = i.x; const s = i.y;this.isFrameSelecting = !1, this.frameSelectorPos = { x: 0, y: 0 }, this.frameSelectorRect = { width: 0, height: 0 }, this.selectedNodes = e, this.clearNodesDragSelection(), this.addNodesToDragSelection(n), this.$emit('onFrameSelectEnd', e.slice(0), o, s)
}, getSelectedNodes () {
  const t = this; const e = this.frameSelectorPos; const n = e.x; const i = e.y; const o = this.frameSelectorRect; const s = o.width; const r = o.height;return this.nodes.filter((e) => {
    const o = document.querySelector('#'.concat(e.id)).getBoundingClientRect(); const a = o.left - t.canvasRect.left; const l = o.top - t.canvasRect.top;if (n < a && n + s > a && i < l && i + r > l) return !0
  })
}, cancelFrameSelectorHandler (t) {
  this.selectedNodes = [], this.clearNodesDragSelection(), this.$emit('onCloseFrameSelect')
}, addNodesToDragSelection (t) {
  t.forEach((t) => {
    const e = document.querySelector('#'.concat(t));e && e.classList.add('selected')
  }), this.instance.addToDragSelection(t)
}, clearNodesDragSelection () {
  document.querySelectorAll('.jsflow-node.selected').forEach((t) => {
    t.classList.remove('selected')
  }), this.instance.clearDragSelection()
} } }, void 0, !1, void 0, p, void 0);'undefined' !== typeof window && 'Vue' in window && window.Vue.component('js-flow', j);export default j;
