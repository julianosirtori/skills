---
name: race-photo-edit
description: Culls and edits running and street-race photos for sale on platforms like Foco Radical or Fotop, like a professional sports photographer. A script measures every photo (exposure, asphalt color cast, sharpness, EXIF, bursts) and builds contact sheets; the agent reviews them by eye, rejects what will not sell, picks the best of each burst, groups by light and assigns presets with per-photo corrections, crops and optional background blur. After the user approves, it writes every approved photo to an upload-ready folder (originals untouched) and gives feedback on how to shoot better. Camera JPEGs, optionally RAW. Use it whenever the user wants to edit, cull, fix or prepare race, running or sports photos for upload or sale, even without saying "edit" (e.g. "edita as fotos da corrida", "minhas fotos ficaram escuras", "quais fotos vale subir na focoradical", "aplica um preset nas fotos do parque", "as fotos ficaram azuladas").
license: MIT
compatibility: Any agent that reads SKILL.md and can view images. scripts/photo.py needs Python 3.8+ with numpy and Pillow; RAW files need rawpy, background blur needs rembg and onnxruntime (downloads a 170 MB model once). No other network access.
metadata:
  author: julianosirtori
  version: "1.0.0"
---

# Race photo edit

Cull and edit running photos the way a working event photographer would, so more
of them sell. Talk to the user in their language (usually Portuguese).

What sells on these platforms is simple: the runner finds **their own face**
(platforms search by face recognition and bib number), the photo is **sharp
on them**, the **colors look natural** and it **flatters** them. A dramatic
look, a heavy preset or a clever crop sells nothing if the runner's face is soft,
blown out or cut. Judge every photo by that.

## Rules

- **Originals are never modified.** Every approved photo, edited or kept as
  is, goes to `<folder>/editadas/` so the user can select the whole folder and
  upload it; rejects stay out. Review material goes to `<folder>/_revisao/`.
  Never point `output` at the source folder, never move or delete originals.
- **Be critical, not destructive.** Rejecting a photo means "do not upload",
  never deleting it. A photo that is already good is `keep` (copied untouched).
- **Natural beats styled.** Skin must look like skin. Slight warmth is fine,
  oversaturation, HDR halos, heavy vignettes and crushed blacks are not.
- **Consistency.** Photos from the same spot and light get the same preset and
  similar corrections; a buyer often purchases several frames together.
- **JPEG limits.** A camera JPEG is 8-bit: more than about a stop of exposure,
  big shadow lifts or strong WB shifts band and turn noisy. A photo that needs
  more than that is usually a reject, not a rescue.
- **The user decides.** Propose the plan, wait for an OK, then apply.

## Setup

```bash
python -c "import numpy, PIL" || pip install numpy pillow
pip install rawpy                # only if the folder has RAW files
pip install rembg onnxruntime    # only for background blur (bg_blur); 170 MB model on first use
```

Install the optional ones only when needed, and tell the user before
downloading the model.

`S=<this skill's folder>/scripts/photo.py`. Run `python $S presets` to see the
presets and the slider ranges.

## Workflow

### 1. Analyze

Ask for the folder if not given (one event or session per folder) and, in the
same question, anything you cannot see in the photos (event name, if a
specific runner or group matters). Then:

```bash
python "$S" analyze "<folder>"
```

It prints a summary (photo count, bursts, flag counts, scenes, slowest shutter,
ISO range) and writes to `_revisao/`: `analysis.json` (per-photo EXIF,
metrics, flags, scene and suggested adjust), `previews/`, `contato-NN.jpg`
contact sheets (16 photos each, labeled `#index file` and flags) and a draft
`plan.json` (on a re-run an existing plan is kept and the new draft goes to
`plan-draft.json`). About 0.7 s per photo on a normal laptop.

Read [references/metrics.md](references/metrics.md) once to know what each
flag and metric means and how far to trust it.

### 2. Review by eye

What sells, from platform and race-photographer guides: full-body shots with
the bib readable and **both feet off the ground**; **smiles, effort and
emotion**; waist-up portraits with a calm background; the **finish line** with
the event arch in frame; **vertical** frames (runners post them as Stories).
Mid and back-of-pack runners and walkers are reported to buy the most, so do
not reject someone for being slow or walking; reject for focus, face and
framing only.

The numbers are a first pass; your eyes decide. Look at **every contact sheet**
in order and, for each photo, decide:

- **reject**: subject out of focus or motion-blurred (check with `zoom`, see
  below), face hidden or turned away, eyes closed or an unflattering
  mid-stride grimace when a better frame of the same burst exists, subject cut
  at the joints, the runner is a tiny figure with nobody identifiable,
  duplicate frames of a burst, blown face that editing cannot bring back, or
  nothing in it anyone would buy.
