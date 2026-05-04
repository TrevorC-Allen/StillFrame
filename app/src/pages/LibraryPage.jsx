import { useEffect, useMemo, useState } from "react";
import { AlertCircle, CheckCircle2, Film, Play, RefreshCw, Search, Star } from "lucide-react";

import { mediaUrl } from "../api/client.js";

const EMPTY_SET = new Set();
const DEFAULT_LIBRARY_QUERY = {
  search: "",
  sort: "recent",
  segment: "all",
  year: "all",
  quality: "all",
  sourceId: "all"
};
const SEGMENT_OPTIONS = [
  { value: "all", label: "All", stat: "total" },
  { value: "movie", label: "Movie", stat: "movie" },
  { value: "tv", label: "TV", stat: "tv" },
  { value: "favorites", label: "Favorites", stat: "favorites" },
  { value: "offline", label: "Offline", stat: "offline" }
];

export function LibraryPage({
  items = [],
  facets = null,
  query = DEFAULT_LIBRARY_QUERY,
  loading = false,
  sources = [],
  favoritePaths = EMPTY_SET,
  onQueryChange,
  onPlay,
  onToggleFavorite,
  onScanLibrary,
  scanning,
  scanJob,
  onRefreshMetadata,
  metadataRefreshing,
  metadataRefresh
}) {
  const [selectedPath, setSelectedPath] = useState(null);
  const normalizedQuery = useMemo(() => normalizeLibraryQuery(query), [query]);
  const facetModel = useMemo(
    () => buildFacetModel({ facets, items, sources, favoritePaths }),
    [facets, favoritePaths, items, sources]
  );
  const visibleItems = useMemo(
    () => filterAndSortItems(items, normalizedQuery, favoritePaths),
    [items, normalizedQuery, favoritePaths]
  );

  const selectedItem = visibleItems.find((item) => item.path === selectedPath) || visibleItems[0] || null;
  const emptyLibrary = items.length === 0 && facetModel.stats.total === 0 && !hasActiveLibraryQuery(normalizedQuery);
  const noMatches = visibleItems.length === 0 && !emptyLibrary;

  useEffect(() => {
    if (!selectedItem) {
      setSelectedPath(null);
      return;
    }
    if (selectedItem.path !== selectedPath) {
      setSelectedPath(selectedItem.path);
    }
  }, [selectedItem, selectedPath]);

  function updateQuery(patch) {
    onQueryChange?.(normalizeLibraryQuery({ ...normalizedQuery, ...patch }));
  }

  return (
    <section className="library-page">
      <div className="library-toolbar">
        <div className="library-heading">
          <h2>Indexed Library</h2>
          <span>{loading ? "Updating..." : `${visibleItems.length} shown`}</span>
        </div>
        <label className="library-search">
          <Search size={16} />
          <input
            type="search"
            placeholder="Search"
            value={normalizedQuery.search}
            onChange={(event) => updateQuery({ search: event.target.value })}
          />
        </label>
        <select
          className="library-sort"
          value={normalizedQuery.sort}
          onChange={(event) => updateQuery({ sort: event.target.value })}
          aria-label="Sort library"
        >
          <option value="recent">Recently Modified</option>
          <option value="title">Title</option>
          <option value="year">Year</option>
          <option value="quality">Quality</option>
        </select>
        <button className="primary-button scan-button" onClick={onScanLibrary} disabled={scanning}>
          <RefreshCw size={17} className={scanning ? "spinning" : ""} />
          <span>{scanning ? "Scanning" : "Scan Library"}</span>
        </button>
        <button className="text-button metadata-refresh-button" onClick={onRefreshMetadata} disabled={metadataRefreshing}>
          <RefreshCw size={16} className={metadataRefreshing ? "spinning" : ""} />
          <span>{metadataRefreshing ? "Refreshing" : "Refresh Metadata"}</span>
        </button>
      </div>

      <LibraryStats stats={facetModel.stats} loading={loading} />
      <LibraryFacetBar query={normalizedQuery} model={facetModel} onChange={updateQuery} />

      <ScanJobStatus job={scanJob} />
      <MetadataRefreshStatus refresh={metadataRefresh} />

      <div className="library-layout">
        <div className="library-list">
          {emptyLibrary && (
            <div className="empty-state compact">
              <span>Scan your connected sources to build the local library index.</span>
            </div>
          )}
          {noMatches && (
            <div className="empty-state compact">
              <span>No library matches.</span>
            </div>
          )}
          {visibleItems.map((item) => (
            <LibraryRow
              key={item.path}
              item={item}
              favorite={isItemFavorite(item, favoritePaths)}
              selected={selectedItem?.path === item.path}
              onSelect={() => setSelectedPath(item.path)}
              onPlay={() => onPlay(item)}
              onToggleFavorite={() => onToggleFavorite(item)}
            />
          ))}
        </div>

        <LibraryPreview
          item={selectedItem}
          favorite={selectedItem ? isItemFavorite(selectedItem, favoritePaths) : false}
          onPlay={onPlay}
          onToggleFavorite={onToggleFavorite}
        />
      </div>
    </section>
  );
}

