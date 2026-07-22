(function () {
  let photos = [];
  let selectedIndex = 0;

  const thumbnailList = document.getElementById("thumbnailList");
  const albumTitle = document.getElementById("albumTitle");
  const albumSubtitle = document.getElementById("albumSubtitle");
  const albumDescription = document.getElementById("albumDescription");
  const mainPhoto = document.getElementById("mainPhoto");
  const photoCaption = document.getElementById("photoCaption");
  const photoCounter = document.getElementById("photoCounter");
  const previousPhoto = document.getElementById("previousPhoto");
  const nextPhoto = document.getElementById("nextPhoto");
  const galleryShell = document.getElementById("galleryShell");
  const toggleTripPanel = document.getElementById("toggleTripPanel");
  const toggleMapPanel = document.getElementById("toggleMapPanel");
  const photoFrame = document.getElementById("photoFrame");
  const openViewer = document.getElementById("openViewer");
  const viewerPreviousPhoto = document.getElementById("viewerPreviousPhoto");
  const viewerNextPhoto = document.getElementById("viewerNextPhoto");
  const zoomOutPhoto = document.getElementById("zoomOutPhoto");
  const zoomInPhoto = document.getElementById("zoomInPhoto");
  const fitPhoto = document.getElementById("fitPhoto");
  const restoreGallery = document.getElementById("restoreGallery");
  const zoomLevel = document.getElementById("zoomLevel");
  const noDemoCoordinatesText = "No demonstration coordinates for this photo";
  const assetVersion = "viewer-20260722-nav";
  const catalogUrl = `photos.json?v=${assetVersion}`;
  const titleUrl = `title.json?v=${assetVersion}`;
  const regionalZoom = 10;
  const regionalMaxFitZoom = 11;
  const localZoom = 14;
  const minViewerZoom = 1;
  const maxViewerZoom = 4;
  const viewerZoomStep = 0.5;
  let viewerZoom = minViewerZoom;
  let viewerOpen = false;
  let fallbackViewerOpen = false;
  const maps = {
    regional: {
      elementId: "regionalMap",
      fallback: document.querySelector('[data-map-fallback="regional"]'),
      instance: null,
      markers: new Map(),
      zoom: regionalZoom,
      maxFitZoom: regionalMaxFitZoom
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

  function formatDemoLocation(photo) {
    if (!hasCoordinates(photo)) {
      return noDemoCoordinatesText;
    }

    return safeText(photo.demoLocation, "Photo location");
  }

  function showGalleryMessage(message) {
    thumbnailList.textContent = "";
    mainPhoto.removeAttribute("src");
    mainPhoto.alt = "";
    photoCaption.textContent = message;
    photoCounter.textContent = "";
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
      html: isSelected
        ? '<span class="photo-map-star" aria-hidden="true"></span>'
        : '<span class="photo-map-circle" aria-hidden="true"></span>',
      iconSize: isSelected ? [24, 24] : [18, 18],
      iconAnchor: isSelected ? [12, 12] : [9, 9]
    });
  }

  function buildMarkerPopupContent(photo) {
    const popup = document.createElement("div");
    popup.className = "photo-marker-popup";

    const caption = document.createElement("p");
    caption.className = "photo-marker-popup-caption";
    caption.textContent = safeText(photo.caption, photo.image);
    popup.appendChild(caption);

    if (photo.date && photo.date !== caption.textContent) {
      const date = document.createElement("p");
      date.className = "photo-marker-popup-date";
      date.textContent = photo.date;
      popup.appendChild(date);
    }

    return popup;
  }

  function closeAllMarkerPopups() {
    Object.values(maps).forEach((mapState) => {
      mapState.markers.forEach((marker) => {
        if (marker.popup) {
          marker.popup.remove();
        }
      });
      if (mapState.instance) {
        mapState.instance.closePopup();
      }
    });
  }

  function handleDocumentClick(event) {
    if (event.target.closest(".leaflet-marker-icon") || event.target.closest(".leaflet-popup")) {
      return;
    }

    closeAllMarkerPopups();
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
        marker.setZIndexOffset(isSelected ? 1000 : 0);
      });
    });
  }

  function mappedPhotos() {
    return photos.filter(hasCoordinates);
  }

  function fitRegionalMap() {
    const mapState = maps.regional;
    if (!mapState.instance) {
      return;
    }

    const mapped = mappedPhotos();
    if (!mapped.length) {
      return;
    }

    mapState.instance.invalidateSize();

    if (mapped.length === 1) {
      mapState.instance.setView([mapped[0].lat, mapped[0].lon], mapState.maxFitZoom);
      return;
    }

    const bounds = L.latLngBounds(mapped.map((mappedPhoto) => [mappedPhoto.lat, mappedPhoto.lon]));
    mapState.instance.fitBounds(bounds, {
      padding: [28, 28],
      maxZoom: mapState.maxFitZoom
    });
  }

  function updateLocalMapView(photo) {
    if (!hasCoordinates(photo) || !maps.local.instance) {
      return;
    }

    const latLng = [photo.lat, photo.lon];

    maps.local.instance.setView(latLng, maps.local.zoom);
    maps.local.instance.invalidateSize();
  }

  function refreshMapsAfterLayoutChange() {
    Object.values(maps).forEach((mapState) => {
      if (mapState.instance) {
        mapState.instance.invalidateSize();
      }
    });
    fitRegionalMap();
    updateLocalMapView(photos[selectedIndex]);
  }

  function updateViewerZoom() {
    mainPhoto.style.setProperty("--viewer-zoom", viewerZoom);
    zoomLevel.textContent = `${viewerZoom}x`;
    zoomOutPhoto.disabled = viewerZoom <= minViewerZoom;
    zoomInPhoto.disabled = viewerZoom >= maxViewerZoom;
  }

  function fitViewerImage() {
    viewerZoom = minViewerZoom;
    updateViewerZoom();
    photoFrame.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }

  function updatePhotoCounter() {
    if (!photos.length) {
      photoCounter.textContent = "";
      return;
    }

    photoCounter.textContent = `Photo ${selectedIndex + 1} of ${photos.length}`;
  }

  function scrollSelectedThumbnailIntoView() {
    const selectedButton = thumbnailList.querySelector(".thumbnail-button.is-selected");
    if (!selectedButton) {
      return;
    }

    const padding = 16;
    const viewTop = thumbnailList.scrollTop;
    const viewBottom = viewTop + thumbnailList.clientHeight;
    const buttonTop = selectedButton.offsetTop;
    const buttonBottom = buttonTop + selectedButton.offsetHeight;

    if (buttonTop >= viewTop + padding && buttonBottom <= viewBottom - padding) {
      return;
    }

    const nextTop = Math.max(
      0,
      buttonTop - thumbnailList.clientHeight / 2 + selectedButton.offsetHeight / 2
    );

    thumbnailList.scrollTo({ top: nextTop, behavior: "smooth" });
  }

  function setViewerOpen(isOpen, usesFallback) {
    viewerOpen = isOpen;
    fallbackViewerOpen = isOpen && usesFallback;
    photoFrame.classList.toggle("is-viewer-open", isOpen);
    photoFrame.classList.toggle("is-fallback-viewer", fallbackViewerOpen);
    openViewer.setAttribute("aria-expanded", isOpen ? "true" : "false");

    if (isOpen) {
      fitViewerImage();
      photoFrame.focus();
      return;
    }

    fitViewerImage();
    setTimeout(refreshMapsAfterLayoutChange, 0);
  }

  async function openFullScreenViewer() {
    if (viewerOpen) {
      return;
    }

    if (photoFrame.requestFullscreen) {
      try {
        await photoFrame.requestFullscreen();
        setViewerOpen(true, false);
        return;
      } catch (error) {
        setViewerOpen(true, true);
        return;
      }
    }

    setViewerOpen(true, true);
  }

  async function restoreGalleryLayout() {
    if (document.fullscreenElement === photoFrame && document.exitFullscreen) {
      await document.exitFullscreen();
      return;
    }

    setViewerOpen(false, false);
  }

  function adjustViewerZoom(direction) {
    if (!viewerOpen) {
      return;
    }

    const nextZoom = viewerZoom + direction * viewerZoomStep;
    viewerZoom = Math.min(maxViewerZoom, Math.max(minViewerZoom, nextZoom));
    updateViewerZoom();
  }

  function isKeyboardEditableTarget(event) {
    const pathTarget =
      typeof event.composedPath === "function" ? event.composedPath()[0] : event.target;
    const target = pathTarget instanceof Element ? pathTarget : document.activeElement;

    if (!(target instanceof Element)) {
      return false;
    }

    return (
      target.isContentEditable ||
      target.closest("input, textarea, select, [contenteditable='true'], [contenteditable='']") !== null
    );
  }

  function handleViewerKeyboardShortcuts(event) {
    if (event.key === "Escape" && viewerOpen) {
      event.preventDefault();
      restoreGalleryLayout();
      return;
    }

    if (isKeyboardEditableTarget(event)) {
      return;
    }

    if (event.key === "ArrowLeft") {
      event.preventDefault();
      selectPhoto(selectedIndex - 1);
      return;
    }

    if (event.key === "ArrowRight") {
      event.preventDefault();
      selectPhoto(selectedIndex + 1);
      return;
    }

    if (!viewerOpen) {
      return;
    }

    if (event.key === "+" || event.key === "=") {
      event.preventDefault();
      adjustViewerZoom(1);
      return;
    }

    if (event.key === "-" || event.key === "_") {
      event.preventDefault();
      adjustViewerZoom(-1);
    }
  }

  function initializeViewerControls() {
    openViewer.setAttribute("aria-expanded", "false");
    openViewer.addEventListener("click", openFullScreenViewer);
    viewerPreviousPhoto.addEventListener("click", () => selectPhoto(selectedIndex - 1));
    viewerNextPhoto.addEventListener("click", () => selectPhoto(selectedIndex + 1));
    zoomOutPhoto.addEventListener("click", () => adjustViewerZoom(-1));
    fitPhoto.addEventListener("click", fitViewerImage);
    zoomInPhoto.addEventListener("click", () => adjustViewerZoom(1));
    restoreGallery.addEventListener("click", restoreGalleryLayout);
    document.addEventListener("fullscreenchange", () => {
      if (document.fullscreenElement === photoFrame) {
        setViewerOpen(true, false);
        return;
      }

      if (viewerOpen && !fallbackViewerOpen) {
        setViewerOpen(false, false);
      }
    });
    document.addEventListener("keydown", handleViewerKeyboardShortcuts);
    updateViewerZoom();
  }

  function setPanelCollapsed(side, isCollapsed) {
    const isLeft = side === "left";
    const className = isLeft ? "is-left-collapsed" : "is-right-collapsed";
    const button = isLeft ? toggleTripPanel : toggleMapPanel;
    const expanded = !isCollapsed;

    galleryShell.classList.toggle(className, isCollapsed);
    button.setAttribute("aria-expanded", expanded ? "true" : "false");

    if (isLeft) {
      button.innerHTML = isCollapsed ? "&rarr;" : "&larr;";
      button.setAttribute(
        "aria-label",
        isCollapsed ? "Show album and thumbnails" : "Collapse album and thumbnails"
      );
      return;
    }

    button.innerHTML = isCollapsed ? "&larr;" : "&rarr;";
    button.setAttribute("aria-label", isCollapsed ? "Show maps" : "Collapse maps");

    if (!isCollapsed) {
      setTimeout(refreshMapsAfterLayoutChange, 0);
    }
  }

  function initializePanelToggles() {
    toggleTripPanel.addEventListener("click", () => {
      setPanelCollapsed("left", !galleryShell.classList.contains("is-left-collapsed"));
    });
    toggleMapPanel.addEventListener("click", () => {
      setPanelCollapsed("right", !galleryShell.classList.contains("is-right-collapsed"));
    });
  }

  function updateSelectedThumbnail() {
    document.querySelectorAll(".thumbnail-button").forEach((button, buttonIndex) => {
      const isSelected = buttonIndex === selectedIndex;
      button.classList.toggle("is-selected", isSelected);
      if (isSelected) {
        button.setAttribute("aria-current", "true");
      } else {
        button.removeAttribute("aria-current");
      }
      button.setAttribute("aria-pressed", isSelected ? "true" : "false");
    });
  }

  function selectPhoto(index, options = {}) {
    selectedIndex = (index + photos.length) % photos.length;
    const photo = photos[selectedIndex];

    closeAllMarkerPopups();
    mainPhoto.src = photo.image;
    mainPhoto.alt = safeText(photo.alt, safeText(photo.caption, "Trip photo"));
    photoCaption.textContent = safeText(photo.caption, photo.image);
    fitViewerImage();
    updateLocalMapView(photo);
    updateMapMarkerState();
    updateSelectedThumbnail();
    updatePhotoCounter();
    scrollSelectedThumbnailIntoView();

    if (options.popup && options.mapState) {
      options.popup.openOn(options.mapState.instance);
    }
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
    const tiles = L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", {
      maxZoom: 17,
      maxNativeZoom: 17,
      attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)'
    });

    tiles.on("tileerror", () => {
      showMapFallback(mapState, "Map tiles could not load. The gallery and selected photo details remain available.");
    });

    tiles.addTo(mapState.instance);
  }

  function buildMapMarkers(mapState) {
    photos.forEach((photo, index) => {
      if (!hasCoordinates(photo)) {
        return;
      }

      const marker = L.marker([photo.lat, photo.lon], {
        alt: formatDemoLocation(photo),
        bubblingMouseEvents: false,
        keyboard: true,
        icon: createMarkerIcon(false)
      });

      marker.popup = L.popup({
        autoClose: false,
        closeButton: false,
        closeOnClick: false,
        className: "photo-marker-popup",
        maxWidth: 220,
        offset: L.point(0, -10)
      })
        .setLatLng([photo.lat, photo.lon])
        .setContent(buildMarkerPopupContent(photo));
      marker.on("click", (event) => {
        if (event.originalEvent) {
          L.DomEvent.stop(event.originalEvent);
        }
        selectPhoto(index, { mapState, popup: marker.popup });
      });
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

      mapState.instance.on("click", closeAllMarkerPopups);
      addTileLayer(mapState);
      buildMapMarkers(mapState);
      setTimeout(() => mapState.instance.invalidateSize(), 0);
    });

    fitRegionalMap();
    window.addEventListener("resize", fitRegionalMap);

    if ("ResizeObserver" in window) {
      const mapResizeObserver = new ResizeObserver(fitRegionalMap);
      mapResizeObserver.observe(document.getElementById(maps.regional.elementId));
    }
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
    initializePanelToggles();
    initializeViewerControls();
    document.addEventListener("click", handleDocumentClick);
    selectPhoto(0);
  }

  if (location.hostname === "127.0.0.1" || location.hostname === "localhost") {
    window.__tinyPhotoMapDebug = {
      handleViewerKeyboardShortcuts,
      isKeyboardEditableTarget
    };
  }

  initializeGallery();
})();
