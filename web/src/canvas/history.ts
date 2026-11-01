// Undo and redo of canvas edits in this page session (canvas-editor SEL-09): each entry holds the whole file text
// before and after one edit, so undo restores the exact prior text. The caller saves it as a new, version-checked write.
export type Entry = { path: string; before: string; after: string };

/** Steps kept; the oldest are dropped past this. */
export const LIMIT = 50;

export class History {
  private done: Entry[] = [];
  private undone: Entry[] = [];

  /** A new edit: it can be undone, and everything that could have been redone is gone. */
  record(e: Entry): void {
    if (e.before === e.after) return;
    this.done.push(e);
    if (this.done.length > LIMIT) this.done.shift();
    this.undone = [];
  }

  get canUndo(): boolean {
    return this.done.length > 0;
  }

  get canRedo(): boolean {
    return this.undone.length > 0;
  }

  /** The edit to take back (the caller writes `before`), now redoable; undefined with nothing to undo. */
  undo(): Entry | undefined {
    const e = this.done.pop();
    if (e) this.undone.push(e);
    return e;
  }

  /** The edit to apply again (the caller writes `after`), now undoable; undefined with nothing to redo. */
  redo(): Entry | undefined {
    const e = this.undone.pop();
    if (e) this.done.push(e);
    return e;
  }

  /** Forget everything (the file changed on disk, or another diagram was opened). */
  clear(): void {
    this.done = [];
    this.undone = [];
  }
}
