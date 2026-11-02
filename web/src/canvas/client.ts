// Request/response over a Worker: each call carries an id, the worker answers with the same id.
export type Request =
  | { t: "load"; scene: string; files: Record<string, string>; fontBase: string }
  | { t: "drag"; moves: Record<string, [number, number]> }
  | { t: "ops"; yaml: string; ops: string }
  | { t: "srcmap"; yaml: string };
export type Response = { id: number; ok: true; value: string } | { id: number; ok: false; error: string };

/** The part of `Worker` the client needs (so tests can pass a fake). */
export interface Port {
  postMessage(message: unknown): void;
  addEventListener(type: "message", listener: (e: { data: Response }) => void): void;
  terminate?(): void;
}

export class CanvasClient {
  private next = 1;
  private pending = new Map<number, { resolve: (v: string) => void; reject: (e: Error) => void }>();

  constructor(private port: Port) {
    port.addEventListener("message", (e) => {
      const p = this.pending.get(e.data.id);
      if (!p) return;
      this.pending.delete(e.data.id);
      if (e.data.ok) p.resolve(e.data.value);
      else p.reject(new Error(e.data.error));
    });
  }

  call(req: Request): Promise<string> {
    const id = this.next++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.port.postMessage({ id, ...req });
    });
  }

  dispose(): void {
    for (const p of this.pending.values()) p.reject(new Error("canvas worker stopped"));
    this.pending.clear();
    this.port.terminate?.();
  }
}
