# What the analyzer measures

All metrics come from a 1600 px copy, sRGB values 0..1. They are hints: confirm
by eye before acting on them.

## Flags

| Flag | Meaning | Trust |
|---|---|---|
| `soft` | The crispest 1/16 of the frame is under 40% of the batch median. Nothing in the frame is sharp: shake, missed focus or heavy motion blur. | High when set. When not set, the runner can still be soft against a sharp background (foliage scores very high), so zoom on faces. |
| `slow-shutter` | Shutter slower than 1/500 s. Runners' arms and feet smear, faces can too. | EXIF fact. Zoom on a sample. |
| `high-iso` | ISO 3200 or more. Expect visible noise in shadows and skies. | EXIF fact. |
| `blown-subject` | Over 3% of the central half of the frame is pure white. Usually a white shirt, cap or face in hard sun. | Medium: a white bib or a sky gap in the middle also counts. Look. |
| `crushed-shadows` | Over 5% of the frame is pure black. | Medium: black shorts and shoes are fine. |
| `underexposed` | Median under 0.25 and nothing reaches near white. | High. |
| `overexposed` | Median over 0.62 with no real blacks, or with clipping. | Medium: high-key frames with a white sky trigger it. |
| `color-cast` | The asphalt in the lower third is far from neutral. | High on paved streets. Meaningless on grass or dirt (then no reading is taken). |
| `not-srgb` | Embedded profile is Adobe RGB, Display P3 or other. `apply` converts to sRGB; a `keep` copy would not, so use `edit` with preset `nenhum`. | Fact. |

## Metrics in `analysis.json`

- `median`, `p2`, `p98`: luminance percentiles. Exposure is judged by the ends
  of the histogram, not the median, because dark asphalt or a white sky moves
  the median while the runner is fine.
- `contrast`: p95 - p5. Under 0.55 reads as flat (overcast); over 0.75 with
  clipping reads as hard sun.
- `clipped_highlights`: share of pixels with a channel at 255. A white sky
  alone makes this 5-20% in daylight; that is normal.
- `center_blown`: share of pure white pixels in the middle half.
- `center_vs_border`: center brightness over border brightness. Under 0.75
  with a bright border means backlight (`contraluz`).
- `sharpness`: variance of the Laplacian in the crispest tile, x10^4. Only
  meaningful relative to the batch.
- `wb_temp_fix`, `wb_tint_fix`: temp/tint that would make the asphalt fully
  neutral, or `null` when the ground is not gray enough to read (grass, dirt,
  a close-up with no road). The suggested adjust uses only a sixth of it plus a
  `blues` cut, because sky-lit asphalt reads much bluer than the rest of the
  scene and the full value turns skin and trees yellow. Cooling is suggested
  even more gently: warm light flatters skin.
- `burst`: frames less than 1 s apart share a number; `null` when single.

## Suggested scene

`suggest` picks a preset from the numbers: `baixa-luz` for ISO 3200+,
`contraluz` for a dark center against a bright border, `sol-forte` for hard
contrast with clipping, `nublado` for flat light, `sombra` for a cold cast,
`neutro` otherwise. It never picks `golden` or `pb-impacto`: those are
judgment calls made by eye.
