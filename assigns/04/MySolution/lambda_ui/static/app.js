"use strict";
// Browser half of the View. It renders the view-model sent by the server and
// forwards user interactions to the controller endpoints. It contains no
// language analysis and does not know how interpreters or compilers run.

const $ = (id) => document.getElementById(id);
const editor = $("editor");
const fileInput = $("file-input");

let vm = null;            // latest view-model from the server
let lastEpoch = null;     // editor_epoch the textarea was last synchronised to
let clientBusy = false;   // a request is in flight
let draftTimer = null;

async function call(method, url, body) {
  const opts = { method, headers: {} };
  if (body instanceof FormData) {
    opts.body = body;
  } else if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  vm = await res.json();
  render();
  return vm;
}

function localDirty() {
  return vm !== null && editor.value !== vm.applied_text;
}

function render() {
  if (vm.editor_epoch !== lastEpoch) {      // load/manual/discard replaced the text
    editor.value = vm.editor_text;
    lastEpoch = vm.editor_epoch;
  }
  const busy = clientBusy || vm.busy !== null;
  const dirty = localDirty();
  $("source-label").textContent = "Source: " + vm.source_label;
  editor.readOnly = busy;

  for (const id of ["load-file", "load-manual", "load-factorial", "load-fibonacci"]) {
    $(id).disabled = busy || dirty;
  }
  $("apply").disabled = busy || !dirty;
  $("discard").disabled = busy || !dirty;

  const actions = $("actions");
  actions.replaceChildren();
  for (const a of vm.actions) {
    const b = document.createElement("button");
    b.type = "button";
    b.id = "action-" + a.id;
    b.textContent = a.label;
    b.disabled = busy || dirty || !a.enabled;
    if (!a.enabled && a.reason) b.title = a.reason;
    b.addEventListener("click", () => runAction(a.id));
    actions.appendChild(b);
  }
  const exec = vm.actions.find((a) => a.id === "execute");
  $("execute-help").textContent =
    exec && !exec.enabled ? "Execute is disabled: " + vm.execute_help : "";

  $("status").textContent = busy && vm.busy === null
    ? "Busy: working…" : vm.status;

  const notice = $("notice");
  if (vm.notice) {
    notice.hidden = false;
    notice.textContent = (vm.notice.ok ? "OK: " : "Error: ") + vm.notice.message;
    notice.classList.toggle("error", !vm.notice.ok);
  }

  const results = $("results");
  results.replaceChildren();
  $("no-results").hidden = vm.results.length > 0;
  for (const r of vm.results) {
    const art = document.createElement("article");
    if (r.outcome !== "success" && r.outcome !== "not_implemented") art.classList.add("bad");
    const h = document.createElement("h3");
    h.textContent = r.title;                 // textContent: never parsed as HTML
    const pre = document.createElement("pre");
    pre.textContent = r.message;
    art.append(h, pre);
    results.appendChild(art);
  }
}

async function flushDraft() {
  if (draftTimer !== null) {
    clearTimeout(draftTimer);
    draftTimer = null;
    await call("PUT", "/api/draft", { text: editor.value });
  }
}

editor.addEventListener("input", () => {
  render();                                   // update button states at once
  clearTimeout(draftTimer);
  draftTimer = setTimeout(async () => {
    draftTimer = null;
    await call("PUT", "/api/draft", { text: editor.value });
  }, 200);
});

async function guarded(fn) {
  clientBusy = true;
  if (vm) render();
  try {
    await fn();
  } catch (err) {
    const message = "could not reach the local server (" + err.message +
      "). Your source is still in the editor; try again.";
    if (vm) {
      vm.notice = { ok: false, message };   // render() shows it like any other notice
    } else {
      const notice = $("notice");
      notice.hidden = false;
      notice.classList.add("error");
      notice.textContent = "Error: " + message;
    }
  } finally {
    clientBusy = false;
    if (vm) render();
  }
}

function runAction(id) {
  return guarded(async () => { await flushDraft(); await call("POST", "/api/action/" + id); });
}

$("apply").addEventListener("click", () => guarded(async () => {
  clearTimeout(draftTimer); draftTimer = null;
  await call("POST", "/api/apply", { text: editor.value });
}));
$("discard").addEventListener("click", () => guarded(async () => {
  clearTimeout(draftTimer); draftTimer = null;
  await call("POST", "/api/discard");
}));
$("load-manual").addEventListener("click", () => guarded(() => call("POST", "/api/load/manual")));
for (const id of ["load-factorial", "load-fibonacci"]) {
  $(id).addEventListener("click", () =>
    guarded(() => call("POST", "/api/load/canned", { key: $(id).dataset.key })));
}
$("load-file").addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file, file.name);
  fileInput.value = "";                      // allow choosing the same file again
  guarded(() => call("POST", "/api/load/file", form));
});

guarded(() => call("GET", "/api/state"));
