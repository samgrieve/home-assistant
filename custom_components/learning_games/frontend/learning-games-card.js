/* Learning Games card — touch-first maths & English games for kids.
 * Vanilla web component: no build step, no external dependencies, works
 * offline on tablets. Talks to the learning_games integration over the
 * Home Assistant websocket (hass.callWS — auth is automatic).
 */
(() => {
  "use strict";

  const AVATARS = {
    fox: "🦊", owl: "🦉", cat: "🐱", dragon: "🐲",
    unicorn: "🦄", robot: "🤖", panda: "🐼", rocket: "🚀",
  };

  const SUBJECT_COLORS = {
    maths: ["#6C5CE7", "#8E7CF8"],
    english: ["#00B894", "#26D0A8"],
    challenge: ["#d63031", "#e84393"],
  };

  const ARCADE_CATEGORIES = [
    { id: "synonyms", label: "Synonyms", emoji: "📖", blurb: "Words that mean the same" },
    { id: "antonyms", label: "Antonyms", emoji: "🔄", blurb: "Words that mean the opposite" },
    { id: "homophones", label: "Homophones", emoji: "👯", blurb: "Words that sound the same" },
  ];

  const PRAISE = ["Brilliant!", "Nailed it!", "Super!", "You star!", "Wowza!", "Genius!"];
  const NUDGE = ["Nearly!", "Good try!", "Keep going!", "You'll get it!"];

  class LearningGamesCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this.S = {
        screen: "loading",
        error: null,
        profiles: null,
        profile: null,       // {profile_id, name, avatar, ...}
        stats: null,
        badges: null,
        session: null,       // {session_id, total}
        mode: null,          // mode id of the active round
        question: null,
        shownAt: 0,
        feedback: null,      // {correct, correctAnswer, explain, xpDelta, praise}
        results: null,
        celebrating: false,
        entry: { value: "", remainder: "", field: "value", letters: [], usedTiles: [] },
        busy: false,
        bossHits: 0,
        arcadeResults: null,
      };
      this.A = null; // live Fly Snap state — never touched by _render()
      this._onVisibility = () => {
        if (document.hidden && this.A && this.A.phase === "play") this._arcadePause();
      };
      this._initialized = false;
      this._audio = null;
      this._confetti = [];
      this._confettiRunning = false;
    }

    setConfig(config) {
      this._config = config || {};
      this._sounds = this._config.sounds !== false;
    }

    static getStubConfig() {
      return {};
    }

    getCardSize() {
      return 8;
    }

    set hass(hass) {
      this._hass = hass;
      if (!this._initialized && this.isConnected) {
        this._initialized = true;
        this._firstRender();
        this._loadProfiles();
      }
    }

    connectedCallback() {
      if (this._hass && !this._initialized) {
        this._initialized = true;
        this._firstRender();
        this._loadProfiles();
      }
    }

    // ------------------------------------------------------------ data

    async _ws(msg) {
      return this._hass.callWS(msg);
    }

    async _loadProfiles() {
      try {
        const profiles = await this._ws({ type: "learning_games/get_profiles" });
        this.S.profiles = profiles;
        const want = (this._config.profile || "").toLowerCase();
        let chosen = null;
        if (want) {
          chosen = profiles.find(
            (p) => p.name.toLowerCase() === want || p.profile_id === this._config.profile
          );
        } else if (profiles.length === 1) {
          chosen = profiles[0];
        }
        if (chosen) {
          this.S.profile = chosen;
          await this._goHome();
        } else if (profiles.length === 0) {
          this._setError("No player profiles yet. Add one in Settings → Devices & services → Learning Games.");
        } else {
          this.S.screen = "pick";
          this._render();
        }
      } catch (err) {
        this._setError("Couldn't reach Learning Games. Is the integration installed?");
      }
    }

    async _goHome() {
      try {
        this.S.stats = await this._ws({
          type: "learning_games/get_stats",
          profile_id: this.S.profile.profile_id,
        });
        this.S.screen = "home";
        this.S.results = null;
        this.S.question = null;
        this.S.session = null;
        this._render();
      } catch (err) {
        this._setError("Couldn't load your stats. Try again in a moment.");
      }
    }

    async _startRound(modeId) {
      if (this.S.busy) return;
      this.S.busy = true;
      try {
        const res = await this._ws({
          type: "learning_games/start_session",
          profile_id: this.S.profile.profile_id,
          mode: modeId,
          length: 10,
        });
        this.S.session = { session_id: res.session_id, total: res.total };
        this.S.mode = modeId;
        this.S.screen = "game";
        this.S.bossHits = 0;
        this._setQuestion(res.question);
      } catch (err) {
        this._setError("Couldn't start the game. Give it another go!");
      } finally {
        this.S.busy = false;
      }
    }

    _setQuestion(question) {
      this.S.question = question;
      this.S.feedback = null;
      this.S.entry = { value: "", remainder: "", field: "value", letters: [], usedTiles: [] };
      this.S.shownAt = performance.now();
      this._render();
    }

    async _submit(answer) {
      if (this.S.busy || this.S.feedback) return;
      this.S.busy = true;
      const elapsed = Math.round(performance.now() - this.S.shownAt);
      let res;
      try {
        res = await this._ws({
          type: "learning_games/submit_answer",
          profile_id: this.S.profile.profile_id,
          session_id: this.S.session.session_id,
          question_id: this.S.question.question_id,
          answer: String(answer),
          elapsed_ms: elapsed,
        });
      } catch (err) {
        this.S.busy = false;
        if (err && err.code === "session_not_found") {
          this._toastAndHome("Oops, that round expired — let's start a fresh one!");
        } else {
          this._setError("Connection hiccup — your round is safe, try the answer again.");
          this.S.screen = "game";
          setTimeout(() => this._render(), 1500);
        }
        return;
      }
      this.S.busy = false;
      this.S.feedback = {
        correct: res.correct,
        correctAnswer: res.correct_answer,
        explain: res.explain,
        xpDelta: res.xp_delta,
        speedBonus: res.speed_bonus,
        runStreak: res.run_streak,
        praise: res.correct
          ? PRAISE[Math.floor(Math.random() * PRAISE.length)]
          : NUDGE[Math.floor(Math.random() * NUDGE.length)],
      };
      if (res.correct) this.S.bossHits += 1;
      this._render();
      if (res.correct) {
        this._sound("correct");
        if (res.run_streak >= 3) this._burstConfetti(30 + res.run_streak * 4);
      } else {
        this._sound("wrong");
      }
      const delay = res.correct ? 1100 : 2400;
      setTimeout(() => {
        if (res.results) {
          this.S.results = res.results;
          this.S.screen = "results";
          this._render();
          this._sound(res.results.level_up ? "levelup" : "finish");
          if (res.results.level_up || res.results.correct === res.results.total) {
            this._burstConfetti(160);
          }
        } else if (res.next_question) {
          this._setQuestion(res.next_question);
        }
      }, delay);
    }

    async _quitRound() {
      if (this.S.session) {
        try {
          await this._ws({
            type: "learning_games/abandon_session",
            profile_id: this.S.profile.profile_id,
            session_id: this.S.session.session_id,
          });
        } catch (err) { /* already gone — fine */ }
      }
      this._goHome();
    }

    async _showBadges() {
      try {
        this.S.badges = await this._ws({
          type: "learning_games/get_badges",
          profile_id: this.S.profile.profile_id,
        });
        this.S.screen = "badges";
        this._render();
      } catch (err) {
        this._setError("Couldn't load badges right now.");
      }
    }

    _setError(message) {
      this.S.screen = "error";
      this.S.error = message;
      this._render();
    }

    _toastAndHome(message) {
      this.S.error = message;
      this.S.screen = "error";
      this._render();
      setTimeout(() => this._goHome(), 2200);
    }

    // ------------------------------------------------------------ audio

    _ensureAudio() {
      if (!this._sounds) return null;
      if (!this._audio) {
        try {
          this._audio = new (window.AudioContext || window.webkitAudioContext)();
        } catch (err) {
          return null;
        }
      }
      if (this._audio.state === "suspended") this._audio.resume();
      return this._audio;
    }

    _beep(freq, start, duration, type = "sine", gain = 0.12) {
      const ctx = this._audio;
      const osc = ctx.createOscillator();
      const amp = ctx.createGain();
      osc.type = type;
      osc.frequency.value = freq;
      amp.gain.setValueAtTime(gain, ctx.currentTime + start);
      amp.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + duration);
      osc.connect(amp).connect(ctx.destination);
      osc.start(ctx.currentTime + start);
      osc.stop(ctx.currentTime + start + duration + 0.02);
    }

    _sound(kind) {
      if (!this._ensureAudio()) return;
      if (kind === "tap") this._beep(600, 0, 0.05, "square", 0.04);
      else if (kind === "correct") { this._beep(660, 0, 0.12); this._beep(880, 0.1, 0.18); }
      else if (kind === "wrong") this._beep(180, 0, 0.3, "sawtooth", 0.08);
      else if (kind === "finish") { this._beep(523, 0, 0.12); this._beep(659, 0.12, 0.12); this._beep(784, 0.24, 0.25); }
      else if (kind === "levelup") {
        [523, 659, 784, 1047].forEach((f, i) => this._beep(f, i * 0.12, 0.2));
      }
    }

    // ------------------------------------------------------------ confetti

    _burstConfetti(count) {
      const canvas = this.shadowRoot.getElementById("fx");
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width;
      canvas.height = rect.height;
      const colors = ["#FDCB6E", "#E17055", "#00B894", "#6C5CE7", "#0984E3", "#E84393"];
      for (let i = 0; i < count; i++) {
        this._confetti.push({
          x: rect.width * Math.random(),
          y: -10 - Math.random() * 40,
          vx: (Math.random() - 0.5) * 3,
          vy: 2 + Math.random() * 3.5,
          size: 5 + Math.random() * 6,
          rot: Math.random() * Math.PI,
          vr: (Math.random() - 0.5) * 0.3,
          color: colors[i % colors.length],
        });
      }
      if (!this._confettiRunning) this._runConfetti(canvas);
    }

    _runConfetti(canvas) {
      this._confettiRunning = true;
      const ctx = canvas.getContext("2d");
      const step = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        this._confetti = this._confetti.filter((p) => p.y < canvas.height + 20);
        for (const p of this._confetti) {
          p.x += p.vx;
          p.y += p.vy;
          p.rot += p.vr;
          ctx.save();
          ctx.translate(p.x, p.y);
          ctx.rotate(p.rot);
          ctx.fillStyle = p.color;
          ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
          ctx.restore();
        }
        if (this._confetti.length) {
          requestAnimationFrame(step);
        } else {
          this._confettiRunning = false;
          ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
      };
      requestAnimationFrame(step);
    }

    // ------------------------------------------------------------ entry handling

    _keypadPress(key) {
      const entry = this.S.entry;
      const field = entry.field;
      this._sound("tap");
      if (key === "back") {
        entry[field] = entry[field].slice(0, -1);
      } else if (key === "sign") {
        entry[field] = entry[field].startsWith("-")
          ? entry[field].slice(1)
          : "-" + entry[field];
      } else if (key === "." && !entry[field].includes(".")) {
        entry[field] += ".";
      } else if (/^[0-9]$/.test(key) && entry[field].replace("-", "").length < 7) {
        entry[field] += key;
      }
      this._render();
    }

    _tilePress(index) {
      const q = this.S.question;
      const entry = this.S.entry;
      const blanks = (q.fill_pattern.match(/_/g) || []).length;
      if (entry.letters.length >= blanks) return;
      if (q.type === "unscramble" && entry.usedTiles.includes(index)) return;
      this._sound("tap");
      entry.letters.push(q.options[index]);
      entry.usedTiles.push(index);
      this._render();
    }

    _tileBackspace() {
      const entry = this.S.entry;
      if (!entry.letters.length) return;
      this._sound("tap");
      entry.letters.pop();
      entry.usedTiles.pop();
      this._render();
    }

    _assembleWord() {
      const q = this.S.question;
      const letters = [...this.S.entry.letters];
      let out = "";
      for (const ch of q.fill_pattern) {
        out += ch === "_" ? (letters.shift() || "_") : ch;
      }
      return out;
    }

    // ------------------------------------------------------------ Fly Snap arcade

    async _startArcade(category) {
      if (this.S.busy) return;
      this.S.busy = true;
      try {
        const res = await this._ws({
          type: "learning_games/start_arcade",
          profile_id: this.S.profile.profile_id,
          category,
        });
        this.A = {
          game: res,
          category,
          round: 1,
          lives: res.lives,
          phase: "intro",
          pairIdx: 0,
          pairs: [],
          flies: [],
          frogWord: "",
          matchIdx: -1,
          timeLeft: res.round_time_s,
          lastTs: 0,
          raf: 0,
          lockedUntil: 0,
          correct: 0,
          wrong: 0,
          roundsCompleted: 0,
          roundsPlayed: 0,
        };
        document.addEventListener("visibilitychange", this._onVisibility);
        this.S.screen = "arcade";
        this._render();
        this._arcadeBind();
        this._arcadeOverlay(`Round 1`, "Tap the fly that matches the frog's word!", "Start");
      } catch (err) {
        this._setError("Couldn't start Fly Snap. Give it another go!");
      } finally {
        this.S.busy = false;
      }
    }

    _arcadeEls() {
      const root = this.shadowRoot;
      return {
        pond: root.getElementById("pond"),
        frogword: root.getElementById("frogword"),
        bar: root.getElementById("abar-fill"),
        lives: root.getElementById("alives"),
        roundLabel: root.getElementById("around"),
        overlay: root.getElementById("aoverlay"),
        flies: Array.from(root.querySelectorAll(".fly")),
      };
    }

    _arcadeBind() {
      const els = this._arcadeEls();
      els.flies.forEach((el, i) => {
        el.addEventListener("pointerdown", (ev) => {
          ev.preventDefault();
          this._onFlySnap(i);
        });
      });
      els.overlay.addEventListener("pointerdown", () => this._arcadeOverlayTap());
      this._arcadeUpdateHud();
    }

    _arcadeOverlay(title, sub, button) {
      const els = this._arcadeEls();
      els.overlay.innerHTML = `
        <div class="ao-title">${esc(title)}</div>
        ${sub ? `<div class="ao-sub">${esc(sub)}</div>` : ""}
        ${button ? `<div class="ao-btn">${esc(button)}</div>` : ""}`;
      els.overlay.classList.add("show");
    }

    _arcadeOverlayTap() {
      const A = this.A;
      if (!A) return;
      if (A.phase === "intro" || A.phase === "roundWon" || A.phase === "roundLost") {
        this._arcadeBeginRound();
      } else if (A.phase === "paused") {
        this._arcadeResume();
      }
    }

    _arcadeBeginRound() {
      const A = this.A;
      const els = this._arcadeEls();
      els.overlay.classList.remove("show");
      A.phase = "play";
      A.timeLeft = A.game.round_time_s;
      A.pairs = [...A.game.rounds_data[A.round - 1].pairs];
      A.decoys = [...A.game.rounds_data[A.round - 1].decoys];
      A.pairIdx = 0;
      this._shuffle(A.pairs);
      A.flies = els.flies.map((el) => ({ el, x: 0, y: 0, word: "" }));
      A.flies.forEach((f) => this._flyToEdge(f));
      this._arcadeDealAll();
      A.lastTs = performance.now();
      this._arcadeUpdateHud();
      A.raf = requestAnimationFrame((ts) => this._arcadeTick(ts));
    }

    _shuffle(arr) {
      for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
      }
    }

    _pondSize() {
      const pond = this._arcadeEls().pond;
      return { w: pond.clientWidth, h: pond.clientHeight };
    }

    _flyToEdge(fly) {
      const { w, h } = this._pondSize();
      const angle = Math.random() * Math.PI * 2;
      fly.x = w / 2 + Math.cos(angle) * (w / 2 - 8);
      fly.y = h / 2 + Math.sin(angle) * (h / 2 - 8);
      fly.wobblePhase = Math.random() * Math.PI * 2;
      this._flyPaint(fly);
    }

    _flyPaint(fly) {
      fly.el.style.transform = `translate(${fly.x - 33}px, ${fly.y - 33}px)`;
    }

    _nextPair() {
      const A = this.A;
      if (A.pairIdx >= A.pairs.length) {
        this._shuffle(A.pairs);
        A.pairIdx = 0;
      }
      return A.pairs[A.pairIdx++];
    }

    _freshDecoys(count, exclude) {
      const A = this.A;
      const pool = A.decoys.filter((w) => !exclude.has(w));
      this._shuffle(pool);
      return pool.slice(0, count);
    }

    _arcadeDealAll() {
      const A = this.A;
      const pair = this._nextPair();
      A.frogWord = pair.t;
      A.matchIdx = Math.floor(Math.random() * 6);
      const exclude = new Set([pair.t, pair.m]);
      const decoys = this._freshDecoys(5, exclude);
      A.flies.forEach((fly, i) => {
        fly.word = i === A.matchIdx ? pair.m : decoys.pop() || pair.t.split("").reverse().join("");
        fly.el.querySelector(".flyword").textContent = fly.word;
      });
      this._arcadeEls().frogword.textContent = A.frogWord;
    }

    _arcadeReDeal(snappedIdx) {
      // Faithful to the original game: the snapped fly resets with a fresh
      // decoy; the NEW match word lands on one of the flies still in flight.
      const A = this.A;
      const pair = this._nextPair();
      A.frogWord = pair.t;
      const others = [0, 1, 2, 3, 4, 5].filter((i) => i !== snappedIdx);
      A.matchIdx = others[Math.floor(Math.random() * others.length)];
      const shown = new Set(A.flies.map((f) => f.word));
      shown.add(pair.t);
      shown.add(pair.m);
      const fresh = this._freshDecoys(1, shown);
      A.flies[snappedIdx].word = fresh[0] || A.flies[snappedIdx].word;
      A.flies[A.matchIdx].word = pair.m;
      A.flies.forEach((fly) => {
        fly.el.querySelector(".flyword").textContent = fly.word;
      });
      this._arcadeEls().frogword.textContent = A.frogWord;
    }

    _onFlySnap(i) {
      const A = this.A;
      if (!A || A.phase !== "play") return;
      const now = performance.now();
      if (now < A.lockedUntil) return;
      const fly = A.flies[i];
      if (i === A.matchIdx) {
        A.correct += 1;
        this._sound("correct");
        const frog = this.shadowRoot.getElementById("frog");
        frog.classList.remove("snap");
        void frog.offsetWidth; // restart the animation
        frog.classList.add("snap");
        this._flyToEdge(fly);
        this._arcadeReDeal(i);
      } else {
        A.wrong += 1;
        A.lockedUntil = now + 1000;
        this._sound("wrong");
        fly.el.classList.remove("shake");
        void fly.el.offsetWidth;
        fly.el.classList.add("shake");
        this._arcadeEls().pond.classList.add("locked");
        setTimeout(() => {
          const els = this._arcadeEls();
          if (els.pond) els.pond.classList.remove("locked");
        }, 1000);
      }
    }

    _arcadeTick(ts) {
      const A = this.A;
      if (!A || A.phase !== "play") return;
      let dt = (ts - A.lastTs) / 1000;
      A.lastTs = ts;
      if (dt > 0.5) dt = 0.016; // tab was hidden / long frame — don't teleport
      A.timeLeft -= dt;

      const { w, h } = this._pondSize();
      const cx = w / 2;
      const cy = h / 2;
      const travel = A.game.travel_s[A.round - 1];
      const speed = Math.min(w, h) / 2 / travel; // px per second
      let lost = false;

      for (const fly of A.flies) {
        const dx = cx - fly.x;
        const dy = cy - fly.y;
        const dist = Math.hypot(dx, dy) || 1;
        fly.wobblePhase += dt * 5;
        const wobble = Math.sin(fly.wobblePhase) * 14;
        fly.x += (dx / dist) * speed * dt + (-dy / dist) * wobble * dt;
        fly.y += (dy / dist) * speed * dt + (dx / dist) * wobble * dt;
        this._flyPaint(fly);
        if (dist < 46) lost = true;
      }

      const els = this._arcadeEls();
      els.bar.style.transform = `scaleX(${Math.max(0, A.timeLeft / A.game.round_time_s)})`;

      if (lost) {
        this._arcadeRoundLost();
        return;
      }
      if (A.timeLeft <= 0) {
        this._arcadeRoundWon();
        return;
      }
      A.raf = requestAnimationFrame((t) => this._arcadeTick(t));
    }

    _arcadeRoundWon() {
      const A = this.A;
      cancelAnimationFrame(A.raf);
      A.roundsCompleted += 1;
      A.roundsPlayed += 1;
      this._sound("finish");
      this._burstConfetti(60);
      if (A.round >= A.game.rounds) {
        this._arcadeFinish(true);
        return;
      }
      A.round += 1;
      A.phase = "roundWon";
      this._arcadeUpdateHud();
      this._arcadeOverlay(
        `Round ${A.round - 1} cleared! 🎉`,
        `Round ${A.round} — the flies are getting faster…`,
        "Go!"
      );
    }

    _arcadeRoundLost() {
      const A = this.A;
      cancelAnimationFrame(A.raf);
      A.lives -= 1;
      A.roundsPlayed += 1;
      this._sound("wrong");
      if (A.lives <= 0) {
        this._arcadeFinish(false);
        return;
      }
      A.phase = "roundLost";
      this._arcadeUpdateHud();
      this._arcadeOverlay(
        "A fly reached the lilypad! 😱",
        `${A.lives} ${A.lives === 1 ? "life" : "lives"} left — try round ${A.round} again`,
        "Try again"
      );
    }

    _arcadePause() {
      const A = this.A;
      if (!A || A.phase !== "play") return;
      cancelAnimationFrame(A.raf);
      A.phase = "paused";
      this._arcadeOverlay("Paused", "", "Tap to keep playing");
      const overlay = this._arcadeEls().overlay;
      const quit = document.createElement("button");
      quit.className = "btn ghost ao-quit";
      quit.textContent = "Quit game";
      quit.addEventListener("pointerdown", (ev) => {
        ev.stopPropagation();
        this._arcadeQuit();
      });
      overlay.appendChild(quit);
    }

    _arcadeResume() {
      const A = this.A;
      A.phase = "play";
      this._arcadeEls().overlay.classList.remove("show");
      A.lastTs = performance.now();
      A.raf = requestAnimationFrame((ts) => this._arcadeTick(ts));
    }

    _arcadeQuit() {
      const A = this.A;
      if (A && (A.correct > 0 || A.roundsCompleted > 0)) {
        this._arcadeFinish(false);
      } else {
        this._arcadeTeardown();
        this._goHome();
      }
    }

    _arcadeTeardown() {
      if (this.A) cancelAnimationFrame(this.A.raf);
      document.removeEventListener("visibilitychange", this._onVisibility);
      this.A = null;
    }

    async _arcadeFinish(won) {
      const A = this.A;
      cancelAnimationFrame(A.raf);
      A.phase = "finished";
      const payload = {
        type: "learning_games/finish_arcade",
        profile_id: this.S.profile.profile_id,
        arcade_id: A.game.arcade_id,
        rounds_completed: Math.min(A.roundsCompleted, 6),
        rounds_played: Math.max(1, A.roundsPlayed),
        correct: A.correct,
        wrong: A.wrong,
        won,
      };
      let res = null;
      try {
        res = await this._ws(payload);
      } catch (err) {
        await new Promise((r) => setTimeout(r, 1500));
        try {
          res = await this._ws(payload);
        } catch (err2) {
          this._arcadeTeardown();
          this._toastAndHome("Couldn't save your Fly Snap score this time — but great playing!");
          return;
        }
      }
      const summary = {
        won,
        correct: A.correct,
        roundsCompleted: Math.min(A.roundsCompleted, 6),
        category: A.category,
        server: res,
      };
      this._arcadeTeardown();
      this.S.arcadeResults = summary;
      this.S.screen = "arcade_results";
      this._render();
      this._sound(won ? "levelup" : "finish");
      if (won || (res && res.level_up)) this._burstConfetti(160);
    }

    _arcadeUpdateHud() {
      const A = this.A;
      const els = this._arcadeEls();
      if (!A || !els.lives) return;
      els.lives.textContent = "🐸".repeat(Math.max(0, A.lives));
      els.roundLabel.textContent = `Round ${A.round}/${A.game.rounds}`;
    }

    // ------------------------------------------------------------ rendering

    _firstRender() {
      this.shadowRoot.innerHTML = `
        <style>${STYLES}</style>
        <ha-card>
          <div class="wrap">
            <div id="root"></div>
            <canvas id="fx"></canvas>
          </div>
        </ha-card>`;
      this.shadowRoot.addEventListener("pointerdown", () => this._ensureAudio(), { once: true });
      this.shadowRoot.addEventListener("click", (ev) => {
        const el = ev.composedPath().find(
          (n) => n.dataset && n.dataset.action
        );
        if (!el) return;
        this._handleAction(el.dataset.action, el.dataset);
      });
      this._render();
    }

    _handleAction(action, data) {
      switch (action) {
        case "pick-profile": {
          this.S.profile = this.S.profiles.find((p) => p.profile_id === data.id);
          this._goHome();
          break;
        }
        case "start": this._sound("tap"); this._startRound(data.mode); break;
        case "home": this._sound("tap"); this._goHome(); break;
        case "quit": this._quitRound(); break;
        case "badges": this._sound("tap"); this._showBadges(); break;
        case "again": this._sound("tap"); this._startRound(this.S.mode); break;
        case "answer": this._submit(data.value); break;
        case "key": this._keypadPress(data.key); break;
        case "field": this.S.entry.field = data.field; this._render(); break;
        case "tile": this._tilePress(Number(data.index)); break;
        case "tile-back": this._tileBackspace(); break;
        case "submit-numeric": {
          const e = this.S.entry;
          if (this.S.question.type === "numeric_with_remainder") {
            if (e.value !== "" && e.remainder !== "") this._submit(`${e.value} r ${e.remainder}`);
          } else if (e.value !== "" && e.value !== "-") {
            this._submit(e.value);
          }
          break;
        }
        case "submit-word": {
          const blanks = (this.S.question.fill_pattern.match(/_/g) || []).length;
          if (this.S.entry.letters.length === blanks) this._submit(this._assembleWord());
          break;
        }
        case "arcade-setup": this._sound("tap"); this.S.screen = "arcade_setup"; this._render(); break;
        case "arcade-start": this._startArcade(data.category); break;
        case "arcade-pause": this._arcadePause(); break;
        case "arcade-again": this._sound("tap"); this._startArcade(this.S.arcadeResults.category); break;
        case "retry": this._loadProfiles(); break;
      }
    }

    _render() {
      const root = this.shadowRoot.getElementById("root");
      if (!root) return;
      const screen = this.S.screen;
      let html = "";
      if (screen === "loading") html = this._tplLoading();
      else if (screen === "pick") html = this._tplPick();
      else if (screen === "home") html = this._tplHome();
      else if (screen === "game") html = this._tplGame();
      else if (screen === "results") html = this._tplResults();
      else if (screen === "badges") html = this._tplBadges();
      else if (screen === "arcade_setup") html = this._tplArcadeSetup();
      else if (screen === "arcade") html = this._tplArcade();
      else if (screen === "arcade_results") html = this._tplArcadeResults();
      else if (screen === "error") html = this._tplError();
      root.innerHTML = html;
    }

    _tplLoading() {
      return `<div class="center"><div class="spinner"></div><p>Loading…</p></div>`;
    }

    _tplError() {
      return `<div class="center">
        <div class="bigmoji">🙈</div>
        <p class="errmsg">${esc(this.S.error || "Something went wrong.")}</p>
        <button class="btn primary" data-action="retry">Try again</button>
      </div>`;
    }

    _tplPick() {
      return `<div class="center">
        <h2>Who's playing?</h2>
        <div class="profile-grid">
          ${this.S.profiles.map((p) => `
            <button class="profile-tile" data-action="pick-profile" data-id="${esc(p.profile_id)}">
              <span class="avatar">${AVATARS[p.avatar] || "🙂"}</span>
              <span class="pname">${esc(p.name)}</span>
              <span class="psub">Level ${p.level} · 🔥 ${p.streak}</span>
            </button>`).join("")}
        </div>
      </div>`;
    }

    _tplHome() {
      const s = this.S.stats;
      const pct = Math.min(100, Math.round((s.daily.questions / s.daily.goal) * 100));
      const ringPct = Math.round((s.xp.into_level / s.xp.to_next) * 100);
      const modes = Object.entries(s.modes);
      const maths = modes.filter(([, m]) => m.subject === "maths");
      const english = modes.filter(([, m]) => m.subject === "english");
      const challenge = modes.filter(([, m]) => m.subject === "challenge");
      const tile = ([id, m]) => {
        const mastery = Math.round(
          m.skills.reduce((acc, sk) => acc + (s.skills[sk] ? s.skills[sk].mastery : 0), 0) /
          m.skills.length
        );
        const stars = Math.max(0, Math.min(5, Math.round(mastery / 20)));
        const [c1, c2] = SUBJECT_COLORS[m.subject];
        return `<button class="mode-tile" data-action="start" data-mode="${id}"
            style="background:linear-gradient(135deg,${c1},${c2})">
          <span class="memoji">${m.emoji}</span>
          <span class="mname">${esc(m.name)}</span>
          <span class="mstars">${"★".repeat(stars)}${"☆".repeat(5 - stars)}</span>
        </button>`;
      };
      return `
        <div class="home-head">
          <div class="who">
            <span class="avatar big">${AVATARS[s.avatar] || "🙂"}</span>
            <div>
              <div class="hname">${esc(s.name)}</div>
              <div class="hsub">🔥 ${s.streak.current} day streak${s.streak.freezes ? ` · ❄️×${s.streak.freezes}` : ""}</div>
            </div>
          </div>
          <div class="ring" style="--p:${ringPct}">
            <span class="ringlvl">Lv ${s.xp.level}</span>
          </div>
        </div>
        <div class="goal ${s.daily.goal_met ? "done" : ""}">
          <div class="goal-label">
            ${s.daily.goal_met ? "🏁 Daily goal smashed!" : `Today: ${s.daily.questions} / ${s.daily.goal} questions`}
          </div>
          <div class="bar"><div class="fill" style="width:${pct}%"></div></div>
        </div>
        ${this._tplChallengesSection(s)}
        <div class="subject-label">Maths</div>
        <div class="mode-grid">${maths.map(tile).join("")}</div>
        <div class="subject-label">English</div>
        <div class="mode-grid">${english.map(tile).join("")}</div>
        <div class="subject-label">Challenges</div>
        <div class="mode-grid">
          ${challenge.map(tile).join("")}
          ${s.arcade ? `
          <button class="mode-tile" data-action="arcade-setup"
              style="background:linear-gradient(135deg,#00897B,#4DB6AC)">
            <span class="memoji">${s.arcade.emoji}</span>
            <span class="mname">${esc(s.arcade.name)}</span>
            <span class="mstars">${s.arcade.wins ? `👑×${s.arcade.wins}` : `best: round ${s.arcade.best_round}`}</span>
          </button>` : ""}
        </div>
        <button class="btn ghost wide" data-action="badges">🏅 My badges (${s.badge_count})</button>
      `;
    }

    _tplChallengesSection(s) {
      if (!s.challenges || !s.challenges.length) return "";
      const row = (c) => {
        const pct = Math.min(100, Math.round((c.progress / c.target) * 100));
        return `<div class="chal ${c.done ? "done" : ""}">
          <span class="chal-icon">${c.icon}</span>
          <div class="chal-mid">
            <div class="chal-desc">${esc(c.desc)}</div>
            <div class="bar small"><div class="fill" style="width:${pct}%"></div></div>
          </div>
          <span class="chal-state">${c.done ? "✅" : `${c.progress}/${c.target}`}</span>
        </div>`;
      };
      return `<div class="subject-label">This week's challenges</div>
        <div class="chal-list">${s.challenges.map(row).join("")}</div>`;
    }

    _tplGame() {
      const q = this.S.question;
      const fb = this.S.feedback;
      const dots = Array.from({ length: this.S.session.total }, (_, i) => {
        const n = i + 1;
        const cls = n < q.index ? "done" : n === q.index ? "now" : "";
        return `<span class="dot ${cls}"></span>`;
      }).join("");
      const boss = this.S.mode === "boss_battle";
      const hp = boss
        ? `<div class="boss-strip">
            <span class="boss-emoji ${this.S.bossHits >= 10 ? "dead" : ""}">👾</span>
            <div class="boss-hp">${Array.from({ length: 10 }, (_, i) =>
              `<span class="hp ${i < 10 - this.S.bossHits ? "on" : ""}"></span>`).join("")}</div>
          </div>`
        : "";
      return `
        <div class="game-head">
          <button class="btn tiny ghost" data-action="quit">✕</button>
          <div class="dots">${dots}</div>
          <div class="rstreak">${fb && fb.runStreak >= 3 ? `🔥${fb.runStreak}` : ""}</div>
        </div>
        ${hp}
        <div class="qa ${fb ? (fb.correct ? "good" : "bad") : ""}">
          <div class="prompt">${esc(q.prompt)}</div>
          ${q.prompt_secondary ? `<div class="prompt2">${esc(q.prompt_secondary)}</div>` : ""}
          ${this._tplAnswerArea(q, fb)}
          ${fb ? this._tplFeedback(fb) : ""}
        </div>`;
    }

    _tplAnswerArea(q, fb) {
      if (q.type === "multiple_choice") {
        const long = q.options.some((o) => o.length > 18);
        return `<div class="opts ${long ? "stack" : "grid"}">
          ${q.options.map((o) => {
            let cls = "opt";
            if (fb) {
              if (o === fb.correctAnswer) cls += " reveal-good";
              else cls += " faded";
            }
            return `<button class="${cls}" data-action="answer" data-value="${esc(o)}" ${fb ? "disabled" : ""}>${esc(o)}</button>`;
          }).join("")}
        </div>`;
      }
      if (q.type === "numeric" || q.type === "numeric_with_remainder") {
        const e = this.S.entry;
        const rem = q.type === "numeric_with_remainder";
        return `
          <div class="entry-row">
            <div class="entry ${(!rem || e.field === "value") ? "focus" : ""}" data-action="field" data-field="value">${esc(e.value) || "&nbsp;"}</div>
            ${rem ? `<span class="rlabel">r</span>
            <div class="entry ${e.field === "remainder" ? "focus" : ""}" data-action="field" data-field="remainder">${esc(e.remainder) || "&nbsp;"}</div>` : ""}
          </div>
          <div class="keypad">
            ${["7","8","9","4","5","6","1","2","3"].map((k) => `<button class="key" data-action="key" data-key="${k}" ${fb ? "disabled" : ""}>${k}</button>`).join("")}
            <button class="key" data-action="key" data-key="sign" ${fb ? "disabled" : ""}>±</button>
            <button class="key" data-action="key" data-key="0" ${fb ? "disabled" : ""}>0</button>
            <button class="key" data-action="key" data-key="." ${fb ? "disabled" : ""}>·</button>
            <button class="key back" data-action="key" data-key="back" ${fb ? "disabled" : ""}>⌫</button>
            <button class="key go" data-action="submit-numeric" ${fb ? "disabled" : ""}>✓</button>
          </div>`;
      }
      // letters_fill / unscramble
      const e = this.S.entry;
      let li = 0;
      const slots = [...q.fill_pattern].map((ch) => {
        if (ch === "_") {
          const letter = e.letters[li++];
          return `<span class="slot ${letter ? "filled" : ""}">${letter ? esc(letter) : ""}</span>`;
        }
        return `<span class="slot fixed">${esc(ch)}</span>`;
      }).join("");
      const blanks = (q.fill_pattern.match(/_/g) || []).length;
      return `
        <div class="slots">${slots}</div>
        <div class="tiles">
          ${q.options.map((letter, i) => {
            const used = q.type === "unscramble" && e.usedTiles.includes(i);
            return `<button class="tile ${used ? "used" : ""}" data-action="tile" data-index="${i}" ${fb || used ? "disabled" : ""}>${esc(letter)}</button>`;
          }).join("")}
        </div>
        <div class="word-actions">
          <button class="key back" data-action="tile-back" ${fb ? "disabled" : ""}>⌫</button>
          <button class="key go wide" data-action="submit-word" ${fb || e.letters.length !== blanks ? "disabled" : ""}>✓</button>
        </div>`;
    }

    _tplFeedback(fb) {
      if (fb.correct) {
        return `<div class="fb good-fb">
          <span class="fb-praise">${fb.praise}</span>
          <span class="xp-float">+${fb.xpDelta} XP${fb.speedBonus ? " ⚡" : ""}</span>
        </div>`;
      }
      return `<div class="fb bad-fb">
        <span class="fb-praise">${fb.praise}</span>
        <span class="fb-correct">Answer: <b>${esc(fb.correctAnswer)}</b></span>
        ${fb.explain ? `<span class="fb-explain">${esc(fb.explain)}</span>` : ""}
      </div>`;
    }

    _tplResults() {
      const r = this.S.results;
      const accuracy = Math.round((r.correct / r.total) * 100);
      const stars = accuracy === 100 ? 3 : accuracy >= 70 ? 2 : 1;
      let bossLine = "";
      if (r.mode === "boss_battle") {
        if (r.correct >= 10) bossLine = `<div class="levelup">💥 FLAWLESS VICTORY! 💥</div>`;
        else if (r.boss_defeated) bossLine = `<div class="levelup">👾💨 The boss flees!</div>`;
        else bossLine = `<div class="pill up-pill">👾 The boss escaped — train up and rematch!</div>`;
      }
      return `
        <div class="center results">
          ${r.level_up ? `<div class="levelup">⬆️ LEVEL ${r.new_level}! ⬆️</div>` : ""}
          ${bossLine}
          <div class="score-ball">${r.correct}/${r.total}</div>
          <div class="result-stars">${"⭐".repeat(stars)}</div>
          <div class="xp-gain">+${r.xp_gained} XP</div>
          ${r.daily_goal_met ? `<div class="pill done-pill">🏁 Daily goal done!</div>` : ""}
          ${(r.new_badges || []).map((b) => `
            <div class="badge-pop">
              <span class="bicon">${b.icon}</span>
              <span><b>${esc(b.name)}</b><br><small>${esc(b.desc)}</small></span>
            </div>`).join("")}
          ${(r.skill_changes || []).filter((c) => c.new_band > c.old_band).map((c) => `
            <div class="pill up-pill">📈 ${esc(prettySkill(c.skill))} → level ${c.new_band}</div>`).join("")}
          <div class="result-actions">
            <button class="btn primary" data-action="again">Play again</button>
            <button class="btn ghost" data-action="home">Home</button>
          </div>
        </div>`;
    }

    _tplBadges() {
      const b = this.S.badges;
      const card = (badge, locked) => `
        <div class="badge ${locked ? "locked" : ""}">
          <span class="bicon">${badge.icon}</span>
          <span class="bname">${esc(badge.name)}</span>
          <span class="bdesc">${esc(locked ? badge.hint : badge.desc)}</span>
        </div>`;
      return `
        <div class="game-head">
          <button class="btn tiny ghost" data-action="home">←</button>
          <h3 class="bh">My badges</h3><span></span>
        </div>
        <div class="badge-grid">
          ${b.earned.map((x) => card(x, false)).join("")}
          ${b.locked.map((x) => card(x, true)).join("")}
        </div>`;
    }

    _tplArcadeSetup() {
      return `
        <div class="game-head">
          <button class="btn tiny ghost" data-action="home">←</button>
          <h3 class="bh">🐸 Fly Snap</h3><span></span>
        </div>
        <div class="center" style="min-height:380px">
          <div class="bigmoji">🐸</div>
          <p class="errmsg">Tap the fly that matches the frog's word — before the flies reach the lilypad!</p>
          <div class="acat-grid">
            ${ARCADE_CATEGORIES.map((c) => `
              <button class="acat" data-action="arcade-start" data-category="${c.id}">
                <span class="memoji">${c.emoji}</span>
                <span class="pname">${c.label}</span>
                <span class="psub">${c.blurb}</span>
              </button>`).join("")}
          </div>
        </div>`;
    }

    _tplArcade() {
      return `
        <div class="game-head">
          <button class="btn tiny ghost" data-action="arcade-pause">✕</button>
          <span id="around" class="around"></span>
          <span id="alives" class="alives"></span>
        </div>
        <div class="abar"><div id="abar-fill" class="abar-fill"></div></div>
        <div id="pond" class="pond">
          <div class="lilypad"></div>
          <div id="frog" class="frog">🐸</div>
          <div id="frogword" class="frogword"></div>
          ${[0, 1, 2, 3, 4, 5].map((i) => `
            <button class="fly" id="fly${i}">
              <span class="flymoji">🪰</span>
              <span class="flyword"></span>
            </button>`).join("")}
          <div id="aoverlay" class="aoverlay"></div>
        </div>`;
    }

    _tplArcadeResults() {
      const r = this.S.arcadeResults;
      const server = r.server || {};
      return `
        <div class="center results">
          ${r.won ? `<div class="levelup">👑 POND CHAMPION! 👑</div>` : ""}
          ${server.level_up ? `<div class="levelup">⬆️ LEVEL ${server.new_level}! ⬆️</div>` : ""}
          <div class="score-ball" style="background:linear-gradient(135deg,#00897B,#4DB6AC);box-shadow:0 6px 0 #00695C">
            ${r.correct} 🪰</div>
          <div class="result-stars">${r.won ? "⭐⭐⭐" : "⭐".repeat(Math.min(3, Math.max(1, Math.ceil(r.roundsCompleted / 2))))}</div>
          <div class="xp-gain">+${server.xp_gained || 0} XP</div>
          <div class="pill up-pill">Rounds survived: ${r.roundsCompleted} / 6</div>
          ${server.daily_goal_met ? `<div class="pill done-pill">🏁 Daily goal done!</div>` : ""}
          ${(server.new_badges || []).map((b) => `
            <div class="badge-pop">
              <span class="bicon">${b.icon}</span>
              <span><b>${esc(b.name)}</b><br><small>${esc(b.desc)}</small></span>
            </div>`).join("")}
          <div class="result-actions">
            <button class="btn primary" data-action="arcade-again">Play again</button>
            <button class="btn ghost" data-action="home">Home</button>
          </div>
        </div>`;
    }
  }

  // ------------------------------------------------------------ helpers

  function esc(value) {
    return String(value)
      .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;").replaceAll("'", "&#39;");
  }

  function prettySkill(skill) {
    return skill.split(".", 2)[1].replaceAll("_", " ");
  }

  const STYLES = `
    :host { display: block; }
    ha-card {
      border-radius: 24px;
      overflow: hidden;
      background: linear-gradient(180deg, #FFF7E6 0%, #FFEFF5 100%);
      color: #2D3436;
      font-family: "Comic Sans MS", "Chalkboard SE", "Segoe UI", system-ui, sans-serif;
    }
    .wrap { position: relative; padding: 16px; min-height: 480px; }
    #fx { position: absolute; inset: 0; width: 100%; height: 100%;
          pointer-events: none; z-index: 5; }
    button { font-family: inherit; border: none; cursor: pointer;
             -webkit-tap-highlight-color: transparent; touch-action: manipulation; }
    button:active { transform: scale(0.96); }
    .center { display: flex; flex-direction: column; align-items: center;
              justify-content: center; gap: 14px; min-height: 440px; text-align: center; }
    .spinner { width: 44px; height: 44px; border: 5px solid #ddd;
               border-top-color: #6C5CE7; border-radius: 50%;
               animation: spin 0.9s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .bigmoji { font-size: 56px; }
    .errmsg { font-size: 18px; max-width: 320px; }

    .btn { border-radius: 18px; padding: 14px 26px; font-size: 19px; font-weight: 700; }
    .btn.primary { background: #6C5CE7; color: #fff; box-shadow: 0 4px 0 #4f41b8; }
    .btn.ghost { background: #fff; color: #6C5CE7; box-shadow: 0 3px 0 #e0dcf8; }
    .btn.tiny { padding: 8px 14px; font-size: 17px; }
    .btn.wide { width: 100%; margin-top: 14px; }

    .profile-grid { display: flex; gap: 14px; flex-wrap: wrap; justify-content: center; }
    .profile-tile { display: flex; flex-direction: column; align-items: center; gap: 6px;
      background: #fff; border-radius: 22px; padding: 20px 26px;
      box-shadow: 0 4px 0 #eadcf0; min-width: 130px; }
    .avatar { font-size: 40px; } .avatar.big { font-size: 52px; }
    .pname { font-size: 20px; font-weight: 800; }
    .psub { font-size: 14px; opacity: 0.7; }

    .home-head { display: flex; justify-content: space-between; align-items: center; }
    .who { display: flex; gap: 12px; align-items: center; }
    .hname { font-size: 24px; font-weight: 800; }
    .hsub { font-size: 15px; opacity: 0.8; }
    .ring { width: 64px; height: 64px; border-radius: 50%; display: flex;
      align-items: center; justify-content: center;
      background: conic-gradient(#FDCB6E calc(var(--p) * 1%), #f0e9da 0); }
    .ring::before { content: ""; position: absolute; width: 48px; height: 48px;
      border-radius: 50%; background: #fff; }
    .ring { position: relative; }
    .ringlvl { position: relative; z-index: 1; font-weight: 800; font-size: 14px; }

    .goal { margin: 14px 0 6px; background: #fff; border-radius: 16px; padding: 10px 14px;
            box-shadow: 0 3px 0 #f0e3d8; }
    .goal.done { background: #E8FBF3; }
    .goal-label { font-size: 15px; font-weight: 700; margin-bottom: 6px; }
    .bar { height: 14px; background: #f0e9da; border-radius: 8px; overflow: hidden; }
    .fill { height: 100%; border-radius: 8px;
      background: linear-gradient(90deg, #FDCB6E, #E17055);
      transition: width 0.6s cubic-bezier(.2,.8,.2,1); }
    .goal.done .fill { background: linear-gradient(90deg, #00B894, #26D0A8); }

    .subject-label { font-size: 14px; font-weight: 800; letter-spacing: 1px;
      text-transform: uppercase; opacity: 0.55; margin: 12px 4px 6px; }
    .mode-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
    .mode-tile { display: flex; flex-direction: column; align-items: center; gap: 2px;
      color: #fff; border-radius: 20px; padding: 14px 8px; min-height: 96px;
      justify-content: center; box-shadow: 0 4px 0 rgba(0,0,0,0.18); }
    .memoji { font-size: 30px; }
    .mname { font-size: 16px; font-weight: 800; text-shadow: 0 1px 2px rgba(0,0,0,0.25); }
    .mstars { font-size: 12px; letter-spacing: 2px; opacity: 0.95; }

    .game-head { display: flex; align-items: center; justify-content: space-between;
                 gap: 10px; margin-bottom: 10px; }
    .bh { margin: 0; }
    .dots { display: flex; gap: 5px; flex-wrap: wrap; justify-content: center; flex: 1; }
    .dot { width: 11px; height: 11px; border-radius: 50%; background: #e7ddcd; }
    .dot.done { background: #00B894; }
    .dot.now { background: #6C5CE7; transform: scale(1.3); }
    .rstreak { min-width: 44px; text-align: right; font-weight: 800; font-size: 17px; }

    .qa { background: #fff; border-radius: 22px; padding: 18px 14px 22px;
          box-shadow: 0 4px 0 #f0e3d8; transition: background 0.25s; }
    .qa.good { background: #E8FBF3; }
    .qa.bad { background: #FDEDEE; animation: shake 0.4s; }
    @keyframes shake { 25% { transform: translateX(-6px); } 75% { transform: translateX(6px); } }
    .prompt { font-size: clamp(22px, 5.5vw, 34px); font-weight: 800;
              text-align: center; margin: 6px 4px 4px; }
    .prompt2 { font-size: clamp(17px, 4vw, 22px); text-align: center;
               margin: 4px 8px 8px; opacity: 0.85; }

    .opts { margin-top: 14px; gap: 10px; display: grid; }
    .opts.grid { grid-template-columns: repeat(2, 1fr); }
    .opts.stack { grid-template-columns: 1fr; }
    .opt { min-height: 64px; border-radius: 16px; background: #F4F1FE; color: #2D3436;
      font-size: clamp(17px, 4.2vw, 23px); font-weight: 700; padding: 10px 12px;
      box-shadow: 0 3px 0 #ddd6f5; }
    .opt.reveal-good { background: #00B894; color: #fff; box-shadow: 0 3px 0 #00916f; }
    .opt.faded { opacity: 0.45; }

    .entry-row { display: flex; gap: 10px; align-items: center; justify-content: center;
                 margin-top: 12px; }
    .entry { min-width: 110px; min-height: 56px; background: #F4F1FE; border-radius: 14px;
      font-size: 30px; font-weight: 800; display: flex; align-items: center;
      justify-content: center; padding: 4px 16px; border: 3px solid transparent; }
    .entry.focus { border-color: #6C5CE7; }
    .rlabel { font-size: 24px; font-weight: 800; opacity: 0.6; }
    .keypad { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
              max-width: 320px; margin: 14px auto 0; }
    .key { min-height: 58px; border-radius: 14px; background: #fff; font-size: 24px;
           font-weight: 800; box-shadow: 0 3px 0 #e8e0d2; }
    .key.back { background: #FFE3E3; }
    .key.go { background: #00B894; color: #fff; box-shadow: 0 3px 0 #00916f;
              grid-column: span 2; }
    .key.go.wide { grid-column: auto; flex: 1; }
    .key:disabled, .opt:disabled, .tile:disabled { opacity: 0.55; }

    .slots { display: flex; gap: 5px; flex-wrap: wrap; justify-content: center;
             margin-top: 16px; }
    .slot { width: 34px; height: 44px; border-radius: 10px; background: #F4F1FE;
      display: flex; align-items: center; justify-content: center; font-size: 24px;
      font-weight: 800; border-bottom: 3px solid #cfc6f2; }
    .slot.fixed { background: transparent; border-bottom-color: transparent; opacity: 0.85; }
    .slot.filled { background: #E8E2FB; }
    .tiles { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center;
             margin-top: 16px; }
    .tile { width: 52px; height: 52px; border-radius: 12px; background: #FDCB6E;
      font-size: 24px; font-weight: 800; box-shadow: 0 3px 0 #d9a33f; }
    .tile.used { visibility: hidden; }
    .word-actions { display: flex; gap: 10px; max-width: 320px; margin: 14px auto 0; }
    .word-actions .key { flex: 1; }

    .fb { display: flex; flex-direction: column; align-items: center; gap: 4px;
          margin-top: 14px; animation: pop 0.3s; }
    @keyframes pop { from { transform: scale(0.6); opacity: 0; } }
    .fb-praise { font-size: 22px; font-weight: 800; }
    .good-fb .fb-praise { color: #00916f; }
    .bad-fb .fb-praise { color: #d63031; }
    .fb-correct { font-size: 18px; }
    .fb-explain { font-size: 15px; opacity: 0.75; text-align: center; }
    .xp-float { font-size: 20px; font-weight: 800; color: #E17055;
                animation: floatup 1s ease-out; }
    @keyframes floatup { from { transform: translateY(14px); opacity: 0; } }

    .results { gap: 10px; }
    .levelup { font-size: 26px; font-weight: 800; color: #6C5CE7;
               animation: pop 0.5s; }
    .score-ball { width: 120px; height: 120px; border-radius: 50%;
      background: linear-gradient(135deg, #6C5CE7, #8E7CF8); color: #fff;
      display: flex; align-items: center; justify-content: center;
      font-size: 34px; font-weight: 800; box-shadow: 0 6px 0 #4f41b8; }
    .result-stars { font-size: 30px; }
    .xp-gain { font-size: 24px; font-weight: 800; color: #E17055; }
    .pill { border-radius: 999px; padding: 8px 18px; font-weight: 700; font-size: 15px; }
    .done-pill { background: #E8FBF3; color: #00916f; }
    .up-pill { background: #F4F1FE; color: #6C5CE7; }
    .badge-pop { display: flex; gap: 12px; align-items: center; background: #fff;
      border-radius: 18px; padding: 12px 18px; box-shadow: 0 4px 0 #f0e3d8;
      animation: pop 0.45s; text-align: left; }
    .badge-pop .bicon { font-size: 34px; }
    .result-actions { display: flex; gap: 12px; margin-top: 10px; }

    .badge-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
                  gap: 10px; }
    .badge { background: #fff; border-radius: 18px; padding: 14px 10px; display: flex;
      flex-direction: column; align-items: center; gap: 4px; text-align: center;
      box-shadow: 0 3px 0 #f0e3d8; }
    .badge .bicon { font-size: 34px; }
    .badge .bname { font-weight: 800; font-size: 15px; }
    .badge .bdesc { font-size: 12.5px; opacity: 0.7; }
    .badge.locked { filter: grayscale(1); opacity: 0.55; }

    .chal-list { display: flex; flex-direction: column; gap: 8px; }
    .chal { display: flex; align-items: center; gap: 10px; background: #fff;
      border-radius: 14px; padding: 8px 12px; box-shadow: 0 3px 0 #f0e3d8; }
    .chal.done { background: #E8FBF3; }
    .chal-icon { font-size: 24px; }
    .chal-mid { flex: 1; }
    .chal-desc { font-size: 14px; font-weight: 700; margin-bottom: 4px; }
    .bar.small { height: 8px; }
    .chal-state { font-size: 14px; font-weight: 800; min-width: 48px; text-align: right; }

    .boss-strip { display: flex; align-items: center; gap: 10px; background: #2D3436;
      border-radius: 14px; padding: 8px 12px; margin-bottom: 10px; }
    .boss-emoji { font-size: 28px; }
    .boss-emoji.dead { filter: grayscale(1); opacity: 0.4; }
    .boss-hp { display: flex; gap: 4px; flex: 1; }
    .hp { flex: 1; height: 12px; border-radius: 4px; background: #555; transition: background 0.3s; }
    .hp.on { background: linear-gradient(90deg, #d63031, #e84393); }

    .acat-grid { display: flex; flex-direction: column; gap: 12px; width: 100%;
      max-width: 340px; }
    .acat { display: flex; flex-direction: column; align-items: center; gap: 4px;
      background: #fff; border-radius: 20px; padding: 14px;
      box-shadow: 0 4px 0 #d8ece8; }

    .around { font-weight: 800; font-size: 17px; }
    .alives { font-size: 20px; min-width: 80px; text-align: right; }
    .abar { height: 12px; background: #d8ece8; border-radius: 8px; overflow: hidden;
      margin-bottom: 10px; }
    .abar-fill { height: 100%; width: 100%; transform-origin: left;
      background: linear-gradient(90deg, #00897B, #4DB6AC); }
    .pond { position: relative; height: 440px; border-radius: 22px; overflow: hidden;
      background: radial-gradient(circle at 50% 50%, #7EDDD0 0%, #3FB8AF 55%, #2E9C94 100%);
      touch-action: manipulation; }
    .pond.locked { filter: saturate(0.55) brightness(0.92); }
    .lilypad { position: absolute; left: 50%; top: 50%; width: 110px; height: 96px;
      transform: translate(-50%, -50%); background: #4CAF50; border-radius: 50%;
      box-shadow: inset 0 -6px 0 #388E3C; }
    .lilypad::after { content: ""; position: absolute; right: -4px; top: 36%;
      border: 16px solid transparent; border-left: 26px solid #3FB8AF; }
    .frog { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -58%);
      font-size: 44px; z-index: 2; pointer-events: none; }
    .frog.snap { animation: tongue 0.3s; }
    @keyframes tongue { 50% { transform: translate(-50%, -58%) scale(1.45); } }
    .frogword { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -150%);
      background: #fff; border-radius: 12px; padding: 5px 14px; font-size: 19px;
      font-weight: 800; box-shadow: 0 3px 0 rgba(0,0,0,0.15); z-index: 3;
      pointer-events: none; white-space: nowrap; }
    .fly { position: absolute; left: 0; top: 0; width: 66px; height: 66px;
      border-radius: 50%; background: rgba(255,255,255,0.92); display: flex;
      flex-direction: column; align-items: center; justify-content: center;
      gap: 0; box-shadow: 0 3px 0 rgba(0,0,0,0.18); z-index: 4; padding: 2px;
      will-change: transform; }
    .fly .flymoji { font-size: 18px; line-height: 1; pointer-events: none; }
    .fly .flyword { font-size: 12.5px; font-weight: 800; line-height: 1.1;
      text-align: center; pointer-events: none; max-width: 62px; overflow: hidden; }
    .fly.shake { animation: shake 0.4s; background: #FFD5D5; }
    .aoverlay { position: absolute; inset: 0; z-index: 6; display: none;
      flex-direction: column; align-items: center; justify-content: center; gap: 10px;
      background: rgba(20, 60, 56, 0.78); color: #fff; text-align: center;
      padding: 20px; }
    .aoverlay.show { display: flex; }
    .ao-title { font-size: 28px; font-weight: 800; }
    .ao-sub { font-size: 17px; opacity: 0.9; max-width: 300px; }
    .ao-btn { margin-top: 8px; background: #FDCB6E; color: #2D3436; font-weight: 800;
      border-radius: 16px; padding: 12px 30px; font-size: 19px;
      box-shadow: 0 4px 0 #d9a33f; }
    .ao-quit { margin-top: 14px; }

    @media (min-width: 700px) {
      .mode-grid { grid-template-columns: repeat(4, 1fr); }
      .wrap { padding: 22px; }
      .pond { height: 520px; }
    }
  `;

  if (!customElements.get("learning-games-card")) {
    customElements.define("learning-games-card", LearningGamesCard);
  }
  window.customCards = window.customCards || [];
  if (!window.customCards.some((c) => c.type === "learning-games-card")) {
    window.customCards.push({
      type: "learning-games-card",
      name: "Learning Games",
      description: "Maths & English games for kids with XP, streaks and badges",
    });
  }
})();
