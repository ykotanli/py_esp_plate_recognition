let lastImageUrl = ""; // Başlangıçta herhangi bir resim yok

// 0.5 saniyede bir sunucudan en son resmi alıyoruz
setInterval(async function () {
  const response = await fetch("/son-resim"); // En son resmi alacak endpoint
  const data = await response.json();
  if (data.last_image_url !== lastImageUrl) {
    lastImageUrl = data.last_image_url; // En son resmi güncelliyoruz
    const imgElement = document.getElementById("plate-image");
    imgElement.src = lastImageUrl; // Resmi URL ile değiştiriyoruz
    imgElement.style.display = "block"; // Resmi görünür yapıyoruz
  }
}, 500); // 0.5 saniyede bir sunucudan en son resmi alıyoruz

// İzinli plaka ekleme
document
  .getElementById("plaka-add-form")
  .addEventListener("submit", async function (event) {
    event.preventDefault();
    const newPlaka = document.getElementById("new-plaka").value;
    const response = await fetch("/izinli-plaka-ekle", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ plaka: newPlaka }),
    });
    const result = await response.json();
    if (result.success) {
      alert("Plaka eklendi!");
      updatePlakalar(result.izinli_plakalar);
    } else {
      alert(result.message);
    }
  });

// İzinli plakaları güncelleme
function updatePlakalar(plakalar) {
  const list = document.getElementById("izinli-plakalar");
  list.innerHTML = "";
  plakalar.forEach((plaka) => {
    const li = document.createElement("li");
    li.setAttribute("data-plaka", plaka);
    li.innerHTML = `<i class='fa-solid fa-circle-check' style='color: #4caf50;'></i> ${plaka}
      <button class='btn btn-red btn-delete-plaka' title='Sil' style='margin-left:auto; padding: 6px 10px; font-size: 1rem;'>
        <i class='fa-solid fa-trash'></i>
      </button>`;
    list.appendChild(li);
  });
  // Silme butonlarına event ekle
  document.querySelectorAll(".btn-delete-plaka").forEach((btn) => {
    btn.addEventListener("click", async function (e) {
      e.preventDefault();
      const plaka = this.closest("li").getAttribute("data-plaka");
      if (confirm(`${plaka} plakası silinsin mi?`)) {
        const response = await fetch("/izinli-plaka-sil", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plaka }),
        });
        const result = await response.json();
        if (result.success) {
          updatePlakalar(result.izinli_plakalar);
        } else {
          alert(result.message);
        }
      }
    });
  });
}

// Sayfa ilk yüklendiğinde izinli plakaları sunucudan çek
window.addEventListener("DOMContentLoaded", async () => {
  const response = await fetch("/izinli-plakalar");
  const data = await response.json();
  updatePlakalar(data.izinli_plakalar);
});

// Logları güncelleme fonksiyonu
async function updateLog() {
  const response = await fetch("/plaka-log");
  const data = await response.json();
  const logList = document.getElementById("plaka-log-list");
  logList.innerHTML = "";
  // En yeni log en üstte olacak şekilde tersten sırala
  data.logs
    .slice()
    .reverse()
    .forEach((log) => {
      // Log formatı: 2025-06-12 03:37:25 - 27AJU998 - GİRİŞ - static/kayitlar/goruntu_1749688645.jpg
      const parts = log.split(" - ");
      if (parts.length === 4) {
        const [zaman, plaka, durum, imgPath] = parts;
        const tr = document.createElement("tr");
        tr.innerHTML = `
        <td>${zaman}</td>
        <td>${plaka}</td>
        <td><span class="log-status ${
          durum === "GİRİŞ" ? "status-in" : "status-out"
        }">${durum}</span></td>
        <td>${
          imgPath
            ? `<img src='/${imgPath.replace(
                /^\//,
                ""
              )}' alt='görsel' class='log-thumb' style='cursor:pointer;'>`
            : "-"
        }</td>
      `;
        logList.appendChild(tr);
      }
    });
  // Küçük resimlere tıklama eventi ekle
  document.querySelectorAll(".log-thumb").forEach((img) => {
    img.addEventListener("click", function () {
      showImageModal(this.src);
    });
  });
}

// Sayfa yüklendiğinde ve her 2 saniyede bir logları güncelle
updateLog();
setInterval(updateLog, 2000);

// Modal fonksiyonları
document.body.insertAdjacentHTML(
  "beforeend",
  `
  <div id="img-modal" class="img-modal">
    <span class="img-modal-close">&times;</span>
    <img class="img-modal-content" id="img-modal-big">
  </div>
`
);
function showImageModal(src) {
  const modal = document.getElementById("img-modal");
  const modalImg = document.getElementById("img-modal-big");
  modal.style.display = "flex";
  modalImg.src = src;
}
document.querySelector(".img-modal-close").onclick = function () {
  document.getElementById("img-modal").style.display = "none";
};
document.getElementById("img-modal").onclick = function (e) {
  if (e.target === this) this.style.display = "none";
};
