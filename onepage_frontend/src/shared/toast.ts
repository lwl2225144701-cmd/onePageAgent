export function toast(message: string) {
  window.dispatchEvent(new CustomEvent("onepage:toast", { detail: message }));
}
