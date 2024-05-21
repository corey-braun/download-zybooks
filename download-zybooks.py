#!/usr/bin/env python3
import sys
import argparse
import logging

from playwright.sync_api import sync_playwright, expect, Page, ElementHandle

#from authenticate import zybooks_logged_in


class AuthenticationError(Exception):
    pass

def slice_arg(arg: str) -> slice:
    return slice(*(int(x) if x else None for x in arg.split(':')))

def await_stable_html(page: Page, element: ElementHandle, poll_delay: int = 1000):
    """Ensure that a page element has reached a stable state
    by confirming its inner HTML is identical after poll_delay milliseconds."""
    html_previous = str()
    while True:
        html_current = element.inner_html()
        if html_current == html_previous:
            break
        logging.debug("Unstable!")
        html_previous = html_current
        page.wait_for_timeout(poll_delay)
    logging.debug("Stable.")

# Alternative to await_stable_html, currently unused
def await_stable_screenshot(page: Page, element: ElementHandle, poll_delay: int = 1000):
    """Ensure that a page element has reached a stable state
    by confirming a screenshot of it is identical after poll_delay milliseconds."""
    screenshot_previous = bytes()
    while True:
        screenshot_current = element.screenshot(animations='disabled', scale='css')
        if screenshot_current == screenshot_previous:
            break
        logging.debug("Unstable!")
        screenshot_previous = screenshot_current
        page.wait_for_timeout(poll_delay)
    logging.debug("Stable.")

def print_chapter(page: Page, url: str, file: str):
    page.goto(url)
    # Becomes actionable when we have recieved all data, but before we have rendered everything
    page.get_by_role("button", name="Print").first.click(trial=True, timeout=600000)
    for section in page.query_selector('.print-this').query_selector_all('.zybook-section'):
        logging.debug(section.query_selector('.zybook-section-title').text_content().strip())
        # Wait until we have finished rendering the section's content
        await_stable_html(page, section)
    page.pdf(path=file)

def print_zybook(page: Page, zybook_url: str, output_dir: str = '.', chapters_slice: slice = None) -> None:
    page.goto(zybook_url)
    #page.wait_for_timeout(5000)
    expect(page.locator('.table-of-contents')).to_be_visible()

    chapters = [
	    x.query_selector('.chapter-title').text_content().strip()
	    for x in page.locator('ul > li').element_handles()
    ]
    logging.debug(f'Chapters: {chapters}')
    base_url = page.url.rstrip('/')
    output_dir = output_dir.rstrip('/')

    # ElementHandle.inner_html and ElementHandle.screenshot may exceed the default timeout of 30s for large chapters.
    # These methods do not accept a 'timeout' parameter, so we must change the default timeout here.
    page.set_default_timeout(120000)

    sliced_chapters = chapters[chapters_slice] if chapters_slice else chapters
    for i in sliced_chapters:
        chapter_url = f'{base_url}/chapter/{chapters.index(i)+1}/print'
        file_name = f'{output_dir}/{i}.pdf'
        logging.debug(chapter_url)
        print_chapter(page, chapter_url, file_name)
        logging.debug(file_name)

def main():
    parser = argparse.ArgumentParser(description='Downloads zyBooks e-textbook chapters as PDFs')
    parser.add_argument('zybook_url', help='URL of the zyBooks textbook to download')
    parser.add_argument('-d', '--output-dir', default='output', help='The directory PDFs will be written to')
    parser.add_argument('--auth-file', default='.auth/state.json', help='Path to file storing authenticated session state')
    parser.add_argument('--no-headless', dest='headless', action='store_false', help='Do not run browser in headless mode')
    parser.add_argument('--chapters-slice', type=slice_arg, help='Slice object to limit what chapters should be printed')
    args = parser.parse_args()

    logging.basicConfig(
        stream=sys.stdout,
        format='%(asctime)s %(levelname)s - %(message)s',
        datefmt='%H:%M:%S',
#        level=logging.DEBUG
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=args.headless)
        context = browser.new_context(storage_state=args.auth_file)
        with context.new_page() as page:
            #if not zybooks_logged_in(page):
            #    raise AuthenticationError('Not logged in to zyBooks')
            print_zybook(
                page,
                args.zybook_url,
                args.output_dir,
                args.chapters_slice
            )

if __name__ == '__main__':
    main()
