# Context — auto-layout (user decisions)

- 2026-10-08 · **Engines**: user asked to "support different backends such as dot, d2 and ELK +
  nested flex". → Pluggable engine interface; flex built-in (default), dot / d2 / ELK as adapters.
- Group use case named by the user: AWS Region, AWS AZ ("elements groups such as AWS Region, AWS AZ").
- Audience: "for humans" — specs written without coordinates.

Local environment (verified 2026-10-08): graphviz 2.43 (`dot -Tjson` OK), d2 0.7.1 (dagre, elk, tala),
bun 1.3.14, node 22, elkjs 0.12.0 on the npm registry.
