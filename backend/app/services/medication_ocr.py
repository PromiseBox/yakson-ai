from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.schemas import MedicationOcrCandidate, MedicationOcrResponse

SUPPORTED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}

DEFAULT_UPLOAD_LIMIT_MB = 8
GOOGLE_VISION_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"
METADATA_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
)

_DRUG_FORM_PATTERN = re.compile(
    r"(정|캡슐|캡셀|시럽|현탁액|액|점안액|점이액|연고|크림|겔|패치|패취|주사|주|산|과립|구강붕해정|서방정)"
)
_HANGUL_PATTERN = re.compile(r"[가-힣]")
_DOSE_MARKER_PATTERN = re.compile(
    r"\s(?:1일|일\s*\d+\s*회|하루|매일|아침|점심|저녁|취침|식전|식후|복용|투약|총|#)"
)
_LINE_PREFIX_PATTERN = re.compile(r"^\s*(?:\d+[\).:-]?|[-*•·])\s*")
_DURATION_PATTERNS = [
    re.compile(r"(?:총|투약|처방)?\s*(\d{1,3})\s*일"),
    re.compile(r"(\d{1,3})\s*days?", re.IGNORECASE),
]
_DOSES_PER_DAY_PATTERNS = [
    re.compile(r"(?:1일|하루|일)\s*(\d+(?:\.\d+)?)\s*회"),
    re.compile(r"(\d+(?:\.\d+)?)\s*회\s*/?\s*일"),
]
_DOSE_AMOUNT_PATTERNS = [
    re.compile(r"1회\s*(\d+(?:\.\d+)?)\s*(정|캡슐|캡셀|포|병|mL|ml|cc|방울)?"),
    re.compile(r"(\d+(?:\.\d+)?)\s*(정|캡슐|캡셀|포|병|mL|ml|cc|방울)"),
]
_CATEGORY_KEYWORDS = {
    "정형외과": "정형외과",
    "내과": "내과",
    "외과": "외과",
    "성인병": "성인병약",
    "당뇨": "당뇨약",
    "수면": "수면/신경안정",
    "신경": "수면/신경안정",
}
_IGNORE_LINE_KEYWORDS = {
    "환자",
    "성명",
    "주민",
    "전화",
    "주소",
    "병원",
    "의원",
    "약국",
    "처방전",
    "조제",
    "투약번호",
    "보험",
    "본인부담",
    "결제",
    "합계",
    "복약지도",
}


class OcrUnavailableError(RuntimeError):
    pass


class OcrUploadError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedMedicationLine:
    entered_drug_name: str
    category_name: str | None
    duration_days: int | None
    doses_per_day: float | None
    dose_amount: float | None
    dose_unit: str | None
    source_line: str
    confidence: float
    needs_review: bool


def upload_limit_bytes() -> int:
    raw_value = os.getenv("OCR_MAX_UPLOAD_MB", str(DEFAULT_UPLOAD_LIMIT_MB)).strip()
    try:
        max_mb = max(1, int(raw_value))
    except ValueError:
        max_mb = DEFAULT_UPLOAD_LIMIT_MB
    return max_mb * 1024 * 1024


def analyze_medication_image(_filename: str | None, content_type: str | None, content: bytes) -> MedicationOcrResponse:
    mime_type = (content_type or "").split(";")[0].strip().lower()
    if mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
        raise OcrUploadError("지원되는 이미지 형식은 JPG, PNG, WEBP입니다.")

    if not content:
        raise OcrUploadError("업로드된 파일이 비어 있습니다.")

    if len(content) > upload_limit_bytes():
        limit_mb = upload_limit_bytes() // (1024 * 1024)
        raise OcrUploadError(f"이미지는 {limit_mb}MB 이하로 업로드해주세요.")

    provider = os.getenv("OCR_PROVIDER", "google_vision").strip().lower()
    if provider in {"google_vision", "vision", "google"}:
        raw_text = _extract_text_with_google_vision(content)
        provider_name = "GOOGLE_VISION"
    elif provider == "mock":
        raw_text = os.getenv("OCR_MOCK_TEXT", "")
        provider_name = "MOCK"
    else:
        raise OcrUnavailableError("OCR_PROVIDER가 설정되어 있지 않습니다.")

    candidates, warnings = parse_medication_candidates(raw_text)
    return MedicationOcrResponse(
        provider=provider_name,
        rawText=raw_text,
        candidates=candidates,
        warnings=warnings,
    )


