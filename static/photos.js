(function () {
  "use strict";
  var lightbox = document.getElementById("lightbox");
  var img = document.getElementById("lightbox-img");
  var closeBtn = document.getElementById("lightbox-close");
  if (!lightbox) return;

  function open(src, caption) {
    img.src = src;
    img.alt = caption || "";
    lightbox.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function close() {
    lightbox.hidden = true;
    img.src = "";
    document.body.style.overflow = "";
  }

  document.querySelectorAll(".photo-thumb").forEach(function (btn) {
    btn.addEventListener("click", function () {
      open(btn.dataset.full, btn.dataset.caption);
    });
  });

  closeBtn.addEventListener("click", close);
  lightbox.addEventListener("click", function (e) {
    if (e.target === lightbox) close();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !lightbox.hidden) close();
  });
})();