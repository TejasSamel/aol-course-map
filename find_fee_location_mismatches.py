import pandas as pd
import math
from collections import Counter

INPUT_CSV = "courses_for_map_final.csv"
OUTPUT_CSV = "fee_location_suspicious_review.csv"

# Nearby area radius
RADIUS_KM = 10

# Minimum nearby courses of same type needed before we trust local fee pattern
MIN_NEARBY_SAME_TYPE = 3

# Fee difference threshold
MIN_FEE_DIFFERENCE = 100


def clean(v):
    if pd.isna(v):
        return ""
    return str(v).strip()


def to_float(v):
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return None


def normalize_fee(v):
    v = clean(v)
    if not v:
        return None

    # Keep only digits and decimal point
    cleaned = ""
    for ch in v:
        if ch.isdigit() or ch == ".":
            cleaned += ch

    if not cleaned:
        return None

    try:
        return int(float(cleaned))
    except Exception:
        return None


def normalize_course_type(row):
    title = clean(row.get("title", "")).lower()
    ctype = clean(row.get("ctype", "")).lower()

    text = f"{title} {ctype}"

    if "rural" in text:
        return "rural_happiness_program"

    if "youth" in text:
        return "youth_happiness_program"

    if "happiness" in text:
        return "happiness_program"

    return title or ctype or "unknown"


def haversine_km(lat1, lon1, lat2, lon2):
    lat1 = to_float(lat1)
    lon1 = to_float(lon1)
    lat2 = to_float(lat2)
    lon2 = to_float(lon2)

    if None in [lat1, lon1, lat2, lon2]:
        return None

    r = 6371.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return r * c


def main():
    print("Reading:", INPUT_CSV)
    df = pd.read_csv(INPUT_CSV, dtype=str, keep_default_na=False)

    # Prepare working fields
    df["_lat"] = df["final_map_latitude"].apply(to_float)
    df["_lng"] = df["final_map_longitude"].apply(to_float)
    df["_fee"] = df["course_fee"].apply(normalize_fee)
    df["_course_type"] = df.apply(normalize_course_type, axis=1)

    valid = df[
        df["_lat"].notna()
        & df["_lng"].notna()
        & df["_fee"].notna()
        & (df["_fee"] > 0)
    ].copy()

    print("Total courses:", len(df))
    print("Courses with valid lat/lng/fee:", len(valid))

    review_rows = []

    records = valid.to_dict(orient="records")

    for course in records:
        course_id = clean(course.get("course_id", ""))
        course_type = clean(course.get("_course_type", ""))
        course_fee = course.get("_fee")
        lat = course.get("_lat")
        lng = course.get("_lng")

        nearby = []

        for other in records:
            other_id = clean(other.get("course_id", ""))

            if other_id == course_id:
                continue

            if clean(other.get("_course_type", "")) != course_type:
                continue

            other_fee = other.get("_fee")
            other_lat = other.get("_lat")
            other_lng = other.get("_lng")

            distance = haversine_km(lat, lng, other_lat, other_lng)

            if distance is None:
                continue

            if distance <= RADIUS_KM:
                nearby.append({
                    "course_id": other_id,
                    "fee": other_fee,
                    "distance": distance,
                    "city": clean(other.get("city", "")),
                    "pincode": clean(other.get("pincode", "")),
                    "address": clean(other.get("address", "")),
                })

        if len(nearby) < MIN_NEARBY_SAME_TYPE:
            continue

        fee_counts = Counter([n["fee"] for n in nearby if n["fee"] is not None])

        if not fee_counts:
            continue

        local_common_fee, common_count = fee_counts.most_common(1)[0]

        if course_fee == local_common_fee:
            continue

        fee_difference = abs(course_fee - local_common_fee)

        if fee_difference < MIN_FEE_DIFFERENCE:
            continue

        nearest_same_fee_count = sum(1 for n in nearby if n["fee"] == course_fee)

        # Stronger suspicion if most nearby same-type courses have the common fee
        common_fee_share = common_count / len(nearby)

        if common_fee_share < 0.6:
            severity = "review"
        else:
            severity = "likely_wrong_area_or_special_fee"

        nearest_examples = sorted(nearby, key=lambda x: x["distance"])[:5]
        examples_text = " | ".join(
            f"{e['course_id']} fee {e['fee']} at {round(e['distance'], 1)} km"
            for e in nearest_examples
        )

        review_rows.append({
            "course_id": course_id,
            "register_url": clean(course.get("register_url", "")),
            "title": clean(course.get("title", "")),
            "course_type": course_type,
            "address": clean(course.get("address", "")),
            "city": clean(course.get("city", "")),
            "pincode": clean(course.get("pincode", "")),
            "course_fee": int(course_fee),
            "local_common_fee": int(local_common_fee),
            "fee_difference": int(fee_difference),
            "nearby_same_type_count": len(nearby),
            "nearby_common_fee_count": common_count,
            "nearby_same_fee_count": nearest_same_fee_count,
            "common_fee_share": round(common_fee_share, 2),
            "radius_km": RADIUS_KM,
            "severity": severity,
            "notes": f"Course fee differs from most nearby same-type courses. Nearby examples: {examples_text}",

            # Manual-fix friendly columns
            "manual_latitude": "",
            "manual_longitude": "",
            "manual_status": "",
            "manual_notes": "",

            # Current location reference
            "current_latitude": clean(course.get("final_map_latitude", "")),
            "current_longitude": clean(course.get("final_map_longitude", "")),
            "current_google_maps_url": clean(course.get("final_google_maps_url", "")),
            "final_location_source": clean(course.get("final_location_source", "")),
        })

    out = pd.DataFrame(review_rows)

    columns = [
        "course_id",
        "register_url",
        "title",
        "course_type",
        "address",
        "city",
        "pincode",
        "course_fee",
        "local_common_fee",
        "fee_difference",
        "nearby_same_type_count",
        "nearby_common_fee_count",
        "nearby_same_fee_count",
        "common_fee_share",
        "radius_km",
        "severity",
        "notes",
        "manual_latitude",
        "manual_longitude",
        "manual_status",
        "manual_notes",
        "current_latitude",
        "current_longitude",
        "current_google_maps_url",
        "final_location_source",
    ]

    out = out.reindex(columns=columns)

    if not out.empty:
        out = out.sort_values(
            by=["severity", "fee_difference", "nearby_common_fee_count"],
            ascending=[True, False, False],
        )

    out.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print()
    print("DONE")
    print("Suspicious fee/location rows:", len(out))
    print("Saved:", OUTPUT_CSV)

    if not out.empty:
        print()
        print("Severity counts:")
        print(out["severity"].value_counts())

        print()
        print("Top 20:")
        print(out[[
            "course_id",
            "city",
            "pincode",
            "course_fee",
            "local_common_fee",
            "fee_difference",
            "nearby_same_type_count",
            "severity",
        ]].head(20))


if __name__ == "__main__":
    main()