def parse_medication_candidates(raw_text: str) -> tuple[list[MedicationOcrCandidate], list[str]]:
    lines = [_clean_line(line) for line in raw_text.splitlines()]
    lines = [line for line in lines if line]
    category_name = _infer_category(raw_text)
    parsed_items: list[ParsedMedicationLine] = []
    seen_names: set[str] = set()

    for line in lines:
        parsed = _parse_medication_line(line, category_name)
        if not parsed:
            continue
        key = _normalize_name(parsed.entered_drug_name)
        if key in seen_names:
            continue
        seen_names.add(key)
        parsed_items.append(parsed)

    warnings: list[str] = []
    if not raw_text.strip():
        warnings.append("OCR 텍스트를 읽지 못했습니다. 더 밝고 선명한 사진으로 다시 시도해주세요.")
    elif not parsed_items:
        warnings.append("약명 후보를 찾지 못했습니다. OCR 원문을 확인하고 약명을 직접 검색해주세요.")

    candidates = [
        MedicationOcrCandidate(
            candidateId=f"ocr_{index}",
            enteredDrugName=item.entered_drug_name,
            categoryName=item.category_name,
            durationDays=item.duration_days,
            dosesPerDay=item.doses_per_day,
            doseAmount=item.dose_amount,
            doseUnit=item.dose_unit,
            sourceLine=item.source_line,
            confidence=item.confidence,
            needsReview=item.needs_review,
        )
        for index, item in enumerate(parsed_items, start=1)
    ]
    return candidates, warnings


def _extract_text_with_google_vision(content: bytes) -> str:
    api_key = os.getenv("GOOGLE_VISION_API_KEY", "").strip()
    url = GOOGLE_VISION_ENDPOINT if not api_key else f"{GOOGLE_VISION_ENDPOINT}?key={api_key}"
    headers = {"Content-Type": "application/json"}
    if not api_key:
        token = _metadata_access_token()
        headers["Authorization"] = f"Bearer {token}"

    payload = {
        "requests": [
            {
                "image": {"content": base64.b64encode(content).decode("ascii")},
                "features": [{"type": "TEXT_DETECTION", "maxResults": 1}],
                "imageContext": {"languageHints": ["ko", "en"]},
            }
        ]
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=float(os.getenv("OCR_TIMEOUT_SECONDS", "12"))) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OcrUnavailableError(f"Google Vision OCR 요청에 실패했습니다. {detail}") from exc
    except Exception as exc:
        raise OcrUnavailableError("Google Vision OCR에 연결하지 못했습니다.") from exc

    response_item: dict[str, Any] = (body.get("responses") or [{}])[0]
    if response_item.get("error"):
        message = response_item["error"].get("message") or "Google Vision OCR 오류가 발생했습니다."
        raise OcrUnavailableError(message)

    full_text = ((response_item.get("fullTextAnnotation") or {}).get("text") or "").strip()
    if full_text:
        return full_text

    annotations = response_item.get("textAnnotations") or []
    if annotations:
        return str(annotations[0].get("description") or "").strip()
    return ""


def _metadata_access_token() -> str:
    request = urllib.request.Request(METADATA_TOKEN_URL, headers={"Metadata-Flavor": "Google"})
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise OcrUnavailableError(
            "Google Vision 인증 정보를 찾지 못했습니다. Cloud Run 서비스 계정 권한 또는 "
            "GOOGLE_VISION_API_KEY를 확인해주세요."
        ) from exc

    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise OcrUnavailableError("Google Vision 인증 토큰을 가져오지 못했습니다.")
    return token


