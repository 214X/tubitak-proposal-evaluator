from __future__ import annotations

import base64
import csv
import io
import re
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

MONTH_NAMES = [
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
]
DEFAULT_MONTH_LABELS = [f"Ay {index}" for index in range(1, 13)]
TESSERACT_BINARY = Path("/opt/homebrew/bin/tesseract")
GANTT_HEADING_HINT = re.compile(r"\bis zaman cubuk grafigi\b", re.IGNORECASE)
DATA_URI_PATTERN = re.compile(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$")


@dataclass(frozen=True)
class OCRWord:
    text: str
    left: int
    top: int
    width: int
    height: int
    confidence: float
    block_num: int
    par_num: int
    line_num: int

    @property
    def center_x(self) -> float:
        return self.left + (self.width / 2)

    @property
    def center_y(self) -> float:
        return self.top + (self.height / 2)


@dataclass(frozen=True)
class RowBand:
    top: int
    bottom: int
    center: float


def normalize_tubitak_gantt_picture(
    picture_item: dict[str, Any],
    active_heading_text: str | None,
    docling_output: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    normalized_heading = _normalize_text(active_heading_text)
    if not normalized_heading or not GANTT_HEADING_HINT.search(normalized_heading):
        return None

    image_uri = _extract_image_uri(picture_item)
    if not image_uri:
        return None

    image = _decode_data_uri_image(image_uri)
    if image is None:
        return None

    chart_payload = _extract_gantt_chart_payload(
        image,
        active_heading_text or "İş Zaman Çubuk Grafiği",
        child_texts=_extract_picture_child_texts(picture_item, docling_output or {}),
    )
    if chart_payload is None:
        return None

    chart_payload["image_uri"] = image_uri
    chart_payload["source_ref"] = picture_item.get("self_ref")
    return chart_payload


def _extract_gantt_chart_payload(
    image: Image.Image,
    title: str,
    child_texts: list[str],
) -> dict[str, Any] | None:
    bgr_image = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    grayscale = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
    dark_mask = grayscale < 120

    height, width = grayscale.shape
    vertical_segments = _find_dark_segments(dark_mask.sum(axis=0), max(30, int(height * 0.16)))
    if len(vertical_segments) < 3:
        return None

    grid_start_x = _pick_grid_start_x(vertical_segments, width)
    grid_end_x = _pick_grid_end_x(vertical_segments, width)
    if grid_end_x <= grid_start_x:
        return None

    package_label_end_x = _pick_package_label_end_x(vertical_segments, grid_start_x, width)
    task_text_start_x = min(package_label_end_x + 6, grid_start_x - 10)

    green_mask = _build_green_mask(bgr_image)
    task_rows = _extract_task_rows(
        image=image,
        crop_left=task_text_start_x,
        crop_right=max(task_text_start_x + 24, grid_start_x - 8),
        grid_start_x=grid_start_x,
        green_mask=green_mask,
        min_width=max(8, width // 130),
        child_texts=child_texts,
    )
    if not task_rows:
        return None

    row_bands = [task_row["band"] for task_row in task_rows]
    package_boundaries = _pick_package_boundaries(dark_mask, width, row_bands)
    month_labels = _extract_month_labels(
        image=image,
        grid_start_x=grid_start_x,
        grid_end_x=grid_end_x,
        package_boundaries=package_boundaries,
        child_texts=child_texts,
    )

    work_packages = _build_work_packages(
        task_rows=task_rows,
        grid_start_x=grid_start_x,
        grid_end_x=grid_end_x,
        package_boundaries=package_boundaries,
        month_labels=month_labels,
    )
    if not work_packages:
        return None

    return {
        "type": "gantt_chart",
        "title": title,
        "months": month_labels,
        "week_count": 48,
        "work_packages": work_packages,
    }


def _extract_task_rows(
    image: Image.Image,
    crop_left: int,
    crop_right: int,
    grid_start_x: int,
    green_mask: np.ndarray,
    min_width: int,
    child_texts: list[str],
) -> list[dict[str, Any]]:
    if crop_right <= crop_left:
        return []

    crop = image.crop((crop_left, 0, crop_right, image.height))
    prepared = _prepare_ocr_image(crop, scale=3)
    words = _run_tesseract_tsv(prepared)
    scale_factor = prepared.width / max(crop.width, 1)

    line_groups: dict[tuple[int, int, int], list[OCRWord]] = {}
    for word in words:
        line_groups.setdefault((word.block_num, word.par_num, word.line_num), []).append(word)

    rows: list[dict[str, Any]] = []
    for grouped_words in sorted(
        line_groups.values(),
        key=lambda current: min(word.top for word in current),
    ):
        grouped_words.sort(key=lambda word: word.left)
        label = _cleanup_ocr_text(" ".join(word.text for word in grouped_words if word.text))
        if len(label) < 4:
            continue

        top = max(0, int(min(word.top for word in grouped_words) / scale_factor) - 2)
        bottom = min(image.height, int(max(word.top + word.height for word in grouped_words) / scale_factor) + 2)
        band = RowBand(top=top, bottom=bottom, center=(top + bottom) / 2)
        sample_top = max(0, int(band.center) - 2)
        sample_bottom = min(image.height, int(band.center) + 2)
        row_slice = green_mask[sample_top:sample_bottom, grid_start_x:]
        xs = np.where(row_slice > 0)[1]
        if xs.size == 0:
            continue
        x_start = grid_start_x + int(xs.min())
        x_end = grid_start_x + int(xs.max()) + 1
        if x_end - x_start < min_width:
            continue
        rows.append(
            {
                "band": band,
                "label": label,
                "x_start": x_start,
                "x_end": x_end,
            }
        )

    structured_labels = _extract_task_labels_from_child_texts(child_texts)
    for index, row in enumerate(rows):
        if index < len(structured_labels):
            row["label"] = structured_labels[index]

    return rows


def _extract_month_labels(
    image: Image.Image,
    grid_start_x: int,
    grid_end_x: int,
    package_boundaries: list[int],
    child_texts: list[str],
) -> list[str]:
    structured_labels = _extract_month_labels_from_child_texts(child_texts)
    if len(structured_labels) == 12:
        return structured_labels

    header_bottom = package_boundaries[0] if package_boundaries else max(48, image.height // 6)
    crop = image.crop((grid_start_x, 0, grid_end_x, max(24, header_bottom - 6)))
    prepared = _prepare_ocr_image(crop, scale=3)
    words = _run_tesseract_tsv(prepared)

    labels = DEFAULT_MONTH_LABELS.copy()
    if not words:
        return labels

    scale_factor = prepared.width / max(crop.width, 1)
    month_width = crop.width / 12

    for word in words:
        matched_month = _match_month_name(word.text)
        if not matched_month:
            continue

        original_center_x = word.center_x / scale_factor
        month_index = min(11, max(0, int(original_center_x / max(month_width, 1))))
        labels[month_index] = matched_month

    return labels


def _build_work_packages(
    task_rows: list[dict[str, Any]],
    grid_start_x: int,
    grid_end_x: int,
    package_boundaries: list[int],
    month_labels: list[str],
) -> list[dict[str, Any]]:
    week_width = max((grid_end_x - grid_start_x) / 48, 1)
    package_map: dict[int, list[dict[str, Any]]] = {}

    for index, task_row in enumerate(task_rows):
        band = task_row["band"]
        x_start = int(task_row["x_start"])
        x_end = int(task_row["x_end"])
        start_week = min(48, max(1, int(round((x_start - grid_start_x) / week_width)) + 1))
        end_week = min(48, max(start_week, int(np.ceil((x_end - grid_start_x) / week_width))))
        package_index = _assign_package_index(band.center, package_boundaries)
        package_map.setdefault(package_index, []).append(
            {
                "label": str(task_row["label"]),
                "start_week": start_week,
                "end_week": end_week,
                "months": _describe_month_span(start_week, end_week, month_labels),
            }
        )

    work_packages: list[dict[str, Any]] = []
    for sequence_index, package_index in enumerate(sorted(package_map), start=1):
        work_packages.append(
            {
                "label": f"İş Paketi {sequence_index}",
                "tasks": package_map[package_index],
            }
        )
    return work_packages


def _extract_picture_child_texts(
    picture_item: dict[str, Any],
    docling_output: dict[str, Any],
) -> list[str]:
    text_items = docling_output.get("texts", [])
    extracted: list[tuple[float, float, str]] = []

    for child in picture_item.get("children", []):
        ref = child.get("cref") or child.get("$ref")
        if not isinstance(ref, str) or not ref.startswith("#/texts/"):
            continue

        try:
            index = int(ref.rsplit("/", maxsplit=1)[-1])
            text_item = text_items[index]
        except (ValueError, IndexError, TypeError):
            continue

        text = text_item.get("text")
        if not isinstance(text, str) or not text.strip():
            continue

        prov = text_item.get("prov") or []
        bbox = prov[0].get("bbox") if prov and isinstance(prov[0], dict) else None
        left = float(bbox.get("l", 0.0)) if isinstance(bbox, dict) else 0.0
        top = float(bbox.get("t", 0.0)) if isinstance(bbox, dict) else 0.0
        extracted.append((top, left, text.strip()))

    extracted.sort(key=lambda current: (-current[0], current[1]))
    return [text for _, _, text in extracted]


def _extract_month_labels_from_child_texts(child_texts: list[str]) -> list[str]:
    labels: list[str] = []
    for text in child_texts:
        matched_month = _match_month_name(text)
        if matched_month:
            labels.append(matched_month)
    return labels[:12]


def _extract_task_labels_from_child_texts(child_texts: list[str]) -> list[str]:
    labels: list[str] = []
    for text in child_texts:
        cleaned = " ".join(text.split()).strip()
        if not cleaned or cleaned == "Aylar":
            continue
        if cleaned.startswith("İş Paketi"):
            continue
        if _match_month_name(cleaned):
            continue
        if cleaned.isdigit():
            continue
        labels.append(cleaned)
    return labels


def _assign_package_index(row_center: float, boundaries: list[int]) -> int:
    if len(boundaries) < 2:
        return 0

    for index in range(len(boundaries) - 1):
        if boundaries[index] <= row_center < boundaries[index + 1]:
            return index
    return max(0, len(boundaries) - 2)


def _describe_month_span(start_week: int, end_week: int, month_labels: list[str]) -> str:
    start_month = month_labels[min(11, max(0, (start_week - 1) // 4))]
    end_month = month_labels[min(11, max(0, (end_week - 1) // 4))]
    return start_month if start_month == end_month else f"{start_month} - {end_month}"


def _pick_grid_start_x(vertical_segments: list[tuple[int, int, int]], width: int) -> int:
    candidates = [
        segment
        for segment in vertical_segments
        if int(width * 0.22) <= segment[0] <= int(width * 0.6)
    ]
    if not candidates:
        return width // 3
    return max(candidates, key=lambda segment: segment[2])[0]


def _pick_grid_end_x(vertical_segments: list[tuple[int, int, int]], width: int) -> int:
    candidates = [
        segment
        for segment in vertical_segments
        if segment[0] >= int(width * 0.82)
    ]
    if not candidates:
        return width - 4
    return max(candidates, key=lambda segment: segment[0])[0]


def _pick_package_label_end_x(
    vertical_segments: list[tuple[int, int, int]],
    grid_start_x: int,
    width: int,
) -> int:
    candidates = [
        segment
        for segment in vertical_segments
        if int(width * 0.03) <= segment[0] <= int(width * 0.26)
    ]
    if not candidates:
        return max(48, grid_start_x // 4)
    return max(candidates, key=lambda segment: segment[0])[0]


def _pick_package_boundaries(
    dark_mask: np.ndarray,
    width: int,
    row_bands: list[RowBand],
) -> list[int]:
    if not row_bands:
        return [0, dark_mask.shape[0]]

    horizontal_strength = dark_mask.sum(axis=1)
    raw_segments = _find_dark_segments(horizontal_strength, max(60, int(width * 0.45)))
    row_top = row_bands[0].top
    candidates = [
        segment[0]
        for segment in raw_segments
        if row_top - 24 <= segment[0] <= dark_mask.shape[0] - 12
    ]
    candidates = sorted(set(candidates))
    if len(candidates) >= 2:
        return [max(0, candidates[0])] + candidates[1:] + [dark_mask.shape[0]]

    # Fallback: split by visually larger row gaps when thick separator lines
    # are not detected cleanly.
    centers = [band.center for band in row_bands]
    gaps = [centers[index + 1] - centers[index] for index in range(len(centers) - 1)]
    if not gaps:
        return [row_bands[0].top, row_bands[-1].bottom]

    median_gap = float(np.median(gaps))
    boundaries = [row_bands[0].top]
    for index, gap in enumerate(gaps):
        if gap > median_gap * 1.45:
            boundaries.append(int((centers[index] + centers[index + 1]) / 2))
    boundaries.append(row_bands[-1].bottom)
    return boundaries


def _build_green_mask(bgr_image: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
    lower = np.array([35, 40, 40])
    upper = np.array([95, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    kernel = np.ones((3, 3), np.uint8)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)


def _find_dark_segments(strengths: np.ndarray, threshold: int) -> list[tuple[int, int, int]]:
    segments: list[tuple[int, int, int]] = []
    start: int | None = None
    peak = 0

    for index, value in enumerate(strengths):
        if int(value) >= threshold:
            if start is None:
                start = index
                peak = int(value)
            else:
                peak = max(peak, int(value))
            continue

        if start is not None:
            center = int((start + index - 1) / 2)
            segments.append((center, index - start, peak))
            start = None
            peak = 0

    if start is not None:
        center = int((start + len(strengths) - 1) / 2)
        segments.append((center, len(strengths) - start, peak))

    return segments


def _prepare_ocr_image(image: Image.Image, scale: int) -> Image.Image:
    grayscale = np.array(image.convert("L"))
    scaled = cv2.resize(
        grayscale,
        (max(1, grayscale.shape[1] * scale), max(1, grayscale.shape[0] * scale)),
        interpolation=cv2.INTER_CUBIC,
    )
    normalized = cv2.normalize(scaled, None, 0, 255, cv2.NORM_MINMAX)
    _, thresholded = cv2.threshold(normalized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(thresholded)


def _run_tesseract_tsv(image: Image.Image) -> list[OCRWord]:
    if not TESSERACT_BINARY.exists():
        return []

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
        temp_path = Path(handle.name)
        image.save(temp_path)

    try:
        result = subprocess.run(
            [
                str(TESSERACT_BINARY),
                str(temp_path),
                "stdout",
                "--psm",
                "6",
                "tsv",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        temp_path.unlink(missing_ok=True)

    if result.returncode != 0 or not result.stdout.strip():
        return []

    reader = csv.DictReader(io.StringIO(result.stdout), delimiter="\t")
    words: list[OCRWord] = []
    for row in reader:
        text = _cleanup_ocr_text(row.get("text", ""))
        if not text:
            continue
        try:
            confidence = float(row.get("conf", "-1"))
            left = int(row.get("left", "0"))
            top = int(row.get("top", "0"))
            width = int(row.get("width", "0"))
            height = int(row.get("height", "0"))
        except ValueError:
            continue
        if confidence < 0:
            continue
        words.append(
            OCRWord(
                text=text,
                left=left,
                top=top,
                width=width,
                height=height,
                confidence=confidence,
                block_num=int(row.get("block_num", "0") or 0),
                par_num=int(row.get("par_num", "0") or 0),
                line_num=int(row.get("line_num", "0") or 0),
            )
        )
    return words


def _match_month_name(raw_text: str) -> str | None:
    normalized = _normalize_text(raw_text).replace(".", "")
    for month_name in MONTH_NAMES:
        normalized_month = _normalize_text(month_name)
        if normalized == normalized_month:
            return month_name
        if normalized_month.startswith(normalized) or normalized.startswith(normalized_month[:4]):
            return month_name
    return None


def _cleanup_ocr_text(value: str) -> str:
    cleaned = " ".join(value.split()).strip(" |")
    return cleaned


def _extract_image_uri(picture_item: dict[str, Any]) -> str | None:
    image = picture_item.get("image")
    if isinstance(image, dict):
        uri = image.get("uri")
        if uri is not None:
            normalized_uri = str(uri)
            if normalized_uri.startswith("data:image/"):
                return normalized_uri
    return None


def _decode_data_uri_image(uri: str) -> Image.Image | None:
    match = DATA_URI_PATTERN.match(uri)
    if not match:
        return None

    try:
        image_bytes = base64.b64decode(match.group("data"))
    except ValueError:
        return None

    try:
        return Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except OSError:
        return None


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""

    folded = unicodedata.normalize("NFKD", value.casefold())
    stripped = "".join(char for char in folded if not unicodedata.combining(char))

    return (
        stripped
        .replace("ı", "i")
        .replace("ş", "s")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ö", "o")
        .replace("ç", "c")
        .strip()
    )
