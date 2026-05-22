import pandas as pd
import json
from pathlib import Path

# -------------------------------------------------
# SETTINGS
# -------------------------------------------------

INPUT = Path("all_india_happiness_programs_offline.csv")

OUT_CSV = Path("courses_for_map.csv")
OUT_JSON = Path("courses_for_map.json")
OUT_SUMMARY = Path("courses_for_map_summary.txt")


# -------------------------------------------------
# HELPERS
# -------------------------------------------------

def clean_text(v):
    if pd.isna(v):
        return ""
    return str(v).strip()


def clean_int_like(v):
    if pd.isna(v) or v == "":
        return ""

    try:
        f = float(v)
        if f.is_integer():
            return str(int(f))
    except Exception:
        pass

    return str(v).strip()


def google_maps_url(lat, lng):
    if pd.isna(lat) or pd.isna(lng):
        return ""

    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except Exception:
        return ""

    return f"https://www.google.com/maps?q={lat_f},{lng_f}"


def map_label(row):
    bits = [
        row.get("title", ""),
        row.get("city", ""),
        row.get("start_date", ""),
    ]

    return " | ".join([clean_text(x) for x in bits if clean_text(x)])


def popup_html(row):
    title = clean_text(row.get("title"))
    date = " - ".join([
        x for x in [
            clean_text(row.get("start_date")),
            clean_text(row.get("end_date")),
        ]
        if x
    ])

    timings = clean_text(row.get("weekday_timings")) or clean_text(row.get("weekend_timings"))
    address = clean_text(row.get("address"))
    teachers = clean_text(row.get("teachers"))
    phone = clean_text(row.get("phone"))
    register_url = clean_text(row.get("register_url"))

    html = f"<strong>{title}</strong>" if title else "<strong>Happiness Program</strong>"

    if date:
        html += f"<br>Date: {date}"

    if timings:
        html += f"<br>Time: {timings}"

    if address:
        html += f"<br>Address: {address}"

    if teachers:
        html += f"<br>Teacher(s): {teachers}"

    if phone:
        html += f"<br>Phone: {phone}"

    if register_url:
        html += f'<br><a href="{register_url}" target="_blank">Register</a>'

    return html


# -------------------------------------------------
# MAIN
# -------------------------------------------------

