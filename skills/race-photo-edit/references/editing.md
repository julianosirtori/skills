# Editing running photos

Exact preset values: `python scripts/photo.py presets`. This file is the why.

## Order of work (the same as Lightroom)

1. Cull. Editing time goes only to photos that can sell.
2. Group by light: same spot, same direction of sun, same time block.
3. White balance, then exposure, for the group.
4. Tone (highlights, shadows, whites, blacks, contrast).
5. Presence (clarity, vibrance, saturation).
6. Per photo: crop, straighten, small exposure fixes.
7. Noise reduction, then sharpening for output. The script runs steps 3 to 7 in
   this order.

## The look that sells

Warm and lively, never gray. Runners buy photos that make them look healthy,
strong and happy, and share them on social media. Every preset is built on the
same base that sports editors use: real contrast (+15..+30) with deep blacks
(-10..-20), vibrance (+20..+30) instead of saturation because it spares skin,
clarity around +15, a slightly warm white balance and a golden grade in the
light (`warmth`). The road is made neutral with `blues`, never by cooling
the whole photo.

The first version of these presets lifted shadows and pulled highlights with
no contrast. On real event photos that read as "frias e secas" (cold and
dry): gray, flat, lifeless. Lifting shadows and pulling highlights hard is what
makes a photo look flat; add contrast back whenever you do it.

## Presets

| Preset | Light | What it does |
|---|---|---|
| `nenhum` | any | Nothing. Base for a photo that needs only `adjust`, a crop, or an sRGB conversion. |
| `neutro` | good, even light | The base look, lighter: contrast, deep blacks, vibrance, a little warmth. |
| `sol-forte` | midday sun, hard shadows under caps, white sky | Moderate highlight pull and shadow lift with strong contrast, vibrance and golden warmth. The workhorse for morning races in Brazil. |
| `sombra` | runners in shade, cold blue cast | Warms (temp and warmth), adds contrast and vibrance so shade does not look dead. |
| `nublado` | overcast, flat | The most contrast, clarity and vibrance. Brings back the punch overcast takes away. |
| `contraluz` | sun behind the runner, dark face, bright background | Big shadow lift and highlight pull, with some contrast kept. Usually also `exposure` +0.3 to +0.7. |
| `golden` | sunrise or late-afternoon warm light | Protects the warm mood: does not neutralize WB, gentle highlight pull. Drop the suggested `temp` from `adjust`. |
| `baixa-luz` | high ISO, dusk, night | Noise reduction first, softer sharpening, mild contrast. |
| `pb-impacto` | as an extra, never the only version | High-contrast black and white for emotional moments (finish line, effort, celebration). Sells far less than color; offer sparingly. |

## Sliders