- **best of burst**: frames less than 1 s apart share a `burst` number. Keep
  the one or two best (face visible, eyes open, legs in a good phase of the
  stride: both feet off the ground or the front foot just landing, bib
  readable) and reject the rest. Do not sell five near-identical frames.
- **keep**: already well exposed, natural color, straight. Uploading untouched
  is a valid answer.
- **edit**: choose the preset that matches the light (table in
  [references/editing.md](references/editing.md)), then per-photo `adjust`,
  `crop` and `rotate`.

Check focus on the face before keeping a doubtful photo or picking the best of
a burst. Find the face on the preview, estimate its position as fractions of
the frame (0,0 top-left) and:

```bash
python "$S" zoom "<folder>/IMG_1234.JPG" 0.45 0.30
```

It saves an 800 px crop at 100% to `_revisao/zoom/` and prints the path; open
it. Eyelashes, bib text and shirt texture must be crisp; doubled edges mean
motion blur, a soft face with a sharp background means missed focus.

Do not zoom on every photo. Zoom on bursts (to pick the best), on anything
flagged `soft`, and on a sample of the rest when the shutter was slow
(`slow-shutter`), since that is when limbs and faces smear.

**Panning is not a mistake.** A frame at 1/30-1/125 with the background
streaked sideways and the runner reasonably sharp is a deliberate technique,
and it gives the blurred background runners love. Judge only the face: keep it
if it reads well at half size, and never add `bg_blur` on top.

### 3. Write the plan

Edit `_revisao/plan.json`. Each image entry:

```json
{"file": "IMG_4199.JPG", "action": "edit", "preset": "sol-forte",
 "adjust": {"temp": 30, "tint": -25, "blues": -50, "bg_blur": 20},
 "crop": [0.05, 0.08, 0.95, 0.98], "rotate": -1.2, "note": "asfalto roxo; fundo de árvores desfocado"}
```

- `action`: `edit`, `keep` or `reject`. `preset` and `adjust` matter only for `edit`.
- `adjust` is **added** to the preset (keys from `presets`; values clamp to
  the ranges). The analyzer's suggestion is already there: keep it, change it
  or drop it after looking at the photo.
- `crop`: fractions `[left, top, right, bottom]` of the straightened frame,
  or `null`. `rotate`: degrees, positive turns counter-clockwise, to level a
  tilted horizon, lamp post or building.
- `bg_blur` (background blur) is never suggested by the analyzer: decide it
  per photo by eye, following the rules in
  [references/editing.md](references/editing.md#background-blur). Light
  (15..25) and on people **running**, not walking. Blurring other runners'
  faces costs their sale.
- `note`: why, in the user's language. It goes into the report.
- Top level: `output` (default `<folder>/editadas`) and `quality` (JPEG
  quality, default 90).

Group first, then tune: give a whole run of photos from the same spot the same
preset and WB, then adjust only the outliers.

### 4. Propose and confirm

Show the user a short proposal before applying:

- totals: edit / keep / reject, and how many bursts were thinned;
- groups: which photos got which preset and why (one line per group);
- rejects with the reason, grouped (`fora de foco: IMG_4188, IMG_4189...`);
- notable individual calls (strong crops, rescues, borderline rejects);
- the shooting feedback from step 6, if it is striking.

Wait for the OK or changes. Apply them to the plan.

### 5. Apply and check

```bash
python "$S" apply "<folder>/_revisao/plan.json"
```

It renders every `edit` (in parallel), copies every `keep`, removes outputs of
photos now marked `reject`, keeps EXIF (capture time matters to the platforms)
with the orientation reset, embeds sRGB, and writes `antes-depois-NN.jpg`
sheets (3 pairs each) to `_revisao/`.

Look at **every** before/after sheet. Typical misses: sky or white shirts gone
gray or tinted, skin too orange or too pink, shadows lifted into flat mud,
asphalt still purple. Fix the plan entry and re-render only those:

```bash
python "$S" apply "<folder>/_revisao/plan.json" --only IMG_4199.JPG,IMG_4201.JPG
```

### 6. Report

End with a short report in the user's language:

- where the files are (`editadas/` is ready to upload; `_revisao/` is not for upload
  and can be deleted);
- counts (edited, kept, rejected) and the main reasons for rejects;
- **how to shoot better next time**: read
  [references/shooting.md](references/shooting.md) and turn the EXIF summary
  into two or three concrete changes (shutter speed, ISO, white balance,
  position relative to the sun, framing). This is where the user gains most:
  editing rescues a little, shooting right fixes everything.

Do not upload anything or touch any account. Do not add watermarks: the
platforms apply their own.
