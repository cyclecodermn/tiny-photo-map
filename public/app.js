(function () {
  let photos = [];
  let selectedIndex = 0;

  const thumbnailList = document.getElementById("thumbnailList");
  const albumTitle = document.getElementById("albumTitle");
  const albumSubtitle = document.getElementById("albumSubtitle");
  const albumDescription = document.getElementById("albumDescription");
  const mainPhoto = document.getElementById("mainPhoto");
  const photoCaption = document.getElementById("photoCaption");
  const photoDate = document.getElementById("photoDate");
  const previousPhoto = document.getElementById("previousPhoto");
  const nextPhoto = document.getElementById("nextPhoto");
  const regionalCoordinates = document.getElementById("regionalCoordinates");
  const localCoordinates = document.getElementById("localCoordinates");
  const noDemoCoordinatesText = "No demonstration coordinates for this photo";
  const assetVersion = "album-title-20260721";
  const catalogUrl = `photos.json?v=${assetVersion}`;
  const titleUrl = `title.json?v=${assetVersion}`;
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

  function safeText(value, fallback) {
    return typeof value === "string" && value.trim() ? value : fallback;
  }

  function formatCoordinates(photo) {
    return `${photo.lat.toFixed(4)}, ${photo.lon.toFixed(4)}`;
  }

  function formatDemoLocation(photo) {
    if (!hasCoordinates(photo)) {
      return noDemoCoordinatesText;
    }

    return `Location: ${safeText(photo.demoLocation, "Photo coordinates")} (${formatCoordinates(photo)})`;
  }

  function showGalleryMessage(message) {
    thumbnailList.textContent = "";
    mainPhoto.removeAttribute("src");
    mainPhoto.alt = "";
    photoCaption.textContent = message;
    photoDate.textContent = "";
    regionalCoordinates.textContent = noDemoCoordinatesText;
    localCoordinates.textContent = noDemoCoordinatesText;
    previousPhoto.disabled = true;
    nextPhoto.disabled = true;
  }

  function renderAlbumTitle(titleData) {
    if (!titleData || typeof titleData !== "object") {
      return;
    }

    albumTitle.textContent = safeText(titleData.title, "Photo album");
    albumSubtitle.textContent = safeText(titleData.subtitle, "");
    albumSubtitle.hidden = !albumSubtitle.textContent;
    albumDescription.textContent = "";

    if (Array.isArray(titleData.paragraphs)) {
      titleData.paragraphs.forEach((paragraph) => {
        if (typeof paragraph !== "string" || !paragraph.trim()) {
          return;
        }
        const element = document.createElement("p");
        element.textContent = paragraph;
        albumDescription.appendChild(element);
      });
    }
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
    if (!photo) {
      return;
    }

    Object.values(maps).forEach((mapState) => {
      if (!mapState.instance) {
        return;
      }

      mapState.markers.forEach((marker, photoId) => {
        const isSelected = photoId === photo.id;
        marker.setIcon(createMarkerIcon(isSelected));

        if (isSelected) {
          if (hasCoordinates(photo)) {
            marker.openPopup();
          }
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
    mainPhoto.alt = safeText(photo.alt, safeText(photo.caption, "Trip photo"));
    photoCaption.textContent = safeText(photo.caption, photo.image);
    photoDate.textContent = safeText(photo.date, "Date unavailable");
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
      button.setAttribute("aria-label", safeText(photo.caption, photo.image));
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

    location.textContent = safeText(photo.demoLocation, "Photo coordinates");
    caption.textContent = safeText(photo.caption, photo.image);
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
        title: `${formatDemoLocation(photo)} - ${safeText(photo.demoLocationNote, "Photo location")}`,
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
      Object.values(maps).forEach((mapState) => {
        showMapFallback(mapState, "No photo coordinates are available. The gallery remains available.");
      });
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

  function normalizePhoto(rawPhoto, index) {
    if (!rawPhoto || typeof rawPhoto !== "object" || Array.isArray(rawPhoto)) {
      return null;
    }

    const image = safeText(rawPhoto.image, "");
    if (!image) {
      return null;
    }

    const photo = {
      id: safeText(rawPhoto.id, `photo-${index + 1}`),
      image,
      caption: safeText(rawPhoto.caption, image),
      alt: safeText(rawPhoto.alt, safeText(rawPhoto.caption, "Trip photo")),
      date: safeText(rawPhoto.date, "Date unavailable")
    };

    for (const optionalField of ["demoLocation", "demoLocationNote"]) {
      if (typeof rawPhoto[optionalField] === "string") {
        photo[optionalField] = rawPhoto[optionalField];
      }
    }

    if (Number.isFinite(rawPhoto.lat) && Number.isFinite(rawPhoto.lon)) {
      photo.lat = rawPhoto.lat;
      photo.lon = rawPhoto.lon;
    }

    return photo;
  }

  function parseCatalog(catalog) {
    if (!catalog || typeof catalog !== "object" || !Array.isArray(catalog.photos)) {
      throw new Error("photos.json must contain a photos array.");
    }

    return catalog.photos.map(normalizePhoto).filter(Boolean);
  }

  async function loadCatalog() {
    const response = await fetch(catalogUrl, { cache: "no-cache" });
    if (!response.ok) {
      throw new Error(`photos.json returned HTTP ${response.status}.`);
    }

    return parseCatalog(await response.json());
  }

  async function loadAlbumTitle() {
    const response = await fetch(titleUrl, { cache: "no-cache" });
    if (!response.ok) {
      throw new Error(`title.json returned HTTP ${response.status}.`);
    }

    return response.json();
  }

  async function initializeGallery() {
    try {
      renderAlbumTitle(await loadAlbumTitle());
    } catch (error) {
      renderAlbumTitle({ title: "Photo album", subtitle: "", paragraphs: [] });
    }

    try {
      photos = await loadCatalog();
    } catch (error) {
      showGalleryMessage(`Photo catalog could not load. ${error.message}`);
      return;
    }

    if (!photos.length) {
      showGalleryMessage("No photos found in the catalog.");
      return;
    }

    buildThumbnails();
    initializeMaps();
    previousPhoto.addEventListener("click", () => selectPhoto(selectedIndex - 1));
    nextPhoto.addEventListener("click", () => selectPhoto(selectedIndex + 1));
    selectPhoto(0);
  }

  initializeGallery();
})();