def _parse_medication_line(line: str, category_name: str | None) -> ParsedMedicationLine | None:
    if _is_noise_line(line):
        return None

    name = _extract_drug_name(line)
    if not name:
        return None

    duration_days = _parse_int(line, _DURATION_PATTERNS)
    doses_per_day = _parse_float(line, _DOSES_PER_DAY_PATTERNS)
    dose_amount, dose_unit = _parse_dose_amount(line)
    if dose_unit is None:
        dose_unit = _infer_unit_from_name(name)

    confidence = 0.62
    if _DRUG_FORM_PATTERN.search(name):
        confidence += 0.16
    if duration_days:
        confidence += 0.07
    if doses_per_day:
        confidence += 0.07
    if dose_amount:
        confidence += 0.05
    confidence = min(confidence, 0.96)

    return ParsedMedicationLine(
        entered_drug_name=name,
        category_name=category_name,
        duration_days=duration_days,
        doses_per_day=doses_per_day,
        dose_amount=dose_amount,
        dose_unit=dose_unit,
        source_line=line,
        confidence=round(confidence, 2),
        needs_review=confidence < 0.78 or not duration_days or not doses_per_day,
    )


def _extract_drug_name(line: str) -> str | None:
    candidate = _LINE_PREFIX_PATTERN.sub("", line)
    candidate = re.sub(r"^(?:약품명|약명|제품명|의약품)\s*[:：]?\s*", "", candidate)
    marker = _DOSE_MARKER_PATTERN.search(f" {candidate}")
    if marker:
        candidate = candidate[: max(0, marker.start() - 1)]
    candidate = re.split(r"\s{2,}|[|]", candidate)[0]
    candidate = re.sub(r"\b\d{1,3}\s*일\b.*$", "", candidate)
    candidate = re.sub(r"\b\d+(?:\.\d+)?\s*(?:회|정|캡슐|포)\b.*$", "", candidate)
    candidate = candidate.strip(" -,:：/[]{}")

    if len(candidate) < 2 or not _HANGUL_PATTERN.search(candidate):
        return None
    if not _DRUG_FORM_PATTERN.search(candidate) and not re.search(r"\d+\s*(?:mg|㎎|mcg|μg|g|ml|mL)", candidate, re.I):
        return None
    return candidate[:80]


def _parse_int(line: str, patterns: list[re.Pattern[str]]) -> int | None:
    value = _parse_float(line, patterns)
    return int(value) if value is not None else None


def _parse_float(line: str, patterns: list[re.Pattern[str]]) -> float | None:
    for pattern in patterns:
        match = pattern.search(line)
        if not match:
            continue
        try:
            return float(match.group(1))
        except (TypeError, ValueError):
            continue
    return None


def _parse_dose_amount(line: str) -> tuple[float | None, str | None]:
    fallback: tuple[float | None, str | None] = (None, None)
    for match in _DOSE_AMOUNT_PATTERNS[0].finditer(line):
        try:
            amount = float(match.group(1))
        except (TypeError, ValueError):
            continue
        unit = _normalize_unit(match.group(2) if len(match.groups()) > 1 else None)
        if unit:
            return amount, unit
        fallback = (amount, None)

    for match in _DOSE_AMOUNT_PATTERNS[1].finditer(line):
        try:
            amount = float(match.group(1))
        except (TypeError, ValueError):
            continue
        return amount, _normalize_unit(match.group(2) if len(match.groups()) > 1 else None)

    if fallback[0] is not None:
        return fallback
    return None, None


def _infer_unit_from_name(name: str) -> str | None:
    match = _DRUG_FORM_PATTERN.search(name)
    if not match:
        return None
    unit = match.group(1)
    if unit in {"캡슐", "캡셀"}:
        return "캡슐"
    if unit in {"시럽", "현탁액", "액"}:
        return "mL"
    if unit in {"산", "과립"}:
        return "포"
    if unit in {"연고", "크림", "겔"}:
        return "회"
    if unit in {"패치", "패취"}:
        return "매"
    return "정"


def _normalize_unit(value: str | None) -> str | None:
    if not value:
        return None
    unit = value.strip()
    if unit.lower() == "ml":
        return "mL"
    if unit == "캡셀":
        return "캡슐"
    return unit


def _infer_category(text: str) -> str | None:
    for keyword, category in _CATEGORY_KEYWORDS.items():
        if keyword in text:
            return category
    return None


def _is_noise_line(line: str) -> bool:
    if len(line) < 2 or not _HANGUL_PATTERN.search(line):
        return True
    return any(keyword in line for keyword in _IGNORE_LINE_KEYWORDS)


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace("\u3000", " ")).strip()


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()
