/* Tala: progressive enhancement. Every page works without this file; it adds tap-to-mark seat
   plans, one-by-one roll call, the QR scanner and the picker. No inline scripts (strict CSP). */
(function () {
  "use strict";
  document.documentElement.classList.replace("no-js", "js");

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const csrf = (root = document) => ($("input[name=csrfmiddlewaretoken]", root) || {}).value || "";

  async function post(url, data, root) {
    const body = new FormData();
    Object.entries(data).forEach(([k, v]) => body.append(k, v));
    const res = await fetch(url, {
      method: "POST",
      body,
      headers: { "X-CSRFToken": csrf(root), Accept: "application/json" },
      credentials: "same-origin",
    });
    let json = {};
    try { json = await res.json(); } catch (e) { /* not JSON */ }
    return { ok: res.ok, json };
  }

  // ---- Small helpers: confirm, copy, print, auto-submit, Enter moves down --------------------
  document.addEventListener("submit", (e) => {
    const msg = e.target.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) e.preventDefault();
  });
  $$("[data-copy]").forEach((btn) => btn.addEventListener("click", async () => {
    const input = $(btn.getAttribute("data-copy"));
    try { await navigator.clipboard.writeText(input.value); btn.textContent = "Copied"; }
    catch (e) { input.select(); }
  }));
  $$("[data-print]").forEach((btn) => btn.addEventListener("click", () => window.print()));
  $$("[data-autosubmit]").forEach((el) => el.addEventListener("change", () => el.form.submit()));
  $$("[data-score-input]").forEach((input, i, all) => input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); (all[i + 1] || input).focus(); }
  }));

  // ---- Seat plan editor: tap a learner, tap a seat (or drag) -----------------------------------
  const editor = $("[data-seat-editor]");
  if (editor) {
    const url = editor.getAttribute("data-url");
    let selected = null;
    const clear = () => { $$(".is-selected", editor).forEach((el) => el.classList.remove("is-selected")); selected = null; };
    const move = async (learner, row, col) => {
      const res = await post(url, { action: "move", learner, row: row ?? "off", col: col ?? "off" }, editor);
      if (!res.ok) { window.alert(res.json.error || "Couldn't move that learner."); return; }
      window.location.reload();
    };
    editor.addEventListener("click", (e) => {
      const chip = e.target.closest("[data-chip]");
      const seat = e.target.closest("[data-seat]");
      const off = e.target.closest("[data-seat-off]");
      if (chip) {
        if (selected === chip) { clear(); return; }
        clear(); selected = chip; chip.classList.add("is-selected"); return;
      }
      if (seat) {
        if (selected && selected !== seat) {
          move(selected.getAttribute("data-learner"), seat.getAttribute("data-row"), seat.getAttribute("data-col"));
          return;
        }
        if (selected === seat) { clear(); return; }
        if (seat.hasAttribute("data-learner")) { clear(); selected = seat; seat.classList.add("is-selected"); }
        return;
      }
      if (off && selected && selected.hasAttribute("data-seat")) move(selected.getAttribute("data-learner"), null, null);
    });
    editor.addEventListener("dragstart", (e) => {
      const el = e.target.closest("[data-learner]");
      if (el) e.dataTransfer.setData("text/plain", el.getAttribute("data-learner"));
    });
    editor.addEventListener("dragover", (e) => {
      const target = e.target.closest("[data-seat], [data-seat-off]");
      if (target) { e.preventDefault(); target.classList.add("is-target"); }
    });
    editor.addEventListener("dragleave", (e) => {
      const target = e.target.closest("[data-seat], [data-seat-off]");
      if (target) target.classList.remove("is-target");
    });
    editor.addEventListener("drop", (e) => {
      const learner = e.dataTransfer.getData("text/plain");
      const seat = e.target.closest("[data-seat]");
      const off = e.target.closest("[data-seat-off]");
      if (!learner) return;
      e.preventDefault();
      if (seat) move(learner, seat.getAttribute("data-row"), seat.getAttribute("data-col"));
      else if (off) move(learner, null, null);
    });
  }

  // ---- Attendance: seat taps and one-by-one roll call share the list's radio buttons ----------
  const form = $("[data-attendance]");
  if (form) {
    const ORDER = ["P", "L", "E", "A"];
    const LABEL = { P: "Present", L: "Late", E: "Excused", A: "Absent" };
    const radios = (id) => $$(`input[name="s-${id}"]`, form);
    const get = (id) => (radios(id).find((r) => r.checked) || {}).value || "";
    const counts = $("[data-counts]");
    const refresh = () => {
      const tally = { P: 0, L: 0, E: 0, A: 0 };
      $$("[data-row]", form).forEach((row) => { const s = get(row.getAttribute("data-row")); if (s) tally[s] += 1; });
      counts.textContent = "";
      ORDER.forEach((code) => {
        if (!tally[code]) return;
        const pill = document.createElement("span");
        pill.className = `pill st-${code}`;
        pill.textContent = `${tally[code]} ${code}`;
        counts.append(pill, " ");
      });
      if (!counts.childElementCount) counts.textContent = "Nothing marked yet";
    };
    const set = (id, status) => {
      radios(id).forEach((r) => { r.checked = r.value === status; });
      $$(`[data-mark-seat="${id}"]`, form).forEach((seat) => {
        seat.setAttribute("data-status", status);
        $("[data-badge]", seat).textContent = status;
      });
      refresh();
    };
    form.addEventListener("change", (e) => {
      const m = e.target.name && e.target.name.match(/^s-(\d+)$/);
      if (m) set(m[1], e.target.value);
    });
    form.addEventListener("click", (e) => {
      const seat = e.target.closest("[data-mark-seat]");
      if (!seat) return;
      const id = seat.getAttribute("data-mark-seat");
      const now = get(id);
      set(id, ORDER[(ORDER.indexOf(now) + 1) % ORDER.length]);
    });
    const allPresent = $("[data-all-present]", form);
    if (allPresent) allPresent.addEventListener("click", () => {
      $$("[data-row]", form).forEach((row) => { const id = row.getAttribute("data-row"); if (!get(id)) set(id, "P"); });
    });

    const roll = $("[data-roll]", form);
    if (roll) {
      const rows = $$("[data-row]", form);
      let i = Math.max(0, rows.findIndex((row) => !get(row.getAttribute("data-row"))));
      const show = () => {
        if (i >= rows.length) {
          $("[data-roll-name]", roll).textContent = "All done!";
          $("[data-roll-init]", roll).textContent = "✓";
          $("[data-roll-current]", roll).textContent = "Press “Save attendance”.";
          $("[data-roll-count]", roll).textContent = `${rows.length} of ${rows.length}`;
          return;
        }
        const row = rows[i];
        const status = get(row.getAttribute("data-row"));
        $("[data-roll-name]", roll).textContent = row.getAttribute("data-name");
        $("[data-roll-init]", roll).textContent = row.getAttribute("data-initials");
        $("[data-roll-current]", roll).textContent = status ? `Marked: ${LABEL[status]}` : "Not marked yet";
        $("[data-roll-count]", roll).textContent = `${i + 1} of ${rows.length}`;
      };
      roll.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-roll-set]");
        if (btn && i < rows.length) { set(rows[i].getAttribute("data-row"), btn.getAttribute("data-roll-set")); i += 1; }
        if (e.target.closest("[data-roll-prev]")) i = Math.max(0, i - 1);
        if (e.target.closest("[data-roll-next]")) i = Math.min(rows.length, i + 1);
        show();
      });
      show();
    }
    refresh();
  }

  // ---- QR scanner -----------------------------------------------------------------------------
  const scanner = $("[data-scanner]");
  if (scanner) {
    const video = $("[data-video]", scanner);
    const idle = $("[data-idle]", scanner);
    const status = $("[data-status]", scanner);
    const log = $("[data-log]", scanner);
    const marked = $("[data-marked]", scanner);
    const late = $("[data-late]", scanner);
    const url = scanner.getAttribute("data-url");
    let stream = null, detector = null, canvas = null, running = false;
    const recent = new Map(); // code -> time, to ignore the same card for a few seconds

    const beep = () => {
      try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator(); const gain = ctx.createGain();
        osc.frequency.value = 880; gain.gain.value = 0.08;
        osc.connect(gain).connect(ctx.destination); osc.start(); osc.stop(ctx.currentTime + 0.12);
      } catch (e) { /* no audio */ }
    };
    const loadJsQR = () => new Promise((resolve, reject) => {
      if (window.jsQR) { resolve(); return; }
      const s = document.createElement("script");
      s.src = scanner.getAttribute("data-jsqr"); s.onload = resolve; s.onerror = reject;
      document.head.append(s);
    });
    const read = async () => {
      if (detector) {
        const codes = await detector.detect(video);
        return codes.length ? codes[0].rawValue : null;
      }
      const w = video.videoWidth, h = video.videoHeight;
      if (!w) return null;
      canvas = canvas || document.createElement("canvas");
      canvas.width = w; canvas.height = h;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      ctx.drawImage(video, 0, 0, w, h);
      const found = window.jsQR(ctx.getImageData(0, 0, w, h).data, w, h, { inversionAttempts: "dontInvert" });
      return found ? found.data : null;
    };
    const handle = async (code) => {
      const now = Date.now();
      if (recent.has(code) && now - recent.get(code) < 4000) return;
      recent.set(code, now);
      if (!code.startsWith("TALA:")) { status.textContent = "That's not a Tala card."; return; }
      const res = await post(url, { code, late: late.checked ? "1" : "0" }, scanner);
      const item = document.createElement("li");
      if (res.ok) {
        beep();
        if (navigator.vibrate) navigator.vibrate(60);
        const name = document.createElement("span"); name.textContent = res.json.name;
        const pill = document.createElement("span");
        pill.className = `pill ${res.json.status === "Late" ? "st-L" : "st-P"}`; pill.textContent = res.json.status;
        item.append(name, pill); item.className = "flash";
        marked.textContent = res.json.marked;
        status.textContent = `${res.json.name}: ${res.json.status}`;
      } else {
        item.textContent = res.json.error || "Couldn't mark that card.";
        status.textContent = item.textContent;
      }
      log.prepend(item);
    };
    const loop = async () => {
      if (!running) return;
      try { const code = await read(); if (code) await handle(code); } catch (e) { /* keep scanning */ }
      setTimeout(loop, 250);
    };
    const start = async () => {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        status.textContent = "This browser can't use the camera. Use the seat plan instead."; return;
      }
      try {
        if ("BarcodeDetector" in window) {
          const formats = await window.BarcodeDetector.getSupportedFormats();
          if (formats.includes("qr_code")) detector = new window.BarcodeDetector({ formats: ["qr_code"] });
        }
        if (!detector) await loadJsQR();
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
        video.srcObject = stream; await video.play();
        idle.hidden = true; running = true; status.textContent = "Scanning…"; loop();
      } catch (e) {
        status.textContent = "Camera not available. Allow camera access, or use the seat plan.";
      }
    };
    const stop = () => {
      running = false;
      if (stream) stream.getTracks().forEach((t) => t.stop());
      stream = null; idle.hidden = false; status.textContent = "Camera off.";
    };
    $("[data-start]", scanner).addEventListener("click", start);
    $("[data-stop]", scanner).addEventListener("click", stop);
    window.addEventListener("pagehide", stop);
  }

  // ---- Recitation picker ----------------------------------------------------------------------
  const picker = $("[data-picker]");
  if (picker) {
    const all = JSON.parse($("#picker-names").textContent);
    const out = $("[data-picker-name]", picker);
    const left = $("[data-picker-left]", picker);
    const done = $("[data-picker-done]", picker);
    const presentOnly = $("[data-picker-present]", picker);
    const picked = new Set();
    const pool = () => all.filter((p) => !picked.has(p.id) && (!presentOnly.checked || p.here === "P" || p.here === "L"));
    const update = () => { const n = pool().length; left.textContent = n ? `${n} left to pick` : "Everyone has been picked."; };
    const rand = (n) => { const a = new Uint32Array(1); crypto.getRandomValues(a); return a[0] % n; };
    $("[data-picker-go]", picker).addEventListener("click", () => {
      const options = pool();
      if (!options.length) { update(); return; }
      const winner = options[rand(options.length)];
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      let ticks = reduce ? 0 : 14;
      out.classList.remove("is-done"); out.classList.add("is-rolling");
      const tick = () => {
        if (ticks-- > 0) { out.textContent = options[rand(options.length)].name; setTimeout(tick, 60 + (14 - ticks) * 8); return; }
        out.textContent = winner.name; out.classList.remove("is-rolling"); out.classList.add("is-done");
        picked.add(winner.id);
        const chip = document.createElement("span"); chip.className = "chip"; chip.textContent = winner.name;
        done.prepend(chip); update();
      };
      tick();
    });
    $("[data-picker-reset]", picker).addEventListener("click", () => {
      picked.clear(); done.textContent = ""; out.textContent = "Tap “Pick”"; out.classList.remove("is-done"); update();
    });
    presentOnly.addEventListener("change", update);
    update();
  }

  // ---- Answer checking: live row scores; a learner who didn't take it is greyed out -----------
  const responses = $("[data-responses]");
  if (responses) {
    const score = (row) => {
      const took = $("[data-took]", row).checked;
      row.classList.toggle("is-off", !took);
      $$("[data-item]", row).forEach((box) => { box.disabled = !took; });
      $("[data-row-score]", row).textContent = took ? $$("[data-item]:checked", row).length : "-";
    };
    $$("[data-resp-row]", responses).forEach(score);
    responses.addEventListener("change", (e) => { const row = e.target.closest("[data-resp-row]"); if (row) score(row); });
  }
})();
