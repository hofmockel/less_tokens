document.addEventListener("keydown", event => {
  if (!document.body.classList.contains("presentation-page")) return;
  const slides = Array.from(document.querySelectorAll(".slide"));
  const current = Math.max(0, slides.findIndex(slide => {
    const box = slide.getBoundingClientRect();
    return box.top <= window.innerHeight * 0.4 && box.bottom > window.innerHeight * 0.4;
  }));
  let next = current;
  if (event.key === "ArrowRight" || event.key === "PageDown" || event.key === " ") next = Math.min(slides.length - 1, current + 1);
  if (event.key === "ArrowLeft" || event.key === "PageUp") next = Math.max(0, current - 1);
  if (next !== current) {
    event.preventDefault();
    slides[next].scrollIntoView({block: "start"});
    history.replaceState(null, "", "#" + slides[next].id);
  }
});

const workload = document.querySelector("#workload");
if (workload) {
  const before = document.querySelector("[data-before-value]");
  const after = document.querySelector("[data-after-value]");
  const output = document.querySelector("[data-workload-output]");
  const reduction = document.querySelector("[data-reduction-value]");
  const updateWorkload = () => {
    const input = Number(workload.value);
    const relevant = Math.max(4, Math.round(input / 3));
    before.textContent = `${input}k`;
    after.textContent = `${relevant}k`;
    output.textContent = `${input}k`;
    reduction.textContent = `${Math.round((1 - relevant / input) * 100)}%`;
  };
  workload.addEventListener("input", updateWorkload);
  updateWorkload();
}

document.querySelectorAll("[data-copy-command]").forEach(button => {
  button.addEventListener("click", async () => {
    const command = button.dataset.copyCommand;
    try {
      await navigator.clipboard.writeText(command);
      button.textContent = "Copied";
      window.setTimeout(() => { button.textContent = "Copy"; }, 1400);
    } catch (_error) {
      button.textContent = "Select command";
    }
  });
});
