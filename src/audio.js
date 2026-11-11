const state = {
  audio: null,
  currentUrl: null,
  title: "",
  artist: "",
  isPlaying: false,
};

const listeners = new Set();

function notify() {
  for (const fn of listeners) fn({ ...state });
}

export function subscribeAudio(fn) {
  listeners.add(fn);
  fn({ ...state });
  return () => listeners.delete(fn);
}

export function togglePreview({ previewUrl, title, artist }) {
  if (!previewUrl) return;
  if (!state.audio) {
    state.audio = new Audio();
    state.audio.addEventListener("ended", () => {
      state.isPlaying = false;
      notify();
    });
    state.audio.addEventListener("pause", () => {
      state.isPlaying = false;
      notify();
    });
    state.audio.addEventListener("play", () => {
      state.isPlaying = true;
      notify();
    });
  }

  if (state.currentUrl === previewUrl) {
    if (state.audio.paused) {
      state.audio.play().catch(() => {});
    } else {
      state.audio.pause();
    }
    return;
  }

  state.audio.pause();
  state.currentUrl = previewUrl;
  state.title = title;
  state.artist = artist || "";
  state.audio.src = previewUrl;
  state.audio.play().catch(() => {});
  notify();
}

export function stopPreview() {
  if (state.audio) {
    state.audio.pause();
    state.audio.currentTime = 0;
  }
  state.currentUrl = null;
  state.isPlaying = false;
  notify();
}

export function getAudioState() {
  return { ...state };
}
