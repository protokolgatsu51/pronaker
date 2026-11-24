/* =========================================================================
   Modern Custom Dropdown System (Kemnaker Theme: Unit Kerja, Jabatan, Font, Timezone)
   Shared across Name Table & Note Pad Tools Kemnaker RI
   ========================================================================= */
(function (global) {
  function _ddEscapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  class ModernDropdown {
    constructor(selectEl, config = {}) {
      this.selectEl = selectEl;
      this.config = Object.assign({
        withIcon: false,
        searchable: false,
        compact: false,
        pillMini: false,
        noScroll: false,
        searchPlaceholder: "Cari...",
        defaultPlaceholder: "-- Pilih --",
        isOfficial: false,
        isFont: false,
        isSimple: false
      }, config);

      this.wrapper = null;
      this.trigger = null;
      this.valueSpan = null;
      this.menu = null;
      this.searchInput = null;
      this.optionsContainer = null;
      this.isOpen = false;

      this.init();
    }

    init() {
      if (!this.selectEl) return;
      this.selectEl.style.display = "none";

      this.wrapper = document.createElement("div");
      this.wrapper.className = "custom-select-wrapper" +
        (this.config.withIcon ? " with-icon" : "") +
        (this.config.compact ? " compact" : "") +
        (this.config.pillMini ? " pill-mini" : "") +
        (this.config.noScroll ? " no-scroll" : "");
      this.wrapper.id = "customSelect_" + this.selectEl.id;

      this.trigger = document.createElement("button");
      this.trigger.type = "button";
      this.trigger.className = "custom-select-trigger";
      this.trigger.setAttribute("aria-haspopup", "listbox");
      this.trigger.setAttribute("aria-expanded", "false");

      const parentWrapper = this.selectEl.closest(".input-wrapper");
      const existingIcon = parentWrapper ? parentWrapper.querySelector(".input-icon") : null;
      if (existingIcon) {
        existingIcon.style.display = "none";
        const iconDiv = document.createElement("div");
        iconDiv.className = "custom-select-icon";
        iconDiv.innerHTML = existingIcon.innerHTML;
        this.trigger.appendChild(iconDiv);
      }

      this.valueSpan = document.createElement("span");
      this.valueSpan.className = "custom-select-value";
      this.trigger.appendChild(this.valueSpan);

      const chevronSvg = `
        <svg class="custom-select-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      `;
      this.trigger.insertAdjacentHTML("beforeend", chevronSvg);

      this.menu = document.createElement("div");
      this.menu.className = "custom-select-menu" +
        (this.config.compact ? " is-compact" : "") +
        (this.config.pillMini ? " is-pill-mini" : "") +
        (this.config.noScroll ? " is-no-scroll" : "");
      this.menu.dataset.dropdownId = this.wrapper.id;

      if (this.config.searchable) {
        const searchWrap = document.createElement("div");
        searchWrap.className = "custom-select-search-wrap";
        searchWrap.innerHTML = `
          <span class="custom-select-search-icon">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
          </span>
          <input type="text" class="custom-select-search-input" placeholder="${_ddEscapeHtml(this.config.searchPlaceholder)}">
        `;
        this.searchInput = searchWrap.querySelector("input");
        this.searchInput.addEventListener("input", (e) => this.filter(e.target.value));
        this.searchInput.addEventListener("keydown", (e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            const firstVis = this.optionsContainer.querySelector(".custom-select-option:not([style*='display: none'])");
            if (firstVis) firstVis.click();
          }
        });
        this.menu.appendChild(searchWrap);
      }

      this.optionsContainer = document.createElement("div");
      this.optionsContainer.className = "custom-select-options";
      this.optionsContainer.setAttribute("role", "listbox");
      this.menu.appendChild(this.optionsContainer);

      this.wrapper.appendChild(this.trigger);
      this.wrapper.appendChild(this.menu);

      this.selectEl.parentNode.insertBefore(this.wrapper, this.selectEl.nextSibling);

      this.trigger.addEventListener("click", (e) => {
        e.stopPropagation();
        if (this.selectEl.disabled) return;
        this.toggle();
      });

      this.sync();

      this.observer = new MutationObserver(() => this.sync());
      this.observer.observe(this.selectEl, { childList: true, attributes: true, attributeFilter: ["disabled"] });

      this.selectEl._modernDropdown = this;
    }

    toggle() {
      if (this.isOpen) {
        this.close();
      } else {
        this.open();
      }
    }

    reposition() {
      if (!this.isOpen || !this.trigger || !this.menu) return;
      const rect = this.trigger.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) {
        this.close();
        return;
      }

      const vw = window.innerWidth;
      const vh = window.innerHeight;
      let menuW = rect.width;
      if (this.config.pillMini) {
        menuW = Math.max(rect.width, 96);
      } else if (this.config.compact) {
        menuW = Math.min(Math.max(rect.width, 235), Math.min(320, vw - 24));
      } else {
        menuW = Math.min(rect.width, vw - 16);
      }

      let leftPos = rect.left;
      if (this.config.pillMini) {
        leftPos = rect.right - menuW;
      }
      leftPos = Math.max(8, Math.min(leftPos, vw - menuW - 8));

      const spaceBelow = vh - rect.bottom - 12;
      const spaceAbove = rect.top - 12;
      const desiredMin = this.config.pillMini ? 115 : 175;
      const openUp = !this.config.noScroll && spaceBelow < desiredMin && spaceAbove > spaceBelow;

      this.menu.style.position = "fixed";
      this.menu.style.left = leftPos + "px";
      this.menu.style.right = "auto";
      this.menu.style.width = menuW + "px";
      this.menu.style.minWidth = menuW + "px";
      this.menu.style.zIndex = "250000";

      const searchOverhead = this.config.searchable ? 52 : 12;
      const defaultOptMax = this.config.compact ? 220 : 290;

      if (openUp) {
        this.wrapper.classList.add("drop-up");
        this.menu.classList.add("drop-up");
        this.menu.style.top = "auto";
        this.menu.style.bottom = (vh - rect.top + 5) + "px";
        const maxOptsH = Math.max(96, Math.min(defaultOptMax, spaceAbove - searchOverhead));
        if (!this.config.noScroll) {
          this.optionsContainer.style.maxHeight = maxOptsH + "px";
        }
      } else {
        this.wrapper.classList.remove("drop-up");
        this.menu.classList.remove("drop-up");
        this.menu.style.bottom = "auto";
        this.menu.style.top = (rect.bottom + 5) + "px";
        const maxOptsH = Math.max(96, Math.min(defaultOptMax, spaceBelow - searchOverhead));
        if (!this.config.noScroll) {
          this.optionsContainer.style.maxHeight = maxOptsH + "px";
        }
      }
    }

    open() {
      if (this.selectEl.disabled) return;
      document.querySelectorAll(".custom-select-wrapper.open").forEach(w => {
        if (w !== this.wrapper) {
          const inst = w.previousElementSibling?._modernDropdown || document.getElementById(w.id.replace("customSelect_", ""))?._modernDropdown;
          if (inst && typeof inst.close === "function") {
            inst.close();
          } else {
            w.classList.remove("open");
            w.querySelector(".custom-select-trigger")?.setAttribute("aria-expanded", "false");
          }
        }
      });
      document.querySelectorAll(".ps-size-combo.open").forEach(c => {
        if (typeof c._closePsSizeMenu === "function") c._closePsSizeMenu();
        else c.classList.remove("open");
      });

      if (this.menu.parentNode !== document.body) {
        document.body.appendChild(this.menu);
      }

      this.wrapper.classList.add("open");
      this.menu.classList.add("open", "portal-open");
      this.trigger.setAttribute("aria-expanded", "true");
      this.isOpen = true;
      this.reposition();

      const sec = this.wrapper.closest(".sheet-section");
      if (sec) sec.classList.add("has-open-dropdown");
      const grd = this.wrapper.closest(".sheet-grid-2");
      if (grd) grd.classList.add("has-open-dropdown");

      if (this.searchInput) {
        this.searchInput.value = "";
        this.filter("");
        if (window.innerWidth > 768) {
          setTimeout(() => this.searchInput.focus(), 60);
        }
      }

      const selectedOpt = this.optionsContainer.querySelector(".custom-select-option.selected");
      if (selectedOpt) {
        setTimeout(() => selectedOpt.scrollIntoView({ block: "nearest" }), 50);
      }
    }

    close() {
      this.wrapper.classList.remove("open", "drop-up");
      this.menu.classList.remove("open", "drop-up", "portal-open");
      this.menu.style.position = "";
      this.menu.style.left = "";
      this.menu.style.right = "";
      this.menu.style.top = "";
      this.menu.style.bottom = "";
      this.menu.style.width = "";
      this.menu.style.minWidth = "";
      this.menu.style.zIndex = "";
      this.optionsContainer.style.maxHeight = "";
      if (this.wrapper && this.menu.parentNode !== this.wrapper) {
        this.wrapper.appendChild(this.menu);
      }
      this.trigger.setAttribute("aria-expanded", "false");
      this.isOpen = false;
      const sec = this.wrapper.closest(".sheet-section");
      if (sec) sec.classList.remove("has-open-dropdown");
      const grd = this.wrapper.closest(".sheet-grid-2");
      if (grd) grd.classList.remove("has-open-dropdown");
    }

    sync() {
      const isDisabled = this.selectEl.disabled;
      this.trigger.classList.toggle("disabled", isDisabled);

      this.optionsContainer.innerHTML = "";
      const options = Array.from(this.selectEl.options);
      const curVal = this.selectEl.value;

      let selectedText = "";
      let isPlaceholder = false;

      if (options.length === 0) {
        this.valueSpan.textContent = this.config.defaultPlaceholder;
        this.valueSpan.classList.add("is-placeholder");
        return;
      }

      options.forEach((opt, idx) => {
        if (this.config.isFont && opt.value === "__custom__" && idx > 0) {
          const div = document.createElement("div");
          div.className = "custom-select-divider";
          this.optionsContainer.appendChild(div);
        }

        const item = document.createElement("div");
        item.className = "custom-select-option" + (opt.value === curVal ? " selected" : "");
        item.dataset.value = opt.value;
        item.dataset.searchText = opt.textContent;

        let contentHtml = "";

        if (this.config.isOfficial && opt.value !== "") {
          const rawText = opt.textContent;
          let posText = "";
          let nameText = rawText;
          if (rawText.includes(" — ")) {
            const parts = rawText.split(" — ");
            posText = parts[0] || "";
            nameText = parts[1] || parts[0];
          } else if (rawText.includes(" - ")) {
            const parts = rawText.split(" - ");
            posText = parts[0] || "";
            nameText = parts[1] || parts[0];
          }
          item.dataset.searchText = `${nameText} ${posText}`;

          const photoUrl = opt.dataset.photo || "";
          const personSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`;
          let avatarHtml = "";
          if (photoUrl) {
            avatarHtml = `
              <div class="custom-select-opt-avatar has-photo">
                <img src="${_ddEscapeHtml(photoUrl)}" referrerpolicy="no-referrer" alt="" loading="lazy" onerror="this.parentElement.classList.remove('has-photo'); this.remove();">
                ${personSvg}
              </div>
            `;
          } else {
            avatarHtml = `<div class="custom-select-opt-avatar">${personSvg}</div>`;
          }

          contentHtml = `
            <div class="custom-select-opt-content">
              ${avatarHtml}
              <div class="custom-select-opt-text">
                <span class="custom-select-opt-title">${_ddEscapeHtml(nameText)}</span>
                ${posText ? `<span class="custom-select-opt-sub">${_ddEscapeHtml(posText)}</span>` : ""}
              </div>
            </div>
          `;
        } else if (this.config.isFont) {
          let badgeHtml = "";
          let fontStyle = "";
          if (opt.value === "Montserrat") {
            badgeHtml = `<span class="custom-select-opt-badge badge-kemnaker">Default</span>`;
            fontStyle = 'style="font-family: \'Montserrat-Bold\', Montserrat, sans-serif; font-weight: 700;"';
          } else if (opt.value === "MyriadPro") {
            badgeHtml = `<span class="custom-select-opt-badge badge-neutral">Standar</span>`;
            fontStyle = 'style="font-family: MyriadPro, Arial, sans-serif; font-weight: 600;"';
          } else if (opt.value === "Arial") {
            fontStyle = 'style="font-family: Arial, sans-serif;"';
          } else if (opt.value === "Times New Roman") {
            fontStyle = 'style="font-family: \'Times New Roman\', serif;"';
          } else if (opt.value === "Calibri") {
            fontStyle = 'style="font-family: Calibri, sans-serif;"';
          } else if (opt.value === "Plus Jakarta Sans") {
            badgeHtml = `<span class="custom-select-opt-badge badge-neutral">Modern</span>`;
            fontStyle = 'style="font-family: \'Plus Jakarta Sans\', sans-serif; font-weight: 600;"';
          } else if (opt.value === "Roboto") {
            fontStyle = 'style="font-family: Roboto, sans-serif;"';
          } else if (opt.value === "Open Sans") {
            fontStyle = 'style="font-family: \'Open Sans\', sans-serif;"';
          } else if (opt.value === "Georgia") {
            fontStyle = 'style="font-family: Georgia, serif;"';
          } else if (opt.value === "Garamond") {
            fontStyle = 'style="font-family: \'EB Garamond\', Garamond, serif;"';
          } else if (opt.value === "__custom__") {
            badgeHtml = `<span class="custom-select-opt-badge badge-action">Upload</span>`;
          } else if (opt.value.startsWith("CustomUserFont") || opt.value.startsWith("CustomNameFont") || opt.value.startsWith("CustomPosFont")) {
            badgeHtml = `<span class="custom-select-opt-badge badge-action">Kustom</span>`;
            fontStyle = `style="font-family: '${opt.value}', sans-serif; font-weight: 600;"`;
          }

          if (opt.value === "__custom__") {
            contentHtml = `
              <div class="custom-select-opt-content custom-select-opt-upload">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="color: var(--kemnaker-blue); flex-shrink: 0;">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="17 8 12 3 7 8"></polyline>
                  <line x1="12" y1="3" x2="12" y2="15"></line>
                </svg>
                <span class="custom-select-opt-title" style="font-weight: 600; color: var(--kemnaker-blue);">${_ddEscapeHtml(opt.textContent)}</span>
                ${badgeHtml}
              </div>
            `;
          } else {
            contentHtml = `
              <div class="custom-select-opt-content" ${fontStyle}>
                <span class="custom-select-opt-title">${_ddEscapeHtml(opt.textContent)}</span>
                ${badgeHtml}
              </div>
            `;
          }
        } else if (this.config.isSimple || this.config.pillMini) {
          contentHtml = `
            <div class="custom-select-opt-content">
              <div class="custom-select-opt-text">
                <span class="custom-select-opt-title">${_ddEscapeHtml(opt.textContent)}</span>
              </div>
            </div>
          `;
        } else {
          let iconHtml = "";
          let badgeHtml = "";
          if (opt.value === "__all__") {
            badgeHtml = `<span class="custom-select-opt-badge badge-kemnaker">Semua</span>`;
          } else if (opt.value !== "") {
            iconHtml = `
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--kemnaker-blue); flex-shrink: 0;">
                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
                <polyline points="9 22 9 12 15 12 15 22"></polyline>
              </svg>
            `;
          }

          contentHtml = `
            <div class="custom-select-opt-content">
              ${iconHtml}
              <div class="custom-select-opt-text">
                <span class="custom-select-opt-title">${_ddEscapeHtml(opt.textContent)}</span>
              </div>
              ${badgeHtml}
            </div>
          `;
        }

        const checkSvg = `
          <svg class="custom-select-opt-check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        `;

        item.innerHTML = contentHtml + checkSvg;

        item.addEventListener("click", (e) => {
          e.stopPropagation();
          this.selectValue(opt.value);
          this.close();
        });

        this.optionsContainer.appendChild(item);

        if (opt.value === curVal || (curVal === "" && idx === 0)) {
          selectedText = opt.textContent;
          isPlaceholder = (opt.value === "");
        }
      });

      if (!selectedText) {
        const selectedOpt = this.selectEl.options[this.selectEl.selectedIndex];
        selectedText = selectedOpt ? selectedOpt.textContent : this.config.defaultPlaceholder;
        isPlaceholder = (!selectedOpt || selectedOpt.value === "");
      }

      if (this.config.isOfficial && this.selectEl.value !== "") {
        if (selectedText.includes(" — ")) {
          const parts = selectedText.split(" — ");
          selectedText = `${parts[1]} (${parts[0]})`;
        }
      }

      this.valueSpan.textContent = selectedText;
      this.valueSpan.title = selectedText || "";
      this.valueSpan.classList.toggle("is-placeholder", isPlaceholder);

      if (this.config.isFont && curVal && curVal !== "__custom__" && typeof global.getFontFamilyCss === "function") {
        this.valueSpan.style.fontFamily = global.getFontFamilyCss(curVal);
        this.valueSpan.style.fontWeight = curVal === "Montserrat" ? "700" : "600";
      }

      if (this.config.isOfficial) {
        const iconDiv = this.trigger.querySelector(".custom-select-icon");
        if (iconDiv) {
          const selectedOpt = this.selectEl.options[this.selectEl.selectedIndex];
          const selPhoto = (selectedOpt && selectedOpt.dataset.photo) ? selectedOpt.dataset.photo : "";
          if (selPhoto && this.selectEl.value !== "") {
            iconDiv.innerHTML = `<img src="${_ddEscapeHtml(selPhoto)}" referrerpolicy="no-referrer" style="width: 22px; height: 22px; border-radius: 6px; object-fit: cover; display: block;" alt="" onerror="this.remove()">`;
          } else {
            iconDiv.innerHTML = `
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
                <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
              </svg>
            `;
          }
        }
      }
    }

    selectValue(val) {
      this.selectEl.value = val;
      this.selectEl.dispatchEvent(new Event("change", { bubbles: true }));
      if (typeof this.selectEl.onchange === "function") {
        this.selectEl.onchange();
      }
      this.sync();
    }

    filter(query) {
      const q = (query || "").trim().toLowerCase();
      const items = this.optionsContainer.querySelectorAll(".custom-select-option");
      let visibleCount = 0;

      items.forEach(item => {
        const text = (item.dataset.searchText || "").toLowerCase();
        const match = !q || text.includes(q);
        item.style.display = match ? "flex" : "none";
        if (match) visibleCount++;
      });

      let emptyMsg = this.optionsContainer.querySelector(".custom-select-empty");
      if (visibleCount === 0) {
        if (!emptyMsg) {
          emptyMsg = document.createElement("div");
          emptyMsg.className = "custom-select-empty";
          emptyMsg.textContent = "Tidak ditemukan hasil yang cocok";
          this.optionsContainer.appendChild(emptyMsg);
        }
        emptyMsg.style.display = "block";
      } else if (emptyMsg) {
        emptyMsg.style.display = "none";
      }
    }
  }

  function closeAllCustomDropdowns() {
    document.querySelectorAll(".custom-select-wrapper.open").forEach(w => {
      const selectId = w.id ? w.id.replace("customSelect_", "") : "";
      const inst = selectId ? document.getElementById(selectId)?._modernDropdown : null;
      if (inst && typeof inst.close === "function") {
        inst.close();
      } else {
        w.classList.remove("open");
        w.querySelector(".custom-select-trigger")?.setAttribute("aria-expanded", "false");
      }
    });
  }

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".custom-select-wrapper") && !e.target.closest(".custom-select-menu")) {
      closeAllCustomDropdowns();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeAllCustomDropdowns();
    }
  });

  window.addEventListener("scroll", (e) => {
    if (e.target && e.target.closest && e.target.closest(".custom-select-menu")) return;
    document.querySelectorAll(".custom-select-wrapper.open").forEach(w => {
      const selectId = w.id ? w.id.replace("customSelect_", "") : "";
      const inst = selectId ? document.getElementById(selectId)?._modernDropdown : null;
      if (inst && typeof inst.reposition === "function") inst.reposition();
    });
  }, true);

  window.addEventListener("resize", () => {
    document.querySelectorAll(".custom-select-wrapper.open").forEach(w => {
      const selectId = w.id ? w.id.replace("customSelect_", "") : "";
      const inst = selectId ? document.getElementById(selectId)?._modernDropdown : null;
      if (inst && typeof inst.reposition === "function") inst.reposition();
    });
  });

  global.ModernDropdown = ModernDropdown;
  global.closeAllCustomDropdowns = closeAllCustomDropdowns;
})(window);
