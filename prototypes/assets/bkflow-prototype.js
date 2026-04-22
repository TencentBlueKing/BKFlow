/* ============================================================
   BKFlow Prototype Toolkit - Shared Shell Interaction Layer
   Only the cross-page behaviors needed by prototype masters.
   ============================================================ */

(function () {
  "use strict";

  function openOverlay(id) {
    var el = document.getElementById(id);
    if (el) el.classList.add("is-show");
  }

  function setInteractiveState(el, enabled) {
    if (!el) return;
    if (enabled) {
      el.classList.remove("is-disabled");
      el.classList.add("is-enabled");
      el.removeAttribute("disabled");
      el.setAttribute("aria-disabled", "false");
      return;
    }

    el.classList.remove("is-enabled");
    el.classList.add("is-disabled");
    el.setAttribute("disabled", "disabled");
    el.setAttribute("aria-disabled", "true");
  }

  function applyInteractiveState(selector, enabled) {
    if (!selector) return;
    document.querySelectorAll(selector).forEach(function (el) {
      setInteractiveState(el, enabled);
    });
  }

  function setTaskStatusClass(el, statusText) {
    if (!el) return;

    var statusClassMap = {
      "完成": "is-success",
      "成功": "is-success",
      "失败": "is-failed",
      "运行中": "is-running",
      "未执行": "is-neutral",
      "等待中": "is-neutral",
      "等待人工处理": "is-neutral",
    };

    el.textContent = statusText;
    el.classList.remove("is-success", "is-running", "is-failed", "is-neutral");
    el.classList.add(statusClassMap[statusText] || "is-neutral");
  }

  function applyNodeDetailSource(panel, sourceId) {
    if (!panel || !sourceId) return;

    panel.querySelectorAll("[data-detail-source-group][data-detail-source-id]").forEach(function (block) {
      block.hidden = block.getAttribute("data-detail-source-id") !== sourceId;
    });
  }

  function closeOverlay(el) {
    while (
      el &&
      !el.classList.contains("bk-sideslider") &&
      !el.classList.contains("bk-dialog")
    ) {
      el = el.parentElement;
    }
    if (el) el.classList.remove("is-show");
  }

  document.addEventListener("click", function (e) {
    var opener = e.target.closest("[data-open]");
    if (opener) {
      e.preventDefault();
      openOverlay(opener.getAttribute("data-open"));
      return;
    }

    var closer = e.target.closest("[data-close]");
    if (closer) {
      e.preventDefault();
      closeOverlay(closer);
      return;
    }

    var mask = e.target;
    if (mask.classList.contains("bk-sideslider-mask") || mask.classList.contains("bk-dialog-mask")) {
      closeOverlay(mask);
    }
  });

  document.addEventListener("click", function (e) {
    var navItem = e.target.closest(".bk-navigation-header-nav-item, .bk-prototype-nav-item");
    if (!navItem) return;
    var navLink = navItem.getAttribute("data-nav-link");
    if (navLink) {
      e.preventDefault();
      if (navItem.classList.contains("active")) return;
      window.location.href = navLink;
      return;
    }

    e.preventDefault();

    var groupId = navItem.getAttribute("data-nav-group");
    var nav = navItem.closest(".bk-navigation-header-nav, .bk-prototype-nav");
    if (nav) {
      nav.querySelectorAll(".bk-navigation-header-nav-item, .bk-prototype-nav-item").forEach(function (item) {
        item.classList.toggle("active", item === navItem);
      });
    }

    if (!groupId) return;
    var root = navItem.closest(".bk-navigation, .bk-prototype-shell") || document;
    root.querySelectorAll(".bk-navigation-menu[data-nav-group], .bk-prototype-sidebar[data-nav-group]").forEach(function (menu) {
      menu.style.display = menu.getAttribute("data-nav-group") === groupId ? "" : "none";
    });
    root.querySelectorAll(".bk-navigation-space[data-nav-group], .bk-prototype-space[data-nav-group]").forEach(function (sp) {
      sp.style.display = sp.getAttribute("data-nav-group") === groupId ? "" : "none";
    });

    var visibleMenu = root.querySelector('.bk-navigation-menu[data-nav-group="' + groupId + '"], .bk-prototype-sidebar[data-nav-group="' + groupId + '"]');
    if (visibleMenu) {
      var firstItem = visibleMenu.querySelector(".bk-navigation-menu-item, .bk-prototype-sidebar-item");
      if (firstItem) firstItem.click();
    }
  });

  document.addEventListener("click", function (e) {
    var menuItem = e.target.closest(".bk-navigation-menu-item[data-page], .bk-prototype-sidebar-item[data-page]");
    if (!menuItem) return;
    e.preventDefault();

    var pageId = menuItem.getAttribute("data-page");
    var container = menuItem.closest(".bk-navigation, .bk-prototype-shell") || document;

    container.querySelectorAll(".bk-navigation-menu-item[data-page], .bk-prototype-sidebar-item[data-page]").forEach(function (item) {
      item.classList.toggle("active", item === menuItem);
    });

    container.querySelectorAll(".bk-page-panel").forEach(function (panel) {
      panel.hidden = panel.id !== pageId;
    });
  });

  document.addEventListener("click", function (e) {
    var trigger = e.target.closest("[data-toggle-target][data-toggle-class]");
    if (!trigger) return;
    e.preventDefault();

    var selector = trigger.getAttribute("data-toggle-target");
    var className = trigger.getAttribute("data-toggle-class");
    document.querySelectorAll(selector).forEach(function (target) {
      target.classList.toggle(className);
    });
  });

  document.addEventListener("click", function (e) {
    var opener = e.target.closest("[data-right-panel-open]");
    if (opener) {
      e.preventDefault();
      document.querySelectorAll(opener.getAttribute("data-right-panel-open")).forEach(function (panel) {
        panel.classList.add("is-open");
      });
      return;
    }

    var closer = e.target.closest("[data-right-panel-close]");
    if (closer) {
      e.preventDefault();
      document.querySelectorAll(closer.getAttribute("data-right-panel-close")).forEach(function (panel) {
        panel.classList.remove("is-open");
      });
    }
  });

  document.addEventListener("click", function (e) {
    var trigger = e.target.closest("[data-save-target]");
    if (!trigger) return;
    e.preventDefault();

    applyInteractiveState(trigger.getAttribute("data-save-target"), true);
  });

  document.addEventListener("click", function (e) {
    var collapseBtn = e.target.closest(".bk-navigation-collapse");
    if (!collapseBtn) return;
    e.preventDefault();
    var sidebar = collapseBtn.closest(".bk-navigation-sidebar");
    if (!sidebar) return;
    var isCollapsed = sidebar.classList.toggle("is-collapsed");
    collapseBtn.textContent = isCollapsed ? "⟩" : "⟨";
    collapseBtn.title = isCollapsed ? "展开导航" : "收起导航";
  });

  document.addEventListener("click", function (e) {
    var trigger = e.target.closest("[data-enable-target], [data-disable-target]");
    if (!trigger) return;

    applyInteractiveState(trigger.getAttribute("data-enable-target"), true);
    applyInteractiveState(trigger.getAttribute("data-disable-target"), false);
  });

  document.addEventListener("click", function (e) {
    var node = e.target.closest("[data-node-select]");
    if (!node) return;

    var root = node.closest(".bk-flow-editor, .bk-flow-editor-shell, .bk-task-detail, .bk-task-detail-shell") || document;
    var group = node.getAttribute("data-node-select");
    root.querySelectorAll('[data-node-select="' + group + '"]').forEach(function (item) {
      item.classList.toggle("is-selected", item === node);
    });

    var toolbarSelector = node.getAttribute("data-node-toolbar");
    if (toolbarSelector) {
      root.querySelectorAll(toolbarSelector).forEach(function (toolbar) {
        toolbar.classList.add("is-visible");
        var label = toolbar.querySelector("[data-node-toolbar-label]");
        if (label && node.getAttribute("data-node-name")) {
          label.textContent = node.getAttribute("data-node-name");
        }
      });
    }

    var panelSelector = node.getAttribute("data-node-open");
    if (panelSelector) {
      root.querySelectorAll(panelSelector).forEach(function (panel) {
        panel.classList.add("is-open");

        var title = panel.querySelector("[data-node-panel-title]");
        if (title && node.getAttribute("data-node-name")) {
          title.textContent = node.getAttribute("data-node-name");
        }

        var status = panel.querySelector("[data-node-panel-status]");
        if (status && node.getAttribute("data-node-status")) {
          setTaskStatusClass(status, node.getAttribute("data-node-status"));
        }

        var trail = panel.querySelector("[data-node-panel-trail]");
        if (trail && node.getAttribute("data-node-trail")) {
          trail.textContent = node.getAttribute("data-node-trail");
        }

        applyNodeDetailSource(panel, node.getAttribute("data-node-detail-source"));
      });
    }
  });

  document.addEventListener("dblclick", function (e) {
    var opener = e.target.closest("[data-dblopen]");
    if (!opener) return;
    e.preventDefault();
    openOverlay(opener.getAttribute("data-dblopen"));
  });

  document.addEventListener("click", function (e) {
    var trigger = e.target.closest("[data-tab-group][data-tab-target]");
    if (!trigger) return;
    e.preventDefault();

    var group = trigger.getAttribute("data-tab-group");
    var targetId = trigger.getAttribute("data-tab-target");
    var root = trigger.closest("[data-tab-root]") || document;

    root.querySelectorAll('[data-tab-group="' + group + '"]').forEach(function (item) {
      item.classList.toggle("active", item === trigger);
    });

    root.querySelectorAll('.bk-tab-panel[data-tab-panel-group="' + group + '"]').forEach(function (panel) {
      panel.hidden = panel.id !== targetId;
    });
  });
})();
