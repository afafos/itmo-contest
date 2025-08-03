import requests
import re
from bs4 import BeautifulSoup
import json
import PyPDF2
import io


def fetch_webpage(url: str) -> BeautifulSoup | None:
    try:
        response = requests.get(url)
        response.raise_for_status()
        return BeautifulSoup(response.content, "html.parser")
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None


def extract_next_data(soup: BeautifulSoup) -> dict | None:
    next_data_element = soup.find("script", {"id": "__NEXT_DATA__"})
    if not next_data_element:
        print("Could not find __NEXT_DATA__ element")
        return None

    try:
        return json.loads(next_data_element.string)
    except json.JSONDecodeError as e:
        print(f"Error parsing __NEXT_DATA__ JSON: {e}")
        return None


def extract_program_id(next_data: dict) -> int | None:
    try:
        program_id = next_data["props"]["pageProps"]["apiProgram"]["id"]
        print(f"Found program ID: {program_id}")
        return program_id
    except KeyError as e:
        print(f"Could not find program ID in __NEXT_DATA__: {e}")
        return None


def download_pdf(program_id: int) -> bytes | None:
    pdf_url = f"https://api.itmo.su/constructor-ep/api/v1/static/programs/{program_id}/plan/abit/pdf"
    print(f"Downloading PDF from: {pdf_url}")

    try:
        response = requests.get(pdf_url)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        print(f"Error downloading PDF: {e}")
        return None


def parse_pdf_content(pdf_bytes: bytes) -> str | None:
    try:
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)

        text_content = ""
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text_content += page.extract_text() + "\n"

        return text_content.strip()
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        return None


def parse_courses_from_pdf_text(pdf_text: str) -> list[dict]:
    """
    Parses the text content of a curriculum PDF to extract course information.
    This version handles poorly formatted text where spaces might be missing.
    """
    # Step 1: Pre-process the text to insert spaces where they are likely missing.
    # Insert space between a number and a letter (e.g., "1Воркшоп" -> "1 Воркшоп")
    processed_text = re.sub(r"(\d)([а-яА-Яa-zA-Z])", r"\1 \2", pdf_text)
    # Insert space between a letter and a number (e.g., "Workshop3108" -> "Workshop 3108")
    processed_text = re.sub(r"([а-яА-Яa-zA-Z/])(\d)", r"\1 \2", processed_text)

    courses = []

    # Step 2: Use a robust regex to find lines that are likely courses.
    course_pattern = re.compile(
        # Group 'semester': Captures '1, 2, 3' or single digits '1'-'4'
        # Group 'name': Captures the course name in a non-greedy way
        # Group 'numbers': Captures the block of digits for credits/hours at the end
        r"^(?P<semester>1, 2, 3|[1-4])\s+(?P<name>.+?)\s+(?P<numbers>\d{2,5})\s*$",
        re.MULTILINE,
    )

    # Keywords to identify and filter out header lines that might match the pattern.
    ignore_phrases = [
        "пул выборных дисциплин",
        "обязательные дисциплины",
        "блок",
        "практика",
        "гиа",
        "факультативные",
        "универсальная",
        "мировоззренческий",
        "аспирантский трек",
        "soft skills",
        "иностранный язык",
        "семестр",
        "магистратура/аспирантура",
        "мышление",
        "креативные технологии",
        "предпринимательская культура",
        "история и философия науки",
    ]

    for match in course_pattern.finditer(processed_text):
        data = match.groupdict()

        semester_str = data["semester"].strip()
        course_name = (
            data["name"].strip().replace("\n", " ")
        )  # Clean up any embedded newlines
        numbers_str = data["numbers"].strip()

        # Filter out headers
        if any(phrase in course_name.lower() for phrase in ignore_phrases):
            continue

        if int(numbers_str) == 0:
            continue

        credits, hours = 0, 0

        try:
            # Step 3: Split the credit/hour numbers based on their total length
            if len(numbers_str) == 5:  # e.g., "12432" -> 12 credits, 432 hours
                credits = int(numbers_str[:2])
                hours = int(numbers_str[2:])
            elif len(numbers_str) == 4:  # e.g., "3108" -> 3 credits, 108 hours
                credits = int(numbers_str[0])
                hours = int(numbers_str[1:])
            elif len(numbers_str) == 3:  # e.g., "136" -> 1 credit, 36 hours
                credits = int(numbers_str[0])
                hours = int(numbers_str[1:])

            # Final sanity check on parsed values
            if credits > 0 and credits < 30 and hours > 0:
                courses.append(
                    {
                        "name": course_name,
                        "semester": semester_str,
                        "credits": credits,
                        "hours": hours,
                    }
                )
        except (ValueError, IndexError):
            # Ignore lines where number parsing fails
            continue

    print(f"Successfully parsed {len(courses)} courses from the PDF.")
    return courses


def extract_program_name(soup: BeautifulSoup) -> str | None:
    try:
        h1_element = soup.find("h1")
        if h1_element:
            return h1_element.text.strip()
        return None
    except Exception as e:
        print(f"Error extracting program name: {e}")
        return None


def scrape_program_data(url: str) -> dict | None:
    soup = fetch_webpage(url)
    if not soup:
        return None

    program_name = extract_program_name(soup)
    if not program_name:
        print(f"Could not extract program name from {url}")
        return None

    next_data = extract_next_data(soup)
    if not next_data:
        return None

    program_id = extract_program_id(next_data)
    if not program_id:
        return None

    pdf_bytes = download_pdf(program_id)
    if not pdf_bytes:
        return None

    pdf_content = parse_pdf_content(pdf_bytes)
    if not pdf_content:
        print("Warning: Could not extract text from PDF content")
        courses = []
    else:
        courses = parse_courses_from_pdf_text(pdf_content)

    return {
        "program_name": program_name,
        "program_id": program_id,
        "courses": courses,
    }


def save_data_to_json(data: dict, filename: str = "itmo_programs.json") -> bool:
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Data saved to {filename}")
        return True
    except Exception as e:
        print(f"Error saving data to {filename}: {e}")
        return False


def main():
    urls = [
        "https://abit.itmo.ru/program/master/ai",
        "https://abit.itmo.ru/program/master/ai_product",
    ]

    all_data = {}
    for url in urls:
        program_key = url.split("/")[-1]
        print(f"\nProcessing: {url}")
        data = scrape_program_data(url)
        if data:
            all_data[program_key] = data
        else:
            print(f"Failed to scrape data from {url}")

    if all_data:
        save_data_to_json(all_data)
    else:
        print("No data was successfully scraped")


if __name__ == "__main__":
    main()