function LibraryStats({ stats, loading }) {
  return (
    <div className="library-stats" aria-label="Library totals">
      <span className="stat-chip">Total <strong>{formatCount(stats.total)}</strong></span>
      <span className="stat-chip">Movies <strong>{formatCount(stats.movie)}</strong></span>
      <span className="stat-chip">TV <strong>{formatCount(stats.tv)}</strong></span>
      <span className="stat-chip">Favorites <strong>{formatCount(stats.favorites)}</strong></span>
      <span className="stat-chip">Offline <strong>{formatCount(stats.offline)}</strong></span>
      {loading && (
        <span className="stat-chip live">
          <RefreshCw size={13} className="spinning" />
          Updating
        </span>
      )}
    </div>
  );
}

function LibraryFacetBar({ query, model, onChange }) {
  return (
    <div className="library-facet-bar">
      <div className="segmented-control" role="group" aria-label="Library segment">
        {SEGMENT_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            className={query.segment === option.value ? "active" : ""}
            onClick={() => onChange({ segment: option.value })}
          >
            <span>{option.label}</span>
            <strong>{formatCount(model.stats[option.stat])}</strong>
          </button>
        ))}
      </div>

      <div className="facet-selects">
        <FacetSelect
          label="Year"
          value={query.year}
          allLabel="Any year"
          options={model.years}
          onChange={(year) => onChange({ year })}
        />
        <FacetSelect
          label="Quality"
          value={query.quality}
          allLabel="Any quality"
          options={model.qualities}
          onChange={(quality) => onChange({ quality })}
        />
        <FacetSelect
          className="source"
          label="Source"
          value={query.sourceId}
          allLabel="Any source"
          options={model.sources}
          onChange={(sourceId) => onChange({ sourceId })}
        />
      </div>
    </div>
  );
}

function FacetSelect({ className = "", label, value, allLabel, options, onChange }) {
  return (
    <label className={`facet-select ${className}`}>
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} disabled={options.length === 0}>
        <option value="all">{allLabel}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {formatFacetOption(option)}
          </option>
        ))}
      </select>
    </label>
  );
}

function ScanJobStatus({ job }) {
  if (!job) {
    return null;
  }

  const Icon = job.status === "completed" ? CheckCircle2 : job.status === "failed" ? AlertCircle : RefreshCw;
  return (
    <div className={`scan-note ${job.status}`}>
      <span className="scan-note-header">
        <Icon size={17} className={job.status === "running" ? "spinning" : ""} />
        <strong>Status: {scanStatusLabel(job.status)}</strong>
      </span>
      <span className="scan-stat">{formatCount(job.items_indexed)} indexed</span>
      <span className="scan-stat">{formatCount(job.sources_scanned)} scanned</span>
      <span className="scan-stat">{formatCount(job.sources_skipped)} skipped</span>
      {job.error && <span className="scan-error">Error: {job.error}</span>}
    </div>
  );
}