`exposure` in stops (-1.5..1.5). `temp` + warmer, `tint` + magenta / - green
(100 = half a stop on the red and blue channels). `contrast`, `highlights`,
`shadows`, `whites`, `blacks` -100..100 like Lightroom (negative highlights
recover, positive shadows open). `clarity` 0..50 is local contrast; keep it
under 25 on faces. `vibrance` boosts muted colors and protects skin;
`saturation` boosts everything (prefer vibrance). `blues` -100..30 changes
the saturation of blue and violet hues only (Lightroom's HSL blue slider):
the tool for blue asphalt, leaving skin, foliage and magenta shirts alone; it
skips bright pixels, so the sky stays blue. `warmth` 0..60 is a color grade:
a golden tint in the light and on sunlit skin while shadows stay neutral
(Lightroom's Color Grading highlights). 20..30 is the sweet spot; over 40
skin turns orange.
`denoise` 0..100, `sharpen` 0..100, `vignette` -50..20 (negative darkens
corners; -10 to -15 at most, it should not be noticed). `bg_blur` 0..30 fakes
a shallow depth of field, always subtle, see below.

## Recipes for common problems

- **Looks cold or dry**: raise `warmth` (+10) and `vibrance` (+10), add
  `contrast` and lower `blacks`. Do not just raise `temp`: it turns the white
  lines and the sky yellow before the skin looks warm.
- **Purple or blue asphalt** (sky-lit road, camera AWB): a gentle warm and
  green shift (`temp` +20..+40, `tint` -15..-25) plus `blues` -50..-85. Do not
  neutralize the road with white balance alone: it reads much bluer than the
  rest of the scene, and a full correction turns skin and trees yellow. The
  analyzer suggests all three from the road. Judge on skin and on the road
  paint: white lines should look white, not yellow, and the sky still blue.
  **Runners in navy or dark blue** lose some of that color too (the tool
  cannot tell dark blue fabric from blue asphalt; bright royal blue is
  spared). When the runner's clothing is navy, halve `blues` for that photo:
  a runner who does not recognize their own shirt color will not buy.
- **Green cast under trees** (light filtered by leaves, parks): `tint`
  +10..+25. Check skin, which turns sickly first.
- **Blown white sky**: leave it. Neither JPEG nor the script can bring back
  detail; the script keeps it white. Crop some of it away if it dominates.
- **Hard shadows on faces under caps**: `sol-forte`, then `shadows` up to +60.
  Past that the face goes flat and gray; better reject than mud.
- **Backlit face**: `contraluz` plus exposure. If the face is still dark at
  +1 EV total, reject; it will be noisy and flat.
- **Slight motion blur**: no edit fixes it. Sharpening makes it worse. Reject
  unless it is the only frame of that runner and the face is acceptable at
  web size.
- **Crooked horizon**: `rotate` until verticals (lamp posts, buildings) are
  vertical; on a road the center line is a good guide. Below 0.5 degrees, leave it.
- **Noise (ISO 1600+)**: `denoise` 20..50. More smears skin and bib text.

## Background blur

Runners love a blurred background, and the f/4.5-6.3 kit zoom cannot give one,
so `bg_blur` fakes it: a person-segmentation model (rembg, `u2net_human_seg`)
finds every person, and the rest is blurred more the farther it sits above the
runners' feet, so the road they stand on stays sharp the way a real lens would
keep it. Needs `pip install rembg onnxruntime` (a 170 MB model downloads on
first use) and adds about 5 s per photo.

Use it when:

- the people are **running** (a running stride: knees driven up, arms bent,
  one foot off the ground). Walkers stay as they are: on them the effect
  reads as a gimmick, and it is mostly runners who ask for it;
- one to three runners are clearly separated from a background of scenery
  (trees, buildings, parked cars, tents), and
- the runners are big in the frame (half the height or more).

Do not use it when:

- **other runners fill the background.** They are customers too: the platform
  finds photos by face, and a blurred face does not sell. The model keeps every
  person it detects sharp, which on a crowded frame looks odd;
- the runner is small, partly hidden or overlapping others (masks fail on
  tangled limbs and the error shows);
- the photo is already soft: a blurred background next to a soft runner looks fake.

**Always subtle: `bg_blur` 15..25, hard-capped at 30.** The goal is to calm a
busy background, not to announce an effect. 45 was judged too strong on real
photos, and anything that reads as a phone's portrait mode is a failure. Be
critical: when in doubt, use less or none. A photo that only looks good with
strong blur is not a candidate. Always check one at 100% with `zoom` around the head and
shoulders: a ring of sharp background or a cut-off ponytail means lower it or
leave it off. Do not add it to a whole group blindly; decide per photo.

## Cropping

- Keep the original 2:3 or 3:2 shape unless there is a reason; platforms show
  thumbnails in a grid.
- Do not cut through joints (ankles, knees, wrists, elbows). Either the full
  body with a little ground under the feet, or a cut mid-thigh or at the waist.
- Leave room in the direction the runner is moving or looking.
- The face and the bib must stay in. They are how the runner finds the photo.
- Crop out distractions at the edges (cones, a half-cut stranger, a big empty
  sky), not the context of the race.
- Do not crop below about half of the original frame: a 24 MP file cropped to
  40% is still plenty for web and prints, but further crops show the kit
  lens's softness.

## What not to do

- No skin smoothing, slimming or face edits. It is someone's real moment.
- No heavy presets, teal-and-orange looks or faded blacks: the runner wants to
  see themselves, not a filter.
- No gray, flat "safe" edits either: a photo that looks dull next to the
  others on the platform does not get clicked.
- No watermark: the platform adds its own.
- Do not strip EXIF: capture time helps platforms and buyers find photos.
