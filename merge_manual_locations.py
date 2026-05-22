import os
import pandas as pd

# ---------------- SETTINGS ----------------

INPUT_COURSES_CSV = "courses_for_map.csv"
MANUAL_FIXES_CSV = "manual_location_fixes.csv"

OUTPUT_CSV = "courses_for_map_final.csv"
OUTPUT_JSON = "courses_for_map_final.json"


# ---------------- HELPERS ----------------

def clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def has_manual_coordinates(row):
    lat = clean(row.get("manual_latitude", ""))
    lng = clean(row.get("manual_longitude", ""))

    try:
        float(lat)
        float(lng)
        return True
    except Exception:
        return False


def build_manual_key(row):
    course_id = clean(row.get("course_id", ""))

    if course_id:
        return "course_id:" + course_id

    return ""


def main():
    if not os.path.exists(INPUT_COURSES_CSV):
        raise FileNotFoundError(f"Missing {INPUT_COURSES_CSV}")

    if not os.path.exists(MANUAL_FIXES_CSV):
        raise FileNotFoundError(f"Missing {MANUAL_FIXES_CSV}")

    courses = pd.read_csv(INPUT_COURSES_CSV)
    manual = pd.read_csv(MANUAL_FIXES_CSV)

    # Ensure manual columns exist
    required_manual_cols = [
        "course_id",
        "manual_latitude",
        "manual_longitude",
        "notes",
    ]

    for col in required_manual_cols:
        if col not in manual.columns:
            manual[col] = ""

    manual["manual_key"] = manual.apply(build_manual_key, axis=1)

    manual = manual[manual["manual_key"].astype(str).str.strip() != ""].copy()

    if manual.empty:
        manual_verified = pd.DataFrame(columns=list(manual.columns))
        manual_lookup = {}
    else:
        manual["has_manual_coordinates"] = manual.apply(has_manual_coordinates, axis=1)
        manual_verified = manual[manual["has_manual_coordinates"]].copy()

        if manual_verified.empty:
            manual_lookup = {}
        else:
            manual_verified = manual_verified.drop_duplicates(
                subset=["manual_key"],
                keep="last"
            )
            manual_lookup = manual_verified.set_index("manual_key").to_dict(orient="index")
    final_lats = []
    final_lngs = []
    final_sources = []
    final_urls = []
    manual_notes = []
    manual_statuses = []

    manual_applied = 0

    for _, row in courses.iterrows():
        key = build_manual_key(row)

        if key in manual_lookup:
            fix = manual_lookup[key]

            lat = clean(fix.get("manual_latitude", ""))
            lng = clean(fix.get("manual_longitude", ""))
            url = clean(fix.get("manual_google_maps_url", ""))
            status = "verified"
            notes = clean(fix.get("notes", ""))

            final_lats.append(lat)
            final_lngs.append(lng)
            final_sources.append("manual_verified")
            final_urls.append(url or f"https://www.google.com/maps?q={lat},{lng}")
            manual_notes.append(notes)
            manual_statuses.append(status)

            manual_applied += 1

        else:
            lat = clean(row.get("final_map_latitude", ""))
            lng = clean(row.get("final_map_longitude", ""))
            source = clean(row.get("final_location_source", ""))

            final_lats.append(lat)
            final_lngs.append(lng)
            final_sources.append(source or "existing_final")
            final_urls.append(
                f"https://www.google.com/maps?q={lat},{lng}"
                if lat and lng
                else ""
            )
            manual_notes.append("")
            manual_statuses.append("")

    courses["final_map_latitude"] = final_lats
    courses["final_map_longitude"] = final_lngs
    courses["final_location_source"] = final_sources
    courses["final_google_maps_url"] = final_urls
    courses["manual_status_applied"] = manual_statuses
    courses["manual_notes_applied"] = manual_notes

    courses.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    courses.to_json(OUTPUT_JSON, orient="records", indent=2, force_ascii=False)

    print("DONE")
    print(f"Courses loaded: {len(courses)}")
    print(f"Manual verified fixes available: {len(manual_verified)}")
    print(f"Manual fixes applied: {manual_applied}")
    print("Saved:")
    print(f" - {OUTPUT_CSV}")
    print(f" - {OUTPUT_JSON}")

    print()
    print("Final location source counts:")
    print(courses["final_location_source"].value_counts(dropna=False))


if __name__ == "__main__":
    main()