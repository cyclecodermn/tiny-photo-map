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
  const noDemoCoordinatesText = "No demonstration coordinates for this photo";

  function hasCoordinates(photo) {
    return Number.isFinite(photo.lat) && Number.isFinite(photo.lon);
  }

  function formatCoordinates(photo) {
    return `${photo.lat.toFixed(4)}, ${photo.lon.toFixed(4)}`;
  }

  function formatDemoLocation(photo) {
    if (!hasCoordinates(photo)) {
      return noDemoCoordinatesText;
    }

    return `Demo location: ${photo.demoLocation} (${formatCoordinates(photo)})`;
  }

  function moveMarker(marker, position) {
    marker.style.left = `${position.x}%`;
    marker.style.top = `${position.y}%`;
  }

  function updateMapMarkerState() {
    document.querySelectorAll(".map-marker").forEach((marker) => {
      const isSelected = marker.dataset.photoId === photos[selectedIndex].id;
      marker.classList.toggle("is-selected", isSelected);
      marker.setAttribute("aria-pressed", isSelected ? "true" : "false");
    });
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
    regionalCoordinates.textContent = formatDemoLocation(photo);
    localCoordinates.textContent = formatDemoLocation(photo);
    updateMapMarkerState();
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

  function buildMapMarkers(markerLayer, positionKey) {
    photos.forEach((photo, index) => {
      const position = photo[positionKey];

      if (!hasCoordinates(photo) || !position) {
        return;
      }

      const marker = document.createElement("button");
      marker.className = "map-marker";
      marker.type = "button";
      marker.dataset.photoId = photo.id;
      marker.setAttribute("aria-label", `${formatDemoLocation(photo)}. Select ${photo.caption}.`);
      marker.setAttribute("aria-pressed", "false");
      marker.setAttribute("title", `${formatDemoLocation(photo)} - ${photo.demoLocationNote}`);
      moveMarker(marker, position);
      marker.addEventListener("click", () => selectPhoto(index));
      markerLayer.appendChild(marker);
    });
  }

  if (!photos.length) {
    photoCaption.textContent = "No photos found";
    return;
  }

  buildThumbnails();
  buildMapMarkers(regionalMarker, "regionalPosition");
  buildMapMarkers(localMarker, "localPosition");
  previousPhoto.addEventListener("click", () => selectPhoto(selectedIndex - 1));
  nextPhoto.addEventListener("click", () => selectPhoto(selectedIndex + 1));
  selectPhoto(0);
})();
