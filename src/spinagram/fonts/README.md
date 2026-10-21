# Bundled fallback fonts

Last links of the per-character glyph fallback chain (role font → body font → these):

| File | Font | Licence |
| ---- | ---- | ------- |
| `NotoSansSymbols2-Regular.ttf` | Noto Sans Symbols 2 | SIL Open Font License 1.1 (`OFL.txt`) |
| `NotoSansMath-Regular.ttf` | Noto Sans Math | SIL Open Font License 1.1 (`OFL.txt`) |

Both are subsets (Latin-1 symbols, U+2000–2BFF, U+2E00–2E7F, U+1F300–1F6FF, U+1F900–1F9FF) made with
`fontTools.subset --layout-features='' --no-hinting` from notofonts.github.io. Copyright 2022 The Noto Project
Authors (https://github.com/notofonts/symbols, https://github.com/notofonts/math).
