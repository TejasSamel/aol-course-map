import requests
import pandas as pd
import math
import time
from datetime import date, timedelta

# -------------------------------------------------
# SETTINGS
# -------------------------------------------------

BASE_URL = "https://www.artofliving.org/new-search-course"

# Program filter from website:
# Happiness Program / OMBW
CTYPE_HP_OMBW = "313040,12371,338000,510212,74889,12519,56368,847760,337993,377155"

# Date range: today to 1 year later
FROM_DATE = date.today().isoformat()
TO_DATE = (date.today() + timedelta(days=365)).isoformat()

OUTPUT_CSV = "all_india_happiness_programs_offline.csv"
OUTPUT_JSON = "all_india_happiness_programs_offline.json"
RAW_JSON_CSV = "all_india_happiness_programs_raw.csv"

REQUEST_DELAY_SECONDS = 0.4
MAX_RETRIES = 3

all_courses = {}
raw_rows = []


# -------------------------------------------------
# API CALL
# -------------------------------------------------

def fetch_page(offset):
    """
    Fetch one page from AOL course API.
    offset here behaves like page number:
    offset=1, offset=2, offset=3...
    """

    params = {
        "ctype": CTYPE_HP_OMBW,
        "is_online_event": "0",
        "start-date-format": "02 Jan 2006",
        "end-date-format": "02 Jan 2006",
        "course_language": "",
        "lat": "",
        "lng": "",
        "distance": "30",
        "type": "country",
        "country": "in",
        "has_voucher": "0",
        "start_date_from": FROM_DATE,
        "start_date_to": TO_DATE,
        "start_time_from": "",
        "start_time_to": "",
        "include_private": "",
        "current_day_time_from": "0",
        "mode": "In Person",
        "offset": str(offset),
    }

    headers = {
        "accept": "*/*",
        "referer": "https://www.artofliving.org/in-en/search/course",
        "user-agent": "Mozilla/5.0",
    }

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                BASE_URL,
                params=params,
                headers=headers,
                timeout=30,
            )

            response.raise_for_status()
            return response.json(), response.url

        except Exception as e:
            last_error = e
            print(f"  Attempt {attempt} failed for offset={offset}: {e}")
            time.sleep(2)

    raise Exception(f"Failed offset={offset} after {MAX_RETRIES} attempts: {last_error}")


# -------------------------------------------------
# CLEANING HELPERS
# -------------------------------------------------

def safe_join(value):
    if isinstance(value, list):
        return ", ".join(str(x) for x in value if x is not None)
    return "" if value is None else str(value)


def get_unique_key(course):
    return (
        course.get("id")
        or course.get("sao_id")
        or course.get("course_id")
        or course.get("register_url")
    )


def normalize_course(course):
    coords = course.get("coordinates") or ["", ""]

    longitude = coords[0] if len(coords) > 0 else ""
    latitude = coords[1] if len(coords) > 1 else ""

    return {
        "id": course.get("id"),
        "sao_id": course.get("sao_id"),
        "course_id": course.get("course_id"),
        "ctype": course.get("ctype"),
        "mctype": course.get("mctype"),

        "title": course.get("title"),
        "start_date": course.get("start_date"),
        "end_date": course.get("end_date"),
        "weekday_timings": course.get("weekday_timings"),
        "weekend_timings": course.get("weekend_timings"),
        "timezone": course.get("timezone"),

        "city": course.get("city"),
        "center_name": course.get("center_name"),
        "state": course.get("state"),
        "country": course.get("country"),
        "pincode": course.get("zip_postal_code"),

        "address": course.get("address"),
        "address_short": course.get("address_short"),
        "street_address_1": course.get("street_address_1"),
        "street_address_2": course.get("street_address_2"),

        "latitude_from_api": latitude,
        "longitude_from_api": longitude,
        "wkt": course.get("wkt"),

        "contact_name": course.get("contact_name"),
        "phone": safe_join(course.get("phones")),
        "email": course.get("email"),
        "teachers": safe_join(course.get("teachers")),

        "course_fee": course.get("course_fee"),
        "currency": course.get("currency"),
        "language": safe_join(course.get("course_language")),

        "register_url": course.get("register_url"),
        "link": course.get("link"),
        "local_center_url": course.get("local_center_url"),

        "is_online_event": course.get("is_online_event"),
        "is_private": course.get("is_private"),
        "registration_required": course.get("registration_required"),
        "is_event_capacity_full": course.get("is_event_capacity_full"),

        "last_updated_date": course.get("last_updated_date"),
        "created_date": course.get("created_date"),
    }