function MetadataRefreshStatus({ refresh }) {
  if (!refresh) {
    return null;
  }

  const errors = metadataRefreshErrors(refresh);
  const statusClass = metadataRefreshClass(refresh, errors);
  const Icon = statusClass === "completed" ? CheckCircle2 : statusClass === "failed" ? AlertCircle : RefreshCw;
  return (
    <div className={`scan-note metadata-note ${statusClass}`}>
      <span className="scan-note-header">
        <Icon size={17} className={statusClass === "running" ? "spinning" : ""} />
        <strong>{metadataRefreshLabel(refresh, errors)}</strong>
      </span>
      <span className="scan-stat">{formatCount(refresh.items_refreshed)} refreshed</span>
      <span className="scan-stat">{formatCount(refresh.items_missing)} missing</span>
      <span className="scan-stat">{formatCount(refresh.items_skipped)} skipped</span>
      {refresh.limit != null && <span className="scan-stat">limit {refresh.limit}</span>}
      {errors.length > 0 && <span className="scan-error">Errors: {formatMetadataErrors(errors)}</span>}
    </div>
  );
}

function LibraryRow({ item, favorite, selected, onSelect, onPlay, onToggleFavorite }) {
  const online = isItemAvailable(item);
  const title = displayTitle(item);

  return (
    <div className={`library-row ${selected ? "selected" : ""} ${online ? "" : "offline"}`}>
      <button className="library-select" type="button" onClick={onSelect} onDoubleClick={online ? onPlay : undefined}>
        <PosterThumb item={item} />
        <span className="library-copy">
          <strong>{title}</strong>
          <span className="library-badges">
            <span>{mediaTypeLabel(item.media_type) || "Video"}</span>
            <span>{item.year || "Unknown year"}</span>
            <span>{item.quality || "Unknown quality"}</span>
            <span className={online ? "online-pill" : "offline-pill"}>{online ? "Online" : "Offline"}</span>
            {favorite && <span className="favorite-pill">Favorite</span>}
          </span>
          {item.overview && <span className="library-overview">{item.overview}</span>}
        </span>
      </button>
      <button className="icon-button" type="button" onClick={onPlay} disabled={!online} title="Play">
        <Play size={17} />
      </button>
      <button
        className={favorite ? "icon-button active" : "icon-button"}
        type="button"
        onClick={onToggleFavorite}
        title={favorite ? "Remove favorite" : "Favorite"}
      >
        <Star size={17} />
      </button>
    </div>
  );
}

function LibraryPreview({ item, favorite, onPlay, onToggleFavorite }) {
  if (!item) {
    return (
      <aside className="library-preview empty-preview">
        <Film size={34} />
        <span>No library item selected.</span>
      </aside>
    );
  }

  const online = isItemAvailable(item);
  const posterSrc = mediaUrl(item.artwork_url);

  return (
    <aside className="library-preview">
      <div className="poster-frame">
        {posterSrc ? <img src={posterSrc} alt="" /> : <Film size={42} />}
      </div>

      <div className="preview-title">
        <h2>{displayTitle(item)}</h2>
        <span>{librarySubtitle(item)}</span>
      </div>

      <div className="preview-actions">
        <button className="primary-button" type="button" onClick={() => onPlay(item)} disabled={!online}>
          <Play size={17} />
          <span>Play</span>
        </button>
        <button
          className={favorite ? "text-button active" : "text-button"}
          type="button"
          onClick={() => onToggleFavorite(item)}
        >
          <Star size={16} />
          <span>{favorite ? "Favorited" : "Favorite"}</span>
        </button>
      </div>

      <p className="preview-overview">{item.overview || "No overview is available for this item yet."}</p>

      <dl className="metadata-grid">
        <dt>Status</dt>
        <dd>{online ? "Online" : "Offline"}</dd>
        <dt>Quality</dt>
        <dd>{item.quality || "Unknown"}</dd>
        <dt>Type</dt>
        <dd>{mediaTypeLabel(item.media_type) || "Video"}</dd>
        <dt>Source</dt>
        <dd>{sourceLabelFromItem(item) || "Unknown"}</dd>
        <dt>Metadata</dt>
        <dd>{metadataSourceLabel(item.metadata_source)}</dd>
      </dl>

      <div className="path-block">
        <span>Path</span>
        <code>{item.path}</code>
      </div>
      {item.source_path && (
        <div className="path-block">
          <span>Source</span>
          <code>{item.source_path}</code>
        </div>
      )}
    </aside>
  );
}

