# AirCanvas — Gesture Mapping Table

This document is the authoritative interaction vocabulary. Defaults are also encoded in `aircanvas/config.py` and can be changed from **Mapping** in either interface.

---

## 1. Static pose vocabulary

MediaPipe provides 21 landmarks. AirCanvas computes finger extension from joint angles (PIP angle ≥ 148°, tip farther from the wrist than the PIP) and a pinch ratio from `distance(thumb tip, index tip) / palm_scale`.

| Pose | Visual description | Detection rule (summary) | Typical meaning |
| --- | --- | --- | --- |
| **Point** | Index extended, middle/ring/pinky curled | Index extended; other three not extended; thumb–index gap above pinch threshold | Draw / annotate / position the air cursor |
| **Pinch** | Thumb and index tips touch | `pinch_ratio < 0.28 + 0.14 × sensitivity`, index extended | Left click; hold to drag; pinch a marker to remove |
| **Two fingers** | Index + middle extended, ring/pinky curled | Index and middle extended; ring/pinky not | Right-click hold; page swipe |
| **Open palm** | Four or five fingers extended | At least four extended including index, middle and ring | Navigation arming / rest / cancel |
| **Fist** | Closed hand, no extended fingers | Extended count ≤ 1 and not a pinch | End a stroke / release intent |
| **Three fingers** | Index + middle + ring extended | Index/middle/ring extended; pinky not | Reserved / custom mapping |

Classification priority is **pinch → open palm → three → two fingers → point → fist**. Requiring an extended index for pinch prevents a closed fist with the thumb across the palm from becoming a click.

### Temporal stabilisation

- Default `stability_frames = 5`.
- A pose becomes stable only when a majority (≥ 3/5) of the recent frames agree.
- `held_s` reports how long the stable pose has persisted.
- A missing hand resets the stable pose after 180 ms, preventing a ghost hold.
- The stabiliser is shared; it is not reimplemented in the web client.

---

## 2. Contextual mapping table

### Screen mode

| Active tool | Stable gesture | Context / extra condition | Action | Feedback |
| --- | --- | --- | --- | --- |
| **Draw** | Point | Stable; stroke starts after stabilisation | Begin / continue a freehand stroke | Coral halo, finger cursor, live path |
| Draw | any other pose / hand lost | Stroke active | End stroke; optional smart-circle check | Corrected stroke event + toast |
| **Navigate** | Open palm | Hold 280 ms, then move > `0.115 / sensitivity` in one axis | Swipe up → scroll up; down → scroll down; left → Back; right → Forward | Compass progress ring, armed state, toast |
| Navigate | Two fingers | Same hold; horizontal dominant movement | Swipe left → previous page; right → next page | Page label + toast |
| Navigate | Any non-nav pose | — | Disarm; anchor resets | Hint returns to arming instruction |
| **Mouse** | Pinch | Stable click pose; 180 ms debounce | Left button down; release when no longer pinched | Cursor changes, click ripple |
| Mouse | Pinch + movement | While held | Drag | Pressed cursor, ripple |
| Mouse | Two fingers | Held 420 ms | Right-click once | Blue ripple, partial-two-finger cursor |
| Mouse | Any pose | — | Cursor follows index pointer | Virtual or OS cursor |
| Draw / Navigate / Mouse | Fist / open palm / no hand | — | Ends any active mouse press; no stuck button | Release event |

**Navigation action mapping:** the semantic actions are `scroll_up`, `scroll_down`, `back`, `forward`, `page_prev`, `page_next`. The desktop native bridge maps these to mouse-wheel/Alt+Left/Alt+Right/PageUp/PageDown when *System navigation* is enabled. The web interface cannot send OS shortcuts; it shows the gesture feedback and documents the limitation.

**Mouse mapping:** desktop *Control OS mouse* is off by default and prompts for confirmation. The web interface always provides a virtual cursor and click ripples; it cannot move the OS cursor.

### Mirror mode

| Active tool | Stable gesture | Context / extra condition | Action | Feedback |
| --- | --- | --- | --- | --- |
| **Annotate** | Point | Stable | Draw on the video surface | Strokes aligned to the displayed frame |
| Annotate | Pinch | — | Remove a marker under the fingertip (if any) | Marker disappears; toast |
| **Track** | Point | Draw a loop around an object, close it and hold 260 ms | Acquire object; initialise CSRT | Mint loop trace, progress ring, “Object locked” |
| Track | Point | Loop too small/open | Reject with hint | Amber hint; no marker |
| Track | Pinch | Marker under pointer | Remove marker | Row/marker removal |
| Track | any | Marker lost after occlusion | Attempt recovery for 2.4 s | Amber “occluded / searching” state |
| Track | any | Marker repeatedly at frame edge | Confirm out of view; stop | “Left camera view” toast |
| Track | any | Marker recovered | Resume tracking | Mint state + “re-acquired” toast |

Manual marker removal is also available in the **Tracked objects** list. Removing the last marker is not destructive to the drawing.

---

