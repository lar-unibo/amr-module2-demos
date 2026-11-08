// Runs loop iterations of the Python session at a chosen rate (iterations per second),
// with one request in flight, and hands every answer to onResult.
export class Runner {
    constructor(session, { action = 'step', rate = 30, maxBatch = 6, onResult, onStop } = {}) {
        Object.assign(this, { session, action, rate, maxBatch, onResult, onStop });
        this.running = false;
        this.busy = false;
        this.due = 0;
        this.last = 0;
        this.extra = {};
    }

    start() {
        if (this.running) return;
        this.running = true;
        this.last = performance.now();
        this.due = 1;
        const tick = (now) => {
            if (!this.running) return;
            this.due = Math.min(this.due + (now - this.last) / 1000 * this.rate, this.maxBatch);
            this.last = now;
            if (!this.busy && this.due >= 1) this.request(Math.floor(this.due));
            requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
    }

    stop() {
        if (!this.running) return;
        this.running = false;
        this.onStop?.();
    }

    async request(n) {
        this.busy = true;
        this.due -= n;
        try {
            const result = await this.session.call(this.action, { n, ...this.extra });
            if (this.running) this.onResult(result);
        } catch {
            this.stop();
        }
        this.busy = false;
    }

    // One iteration, outside the running mode (for step-by-step use).
    async once(payload = {}) {
        return this.session.call(this.action, { n: 1, ...this.extra, ...payload });
    }
}
