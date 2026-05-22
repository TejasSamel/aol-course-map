import pandas as pd
import math

COURSES_CSV = "courses_for_map_final.csv"
PINCODE_CSV = "india_pincodes.csv"
OUTPUT_CSV = "pincode_mismatch_review.csv"

# Distance thresholds
GOOD_KM = 20
REVIEW_KM = 50


def clean(v):
    if pd.isna(v):
        return ""
    return str(v).strip()


def normalize_pincode(v):
    v = clean(v)
    v = "".join(ch for ch in v if ch.isdigit())
    if len(v) == 6:
        return v
    return ""


def to_float(v):
    try:
        return float(v)
    except Exception:
        return None


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


def find_column(df, possible_names):
    lower_map = {c.lower().strip(): c for c in df.columns}

    for name in possible_names:
        key = name.lower().strip()
        if key in lower_map:
            return lower_map[key]

    for col in df.columns:
        col_l = col.lower().strip()
        for name in possible_names:
            if name.lower().strip() in col_l:
                return col

    return None


def main():
    print("Reading:", COURSES_CSV)
    courses = pd.read_csv(COURSES_CSV, dtype=str, keep_default_na=False)

    print("Reading:", PINCODE_CSV)
    pins = pd.read_csv(PINCODE_CSV, dtype=str, keep_default_na=False)

    pin_col = find_column(pins, ["pincode", "pin", "postal_code", "postalcode", "zip"])
    lat_col = find_column(pins, ["latitude", "lat"])
    lng_col = find_column(pins, ["longitude", "lng", "lon", "long"])

    if not pin_col:
        raise RuntimeError("Could not find pincode column in india_pincodes.csv")

    if not lat_col or not lng_col:
        raise RuntimeError("Could not find latitude/longitude columns in india_pincodes.csv")

    print("Detected pincode column:", pin_col)
    print("Detected latitude column:", lat_col)
    print("Detected longitude column:", lng_col)

    pins["pincode_clean"] = pins[pin_col].apply(normalize_pincode)
    pins["pin_lat"] = pd.to_numeric(pins[lat_col], errors="coerce")
    pins["pin_lng"] = pd.to_numeric(pins[lng_col], errors="coerce")

    pins = pins[
        (pins["pincode_clean"] != "")
        & pins["pin_lat"].notna()
        & pins["pin_lng"].notna()
    ].copy()

    # If multiple rows exist for same pincode, use average coordinate.
    pin_ref = (
        pins.groupby("pincode_clean", as_index=False)
        .agg(
            pincode_latitude=("pin_lat", "mean"),
            pincode_longitude=("pin_lng", "mean"),
        )
    )

    pin_lookup = pin_ref.set_index("pincode_clean").to_dict(orient="index")

    review_rows = []

    for _, row in courses.iterrows():
        course_pin = normalize_pincode(row.get("pincode", ""))

        if not course_pin:
            continue

        if course_pin not in pin_lookup:
            review_rows.append({
                "course_id": clean(row.get("course_id", "")),
                "register_url": clean(row.get("register_url", "")),
                "title": clean(row.get("title", "")),
                "address": clean(row.get("address", "")),
                "city": clean(row.get("city", "")),
                "pincode": course_pin,

                "manual_latitude": "",
                "manual_longitude": "",
                "manual_google_maps_url": "",
                "manual_status": "",
                "notes": "Pincode not found in india_pincodes.csv",

                "current_latitude": clean(row.get("final_map_latitude", "")),
                "current_longitude": clean(row.get("final_map_longitude", "")),
                "current_google_maps_url": clean(row.get("final_google_maps_url", "")),
                "pincode_latitude": "",
                "pincode_longitude": "",
                "distance_from_pincode_km": "",
                "severity": "pincode_missing",
            })
            continue

        course_lat = clean(row.get("final_map_latitude", ""))
        course_lng = clean(row.get("final_map_longitude", ""))

        p_lat = pin_lookup[course_pin]["pincode_latitude"]
        p_lng = pin_lookup[course_pin]["pincode_longitude"]

        distance = haversine_km(course_lat, course_lng, p_lat, p_lng)

        if distance is None:
            review_rows.append({
                "course_id": clean(row.get("course_id", "")),
                "register_url": clean(row.get("register_url", "")),
                "title": clean(row.get("title", "")),
                "address": clean(row.get("address", "")),
                "city": clean(row.get("city", "")),
                "pincode": course_pin,

                "manual_latitude": "",
                "manual_longitude": "",
                "manual_google_maps_url": "",
                "manual_status": "",
                "notes": "Missing or invalid course coordinate",

                "current_latitude": course_lat,
                "current_longitude": course_lng,
                "current_google_maps_url": clean(row.get("final_google_maps_url", "")),
                "pincode_latitude": p_lat,
                "pincode_longitude": p_lng,
                "distance_from_pincode_km": "",
                "severity": "missing_coordinate",
            })
            continue

        if distance <= GOOD_KM:
            continue

        if distance <= REVIEW_KM:
            severity = "review"
            notes = f"Course marker is {round(distance, 1)} km from pincode center"
        else:
            severity = "likely_wrong"
            notes = f"Course marker is {round(distance, 1)} km from pincode center"

        review_rows.append({
            # SAME COLUMNS AS manual_location_fixes.csv
            "course_id": clean(row.get("course_id", "")),
            "register_url": clean(row.get("register_url", "")),
            "title": clean(row.get("title", "")),
            "address": clean(row.get("address", "")),
            "city": clean(row.get("city", "")),
            "pincode": course_pin,

            "manual_latitude": "",
            "manual_longitude": "",
            "manual_google_maps_url": "",
            "manual_status": "",
            "notes": notes,

            # EXTRA REVIEW COLUMNS
            "current_latitude": course_lat,
            "current_longitude": course_lng,
            "current_google_maps_url": clean(row.get("final_google_maps_url", "")),
            "pincode_latitude": p_lat,
            "pincode_longitude": p_lng,
            "distance_from_pincode_km": round(distance, 2),
            "severity": severity,
        })

    columns = [
        # Same as manual_location_fixes.csv
        "course_id",
        "register_url",
        "title",
        "address",
        "city",
        "pincode",
        "manual_latitude",
        "manual_longitude",
        "manual_google_maps_url",
        "manual_status",
        "notes",

        # Review columns
        "current_latitude",
        "current_longitude",
        "current_google_maps_url",
        "pincode_latitude",
        "pincode_longitude",
        "distance_from_pincode_km",
        "severity",
    ]

    out = pd.DataFrame(review_rows)
    out = out.reindex(columns=columns)

    # Sort worst first
    if not out.empty:
        out["_sort_distance"] = pd.to_numeric(out["distance_from_pincode_km"], errors="coerce")
        out = out.sort_values(
            by=["severity", "_sort_distance"],
            ascending=[True, False],
            na_position="last"
        ).drop(columns=["_sort_distance"])

    out.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print()
    print("DONE")
    print("Total courses:", len(courses))
    print("Pincodes in reference file:", len(pin_ref))
    print("Rows needing pincode review:", len(out))
    print("Saved:", OUTPUT_CSV)

    if not out.empty:
        print()
        print("Severity counts:")
        print(out["severity"].value_counts(dropna=False))

        print()
        print("Top 20 farthest:")
        print(out[[
            "course_id",
            "city",
            "pincode",
            "distance_from_pincode_km",
            "severity",
            "address",
        ]].head(20))


if __name__ == "__main__":
    main()