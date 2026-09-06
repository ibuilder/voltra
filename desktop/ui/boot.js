if (new URLSearchParams(window.location.search).has("preview")) {
  await import("./preview-mock.js");
}
await import("./app.js");
