// The code editor (CodeMirror 6). The only module that imports `@codemirror/*`: CodePanel loads it with
// `import("./codemirror")`, so the catalog pages never download it.
import { css } from "@codemirror/lang-css";
import { python } from "@codemirror/lang-python";
import { yaml } from "@codemirror/lang-yaml";
import { EditorSelection, EditorState, Prec, type Extension } from "@codemirror/state";
import { oneDark } from "@codemirror/theme-one-dark";
import { EditorView, keymap } from "@codemirror/view";
import { basicSetup } from "codemirror";
import type { Language } from "./editor";

export type EditorOptions = {
  onChange: (text: string) => void;
  onSave: () => void;
};

export type EditorHandle = {
  /** Show another file (a new document, its own undo history). */
  load: (text: string, language: Language) => void;
  /** Replace the text of the current document (a newer version on disk), keeping the cursor where it can. */
  setText: (text: string) => void;
  /** Select a 1-based line and scroll it into view. */
  jumpTo: (line: number) => void;
  focus: () => void;
  destroy: () => void;
};

const MODES: Record<Language, () => Extension> = { python, css, yaml, text: () => [] };

function dark(): boolean {
  return typeof matchMedia !== "undefined" && matchMedia("(prefers-color-scheme: dark)").matches;
}

export function createEditor(parent: HTMLElement, opts: EditorOptions): EditorHandle {
  let silent = false; // a setText from the disk is not a user edit
  const extensions = (language: Language): Extension[] => [
    basicSetup,
    MODES[language](),
    Prec.highest(keymap.of([{ key: "Mod-s", preventDefault: true, run: () => (opts.onSave(), true) }])),
    EditorView.updateListener.of((u) => {
      if (u.docChanged && !silent) opts.onChange(u.state.doc.toString());
    }),
    EditorView.theme({ "&": { height: "100%", fontSize: "13px" }, ".cm-scroller": { fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" } }),
    ...(dark() ? [oneDark] : []),
  ];
  const view = new EditorView({ parent, state: EditorState.create({ doc: "", extensions: extensions("text") }) });

  return {
    load(text, language) {
      view.setState(EditorState.create({ doc: text, extensions: extensions(language) }));
    },
    setText(text) {
      const head = Math.min(view.state.selection.main.head, text.length);
      silent = true;
      try {
        view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text }, selection: EditorSelection.cursor(head) });
      } finally {
        silent = false;
      }
    },
    jumpTo(line) {
      const doc = view.state.doc;
      if (line < 1 || line > doc.lines) return;
      const l = doc.line(line);
      view.dispatch({ selection: EditorSelection.range(l.from, l.to), scrollIntoView: true });
      view.focus();
    },
    focus: () => view.focus(),
    destroy: () => view.destroy(),
  };
}