def main():
    if not INPUT.exists():
        raise FileNotFoundError(
            f"Missing input file: {INPUT}\n"
            "First run: python fetch_all_india_hp.py"
        )

    print(f"Reading: {INPUT}")

    # Read as string first, then numeric lat/lng separately.
    # This avoids phone/pincode becoming 1.23E+09.
    df = pd.read_csv(INPUT, dtype=str, keep_default_na=False)

    # Make numeric coords safely.
    df["map_latitude"] = pd.to_numeric(df.get("latitude_from_api", ""), errors="coerce")
    df["map_longitude"] = pd.to_numeric(df.get("longitude_from_api", ""), errors="coerce")

    # Coordinate sanity check for India-ish bounds.
    df["coordinate_status"] = "ok"

    df.loc[
        df["map_latitude"].isna() | df["map_longitude"].isna(),
        "coordinate_status"
    ] = "missing"

    df.loc[
        (df["coordinate_status"] == "ok") &
        (~df["map_latitude"].between(6, 38)),
        "coordinate_status"
    ] = "check"

    df.loc[
        (df["coordinate_status"] == "ok") &
        (~df["map_longitude"].between(68, 98)),
        "coordinate_status"
    ] = "check"

    # Clean common fields.
    text_columns = [
        "id",
        "sao_id",
        "course_id",
        "ctype",
        "mctype",
        "title",
        "start_date",
        "end_date",
        "weekday_timings",
        "weekend_timings",
        "timezone",
        "city",
        "center_name",
        "state",
        "country",
        "pincode",
        "address",
        "address_short",
        "street_address_1",
        "street_address_2",
        "contact_name",
        "phone",
        "email",
        "teachers",
        "course_fee",
        "currency",
        "language",
        "register_url",
        "link",
        "local_center_url",
        "is_online_event",
        "is_private",
        "registration_required",
        "is_event_capacity_full",
        "last_updated_date",
        "created_date",
    ]

    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].apply(clean_text)

    for col in ["id", "sao_id", "course_id", "pincode", "phone"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_int_like)

    # Add map/useful fields.
    df["google_maps_url"] = [
        google_maps_url(lat, lng)
        for lat, lng in zip(df["map_latitude"], df["map_longitude"])
    ]

    df["map_label"] = df.apply(map_label, axis=1)
    df["map_popup_html"] = df.apply(popup_html, axis=1)

    df["coordinate_source"] = "aol_api_coordinates_lng_lat_converted_to_lat_lng"
    df["coordinate_note"] = (
        "API provided coordinates in [longitude, latitude] order. "
        "map_latitude/map_longitude are converted for Google Maps and Leaflet."
    )

    # These are the initial final coordinates before OpenCage/manual corrections.
    # Later scripts can override these.
    df["final_map_latitude"] = df["map_latitude"]
    df["final_map_longitude"] = df["map_longitude"]
    df["final_location_source"] = "aol_api_fallback"
    df["final_google_maps_url"] = df["google_maps_url"]

    # Put map columns first.
    preferred = [
        "id",
        "sao_id",
        "course_id",
        "title",
        "start_date",
        "end_date",
        "weekday_timings",
        "weekend_timings",
        "timezone",
        "city",
        "center_name",
        "state",
        "country",
        "pincode",
        "address",
        "address_short",
        "street_address_1",
        "street_address_2",
        "map_latitude",
        "map_longitude",
        "google_maps_url",
        "final_map_latitude",
        "final_map_longitude",
        "final_location_source",
        "final_google_maps_url",
        "coordinate_status",
        "coordinate_source",
        "coordinate_note",
        "teachers",
        "contact_name",
        "phone",
        "email",
        "course_fee",
        "currency",
        "language",
        "register_url",
        "link",
        "local_center_url",
        "ctype",
        "mctype",
        "is_online_event",
        "is_private",
        "registration_required",
        "is_event_capacity_full",
        "last_updated_date",
        "created_date",
        "map_label",
        "map_popup_html",
    ]

    cols = (
        [c for c in preferred if c in df.columns]
        + [
            c for c in df.columns
            if c not in preferred
            and c not in ["latitude_from_api", "longitude_from_api"]
        ]
    )

    map_df = df[cols]

    # Sort for usability.
    if "start_date" in map_df.columns:
        sort_dates = pd.to_datetime(map_df["start_date"], format="%d %b %Y", errors="coerce")
        map_df = (
            map_df.assign(_sort_date=sort_dates)
            .sort_values(
                ["_sort_date", "city", "title"],
                na_position="last"
            )
            .drop(columns=["_sort_date"])
        )

    # Save files.
    map_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    records = map_df.where(pd.notnull(map_df), None).to_dict(orient="records")
    OUT_JSON.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    summary = []
    summary.append(f"Total map rows: {len(map_df)}")
    summary.append(f"Coordinate status counts: {map_df['coordinate_status'].value_counts(dropna=False).to_dict()}")

    if "address" in map_df.columns:
        summary.append(f"Unique addresses: {map_df['address'].nunique()}")

    summary.append(
        "Unique coordinate pairs: "
        f"{map_df[['map_latitude', 'map_longitude']].drop_duplicates().shape[0]}"
    )

    summary.append("")
    summary.append("Output files:")
    summary.append(str(OUT_CSV))
    summary.append(str(OUT_JSON))
    summary.append("")
    summary.append("Use final_map_latitude/final_map_longitude for the website map.")
    summary.append("Do NOT use original [longitude, latitude] order directly in Google Maps.")

    OUT_SUMMARY.write_text("\n".join(summary), encoding="utf-8")

    print()
    print("\n".join(summary))


if __name__ == "__main__":
    main()