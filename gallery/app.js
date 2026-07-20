(function () {
  const photos = window.tinyPhotoMapPhotos || [];
  let selectedIndex = 0;

  const thumbnailList = document.getElementById("thumbnailList");
  const mainPhoto = document.getElementById("mainPhoto");
  const photoCaption = document.getElementById("photoCaption");
  const photoDate = document.getElementById("photoDate");
  const previousPhoto = document.getElementById("previousPhoto");
  const nextPhoto = document.getElementById("nextPhoto");
  const regionalCoordinates = document.getElementById("regionalCoordinates");
  const localCoordinates = document.getElementById("localCoordinates");
  const regionalMarker = document.getElementById("regionalMarker");
  const localMarker = document.getElementById("localMarker");

  function formatCoordinates(photo) {
    return `${photo.lat.toFixed(3)}, ${photo.lon.toFixed(3)}`;
  }

  function moveMarker(marker, position) {
    marker.style.left = `${position.x}%`;
    marker.style.top = `${position.y}%`;
  }

  function updateMarker(marker, position, photo) {
    moveMarker(marker, position);
    marker.dataset.photoId = photo.id;
    marker.setAttribute("title", `${photo.caption} (${formatCoordinates(photo)})`);
  }

  function updateSelectedThumbnail() {
    document.querySelectorAll(".thumbnail-button").forEach((button, buttonIndex) => {
      const isSelected = buttonIndex === selectedIndex;
      button.classList.toggle("is-selected", isSelected);
      button.setAttribute("aria-current", isSelected ? "true" : "false");
      button.setAttribute("aria-pressed", isSelected ? "true" : "false");
    });
  }

  function selectPhoto(index) {
    selectedIndex = (index + photos.length) % photos.length;
    const photo = photos[selectedIndex];

    mainPhoto.src = photo.image;
    mainPhoto.alt = photo.alt;
    photoCaption.textContent = photo.caption;
    photoDate.textContent = photo.date;
    regionalCoordinates.textContent = formatCoordinates(photo);
    localCoordinates.textContent = formatCoordinates(photo);
    updateMarker(regionalMarker, photo.regionalPosition, photo);
    updateMarker(localMarker, photo.localPosition, photo);
    updateSelectedThumbnail();
  }

  function buildThumbnails() {
    photos.forEach((photo, index) => {
      const button = document.createElement("button");
      button.className = "thumbnail-button";
      button.type = "button";
      button.setAttribute("aria-label", photo.caption);
      button.setAttribute("aria-pressed", "false");
      button.dataset.photoId = photo.id;

      const image = document.createElement("img");
      image.src = photo.image;
      image.alt = "";

      button.appendChild(image);
      button.addEventListener("click", () => selectPhoto(index));
      thumbnailList.appendChild(button);
    });
  }

  if (!photos.length) {
    photoCaption.textContent = "No photos found";
    return;
  }

  buildThumbnails();
  previousPhoto.addEventListener("click", () => selectPhoto(selectedIndex - 1));
  nextPhoto.addEventListener("click", () => selectPhoto(selectedIndex + 1));
  selectPhoto(0);
})();