## 3. Deliberate movement and error prevention

Navigation is the gesture most vulnerable to accidental activation, so it uses five independent guards:

1. The **Navigate tool** must be active (or the gesture role must be mapped and used in that tool).
2. The open palm must be **stable** for several frames.
3. The pose must be **held** for `nav_hold_ms` (default 280 ms).
4. The anchor continuously follows the hand while arming, so ordinary repositioning does not count as a swipe. Movement after arming must exceed the displacement threshold.
5. The swipe fires **once**, then requires the pose to be released and the cooldown (default 1 s) to expire.

A common implementation mistake is to use a single-frame velocity threshold; this would fire on hand jitter and natural hand repositioning. AirCanvas deliberately separates “arming” from “swiping”.

For drawing, the stabiliser plus the requirement that the pointer is moving (not just a single point) reduces accidental dots. A single-point stroke is discarded with reason `single point`.

---

## 4. Smart circle recognition

| Parameter | Default | Meaning |
| --- | --- | --- |
| Minimum points | 12 | Avoids trying to fit a tiny dot |
| Minimum path length | 0.14 normalised units | Rejects short ticks |
| Closure | best trailing-half distance ≤ 0.24 × bbox diagonal | Accepts natural overshoot |
| Angular coverage | ≥ 72% of 12 bins | Requires most of a loop |
| Circularity | ≥ 0.48 | Tolerant of hand wobble |
| Aspect ratio | 0.55–1.9 | Supports wide stages and 16:9 video |
| Fit confidence | ≥ 0.54 | Rejects ambiguous loops |
| Output | 96-point closed circle | Committed as `kind="circle"`, `corrected=true` |

The renderer draws corrected strokes as true physical circles even when the canvas is not square. Turn **Smart shapes** off in the toolbar/inspector to preserve every freehand wobble. The option applies to new strokes; existing committed strokes are preserved and undoable.

---

## 5. Customisation

Each role can be assigned one of the static poses (except “none”/“unknown”):

| Role | Default | Config key | UI location |
| --- | --- | --- | --- |
| Draw / annotate | Point | `gesture.draw_pose` | Mapping grid |
| Left click | Pinch | `gesture.click_pose` | Mapping grid |
| Right click | Two fingers | `gesture.right_click_pose` | Mapping grid |
| Navigation arm | Open palm | `gesture.nav_pose` | Mapping grid |
| Page swipe | Two fingers | `gesture.page_pose` | Mapping grid |

Other controls:

| Setting | Default | Range | Effect |
| --- | --- | --- | --- |
| Pinch sensitivity | 1.00 | 55–180% | Larger tolerates a wider thumb–index gap |
| Pointer smoothing | 0.62 | 0–95% | Higher = calmer but more lag (One Euro filter cutoff) |
| Navigation hold | 280 ms | 120–900 ms | Longer = more deliberate arming |
| Pose stability | 5 frames | 3–11 | Larger = fewer false positives, more latency |
| Right-click hold | 420 ms | 200–1500 ms | Longer = more deliberate right click |
| Dominant hand | Auto | Auto / Left / Right | Filters MediaPipe candidates |
| Left-handed layout | Off | On/Off | Moves the gesture inspector to the left and the tool rail to the right (web and desktop); handedness itself never inverts drawing coordinates |
| Mirror camera | On | On/Off | Selfie view; capture/display share the same origin |
| Show landmarks | On | On/Off | Skeleton overlay only; recognition is unaffected |

All settings are validated and persisted by `AppConfig` (desktop profile JSON; server-side per web session, reset on a new browser session).

---

## 6. Keyboard and mouse alternatives

Every primary action has a non-gesture path:

- Draw/annotate with the mouse by choosing the tool and drawing directly on the stage.
- Mode/tool shortcuts (`1`, `2`, `D`, `N`, `M`, `A`, `T`).
- Undo/redo (`Ctrl+Z`, `Ctrl+Shift+Z`/`Ctrl+Y`) and export (`Ctrl+S`).
- Tracking markers can be removed with an explicit × button; clear-all uses a button.
- Navigation actions are available as UI state and desktop OS shortcuts; no gesture is required to open/use the app.
- Camera errors have Retry and Simulated feed fallbacks.
- Onboarding/help is accessible with `F1` and the help button.

---

## 7. Known gesture limitations

- Handedness labels can be ambiguous in occluded/edge frames; “Auto” ranks by confidence/centrality and falls back to the best candidate.
- A mitten, glove or very dim lighting can reduce landmark quality.
- A physical circle drawn on a 16:9 camera is a normalised ellipse; recognition tolerates this, and the corrected result is rendered as a circle.
- Pinch is defined by thumb–index proximity plus index extension. A user who pinches with a curled index may prefer remapping or increasing sensitivity.
- Two-finger right-click and two-finger page swipe share a pose; they are disambiguated by the **active tool** (mouse vs navigate), not by appearance.
- Selection is deliberately two-phase (loop + hold) and can feel slower than a single pinch; this is the main trade-off for accidental activation resistance.
