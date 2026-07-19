(function () {
    "use strict";

    const userConfig = window.CSCAPE_STORY || {};

    const config = {
        defaultLayout: "dialogue",
        defaultBackground: "",
        defaultMusic: "",
        musicVolume: 0.3,
        musicLoop: true,
        soundVolume: 0.85,
        typeSpeed: 28,
        defaultTextMode: "type",
        audioHintText: "Klick für Musik & Sounds",
        ttsUrl: "",
        defaultVoice: "de-DE-KatjaNeural",
        defaultTtsRate: "+0%",
        defaultTtsPitch: "+0Hz",
        beforeSlide: null,
        afterSlide: null,
        formatText: text => String(text || ""),
        ...userConfig
    };

    const VALID_PHASES = new Set(["before-text", "start", "after-text"]);
    let revealNavigationPatched = false;
    let allowInternalNavigation = false;
    let pendingNavigation = null;
    let originalRevealNext = null;
    let originalRevealPrev = null;
    let originalRevealLeft = null;
    let originalRevealRight = null;
    let originalRevealSlide = null;
    const activeControllers = new Set();
    let initialized = false;
    let audioUnlocked = false;
    let runId = 0;
    let currentController = null;
    let musicAudio = null;
    let musicSrc = "";

    const unlockWaiters = new Set();
    const slideState = new WeakMap();
    const activeOneShots = new Set();
    const activeSlideLoops = new Set();
    const persistentLoops = new Map();

    const api = {
        init,
        isAudioUnlocked: () => audioUnlocked,
        formatText,
        replayCurrentSlide() {
            if (window.Reveal) {
                playSlide(Reveal.getCurrentSlide());
            }
        },
        stopPersistentLoop(id) {
            stopPersistentLoop(id);
        },
        stopAllPersistentLoops() {
            stopAllPersistentLoops();
        }
    };

    window.CSCAPE_STORY_API = api;

    function getSlideState(slide) {
        if (!slideState.has(slide)) {
            slideState.set(slide, {
                ready: false,
                nextScheduled: false
            });
        }
        return slideState.get(slide);
    }

    function boolValue(value, fallback = false) {
        if (value === undefined || value === null || value === "") return fallback;
        const normalized = String(value).trim().toLowerCase();
        if (["1", "true", "yes", "ja", "on"].includes(normalized)) return true;
        if (["0", "false", "no", "nein", "off"].includes(normalized)) return false;
        return fallback;
    }

    function isCurrentSlideStoryBusy() {
        if (!window.Reveal || typeof Reveal.getCurrentSlide !== "function") return false;

        const slide = Reveal.getCurrentSlide();
        if (!slide) return false;

        return slide.getAttribute("data-story-ready") !== "true";
    }

    function queueNavigation(kind, args) {
        pendingNavigation = {kind, args: Array.from(args || [])};
        console.log("[CSCAPE Story] navigation queued until slide ready:", pendingNavigation);
    }

    function runPendingNavigation() {
        if (!pendingNavigation || !window.Reveal) return false;

        const pending = pendingNavigation;
        pendingNavigation = null;

        console.log("[CSCAPE Story] running queued navigation:", pending);

        allowInternalNavigation = true;

        try {
            if (pending.kind === "next" && originalRevealNext) {
                originalRevealNext(...pending.args);
            } else if (pending.kind === "prev" && originalRevealPrev) {
                originalRevealPrev(...pending.args);
            } else if (pending.kind === "left" && originalRevealLeft) {
                originalRevealLeft(...pending.args);
            } else if (pending.kind === "right" && originalRevealRight) {
                originalRevealRight(...pending.args);
            } else if (pending.kind === "slide" && originalRevealSlide) {
                originalRevealSlide(...pending.args);
            }
        } finally {
            allowInternalNavigation = false;
        }

        return true;
    }

    function shouldBlockRevealNavigation() {
        if (allowInternalNavigation) return false;
        if (config.blockNavigationUntilReady === false) return false;
        return isCurrentSlideStoryBusy();
    }

    function patchRevealNavigation() {
        if (revealNavigationPatched || !window.Reveal) return false;

        if (
            typeof Reveal.next !== "function" ||
            typeof Reveal.prev !== "function" ||
            typeof Reveal.left !== "function" ||
            typeof Reveal.right !== "function" ||
            typeof Reveal.slide !== "function"
        ) {
            console.warn("[CSCAPE Story] Reveal navigation API not ready yet.");
            return false;
        }

        revealNavigationPatched = true;

        originalRevealNext = Reveal.next.bind(Reveal);
        originalRevealPrev = Reveal.prev.bind(Reveal);
        originalRevealLeft = Reveal.left.bind(Reveal);
        originalRevealRight = Reveal.right.bind(Reveal);
        originalRevealSlide = Reveal.slide.bind(Reveal);

        Reveal.next = function (...args) {
            if (shouldBlockRevealNavigation()) {
                queueNavigation("next", args);
                return;
            }

            return originalRevealNext(...args);
        };

        Reveal.prev = function (...args) {
            if (shouldBlockRevealNavigation()) {
                queueNavigation("prev", args);
                return;
            }

            return originalRevealPrev(...args);
        };

        Reveal.left = function (...args) {
            if (shouldBlockRevealNavigation()) {
                queueNavigation("left", args);
                return;
            }

            return originalRevealLeft(...args);
        };

        Reveal.right = function (...args) {
            if (shouldBlockRevealNavigation()) {
                queueNavigation("right", args);
                return;
            }

            return originalRevealRight(...args);
        };

        Reveal.slide = function (...args) {
            if (shouldBlockRevealNavigation()) {
                queueNavigation("slide", args);
                return;
            }

            return originalRevealSlide(...args);
        };

        console.log("[CSCAPE Story] Reveal navigation patched.");
        return true;
    }

    function numberValue(value, fallback) {
        if (value === undefined || value === null) return fallback;

        const text = String(value).trim();
        if (text === "") return fallback;

        const number = Number(text);
        return Number.isFinite(number) ? number : fallback;
    }

    function clamp01(value, fallback) {
        const number = numberValue(value, fallback);
        const safeNumber = Number.isFinite(number) ? number : 1;
        return Math.max(0, Math.min(1, safeNumber));
    }

    function assetUrl(path) {
        const trimmed = String(path || "").trim();
        if (!trimmed) return "";

        if (
            trimmed.startsWith("http://") ||
            trimmed.startsWith("https://") ||
            trimmed.startsWith("data:") ||
            trimmed.startsWith("blob:") ||
            trimmed.startsWith("/")
        ) {
            return trimmed;
        }

        return new URL(trimmed, window.location.href).href;
    }

    function cssImageUrl(path) {
        const url = assetUrl(path);
        return url ? `url("${url.replaceAll('"', '\\"')}")` : "";
    }

    function formatText(text) {
        try {
            return String(config.formatText(String(text || "")) || "");
        } catch (error) {
            console.warn("[CSCAPE Story] formatText failed:", error);
            return String(text || "");
        }
    }

    function wait(ms, signal) {
        const duration = Math.max(0, Number(ms) || 0);

        if (duration === 0) return Promise.resolve(true);
        if (signal?.aborted) return Promise.resolve(false);

        return new Promise(resolve => {
            const timeout = window.setTimeout(done, duration);

            function done() {
                signal?.removeEventListener("abort", onAbort);
                resolve(true);
            }

            function onAbort() {
                window.clearTimeout(timeout);
                signal.removeEventListener("abort", onAbort);
                resolve(false);
            }

            signal?.addEventListener("abort", onAbort, {once: true});
        });
    }

    function waitForAudioUnlock(signal) {
        if (audioUnlocked) return Promise.resolve(true);
        if (signal?.aborted) return Promise.resolve(false);

        return new Promise(resolve => {
            const waiter = () => {
                cleanup();
                resolve(true);
            };

            function cleanup() {
                unlockWaiters.delete(waiter);
                signal?.removeEventListener("abort", onAbort);
            }

            function onAbort() {
                cleanup();
                resolve(false);
            }

            unlockWaiters.add(waiter);
            signal?.addEventListener("abort", onAbort, {once: true});
        });
    }

    function resolveUnlockWaiters() {
        for (const waiter of Array.from(unlockWaiters)) {
            waiter();
        }
        unlockWaiters.clear();
    }

    function createCursor() {
        const cursor = document.createElement("span");
        cursor.className = "cursor";
        cursor.textContent = "█";
        return cursor;
    }

    function renderInlineToFragment(text) {
        const fragment = document.createDocumentFragment();
        const parts = String(text || "")
            .split(/(\*\*.+?\*\*|\|.+?(?=\n|$)|\n)/g)
            .filter(part => part !== "");

        for (const part of parts) {
            if (part === "\n") {
                fragment.appendChild(document.createElement("br"));
            } else if (part.startsWith("**") && part.endsWith("**") && part.length >= 4) {
                const strong = document.createElement("strong");
                strong.textContent = part.slice(2, -2);
                fragment.appendChild(strong);
            } else if (part.startsWith("|")) {
                const span = document.createElement("span");
                span.className = "objective";
                span.textContent = part.slice(1).trimStart();
                fragment.appendChild(span);
            } else {
                fragment.appendChild(document.createTextNode(part));
            }
        }

        return fragment;
    }

    function renderText(element, text) {
        if (!element) return;
        element.innerHTML = "";
        element.appendChild(renderInlineToFragment(text));
    }

    function delayForChar(char) {
        if (char === "\n") return Math.max(70, Number(config.typeSpeed) * 3);
        if (char === ".") return Math.max(160, Number(config.typeSpeed) * 7);
        if (char === ",") return Math.max(100, Number(config.typeSpeed) * 4);
        if (char === ":" || char === ";") return Math.max(120, Number(config.typeSpeed) * 5);
        if (char === "!" || char === "?") return Math.max(160, Number(config.typeSpeed) * 7);
        return Number(config.typeSpeed) || 28;
    }

    async function typeText(element, rawText, token, signal) {
        const text = formatText(rawText);
        const chars = Array.from(text);
        let index = 0;

        if (!element) return;
        element.innerHTML = "";

        while (index <= chars.length) {
            if (signal?.aborted || token !== runId) return;

            element.innerHTML = "";
            element.appendChild(renderInlineToFragment(chars.slice(0, index).join("")));

            if (index < chars.length) {
                element.appendChild(createCursor());
                const char = chars[index];
                index += 1;
                const ok = await wait(delayForChar(char), signal);
                if (!ok) return;
            } else {
                break;
            }
        }

        renderText(element, text);
    }

    function ensureSlideMarkup(slide) {
        if (!slide) return;

        let scene = slide.querySelector(":scope > .scene");
        if (!scene) {
            scene = document.createElement("div");
            scene.className = "scene";
            slide.appendChild(scene);
        }

        let speaker = scene.querySelector(":scope > .speaker");
        if (!speaker) {
            speaker = document.createElement("div");
            speaker.className = "speaker";
            scene.appendChild(speaker);
        }

        let img = speaker.querySelector("img");
        if (!img) {
            img = document.createElement("img");
            img.alt = "";
            speaker.appendChild(img);
        }

        let dialogue = scene.querySelector(":scope > .dialogue");
        if (!dialogue) {
            dialogue = document.createElement("div");
            dialogue.className = "dialogue";
            scene.appendChild(dialogue);
        }

        if (!dialogue.querySelector(":scope > .name")) {
            const name = document.createElement("div");
            name.className = "name";
            dialogue.appendChild(name);
        }

        if (!dialogue.querySelector(":scope > .text")) {
            const text = document.createElement("div");
            text.className = "text";
            dialogue.appendChild(text);
        }

        if (!dialogue.querySelector(":scope > .task")) {
            const task = document.createElement("div");
            task.className = "task";
            dialogue.appendChild(task);
        }

        if (!scene.querySelector(":scope > .video-task")) {
            const videoTask = document.createElement("div");
            videoTask.className = "video-task";
            scene.appendChild(videoTask);
        }
    }

    function applySceneBackground(slide) {
        const scene = slide.querySelector(".scene");
        if (!scene) return;

        const background = slide.getAttribute("data-background") ||
            slide.getAttribute("data-bg") ||
            config.defaultBackground ||
            "";

        if (!background) {
            scene.style.backgroundImage = "";
            scene.style.backgroundPosition = "";
            scene.style.backgroundSize = "";
            scene.style.backgroundRepeat = "";
            return;
        }

        const overlay = getComputedStyle(document.body)
            .getPropertyValue("--scene-overlay")
            .trim() || "none";

        scene.style.backgroundImage = `${overlay}, ${cssImageUrl(background)}`;
        scene.style.backgroundPosition = "center center";
        scene.style.backgroundSize = "cover";
        scene.style.backgroundRepeat = "no-repeat";
    }

    function getLayout(slide) {
        const raw = String(slide.getAttribute("data-layout") || config.defaultLayout || "dialogue")
            .trim()
            .toLowerCase();

        if (["video", "dialogue", "hybrid", "none"].includes(raw)) return raw;
        return "dialogue";
    }

    function getTextMode(slide) {
        const explicit = String(slide.getAttribute("data-text-mode") || "")
            .trim()
            .toLowerCase();

        if (["instant", "type", "typed", "none", "hidden"].includes(explicit)) {
            if (explicit === "typed") return "type";
            if (explicit === "hidden") return "none";
            return explicit;
        }

        if (slide.hasAttribute("data-text-instant")) return "instant";
        if (slide.hasAttribute("data-no-text")) return "none";

        return config.defaultTextMode || "type";
    }

    function setupSlide(slide) {
        ensureSlideMarkup(slide);

        const layout = getLayout(slide);
        slide.setAttribute("data-layout", layout);
        slide.classList.remove("story-complete");
        slide.setAttribute("data-story-ready", "false");

        const scene = slide.querySelector(".scene");
        const speaker = slide.querySelector(".speaker");
        const img = slide.querySelector(".speaker img");
        const dialogue = slide.querySelector(".dialogue");
        const name = slide.querySelector(".name");
        const text = slide.querySelector(".text");
        const task = slide.querySelector(".task");
        const videoTask = slide.querySelector(".video-task");

        applySceneBackground(slide);

        const speakerName = formatText(slide.getAttribute("data-speaker") || "");
        const avatarPath = slide.getAttribute("data-avatar") || "";
        const side = String(slide.getAttribute("data-side") || "left").trim().toLowerCase();
        const dialogueText = formatText(slide.getAttribute("data-dialogue") || "");
        const taskText = formatText(slide.getAttribute("data-task") || "").trim();
        const textMode = getTextMode(slide);
        const hasSpeaker = Boolean(speakerName || avatarPath);
        const hasText = Boolean(dialogueText && textMode !== "none");
        const hasTask = Boolean(taskText);

        if (scene) {
            scene.dataset.layout = layout;
        }

        if (speaker) {
            speaker.classList.toggle("is-empty", !hasSpeaker);
            speaker.classList.remove("left", "right", "from-left", "from-right");
            speaker.classList.add(side === "right" ? "right" : "left");

            if (hasSpeaker) {
                void speaker.offsetWidth;
                speaker.classList.add(side === "right" ? "from-right" : "from-left");
            }
        }

        if (img) {
            if (avatarPath) {
                img.src = assetUrl(avatarPath);
                img.alt = speakerName || "Story character";
            } else {
                img.removeAttribute("src");
                img.alt = "";
            }
        }

        if (name) {
            name.textContent = speakerName;
            name.classList.toggle("is-empty", !speakerName);
        }

        if (text) {
            text.innerHTML = "";
            text.classList.toggle("is-empty", !hasText);
        }

        if (task) {
            task.textContent = taskText;
            task.classList.toggle("is-empty", !hasTask);
        }

        if (videoTask) {
            videoTask.textContent = taskText;
            videoTask.classList.toggle("is-empty", !hasTask);
        }

        if (dialogue) {
            dialogue.classList.toggle("is-empty", !hasText && !hasTask && !speakerName);
            dialogue.classList.toggle("has-task", hasTask);
            dialogue.classList.toggle("has-text", hasText);
            dialogue.classList.toggle("has-speaker-name", Boolean(speakerName));
        }
    }

    async function showVisibleText(slide, token, signal) {
        const textEl = slide.querySelector(".text");
        const rawText = slide.getAttribute("data-dialogue") || "";
        const mode = getTextMode(slide);

        if (!textEl || !rawText || mode === "none") return;

        if (mode === "instant") {
            renderText(textEl, formatText(rawText));
            return;
        }

        await typeText(textEl, rawText, token, signal);
    }

    function normalizePhase(value) {
        const phase = String(value || "start").trim().toLowerCase();
        return VALID_PHASES.has(phase) ? phase : "start";
    }

    function prop(cue, name, fallback = "") {
        if (Object.prototype.hasOwnProperty.call(cue.props, name)) return cue.props[name];
        return fallback;
    }

    function propAny(cue, names, fallback = "") {
        for (const name of names) {
            if (Object.prototype.hasOwnProperty.call(cue.props, name)) return cue.props[name];
        }
        return fallback;
    }

    function collectAudioCues(slide) {
        const byIndex = new Map();

        for (const attribute of Array.from(slide.attributes)) {
            if (!attribute.name.startsWith("data-audio-")) continue;

            const rest = attribute.name.slice("data-audio-".length);
            const match = rest.match(/^(\d+)(?:-(.+))?$/);
            if (!match) continue;

            const index = Number(match[1]);
            const key = match[2] || "src";

            if (!byIndex.has(index)) {
                byIndex.set(index, {index, props: {}});
            }

            byIndex.get(index).props[key] = attribute.value;
        }

        if (slide.getAttribute("data-sound")) {
            byIndex.set(-2, {
                index: -2,
                props: {
                    src: slide.getAttribute("data-sound"),
                    phase: slide.getAttribute("data-sound-phase") || "before-text",
                    volume: slide.getAttribute("data-sound-volume") || ""
                }
            });
        }

        if (slide.getAttribute("data-generate-sound") === "true") {
            byIndex.set(-1, {
                index: -1,
                props: {
                    type: "tts",
                    phase: slide.getAttribute("data-tts-phase") || "start",
                    "text-from": slide.getAttribute("data-tts-text-from") || "dialogue",
                    text: slide.getAttribute("data-tts-text") || "",
                    voice: slide.getAttribute("data-tts-voice") || "",
                    rate: slide.getAttribute("data-tts-rate") || "",
                    pitch: slide.getAttribute("data-tts-pitch") || "",
                    volume: slide.getAttribute("data-tts-volume") || ""
                }
            });
        }

        return Array.from(byIndex.values())
            .map(raw => normalizeCue(raw, slide))
            .filter(Boolean)
            .sort((a, b) => a.index - b.index);
    }

    function normalizeCue(raw, slide) {
        const phase = normalizePhase(prop(raw, "phase", "start"));
        const stopId = propAny(raw, ["stop", "stop-loop", "stop-id"], "").trim();
        const text = prop(raw, "text", "");
        const textFrom = prop(raw, "text-from", "").trim().toLowerCase();
        const explicitType = prop(raw, "type", "").trim().toLowerCase();
        const src = propAny(raw, ["src", "url", "file"], "").trim();
        const loop = boolValue(prop(raw, "loop", ""), false) || explicitType === "loop";
        const persistent = boolValue(prop(raw, "persistent", ""), false);
        const mode = String(prop(raw, "mode", "")).trim().toLowerCase();
        const parallel = boolValue(prop(raw, "parallel", ""), false) || mode === "parallel";
        const blocking = boolValue(prop(raw, "blocking", ""), true);
        const id = propAny(raw, ["id", "loop-id"], "").trim();

        let type = explicitType;
        if (!type) {
            if (stopId) type = "stop-loop";
            else if (text || textFrom) type = "tts";
            else type = "sound";
        }

        if (type === "stop" || type === "stoploop") type = "stop-loop";
        if (type === "speech") type = "tts";

        const cue = {
            index: raw.index,
            phase,
            type,
            src,
            text,
            textFrom,
            voice: prop(raw, "voice", "").trim(),
            rate: prop(raw, "rate", "").trim(),
            pitch: prop(raw, "pitch", "").trim(),
            volume: prop(raw, "volume", ""),
            loop,
            persistent,
            id,
            stopId,
            group: prop(raw, "group", "").trim(),
            parallel,
            blocking,
            delay: numberValue(prop(raw, "delay", ""), 0),
            slide
        };

        if (cue.type === "stop-loop") return cue;
        if (cue.type === "tts") return cue.text || cue.textFrom ? cue : null;
        if (cue.src) return cue;
        return null;
    }

    function getCueText(cue) {
        if (cue.textFrom === "dialogue") {
            return formatText(cue.slide.getAttribute("data-dialogue") || "");
        }

        if (cue.textFrom === "task") {
            return formatText(cue.slide.getAttribute("data-task") || "");
        }

        return formatText(cue.text || "");
    }

    function buildTtsUrl(cue) {
        const base = config.ttsUrl;
        const text = getCueText(cue);
        if (!base || !text) return "";

        const url = new URL(base, window.location.href);
        url.searchParams.set("text", text);
        url.searchParams.set("voice", cue.voice || cue.slide.getAttribute("data-tts-voice") || config.defaultVoice);
        url.searchParams.set("rate", cue.rate || cue.slide.getAttribute("data-tts-rate") || config.defaultTtsRate || "+0%");
        url.searchParams.set("pitch", cue.pitch || cue.slide.getAttribute("data-tts-pitch") || config.defaultTtsPitch || "+0Hz");
        console.log("[CSCAPE Story] TTS URL:", url.href);
        return url.href;
    }

    function cueSource(cue) {
        if (cue.type === "tts") return buildTtsUrl(cue);
        return assetUrl(cue.src);
    }

    async function playCuePlan(cues, token, signal) {
        let index = 0;

        while (index < cues.length) {
            if (signal?.aborted || token !== runId) return;

            const cue = cues[index];

            if (cue.parallel) {
                const groupName = cue.group || "__default_parallel_group__";
                const group = [];

                while (index < cues.length) {
                    const candidate = cues[index];
                    const candidateGroup = candidate.group || "__default_parallel_group__";

                    if (!candidate.parallel || candidateGroup !== groupName) break;
                    group.push(candidate);
                    index += 1;
                }

                await Promise.all(group.map(item => playCue(item, token, signal)));
            } else {
                await playCue(cue, token, signal);
                index += 1;
            }
        }
    }

    function cuesForPhase(cues, phase) {
        return cues.filter(cue => cue.phase === phase).sort((a, b) => a.index - b.index);
    }

    function playPhase(cues, phase, token, signal) {
        return playCuePlan(cuesForPhase(cues, phase), token, signal);
    }

    async function playCue(cue, token, signal) {
        if (signal?.aborted || token !== runId) return;

        if (cue.delay > 0) {
            const ok = await wait(cue.delay * 1000, signal);
            if (!ok) return;
        }

        if (cue.type === "stop-loop") {
            if (cue.stopId) stopPersistentLoop(cue.stopId);
            else if (cue.id) stopPersistentLoop(cue.id);
            else stopAllPersistentLoops();
            return;
        }

        if (cue.loop) {
            startLoopCue(cue, token, signal);
            return;
        }

        if (!cue.blocking) {
            startOneShotCue(cue, token, signal);
            return;
        }

        await startOneShotCue(cue, token, signal);
    }

    async function startLoopCue(cue, token, signal) {
        const unlocked = await waitForAudioUnlock(signal);
        if (!unlocked || signal?.aborted || token !== runId) return;

        const src = cueSource(cue);
        if (!src) return;

        const volume = clamp01(cue.volume, config.soundVolume);
        const loopId = cue.id || src;

        if (cue.persistent) {
            const existing = persistentLoops.get(loopId);
            if (existing && existing.src === src && !existing.audio.paused) {
                existing.audio.volume = volume;
                return;
            }
            if (existing) stopAudio(existing.audio);
        }

        const audio = new Audio(src);
        audio.loop = true;
        audio.preload = "auto";
        audio.volume = volume;

        try {
            await audio.play();

            if (cue.persistent) {
                persistentLoops.set(loopId, {audio, src});
            } else {
                activeSlideLoops.add(audio);
                const stopOnAbort = () => {
                    stopAudio(audio);
                    activeSlideLoops.delete(audio);
                };
                signal?.addEventListener("abort", stopOnAbort, {once: true});
            }
        } catch (error) {
            console.warn("[CSCAPE Story] Loop audio failed:", src, error);
        }
    }

    async function startOneShotCue(cue, token, signal) {
        const unlocked = await waitForAudioUnlock(signal);

        if (!unlocked || signal?.aborted || token !== runId) return;

        const src = cueSource(cue);
        if (!src) {
            console.warn("[CSCAPE Story] No audio src for cue", cue);
            return;
        }

        const audio = new Audio();
        audio.loop = false;
        audio.preload = "auto";
        audio.volume = clamp01(cue.volume, config.soundVolume);
        audio.src = src;

        activeOneShots.add(audio);

        return new Promise(resolve => {
            let finished = false;

            function cleanup() {
                audio.removeEventListener("ended", onEnded);
                audio.removeEventListener("error", onError);
                audio.removeEventListener("pause", onPause);
                signal?.removeEventListener("abort", onAbort);
                activeOneShots.delete(audio);
            }

            function finish() {
                if (finished) return;
                finished = true;
                cleanup();
                resolve();
            }

            function onEnded() {
                finish();
            }

            function onError(event) {
                if (!signal?.aborted && token === runId) {
                    console.warn("[CSCAPE Story] Audio failed:", src, event, audio.error);
                }

                finish();
            }

            function onPause() {
                /*
                 * Wichtig:
                 * pause darf NICHT automatisch finish() auslösen.
                 * Sonst gilt Audio als fertig, obwohl es nur gestoppt wurde.
                 * Abbruch wird explizit über onAbort behandelt.
                 */
            }

            function onAbort() {
                try {
                    audio.pause();
                    audio.currentTime = 0;
                    audio.removeAttribute("src");
                    audio.load();
                } catch {
                    // Browser-spezifische Media-Fehler ignorieren.
                }

                finish();
            }

            audio.addEventListener("ended", onEnded, {once: true});
            audio.addEventListener("error", onError, {once: true});
            audio.addEventListener("pause", onPause);
            signal?.addEventListener("abort", onAbort, {once: true});

            audio.play().catch(error => {
                const name = error?.name || "";
                const message = error?.message || "";

                const expectedAbort =
                    signal?.aborted ||
                    token !== runId ||
                    name === "AbortError" ||
                    message.toLowerCase().includes("aborted");

                if (!expectedAbort) {
                    console.error("[CSCAPE Story] audio.play rejected:", {
                        src,
                        name,
                        message,
                        error
                    });
                }

                finish();
            });
        });
    }

    function stopAudio(audio) {
        if (!audio) return;

        try {
            audio.pause();
            audio.currentTime = 0;
            audio.removeAttribute("src");
            audio.load();
        } catch {
            // Ignore browser-specific media state errors.
        }
    }

    function stopActiveOneShots() {
        for (const audio of Array.from(activeOneShots)) {
            stopAudio(audio);
        }
        activeOneShots.clear();
    }

    function stopActiveSlideLoops() {
        for (const audio of Array.from(activeSlideLoops)) {
            stopAudio(audio);
        }
        activeSlideLoops.clear();
    }

    function stopPersistentLoop(id) {
        const entry = persistentLoops.get(id);
        if (!entry) return;
        stopAudio(entry.audio);
        persistentLoops.delete(id);
    }

    function stopAllPersistentLoops() {
        for (const id of Array.from(persistentLoops.keys())) {
            stopPersistentLoop(id);
        }
    }

    function cancelCurrentRun() {
        for (const controller of Array.from(activeControllers)) {
            try {
                controller.abort();
            } catch {
                // Ignore already-aborted controllers.
            }
        }

        activeControllers.clear();

        if (currentController) {
            try {
                currentController.abort();
            } catch {
                // Ignore already-aborted controller.
            }

            currentController = null;
        }

        stopActiveOneShots();
        stopActiveSlideLoops();
    }

    function fadeAudio(audio, from, to, duration = 500) {
        if (!audio) return Promise.resolve();

        const startVolume = Math.max(0, Math.min(1, from));
        const endVolume = Math.max(0, Math.min(1, to));
        const fadeDuration = Math.max(0, Number(duration) || 0);

        if (fadeDuration === 0) {
            audio.volume = endVolume;
            return Promise.resolve();
        }

        audio.volume = startVolume;

        return new Promise(resolve => {
            const start = performance.now();

            function frame(now) {
                const progress = Math.min((now - start) / fadeDuration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                audio.volume = startVolume + (endVolume - startVolume) * eased;

                if (progress < 1) {
                    requestAnimationFrame(frame);
                } else {
                    audio.volume = endVolume;
                    resolve();
                }
            }

            requestAnimationFrame(frame);
        });
    }

    async function stopMusic() {
        if (!musicAudio) return;
        const audio = musicAudio;
        musicAudio = null;
        musicSrc = "";
        await fadeAudio(audio, audio.volume, 0, 450);
        stopAudio(audio);
    }

    async function applyMusicForSlide(slide) {
        if (!audioUnlocked || !slide) return;

        const stopRequested = boolValue(slide.getAttribute("data-stop-music"), false);
        const rawMusic = slide.hasAttribute("data-music")
            ? slide.getAttribute("data-music")
            : config.defaultMusic;
        const musicValue = String(rawMusic || "").trim();

        if (stopRequested || ["stop", "none", "false", "off"].includes(musicValue.toLowerCase())) {
            await stopMusic();
            return;
        }

        if (!musicValue) return;

        const src = assetUrl(musicValue);
        const targetVolume = clamp01(slide.getAttribute("data-music-volume"), config.musicVolume);
        const shouldLoop = boolValue(slide.getAttribute("data-music-loop"), config.musicLoop !== false);

        if (!musicAudio || musicSrc !== src) {
            if (musicAudio) {
                await stopMusic();
            }

            musicAudio = new Audio(src);
            musicAudio.preload = "auto";
            musicAudio.loop = shouldLoop;
            musicAudio.volume = 0;
            musicSrc = src;
        }

        musicAudio.loop = shouldLoop;

        try {
            const rate = slide.getAttribute("data-music-rate");
            if (rate) musicAudio.playbackRate = Number(rate) || 1;
        } catch {
            // Optional attribute. Ignore invalid values.
        }

        try {
            await musicAudio.play();
            await fadeAudio(musicAudio, musicAudio.volume, targetVolume, 650);
        } catch (error) {
            console.warn("[CSCAPE Story] Music failed:", src, error);
        }
    }

    function getReadyCue(slide) {
        const readySound = slide.getAttribute("data-ready-sound") || "";
        const readyText = slide.getAttribute("data-ready-tts-text") || "";
        const readyTextFrom = slide.getAttribute("data-ready-tts-text-from") || "";

        if (!readySound && !readyText && !readyTextFrom) return null;

        return {
            index: Number.MAX_SAFE_INTEGER,
            phase: "after-text",
            type: readySound ? "sound" : "tts",
            src: readySound,
            text: readyText,
            textFrom: readyTextFrom,
            voice: slide.getAttribute("data-ready-tts-voice") || "",
            rate: slide.getAttribute("data-ready-tts-rate") || "",
            pitch: slide.getAttribute("data-ready-tts-pitch") || "",
            volume: slide.getAttribute("data-ready-sound-volume") || slide.getAttribute("data-ready-tts-volume") || "",
            loop: false,
            persistent: false,
            id: "",
            stopId: "",
            group: "",
            parallel: false,
            blocking: boolValue(slide.getAttribute("data-ready-sound-blocking"), true),
            delay: numberValue(slide.getAttribute("data-ready-sound-delay"), 0),
            slide
        };
    }

    function markSlideReady(slide) {
        const state = getSlideState(slide);
        state.ready = true;
        slide.setAttribute("data-story-ready", "true");
        slide.classList.add("story-complete");
    }

    function scheduleAutoNext(slide, token) {
        if (!slide.hasAttribute("data-after-ready-delay")) return;

        const state = getSlideState(slide);
        if (state.nextScheduled) return;

        const delaySeconds = Math.max(0, numberValue(slide.getAttribute("data-after-ready-delay"), 0));
        state.nextScheduled = true;

        window.setTimeout(() => {
            if (token !== runId) return;
            if (!window.Reveal || Reveal.getCurrentSlide() !== slide) return;

            allowInternalNavigation = true;

            try {
                Reveal.next();
            } finally {
                allowInternalNavigation = false;
            }
        }, delaySeconds * 1000);
    }

    async function playSlide(slide) {
        if (!slide) return;

        slide.classList.remove("story-complete");
        slide.setAttribute("data-story-ready", "false");

        cancelCurrentRun();
        const token = ++runId;
        const controller = new AbortController();
        const signal = controller.signal;

        currentController = controller;
        activeControllers.add(controller);

        const state = getSlideState(slide);
        state.ready = false;
        state.nextScheduled = false;

        try {
            console.log("[CSCAPE Story] playSlide", {
                index: window.Reveal ? Reveal.getIndices(slide) : null,
                dialogue: slide?.getAttribute("data-dialogue"),
                layout: slide?.getAttribute("data-layout")
            });

            if (typeof config.beforeSlide === "function") {
                await config.beforeSlide(slide, api);
            }

            if (signal.aborted || token !== runId) return;

            setupSlide(slide);
            await applyMusicForSlide(slide);
            const cues = collectAudioCues(slide);
            console.log("[CSCAPE Story] cues", cues);

            await playPhase(cues, "before-text", token, signal);
            if (signal.aborted || token !== runId) return;

            const startAudio = playPhase(cues, "start", token, signal);
            const visibleText = showVisibleText(slide, token, signal);

            await Promise.all([startAudio, visibleText]);
            if (signal.aborted || token !== runId) return;

            await playPhase(cues, "after-text", token, signal);
            if (signal.aborted || token !== runId) return;

            const readyCue = getReadyCue(slide);
            if (readyCue) {
                await playCue(readyCue, token, signal);
            }

            if (signal.aborted || token !== runId) return;

            markSlideReady(slide);

            if (!runPendingNavigation()) {
                scheduleAutoNext(slide, token);
            }

            if (typeof config.afterSlide === "function") {
                await config.afterSlide(slide, api);
            }
        } catch (error) {
            if (!signal.aborted) {
                console.error("[CSCAPE Story] Slide playback failed:", error);
                markSlideReady(slide);

                if (!runPendingNavigation()) {
                    scheduleAutoNext(slide, token);
                }
            }
        } finally {
            activeControllers.delete(controller);

            if (currentController === controller) {
                currentController = null;
            }
        }
    }

    async function unlockAudio(event) {
        console.log("[CSCAPE Story] unlockAudio event:", event?.type, event?.key || "");
        if (event?.type === "keydown" && ["Shift", "Control", "Alt", "Meta", "Tab"].includes(event.key)) {

            return;
        }

        if (!audioUnlocked) {
            audioUnlocked = true;
            console.log("[CSCAPE Story] audio unlocked");
            document.body.classList.add("story-audio-unlocked");

            const hint = document.getElementById("audioHint");
            if (hint) hint.remove();

            resolveUnlockWaiters();
        }

        if (window.Reveal && typeof Reveal.getCurrentSlide === "function") {
            applyMusicForSlide(Reveal.getCurrentSlide());
        }
    }

    function createAudioHint() {
        let hint = document.getElementById("audioHint");

        if (!hint) {
            hint = document.createElement("button");
            hint.id = "audioHint";
            hint.className = "audio-hint";
            hint.type = "button";
            hint.textContent = config.audioHintText;
            document.body.appendChild(hint);
        }

        hint.addEventListener("pointerdown", unlockAudio, {capture: true});
        hint.addEventListener("click", unlockAudio, {capture: true});
    }

    function init() {
        if (initialized) return;
        initialized = true;

        document.querySelectorAll(".reveal section").forEach(ensureSlideMarkup);
        createAudioHint();

        window.addEventListener("pointerdown", unlockAudio, {capture: true});
        window.addEventListener("keydown", unlockAudio, {capture: true});

        if (!window.Reveal) {
            console.warn("[CSCAPE Story] Reveal is not available.");
            return;
        }

        let revealReadySeen = false;

        Reveal.on("ready", event => {
            revealReadySeen = true;
            document.body.classList.add("story-ready");

            patchRevealNavigation();

            playSlide(event.currentSlide);
        });

        Reveal.on("slidechanged", event => {
            patchRevealNavigation();

            playSlide(event.currentSlide);
        });

        window.setTimeout(() => {
            if (!revealReadySeen && window.Reveal && typeof Reveal.getCurrentSlide === "function") {
                console.log("[CSCAPE Story] initial fallback playSlide");

                patchRevealNavigation();

                playSlide(Reveal.getCurrentSlide());
            }
        }, 700);
    }
})();