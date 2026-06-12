(function () {
  function normalize(value) {
    return String(value || "").trim().toLowerCase();
  }

  function splitTags(value) {
    return String(value || "")
      .split(",")
      .map(function (item) {
        return item.trim().toLowerCase();
      })
      .filter(Boolean);
  }

  function initShowcase() {
    var root = document.querySelector("[data-showcase-root]");
    if (!root) {
      return;
    }

    var searchInput = root.querySelector("[data-showcase-search]");
    var summary = root.querySelector("[data-showcase-summary]");
    var emptyState = root.querySelector("[data-showcase-empty]");
    var cards = Array.prototype.slice.call(root.querySelectorAll("[data-feature-card]"));
    var groups = Array.prototype.slice.call(root.querySelectorAll("[data-showcase-filter-group]"));
    var state = {
      status: "all",
      tag: "all",
      query: "",
    };

    function setGroupActive(group, value) {
      var buttons = group.querySelectorAll("[data-showcase-filter]");
      Array.prototype.forEach.call(buttons, function (button) {
        button.classList.toggle("is-active", button.getAttribute("data-showcase-filter") === value);
      });
    }

    function cardMatches(card) {
      var searchIndex = normalize(card.getAttribute("data-search-index") || card.textContent);
      var status = normalize(card.getAttribute("data-status"));
      var tags = splitTags(card.getAttribute("data-tags"));
      var statusOk = state.status === "all" || status === state.status;
      var tagOk = state.tag === "all" || tags.indexOf(state.tag) !== -1;
      var queryOk = !state.query || searchIndex.indexOf(state.query) !== -1;
      return statusOk && tagOk && queryOk;
    }

    function render() {
      var visibleCount = 0;
      cards.forEach(function (card) {
        var visible = cardMatches(card);
        card.hidden = !visible;
        card.setAttribute("aria-hidden", visible ? "false" : "true");
        if (visible) {
          visibleCount += 1;
        }
      });

      if (summary) {
        summary.textContent = visibleCount
          ? "当前展示 " + visibleCount + " 个 Feature"
          : "当前没有匹配的 Feature";
      }

      if (emptyState) {
        emptyState.hidden = visibleCount !== 0;
      }
    }

    if (searchInput) {
      searchInput.addEventListener("input", function (event) {
        state.query = normalize(event.target.value);
        render();
      });
    }

    groups.forEach(function (group) {
      var groupName = group.getAttribute("data-showcase-filter-group");
      if (!groupName) {
        return;
      }

      var activeButton = group.querySelector('[data-showcase-filter].is-active') || group.querySelector("[data-showcase-filter]");
      if (activeButton) {
        setGroupActive(group, normalize(activeButton.getAttribute("data-showcase-filter")));
      }

      group.addEventListener("click", function (event) {
        var button = event.target.closest("[data-showcase-filter]");
        if (!button || !group.contains(button)) {
          return;
        }

        var value = normalize(button.getAttribute("data-showcase-filter")) || "all";
        if (groupName === "status") {
          state.status = value;
        } else if (groupName === "tag") {
          state.tag = value;
        }
        setGroupActive(group, value);
        render();
      });
    });

    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initShowcase);
  } else {
    initShowcase();
  }
})();
