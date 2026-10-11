import requests
import os
import contextlib
import re
import copy
from bs4 import BeautifulSoup
from typing import Any
from datetime import datetime
from uuid import uuid4
from collections.abc import Generator
import dotenv
import pdfplumber
from icalendar import Calendar, Event


__TABLE_HEAD_RE__ = re.compile(r"^\w+, *([0-9]+)\. *(\w+) *([0-9]{4,4})$")
__TABLE_COURSE_RE__ = re.compile(r"^([0-9]+)\.$")
__COURSE_TIME_RE__ = re.compile(r"^([0-9]+):([0-9]+) *[-\u2013] *([0-9]+):([0-9]+)$")
__COURSE_NAME_RE__ = re.compile(r"^([\w\d()/\. ]+[\-\u2013\&]?)+$")


# Dont wanna mess with locales, so just Mapping all the months
def __MONTH_MAPPING__(month: str) -> int:
    match month.lower():
        case "januar":
            return 1
        case "februar":
            return 2
        case "märz":
            return 3
        case "april":
            return 4
        case "mai":
            return 5
        case "juni":
            return 6
        case "juli":
            return 7
        case "august":
            return 8
        case "september":
            return 9
        case "oktober":
            return 10
        case "november":
            return 11
        case "dezember":
            return 12


@contextlib.contextmanager
def download_as_tmp_file(url: str, filename_ext: str) -> Generator[str, None, None]:
    unique_name = f"{uuid4()}.{filename_ext}"
    try:
        with open(unique_name, mode="wb") as tmpfile:
            response = requests.get(url)
            response.raise_for_status()
            tmpfile.write(response.content)
        yield unique_name
    except Exception as e:
        if os.path.isfile(unique_name):
            os.remove(unique_name)
        raise e
    finally:
        if os.path.isfile(unique_name):
            os.remove(unique_name)


def parse_pdf_url(url: str) -> str:
    search_str = os.getenv("CALENDAR_PAGE_KEY", "")
    if search_str == "":
        return ""

    with download_as_tmp_file(url, "html") as tmpfile:
        with open(tmpfile, "r") as htmlf:
            s = BeautifulSoup(htmlf.read(), "lxml")
            for span in s.select("span"):
                if span.decode_contents() == search_str:
                    return span.parent.parent.get("href", "")


def get_course_entry(current_date: datetime, row: list[str]) -> dict[str, Any]:
    start = copy.deepcopy(current_date)
    end = copy.deepcopy(current_date)

    time_match = __COURSE_TIME_RE__.search(row[1])
    start = start.replace(hour=int(time_match.group(1)), minute=int(time_match.group(2)))
    end = end.replace(hour=int(time_match.group(3)), minute=int(time_match.group(4)))

    course = row[2]

    room = row[3]

    lecturer = row[4]

    return {
        "start": start,
        "end": end,
        "course": course,
        "room": room,
        "lecturer": lecturer
    }


def parse_courses(pdf_file: str) -> list[dict[str, Any]]:
    result = []

    current_date: datetime = None

    with pdfplumber.open(pdf_file) as pdf:
        for i, page in enumerate(pdf.pages):
            for table in page.extract_tables():
                for row in table:
                    if len(row) == 0:
                        continue

                    table_head_match: re.Match = __TABLE_HEAD_RE__.search(row[0].strip())
                    table_course_match: re.Match = __TABLE_COURSE_RE__.search(row[0].strip())
                    if table_head_match:
                        year = int(table_head_match.group(3))
                        month = __MONTH_MAPPING__(table_head_match.group(2))
                        day = int(table_head_match.group(1))
                        current_date = datetime(year=year, month=month, day=day)
                    elif table_course_match and len(row) > 4:
                        # skip second row in table, if two rows are merged for one course
                        # also skip empty or redacted rows
                        if row[1] is None or not __COURSE_NAME_RE__.match(row[2]):
                            continue
                        result.append(get_course_entry(current_date, row))
                    elif len(row) > 1 and row[1].lower() == "uhrzeit":
                        # this is just to recognize parsing issues --> match every row and assert if any row could not be parsed
                        pass
                    else:
                        raise ValueError(f"Could not parse table, unknown row \"{row}\"")

    return result


@contextlib.contextmanager
def create_ics(courses: list[str, Any]) -> Generator[str, None, None]:
    unique_name = f"{uuid4()}.ics"

    try:
        cal = Calendar()
        for course in courses:
            cal.add_component(Event.new(
                summary=course["course"],
                description=f"Room: {course['room']}; Lect: {course['lecturer']}",
                start=course["start"],
                end=course["end"]
            ))
        with open(unique_name, "wb") as file:
            file.write(cal.to_ical())
        yield unique_name
    except Exception as e:
        if os.path.isfile(unique_name):
            os.remove(unique_name)
        raise e
    finally:
        if os.path.isfile(unique_name):
            os.remove(unique_name)


def push_ics_to_caldav(ics_file: str):
    username = "public"
    url = f"{os.getenv("CALDAV_URL", None)}/public/calendar"
    password = os.getenv("CALDAV_PASSWORD", None)

    with open(ics_file, 'rb') as file:
        headers = {
            "Content-Type":"text/calendar",
        }
        session = requests.Session()
        session.auth = (username, password)
        response = session.put(url, data=file.read(), headers=headers)
        response.raise_for_status()
        print("Uploaded ics to caldav server.")


if __name__ == "__main__":
    try:
        dotenv.load_dotenv()
        pdf_url = os.getenv("CALENDAR_URL", "")
        if pdf_url == "":
            pdf_url = parse_pdf_url(os.getenv("CALENDAR_PAGE_URL", ""))

        with download_as_tmp_file(pdf_url, "pdf") as pdf_file:
            courses = parse_courses(pdf_file)
        with create_ics(courses) as ics_file:
            push_ics_to_caldav(ics_file)
    except Exception as e:
        print(f"Script failed with error: {e}")
