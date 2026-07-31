/* HAL Offline ERP — small shared UI behaviors (no external dependencies) */
(function () {
  "use strict";

  function initIconFallback() {
    // Defensive fallback: if the bootstrap-icons font ever fails to load (e.g.
    // a corrupted/missing static asset), swap icon-only buttons over to their
    // "title" tooltip text instead of showing an empty colored box.
    function applyTextFallback() {
      document.querySelectorAll(".btn[title]").forEach(function (btn) {
        if (btn.dataset.iconFallbackApplied === "true") return;
        var icon = btn.querySelector('i[class*="bi-"]');
        if (!icon) return;
        icon.style.display = "none";
        var label = document.createElement("span");
        label.className = "hal-icon-fallback-text";
        label.textContent = btn.getAttribute("title");
        btn.appendChild(label);
        btn.dataset.iconFallbackApplied = "true";
      });
    }

    if (!("fonts" in document)) return; // can't feature-detect; assume icons render fine
    var checkLoaded = function () {
      try {
        return document.fonts.check('16px "bootstrap-icons"');
      } catch (e) {
        return true; // unsupported check syntax — don't force fallback on a guess
      }
    };

    document.fonts.load('16px "bootstrap-icons"').catch(function () { /* handled by the checks below */ });
    setTimeout(function () {
      if (!checkLoaded()) applyTextFallback();
    }, 1200);
  }

  function initThemeToggle() {
    var toggle = document.getElementById("themeToggle");
    if (!toggle) return;
    var root = document.documentElement;
    toggle.addEventListener("click", function () {
      var next = root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-bs-theme", next);
      try { localStorage.setItem("hal_theme", next); } catch (e) { /* localStorage unavailable */ }
    });
  }

  function initFormLoadingStates() {
    document.querySelectorAll("form").forEach(function (form) {
      form.addEventListener("submit", function () {
        if (form.dataset.confirm && form.dataset.confirmed !== "true") return;
        if (form.dataset.promptReason && form.dataset.confirmed !== "true") return;
        form.querySelectorAll("button[type=submit]").forEach(function (btn) {
          if (btn.disabled) return;
          btn.dataset.originalHtml = btn.innerHTML;
          btn.disabled = true;
          btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>' + (btn.textContent.trim() || "Please wait…");
        });
      });
    });
  }

  function initBulkSelect() {
    document.querySelectorAll("[data-bulk-select-all]").forEach(function (selectAll) {
      var scope = document.querySelector(selectAll.getAttribute("data-bulk-select-all"));
      if (!scope) return;
      var rowChecks = function () { return scope.querySelectorAll(".bulk-row-check"); };
      var toolbar = document.querySelector(selectAll.getAttribute("data-bulk-toolbar") || "");

      function syncToolbar() {
        var checked = Array.prototype.filter.call(rowChecks(), function (c) { return c.checked; });
        if (toolbar) {
          toolbar.classList.toggle("d-none", checked.length === 0);
          var countEl = toolbar.querySelector("[data-bulk-count]");
          if (countEl) countEl.textContent = checked.length;
        }
        var idsInput = document.querySelector("[data-bulk-ids-input]");
        if (idsInput) idsInput.value = checked.map(function (c) { return c.value; }).join(",");
      }

      selectAll.addEventListener("change", function () {
        rowChecks().forEach(function (c) { c.checked = selectAll.checked; });
        syncToolbar();
      });
      scope.addEventListener("change", function (evt) {
        if (evt.target.classList.contains("bulk-row-check")) syncToolbar();
      });
      syncToolbar();
    });
  }

  function initSidebarToggle() {
    var toggle = document.getElementById("sidebarToggle");
    var sidebar = document.getElementById("halSidebar");
    var backdrop = document.getElementById("sidebarBackdrop");
    if (!toggle || !sidebar) return;

    function isMobile() { return window.innerWidth < 992; }

    function closeMobile() {
      sidebar.classList.remove("mobile-open");
      if (backdrop) backdrop.classList.remove("show");
    }

    toggle.addEventListener("click", function () {
      if (isMobile()) {
        sidebar.classList.toggle("mobile-open");
        if (backdrop) backdrop.classList.toggle("show", sidebar.classList.contains("mobile-open"));
      } else {
        sidebar.classList.toggle("collapsed");
        try {
          localStorage.setItem("hal_sidebar_collapsed", sidebar.classList.contains("collapsed") ? "1" : "0");
        } catch (e) { /* localStorage unavailable */ }
      }
    });

    if (backdrop) backdrop.addEventListener("click", closeMobile);
    sidebar.querySelectorAll(".nav-link").forEach(function (link) {
      link.addEventListener("click", function () { if (isMobile()) closeMobile(); });
    });
    window.addEventListener("resize", function () { if (!isMobile()) closeMobile(); });

    try {
      if (!isMobile() && localStorage.getItem("hal_sidebar_collapsed") === "1") {
        sidebar.classList.add("collapsed");
      }
    } catch (e) { /* ignore */ }
  }

  function initButtonRipple() {
    document.addEventListener("click", function (e) {
      var btn = e.target.closest(".btn");
      if (!btn || btn.disabled) return;
      var rect = btn.getBoundingClientRect();
      var size = Math.max(rect.width, rect.height);
      var ripple = document.createElement("span");
      ripple.className = "hal-ripple";
      ripple.style.width = ripple.style.height = size + "px";
      ripple.style.left = (e.clientX - rect.left - size / 2) + "px";
      ripple.style.top = (e.clientY - rect.top - size / 2) + "px";
      btn.appendChild(ripple);
      ripple.addEventListener("animationend", function () { ripple.remove(); });
    });
  }

  function initPageLoader() {
    var bar = document.getElementById("pageLoader");
    if (!bar) return;
    window.addEventListener("beforeunload", function () {
      bar.classList.add("active");
    });
  }

  function showToast(message, category) {
    var container = document.getElementById("toastContainer");
    if (!container || !message) return;
    var colorClass = {
      success: "text-bg-success",
      error: "text-bg-danger",
      warning: "text-bg-warning",
      info: "text-bg-info",
    }[category] || "text-bg-info";

    var toastEl = document.createElement("div");
    toastEl.className = "toast align-items-center " + colorClass + " border-0";
    toastEl.setAttribute("role", "alert");
    toastEl.setAttribute("aria-live", "assertive");
    toastEl.setAttribute("aria-atomic", "true");
    toastEl.innerHTML =
      '<div class="d-flex">' +
      '<div class="toast-body"></div>' +
      '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>' +
      "</div>";
    toastEl.querySelector(".toast-body").textContent = message;
    container.appendChild(toastEl);
    var toast = new bootstrap.Toast(toastEl, { delay: 5000 });
    toast.show();
    toastEl.addEventListener("hidden.bs.toast", function () { toastEl.remove(); });
  }

  function initFlashToastsFromQuery() {
    var params = new URLSearchParams(window.location.search);
    ["success", "error", "warning", "info"].forEach(function (category) {
      var message = params.get(category);
      if (message) showToast(message, category);
    });
  }

  function initDeleteConfirmModals() {
    var modalEl = document.getElementById("confirmModal");
    if (!modalEl) return;
    var modalBody = document.getElementById("confirmModalBody");
    var actionBtn = document.getElementById("confirmModalActionBtn");
    var bsModal = new bootstrap.Modal(modalEl);
    var pendingForm = null;

    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (form.dataset.confirmed === "true") return;
        event.preventDefault();
        pendingForm = form;
        modalBody.textContent = form.getAttribute("data-confirm");
        bsModal.show();
      });
    });

    actionBtn.addEventListener("click", function () {
      bsModal.hide();
      if (pendingForm) {
        pendingForm.dataset.confirmed = "true";
        pendingForm.requestSubmit ? pendingForm.requestSubmit() : pendingForm.submit();
        pendingForm = null;
      }
    });
  }

  function initVoidReasonPrompts() {
    document.querySelectorAll("form[data-prompt-reason]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (form.dataset.confirmed === "true") return;
        var reasonInput = form.querySelector('input[name="reason"]');
        if (!reasonInput) return;
        event.preventDefault();
        var reason = window.prompt(form.getAttribute("data-prompt-reason") || "Reason:");
        if (reason === null) return; // cancelled
        if (!reason.trim()) {
          showToast("A reason is required.", "warning");
          return;
        }
        reasonInput.value = reason.trim();
        form.dataset.confirmed = "true";
        form.requestSubmit ? form.requestSubmit() : form.submit();
      });
    });
  }

  function initDesktopDocumentOpen() {
    // Only intercepts clicks when running inside the pywebview desktop shell
    // (window.pywebview is injected by pywebview itself, never present in a
    // plain browser tab). In a browser tab, these links fall through to their
    // normal href and behave exactly as before — this is additive, not a
    // replacement of the browser-facing "View" route.
    document.addEventListener("click", function (e) {
      var link = e.target.closest(".js-open-local-document");
      if (!link) return;

      var bridgeReady = window.pywebview && window.pywebview.api && typeof window.pywebview.api.open_document === "function";
      if (!bridgeReady) {
        console.log("[HAL] Desktop bridge not available (window.pywebview.api.open_document missing) — using browser link instead.");
        return; // not running inside the desktop shell; let the normal href navigate
      }

      e.preventDefault();
      var contractId = parseInt(link.dataset.contractId, 10);
      var docType = link.dataset.docType;
      console.log("[HAL] Calling desktop bridge open_document(" + contractId + ", " + docType + ")");
      window.pywebview.api.open_document(contractId, docType).then(function (result) {
        console.log("[HAL] open_document resolved:", result);
        if (!result || !result.ok) {
          showToast("Could not open document: " + ((result && result.error) || "unknown error"), "error");
        }
      }).catch(function (err) {
        // Without this .catch, any unexpected Python-side exception rejects this
        // promise silently — nothing shows on screen even though the bridge call
        // genuinely failed. This is what makes failures visible going forward.
        console.error("[HAL] open_document bridge call threw:", err);
        showToast("Could not open document: " + (err && err.message ? err.message : "bridge error — see console"), "error");
      });
    });
  }

  function initDocViewModalBackdrop() {
    // Purely cosmetic: tags the Bootstrap-generated backdrop so CSS can blur/darken
    // it only behind the "View Document" modal, without touching Bootstrap's shared
    // backdrop element (which every other modal in the app also uses) and without
    // going anywhere near document-opening/click behavior.
    document.querySelectorAll(".doc-view-modal").forEach(function (modalEl) {
      modalEl.addEventListener("shown.bs.modal", function () {
        var backdrop = document.querySelector(".modal-backdrop:last-of-type");
        if (backdrop) backdrop.classList.add("doc-modal-backdrop");
      });
      modalEl.addEventListener("hidden.bs.modal", function () {
        var backdrop = document.querySelector(".modal-backdrop.doc-modal-backdrop");
        if (backdrop) backdrop.classList.remove("doc-modal-backdrop");
      });
    });
  }

  function initDynamicFieldTypeToggle() {
    document.querySelectorAll(".field-type-select").forEach(function (typeSelect) {
      var wrap = typeSelect.closest("form").querySelector(".dropdown-options-wrap");
      if (!wrap) return;
      function sync() {
        wrap.style.display = typeSelect.value === "dropdown" ? "block" : "none";
      }
      typeSelect.addEventListener("change", sync);
      sync();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initIconFallback();
    initThemeToggle();
    initSidebarToggle();
    initFlashToastsFromQuery();
    initDeleteConfirmModals();
    initVoidReasonPrompts();
    initDynamicFieldTypeToggle();
    initFormLoadingStates();
    initBulkSelect();
    initButtonRipple();
    initPageLoader();
    initDesktopDocumentOpen();
    initDocViewModalBackdrop();
  });

  window.HAL = { showToast: showToast };
})();
