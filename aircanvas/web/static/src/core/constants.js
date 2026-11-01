'use strict';

/** Shared view constants (Vue-like `constants/` layer). */

export const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [17, 18], [18, 19], [19, 20],
  [0, 17],
];

export const GESTURE_LABELS = {
  none: 'No hand', point: 'Point', pinch: 'Pinch', peace: 'Two fingers',
  open_palm: 'Open palm', fist: 'Fist', three: 'Three fingers', unknown: 'Unknown',
};

export const GESTURE_OPTIONS = [
  ['point', 'Point'], ['pinch', 'Pinch'], ['peace', 'Two fingers'],
  ['open_palm', 'Open palm'], ['three', 'Three fingers'], ['fist', 'Fist'],
];

export const DEFAULT_CONFIG = {
  mode: 'screen', tool: 'draw', mirror_tool: 'track',
  auto_shapes: true, show_landmarks: true, mirror_camera: true,
  show_camera_pip: true, brush_color: '#ff6b57', brush_width: 5,
  hand_backend: 'mediapipe', hand_model_path: '', hand_detector_path: '', hand_device: 'auto',
  gesture: {
    smoothing: 0.55, pinch_sensitivity: 1.0, stability_frames: 5,
    nav_sensitivity: 1.0, nav_hold_ms: 280, nav_cooldown_ms: 1000,
    right_click_hold_ms: 420, cursor_smoothing: 0.62,
    dominant_hand: 'auto', left_handed: false,
    draw_pose: 'point', click_pose: 'pinch', right_click_pose: 'peace',
    nav_pose: 'open_palm', page_pose: 'peace', show_gesture_trail: true,
    selection_hold_ms: 260,
  },
};
