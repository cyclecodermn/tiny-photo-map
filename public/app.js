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
  const noDemoCoordinatesText = "No demonstration coordinates for this photo";
  const regionalZoom = 10;
  const localZoom = 14;
  const maps = {
    regional: {
      elementId: "regionalMap",
      fallback: document.querySelector('[data-map-fallback="regional"]'),
      instance: null,
      markers: new Map(),
      zoom: regionalZoom
    },
    local: {
      elementId: "localMap",
      fallback: document.querySelector('[data-map-fallback="local"]'),
      instance: null,
      markers: new Map(),
      zoom: localZoom
    }
  };

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

  function showMapFallback(mapState, message) {
    if (!mapState.fallback) {
      return;
    }

    mapState.fallback.textContent = message;
    mapState.fallback.hidden = false;
  }

  function createMarkerIcon(isSelected) {
    return L.divIcon({
      className: `photo-map-marker${isSelected ? " is-selected" : ""}`,
      iconSize: isSelected ? [22, 22] : [16, 16],
      iconAnchor: isSelected ? [11, 11] : [8, 8]
    });
  }

  function updateMapMarkerState() {
    const photo = photos[selectedIndex];

    Object.values(maps).forEach((mapState) => {
      if (!mapState.instance) {
        return;
      }

      mapState.markers.forEach((marker, photoId) => {
        const isSelected = photoId === photo.id;
        marker.setIcon(createMarkerIcon(isSelected));

        if (isSelected) {
          marker.openPopup();
        } else {
          marker.closePopup();
        }
      });
    });
  }

  function updateMapViews(photo) {
    if (!hasCoordinates(photo)) {
      return;
    }

    const latLng = [photo.lat, photo.lon];

    Object.values(maps).forEach((mapState) => {
      if (!mapState.instance) {
        return;
      }

      mapState.instance.setView(latLng, mapState.zoom);
      mapState.instance.invalidateSize();
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
    updateMapViews(photo);
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

  function addTileLayer(mapState) {
    const tiles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    });

    tiles.on("tileerror", () => {
      showMapFallback(mapState, "Map tiles could not load. The gallery and selected photo details remain available.");
    });

    tiles.addTo(mapState.instance);
  }

  function createMarkerPopup(photo) {
    const wrapper = document.createElement("div");
    const location = document.createElement("strong");
    const caption = document.createElement("span");

    location.textContent = photo.demoLocation;
    caption.textContent = photo.caption;
    wrapper.append(location, document.createElement("br"), caption);

    return wrapper;
  }

  function buildMapMarkers(mapState) {
    photos.forEach((photo, index) => {
      if (!hasCoordinates(photo)) {
        return;
      }

      const marker = L.marker([photo.lat, photo.lon], {
        alt: formatDemoLocation(photo),
        keyboard: true,
        riseOnHover: true,
        title: `${formatDemoLocation(photo)} - ${photo.demoLocationNote}`,
        icon: createMarkerIcon(false)
      });

      marker.bindPopup(createMarkerPopup(photo));
      marker.on("click", () => selectPhoto(index));
      marker.addTo(mapState.instance);
      mapState.markers.set(photo.id, marker);
    });
  }

  function initializeMaps() {
    if (!window.L) {
      Object.values(maps).forEach((mapState) => {
        showMapFallback(mapState, "Map library could not load. The gallery and selected photo details remain available.");
      });
      return;
    }

    const firstMappedPhoto = photos.find(hasCoordinates);

    if (!firstMappedPhoto) {
      return;
    }

    Object.values(maps).forEach((mapState) => {
      mapState.instance = L.map(mapState.elementId, {
        scrollWheelZoom: false
      }).setView([firstMappedPhoto.lat, firstMappedPhoto.lon], mapState.zoom);

      addTileLayer(mapState);
      buildMapMarkers(mapState);
      setTimeout(() => mapState.instance.invalidateSize(), 0);
    });
  }

  if (!photos.length) {
    photoCaption.textContent = "No photos found";
    return;
  }

  buildThumbnails();
  initializeMaps();
  previousPhoto.addEventListener("click", () => selectPhoto(selectedIndex - 1));
  nextPhoto.addEventListener("click", () => selectPhoto(selectedIndex + 1));
  selectPhoto(0);
})();
