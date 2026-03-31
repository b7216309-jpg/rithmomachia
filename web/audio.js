/**
 * Rithmomachia — Procedural Audio Engine (Web Audio API)
 * Medieval-themed sound effects generated in real time.
 */

const Audio = (() => {
    let ctx = null;
    let masterGain = null;
    let _volume = 0.5;
    let _muted = false;

    function ensure() {
        if (!ctx) {
            ctx = new (window.AudioContext || window.webkitAudioContext)();
            masterGain = ctx.createGain();
            masterGain.gain.value = _volume;
            masterGain.connect(ctx.destination);
        }
        if (ctx.state === 'suspended') ctx.resume();
        return ctx;
    }

    function setVolume(v) {
        _volume = Math.max(0, Math.min(1, v));
        if (masterGain) masterGain.gain.value = _muted ? 0 : _volume;
    }

    function getVolume() { return _volume; }

    function toggleMute() {
        _muted = !_muted;
        if (masterGain) masterGain.gain.value = _muted ? 0 : _volume;
        return _muted;
    }

    function isMuted() { return _muted; }

    // -- Utility: noise buffer --
    function noiseBuffer(duration) {
        const c = ensure();
        const len = c.sampleRate * duration;
        const buf = c.createBuffer(1, len, c.sampleRate);
        const data = buf.getChannelData(0);
        for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
        return buf;
    }

    // -- Piece select: soft wooden click --
    function playSelect() {
        const c = ensure();
        const t = c.currentTime;

        const osc = c.createOscillator();
        const gain = c.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(800, t);
        osc.frequency.exponentialRampToValueAtTime(400, t + 0.06);
        gain.gain.setValueAtTime(0.3, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.08);
        osc.connect(gain).connect(masterGain);
        osc.start(t);
        osc.stop(t + 0.08);

        // Click transient
        const noise = c.createBufferSource();
        noise.buffer = noiseBuffer(0.02);
        const nGain = c.createGain();
        nGain.gain.setValueAtTime(0.15, t);
        nGain.gain.exponentialRampToValueAtTime(0.001, t + 0.02);
        const filter = c.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.value = 2000;
        filter.Q.value = 2;
        noise.connect(filter).connect(nGain).connect(masterGain);
        noise.start(t);
        noise.stop(t + 0.02);
    }

    // -- Piece move: stone sliding on wood --
    function playMove() {
        const c = ensure();
        const t = c.currentTime;

        // Slide noise
        const noise = c.createBufferSource();
        noise.buffer = noiseBuffer(0.15);
        const nGain = c.createGain();
        nGain.gain.setValueAtTime(0.08, t);
        nGain.gain.linearRampToValueAtTime(0.12, t + 0.05);
        nGain.gain.exponentialRampToValueAtTime(0.001, t + 0.15);
        const filter = c.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.value = 1200;
        filter.Q.value = 1;
        noise.connect(filter).connect(nGain).connect(masterGain);
        noise.start(t);
        noise.stop(t + 0.15);

        // Thud on placement
        const osc = c.createOscillator();
        const gain = c.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(180, t + 0.1);
        osc.frequency.exponentialRampToValueAtTime(80, t + 0.2);
        gain.gain.setValueAtTime(0, t);
        gain.gain.linearRampToValueAtTime(0.25, t + 0.1);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.25);
        osc.connect(gain).connect(masterGain);
        osc.start(t);
        osc.stop(t + 0.25);
    }

    // -- Capture: metallic clash --
    function playCapture() {
        const c = ensure();
        const t = c.currentTime;

        // Impact burst
        const noise = c.createBufferSource();
        noise.buffer = noiseBuffer(0.3);
        const nGain = c.createGain();
        nGain.gain.setValueAtTime(0.3, t);
        nGain.gain.exponentialRampToValueAtTime(0.001, t + 0.25);
        const filter = c.createBiquadFilter();
        filter.type = 'highpass';
        filter.frequency.value = 800;
        noise.connect(filter).connect(nGain).connect(masterGain);
        noise.start(t);
        noise.stop(t + 0.3);

        // Metallic ring
        [520, 780, 1100].forEach((freq, i) => {
            const osc = c.createOscillator();
            const gain = c.createGain();
            osc.type = 'sine';
            osc.frequency.value = freq;
            gain.gain.setValueAtTime(0.15 - i * 0.03, t);
            gain.gain.exponentialRampToValueAtTime(0.001, t + 0.4 - i * 0.05);
            osc.connect(gain).connect(masterGain);
            osc.start(t);
            osc.stop(t + 0.4);
        });

        // Low impact
        const bass = c.createOscillator();
        const bassGain = c.createGain();
        bass.type = 'sine';
        bass.frequency.setValueAtTime(120, t);
        bass.frequency.exponentialRampToValueAtTime(40, t + 0.15);
        bassGain.gain.setValueAtTime(0.35, t);
        bassGain.gain.exponentialRampToValueAtTime(0.001, t + 0.2);
        bass.connect(bassGain).connect(masterGain);
        bass.start(t);
        bass.stop(t + 0.2);
    }

    // -- Siege: deep resonant bell --
    function playSiege() {
        const c = ensure();
        const t = c.currentTime;

        [130, 195, 260, 390].forEach((freq, i) => {
            const osc = c.createOscillator();
            const gain = c.createGain();
            osc.type = 'sine';
            osc.frequency.value = freq;
            gain.gain.setValueAtTime(0.2 - i * 0.04, t);
            gain.gain.exponentialRampToValueAtTime(0.001, t + 1.2 - i * 0.15);
            osc.connect(gain).connect(masterGain);
            osc.start(t);
            osc.stop(t + 1.2);
        });

        // Bell strike
        const noise = c.createBufferSource();
        noise.buffer = noiseBuffer(0.05);
        const nGain = c.createGain();
        nGain.gain.setValueAtTime(0.2, t);
        nGain.gain.exponentialRampToValueAtTime(0.001, t + 0.05);
        noise.connect(nGain).connect(masterGain);
        noise.start(t);
        noise.stop(t + 0.05);
    }

    // -- Ambush: quick double strike --
    function playAmbush() {
        const c = ensure();
        const t = c.currentTime;

        [0, 0.08].forEach(offset => {
            const osc = c.createOscillator();
            const gain = c.createGain();
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(600, t + offset);
            osc.frequency.exponentialRampToValueAtTime(200, t + offset + 0.1);
            gain.gain.setValueAtTime(0.15, t + offset);
            gain.gain.exponentialRampToValueAtTime(0.001, t + offset + 0.12);
            osc.connect(gain).connect(masterGain);
            osc.start(t + offset);
            osc.stop(t + offset + 0.12);
        });

        const noise = c.createBufferSource();
        noise.buffer = noiseBuffer(0.2);
        const nGain = c.createGain();
        nGain.gain.setValueAtTime(0.2, t);
        nGain.gain.exponentialRampToValueAtTime(0.001, t + 0.2);
        const filter = c.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.value = 1500;
        noise.connect(filter).connect(nGain).connect(masterGain);
        noise.start(t);
        noise.stop(t + 0.2);
    }

    // -- Victory fanfare: triumphant ascending chord --
    function playVictory() {
        const c = ensure();
        const t = c.currentTime;

        const notes = [
            { freq: 262, delay: 0 },     // C4
            { freq: 330, delay: 0.15 },   // E4
            { freq: 392, delay: 0.3 },    // G4
            { freq: 523, delay: 0.5 },    // C5
        ];

        notes.forEach(({ freq, delay }) => {
            const osc = c.createOscillator();
            const gain = c.createGain();
            osc.type = 'triangle';
            osc.frequency.value = freq;
            gain.gain.setValueAtTime(0, t + delay);
            gain.gain.linearRampToValueAtTime(0.2, t + delay + 0.05);
            gain.gain.linearRampToValueAtTime(0.15, t + delay + 0.4);
            gain.gain.exponentialRampToValueAtTime(0.001, t + delay + 1.2);
            osc.connect(gain).connect(masterGain);
            osc.start(t + delay);
            osc.stop(t + delay + 1.2);

            // Octave shimmer
            const osc2 = c.createOscillator();
            const gain2 = c.createGain();
            osc2.type = 'sine';
            osc2.frequency.value = freq * 2;
            gain2.gain.setValueAtTime(0, t + delay);
            gain2.gain.linearRampToValueAtTime(0.06, t + delay + 0.1);
            gain2.gain.exponentialRampToValueAtTime(0.001, t + delay + 0.8);
            osc2.connect(gain2).connect(masterGain);
            osc2.start(t + delay);
            osc2.stop(t + delay + 0.8);
        });
    }

    // -- Turn change: subtle notification --
    function playTurnChange() {
        const c = ensure();
        const t = c.currentTime;

        const osc = c.createOscillator();
        const gain = c.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(440, t);
        osc.frequency.setValueAtTime(520, t + 0.08);
        gain.gain.setValueAtTime(0.08, t);
        gain.gain.linearRampToValueAtTime(0.1, t + 0.08);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.2);
        osc.connect(gain).connect(masterGain);
        osc.start(t);
        osc.stop(t + 0.2);
    }

    return {
        setVolume,
        getVolume,
        toggleMute,
        isMuted,
        playSelect,
        playMove,
        playCapture,
        playSiege,
        playAmbush,
        playVictory,
        playTurnChange,
    };
})();