def add_courses(data):
    courses = data.get("courses", [])

    for course in courses:
        raw_rows.append(course)

        # Safety filter: only offline / in-person
        try:
            if int(course.get("is_online_event", 1)) != 0:
                continue
        except Exception:
            continue

        unique_key = get_unique_key(course)
        if not unique_key:
            continue

        all_courses[unique_key] = normalize_course(course)

    return len(courses)


# -------------------------------------------------
# MAIN
# -------------------------------------------------

def main():
    print("Starting Art of Living India Happiness Program fetch...")
    print(f"Date range: {FROM_DATE} to {TO_DATE}")
    print("Mode: In Person only")
    print("Program: Happiness Program / OMBW")
    print()

    # First page tells us total and limit
    first_data, first_url = fetch_page(1)

    website_total = int(first_data.get("total", 0))
    limit = int(first_data.get("limit", 100))
    total_pages = math.ceil(website_total / limit) if limit else 1

    print(f"Website total: {website_total}")
    print(f"Limit per page: {limit}")
    print(f"Total pages: {total_pages}")
    print(f"First URL: {first_url}")
    print()

    count_page_1 = add_courses(first_data)
    print(f"Page 1/{total_pages}: {count_page_1} courses | unique saved: {len(all_courses)}")

    for page in range(2, total_pages + 1):
        try:
            data, url = fetch_page(page)
            count = add_courses(data)
            print(f"Page {page}/{total_pages}: {count} courses | unique saved: {len(all_courses)}")
            time.sleep(REQUEST_DELAY_SECONDS)

        except Exception as e:
            print(f"Page {page} failed completely: {e}")
            time.sleep(2)

    # Save cleaned unique courses
    df = pd.DataFrame(all_courses.values())

    if not df.empty:
        # Sort by date/title/city for readability
        sort_cols = [col for col in ["start_date", "city", "title"] if col in df.columns]
        if sort_cols:
            df = df.sort_values(by=sort_cols, na_position="last")

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    df.to_json(OUTPUT_JSON, orient="records", indent=2, force_ascii=False)

    # Also save raw rows for checking/debugging
    raw_df = pd.DataFrame(raw_rows)
    raw_df.to_csv(RAW_JSON_CSV, index=False, encoding="utf-8-sig")

    print()
    print("DONE")
    print(f"Website total: {website_total}")
    print(f"Raw rows downloaded: {len(raw_rows)}")
    print(f"Unique offline courses saved: {len(df)}")
    print("Saved:")
    print(f" - {OUTPUT_CSV}")
    print(f" - {OUTPUT_JSON}")
    print(f" - {RAW_JSON_CSV}")

    if not df.empty:
        print()
        print("Course type counts:")
        print(df["ctype"].value_counts())

        print()
        print("Top cities:")
        print(df["city"].value_counts().head(30))

        print()
        print("Sample:")
        sample_cols = [
            "title",
            "start_date",
            "end_date",
            "city",
            "pincode",
            "teachers",
            "phone",
            "register_url",
        ]
        sample_cols = [c for c in sample_cols if c in df.columns]
        print(df[sample_cols].head(20))

    # Warning if count mismatch is large
    if website_total and len(df) < website_total * 0.8:
        print()
        print("WARNING:")
        print("Saved count is much lower than website total.")
        print("This may mean pagination still needs adjustment or the API is returning duplicates/empty pages.")
        print("Check the printed page counts above.")


if __name__ == "__main__":
    main()