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