function PosterThumb({ item }) {
  const posterSrc = mediaUrl(item.artwork_url);
  return (
    <span className="library-thumb">
      {posterSrc ? <img src={posterSrc} alt="" /> : <Film size={20} />}
    </span>
  );
}

function filterAndSortItems(items, query, favoritePaths) {
  const normalized = normalizeLibraryQuery(query);
  const filtered = items.filter((item) => (
    matchesSegment(item, normalized.segment, favoritePaths) &&
    matchesFacet(item.year, normalized.year) &&
    matchesFacet(item.quality, normalized.quality) &&
    matchesFacet(item.source_id, normalized.sourceId) &&
    matchesSearch(item, normalized.search)
  ));

  return filtered.sort((a, b) => compareLibraryItems(a, b, normalized.sort));
}

function compareLibraryItems(a, b, sort) {
  if (sort === "title") {
    return displayTitle(a).localeCompare(displayTitle(b));
  }
  if (sort === "year") {
    return (Number(b.year) || 0) - (Number(a.year) || 0) || displayTitle(a).localeCompare(displayTitle(b));
  }
  if (sort === "quality") {
    return qualityRank(b.quality) - qualityRank(a.quality) || displayTitle(a).localeCompare(displayTitle(b));
  }
  return (Number(b.modified_at) || 0) - (Number(a.modified_at) || 0) || displayTitle(a).localeCompare(displayTitle(b));
}

function matchesSegment(item, segment, favoritePaths) {
  if (segment === "movie") {
    return item.media_type === "movie";
  }
  if (segment === "tv") {
    return item.media_type === "tv";
  }
  if (segment === "favorites") {
    return isItemFavorite(item, favoritePaths);
  }
  if (segment === "offline") {
    return !isItemAvailable(item);
  }
  return true;
}

function matchesFacet(itemValue, selectedValue) {
  return selectedValue === "all" || String(itemValue ?? "") === String(selectedValue);
}

