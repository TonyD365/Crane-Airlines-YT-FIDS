# Fonts

Drop a bundled display face here to override the system fonts, using one of the
file names the registry looks for (see `crane_fids/renderer/fonts.py`):

| Weight  | Preferred file name  |
| ------- | -------------------- |
| Bold    | `FIDS-Bold.ttf`      |
| Regular | `FIDS-Regular.ttf`   |

If nothing is present, the renderer falls back to `Inter`, `Roboto`,
`DejaVu Sans` or `Liberation Sans`, in that order — the Docker image installs
DejaVu and Liberation, so the board always renders.

Only ship fonts whose licence allows redistribution (SIL OFL, Apache-2.0, ...).