function matchesSearch(item, search) {
  const query = search.trim().toLowerCase();
  if (!query) {
    return true;
  }
  return [
    displayTitle(item),
    item.name,
    item.year,
    item.quality,
    item.overview,
    item.path,
    item.source_path,
    sourceLabelFromItem(item),
    item.metadata_source,
    item.media_type
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
    .includes(query);
}

function buildFacetModel({ facets, items, sources, favoritePaths }) {
  const fallback = buildFallbackFacetModel(items, sources, favoritePaths);
  if (!facets || typeof facets !== "object") {
    return fallback;
  }

  const mediaOptions = normalizeFacetOptions(readFacetValue(facets, ["media_types", "media_type", "types"]));
  const availabilityOptions = normalizeFacetOptions(readFacetValue(facets, ["availability", "available", "status"]));
  const yearOptions = mergeFacetOptions(
    normalizeFacetOptions(readFacetValue(facets, ["years", "year"])),
    fallback.years
  ).sort(sortYearOptions);
  const qualityOptions = mergeFacetOptions(
    normalizeFacetOptions(readFacetValue(facets, ["qualities", "quality"])),
    fallback.qualities
  ).sort(sortQualityOptions);
  const sourceLookup = sourceLookupFromSources(sources);
  const sourceOptions = mergeFacetOptions(
    normalizeFacetOptions(readFacetValue(facets, ["sources", "source"])),
    fallback.sources
  )
    .map((option) => ({
      ...option,
      label: sourceLookup.get(option.value) || option.label
    }))
    .sort(sortLabelOptions);

  return {
    stats: {
      total: firstFinite(readNumericFacet(facets, ["total", "total_items", "item_count", "count"]), fallback.stats.total),
      movie: firstFinite(readNumericFacet(facets, ["movie", "movies", "movie_count"]), countFacetOption(mediaOptions, "movie"), fallback.stats.movie),
      tv: firstFinite(readNumericFacet(facets, ["tv", "shows", "tv_count"]), countFacetOption(mediaOptions, "tv"), fallback.stats.tv),
      favorites: firstFinite(readNumericFacet(facets, ["favorites", "favorite", "favorite_count"]), fallback.stats.favorites),
      offline: firstFinite(
        readNumericFacet(facets, ["offline", "unavailable", "unavailable_count"]),
        countFacetOption(availabilityOptions, "false", "offline", "unavailable"),
        fallback.stats.offline
      ),
      online: firstFinite(
        readNumericFacet(facets, ["online", "available_count"]),
        countFacetOption(availabilityOptions, "true", "online", "available"),
        fallback.stats.online
      )
    },
    years: yearOptions,
    qualities: qualityOptions,
    sources: sourceOptions
  };
}

function buildFallbackFacetModel(items = [], sources = [], favoritePaths = EMPTY_SET) {
  const stats = {
    total: items.length,
    movie: 0,
    tv: 0,
    favorites: 0,
    offline: 0,
    online: 0
  };
  const years = new Map();
  const qualities = new Map();
  const sourceOptions = new Map();
  const sourceLookup = sourceLookupFromSources(sources);

  for (const item of items) {
    if (item.media_type === "movie") {
      stats.movie += 1;
    }
    if (item.media_type === "tv") {
      stats.tv += 1;
    }
    if (isItemFavorite(item, favoritePaths)) {
      stats.favorites += 1;
    }
    if (isItemAvailable(item)) {
      stats.online += 1;
    } else {
      stats.offline += 1;
    }
    incrementFacetOption(years, item.year, item.year);
    incrementFacetOption(qualities, item.quality, item.quality);
    if (item.source_id != null) {
      incrementFacetOption(
        sourceOptions,
        item.source_id,
        sourceLookup.get(String(item.source_id)) || sourceLabelFromItem(item)
      );
    }
  }

  for (const source of sources) {
    if (source.id != null && !sourceOptions.has(String(source.id))) {
      sourceOptions.set(String(source.id), {
        value: String(source.id),
        label: sourceLookup.get(String(source.id)) || `Source ${source.id}`,
        count: 0
      });
    }
  }

  return {
    stats,
    years: [...years.values()].sort(sortYearOptions),
    qualities: [...qualities.values()].sort(sortQualityOptions),
    sources: [...sourceOptions.values()].sort(sortLabelOptions)
  };
}

function normalizeFacetOptions(value) {
  if (!value) {
    return [];
  }
  if (Array.isArray(value)) {
    return value.map((entry) => normalizeFacetEntry(entry)).filter(Boolean);
  }
  if (typeof value === "object") {
    return Object.entries(value).map(([key, entry]) => normalizeFacetEntry(entry, key)).filter(Boolean);
  }
  return [];
}

function normalizeFacetEntry(entry, fallbackValue = null) {
  if (entry && typeof entry === "object" && !Array.isArray(entry)) {
    const rawValue = firstDefined(
      entry.value,
      entry.id,
      entry.key,
      entry.year,
      entry.quality,
      entry.media_type,
      entry.source_id,
      entry.sourceId,
      entry.available,
      entry.favorite,
      fallbackValue
    );
    if (rawValue == null || rawValue === "") {
      return null;
    }
    return {
      value: String(rawValue),
      label: String(firstDefined(entry.label, entry.name, entry.title, entry.display_name, rawValue)),
      count: firstFiniteOrNull(entry.count, entry.total, entry.items, entry.item_count)
    };
  }

  if (fallbackValue != null && Number.isFinite(Number(entry))) {
    return {
      value: String(fallbackValue),
      label: String(fallbackValue),
      count: Number(entry)
    };
  }

  const rawValue = firstDefined(fallbackValue, entry);
  if (rawValue == null || rawValue === "") {
    return null;
  }
  return {
    value: String(rawValue),
    label: String(rawValue),
    count: null
  };
}

function mergeFacetOptions(serverOptions, fallbackOptions) {
  if (serverOptions.length === 0) {
    return fallbackOptions;
  }

  const fallbackByValue = new Map(fallbackOptions.map((option) => [option.value, option]));
  return serverOptions.map((option) => {
    const fallback = fallbackByValue.get(option.value);
    return {
      value: option.value,
      label: option.label || fallback?.label || option.value,
      count: firstFinite(option.count, fallback?.count, 0)
    };
  });
}

function incrementFacetOption(map, value, label) {
  if (value == null || value === "") {
    return;
  }
  const key = String(value);
  const current = map.get(key) || {
    value: key,
    label: String(label || value),
    count: 0
  };
  current.count += 1;
  if (!current.label && label) {
    current.label = String(label);
  }
  map.set(key, current);
}

function readFacetValue(facets, keys) {
  const roots = [facets, facets.facets, facets.counts, facets.stats, facets.totals].filter(
    (root) => root && typeof root === "object"
  );
  for (const root of roots) {
    for (const key of keys) {
      if (root[key] != null) {
        return root[key];
      }
    }
  }
  return null;
}

function readNumericFacet(facets, keys) {
  return toFiniteNumber(readFacetValue(facets, keys));
}

function countFacetOption(options, ...values) {
  const targets = new Set(values.map(normalizeFacetKey));
  const option = options.find((entry) => targets.has(normalizeFacetKey(entry.value)));
  return option ? toFiniteNumber(option.count) : null;
}

function sourceLookupFromSources(sources = []) {
  const lookup = new Map();
  for (const source of sources) {
    if (source.id == null) {
      continue;
    }
    const folder = source.path ? source.path.split("/").filter(Boolean).at(-1) : "";
    lookup.set(String(source.id), source.name || folder || `Source ${source.id}`);
  }
  return lookup;
}

function hasActiveLibraryQuery(query) {
  return (
    query.search.trim() ||
    query.segment !== "all" ||
    query.year !== "all" ||
    query.quality !== "all" ||
    query.sourceId !== "all"
  );
}

function isItemFavorite(item, favoritePaths) {
  return favoritePaths.has(item.path) || item.favorite;
}

function isItemAvailable(item) {
  return item.available !== false && item.media_available !== false;
}

function displayTitle(item) {
  return item.display_title || item.title || item.name || item.path?.split("/").at(-1) || "Untitled";
}

function librarySubtitle(item) {
  const parts = [];
  if (item.year) {
    parts.push(item.year);
  }
  if (item.season && item.episode) {
    parts.push(`S${String(item.season).padStart(2, "0")}E${String(item.episode).padStart(2, "0")}`);
  }
  if (item.position && item.duration) {
    parts.push(`${Math.round((item.position / item.duration) * 100)}% watched`);
  }
  const folder = sourceLabelFromItem(item);
  if (folder) {
    parts.push(folder);
  }
  return parts.join(" / ") || item.name || "";
}

function sourceLabelFromItem(item) {
  if (item.source_name) {
    return item.source_name;
  }
  if (item.source_path) {
    return item.source_path.split("/").filter(Boolean).at(-1) || item.source_path;
  }
  if (item.source_id != null) {
    return `Source ${item.source_id}`;
  }
  return "";
}

function mediaTypeLabel(mediaType) {
  if (mediaType === "tv") {
    return "TV";
  }
  if (mediaType === "movie") {
    return "Movie";
  }
  return mediaType || "";
}

function metadataSourceLabel(source) {
  if (source === "tmdb") {
    return "TMDb";
  }
  if (source === "local") {
    return "Local";
  }
  return source || "Unknown";
}

function scanStatusLabel(status) {
  if (status === "completed") {
    return "Completed";
  }
  if (status === "failed") {
    return "Failed";
  }
  return "Running";
}

function metadataRefreshClass(refresh, errors) {
  if (refresh.status === "failed" || refresh.error || errors.length > 0) {
    return "failed";
  }
  if (refresh.status === "running") {
    return "running";
  }
  return "completed";
}

function metadataRefreshLabel(refresh, errors) {
  if (refresh.status === "running") {
    return "Metadata refreshing";
  }
  if (refresh.status === "failed") {
    return "Metadata refresh failed";
  }
  if (errors.length > 0) {
    return "Metadata refreshed with errors";
  }
  return "Metadata refreshed";
}

function metadataRefreshErrors(refresh) {
  const errors = refresh.errors || [];
  const allErrors = refresh.error ? [refresh.error, ...errors] : errors;
  return [...new Set(allErrors.filter(Boolean))];
}

function formatMetadataErrors(errors) {
  if (errors.length <= 3) {
    return errors.join("; ");
  }
  return `${errors.slice(0, 3).join("; ")}; +${errors.length - 3} more`;
}

function formatFacetOption(option) {
  const count = toFiniteNumber(option.count);
  return count == null ? option.label : `${option.label} (${count})`;
}

function normalizeLibraryQuery(query = DEFAULT_LIBRARY_QUERY) {
  return {
    search: query.search || "",
    sort: query.sort || "recent",
    segment: normalizeSegment(query.segment),
    year: normalizeFilterValue(query.year),
    quality: normalizeFilterValue(query.quality),
    sourceId: normalizeFilterValue(query.sourceId)
  };
}

function normalizeSegment(segment) {
  if (segment === "movie" || segment === "tv" || segment === "favorites" || segment === "offline") {
    return segment;
  }
  return "all";
}

function normalizeFilterValue(value) {
  if (value == null || value === "") {
    return "all";
  }
  return String(value);
}

function sortYearOptions(a, b) {
  return (Number(b.value) || 0) - (Number(a.value) || 0) || a.label.localeCompare(b.label);
}

function sortQualityOptions(a, b) {
  return qualityRank(b.value) - qualityRank(a.value) || a.label.localeCompare(b.label);
}

function sortLabelOptions(a, b) {
  return a.label.localeCompare(b.label);
}

function qualityRank(value) {
  const normalized = String(value || "").toUpperCase();
  if (normalized.includes("4320") || normalized.includes("8K")) {
    return 6;
  }
  if (normalized.includes("2160") || normalized.includes("4K") || normalized.includes("UHD")) {
    return 5;
  }
  if (normalized.includes("1080")) {
    return 4;
  }
  if (normalized.includes("720")) {
    return 3;
  }
  if (normalized.includes("576") || normalized.includes("540")) {
    return 2;
  }
  if (normalized.includes("480")) {
    return 1;
  }
  return 0;
}

function normalizeFacetKey(value) {
  return String(value).trim().toLowerCase();
}

function firstDefined(...values) {
  return values.find((value) => value != null);
}

function firstFinite(...values) {
  for (const value of values) {
    const number = toFiniteNumber(value);
    if (number != null) {
      return number;
    }
  }
  return 0;
}

function firstFiniteOrNull(...values) {
  for (const value of values) {
    const number = toFiniteNumber(value);
    if (number != null) {
      return number;
    }
  }
  return null;
}

function toFiniteNumber(value) {
  if (value == null || value === "") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatCount(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}
