# MangaScraper v1.0 Created by UltraViolet
# A command line based manga scraper that (currently) pulls from mangareader.net
# Written in Python 3.7
# Required libraries:
#   BeautifulSoup4
#   Pillow (also knows as PIL or Python Imaging Library)

from requests import get
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
from contextlib import closing
from typing import Optional, List
import shutil
import os
from PIL import Image


# following functions take url and output the raw html if possible
def simple_get(url: str) -> Optional[str]:
    """Attempts to pull content at 'url' by making an HTTP GET request. If
    content-type is some kind of HTML/XML, returns the text content, otherwise
    returns None.
    """
    try:
        # closing is used to ensure any network resources are freed when
        # they go out of scope in the with block
        with closing(get(url, stream=True)) as resp:
            if is_good_response(resp):

                # this should be the raw html content
                return resp.content
            else:
                return None
    except RequestException as e:
        log_error(f'Error during requests to {url} : {str(e)}')
        return None


def is_good_response(resp) -> bool:
    """
    Returns True if <resp> seems to be HTML, False otherwise.
    """
    content_type = resp.headers['Content-Type'].lower()
    return (resp.status_code == 200
            and content_type is not None
            and content_type.find('html') > -1)


def log_error(e):
    """Logs the error by printing it. This method was plagiarised from the
    web scraping tutorial
    """
    print(e)


def img_source(url: str) -> (str, str):
    """
    extracts and return image url for current page and link to next page

    Precondition: <url> must be valid mangareader.net page url
    """
    # creates a BeautifulSoup object for easy traversal of the html content
    html = BeautifulSoup(simple_get(url), 'html.parser')

    # finds the imgholder tag with the link to the next page + current page url
    img_tag = html.find(id='imgholder')

    # pulls out the src attribute of the img tag inside the hyperlink
    # accessing the .a attribute is a bit risky, no idea how it could fuck up
    img_url = img_tag.a.contents[0].attrs['src']
    # next_page_url = 'http://www.mangareader.net' + img_tag.a.attrs['href']

    return img_url


def save_page(url: str, file_name: str, folder_path: str) -> None:
    """
    Saves image to a specified folder. If folder does not exist, will create it

    <folder_path> is of format "{manga name}"
    files are always saved in format "{manga_name} ch{chapter}-{page}.jpeg"
        example: "One Piece ch35-4.jpeg"
    """
    img_url = img_source(url)

    # gets the image file from given url
    response = get(img_url, stream=True)

    # if manga folder does not exist, creates it
    if folder_path not in os.listdir(os.getcwd() + '\\Downloads'):
        os.mkdir(f'Downloads\\{folder_path}')
        os.mkdir(f'Downloads\\{folder_path}\\raws')
        os.mkdir(f'Downloads\\{folder_path}\\PDFs')

    with open(f'Downloads\\{folder_path}\\raws\\{file_name}.jpg',
              'wb') as out_file:
        shutil.copyfileobj(response.raw, out_file)
    del response


def manga_name_to_url(manga_name: str) -> str:
    """
    takes in manga names and converts them to format for mangareader.net urls

    >>> manga_name_to_url("LET'S TAKE THE TRAIN TOGETHER, SHALL WE?")
    'lets-take-the-train-together-shall-we'

    >>> manga_name_to_url('+C SWORD AND CORNETT')
    'c-sword-and-cornett'

    >>> manga_name_to_url('LIAN AI 1/2')
    'lian-ai-12'

    >>> manga_name_to_url('A+B')
    'ab'

    >>> manga_name_to_url('15-SAI (ASAGI RYUU)')
    '15-sai-asagi-ryuu'
    """
    formatted_name = ''

    for char in manga_name:
        if char.isalnum():
            formatted_name += char.lower()
        elif char == ' ' or char == '-':
            formatted_name += '-'

    return formatted_name


def create_pdf(manga_name: str, chapter: int) -> None:
    """
    Creates pdf out of existing .jpeg images and saves to PDFs folder in
    respective manga's folder

    Precondition: 1. manga raws exist in correct folder
    2. files are saved in format "{manga_name} ch{chapter}-{page_number}"
    """
    raws_path = f'Downloads\\{manga_name}\\raws'
    pdf_path = f'Downloads\\{manga_name}\\PDFs'
    image_list = []

    # opens and appends pages to list
    for file_name in os.listdir(raws_path):
        if f' ch{chapter}-' in file_name:
            # done for sorting reasons because python sorting is stupid
            pg_number = int(file_name[file_name.index(f'ch{chapter}-') + 4: file_name.index('.jpg')])
            pg_image_tuple = (pg_number, Image.open(f'{raws_path}\\{file_name}'))

            image_list.append(pg_image_tuple)

    # sorts image_list by page number correctly
    image_list.sort(key=get_key)

    # converts each image and adds to convert list
    converted_list = []
    for i in range(len(image_list)):
        converted_list.append(image_list[i][1].convert('RGB'))

    first_page = converted_list.pop(0)
    first_page.save(f'{pdf_path}\\{manga_name} ch{chapter}.pdf', save_all=True, append_images=converted_list)

    print(f'All done! Chapter {chapter} of {manga_name} has been saved as pdf!')


def get_key(item):
    """
    helper to sort raw images by page number correctly
    """
    return item[0]


def get_page_links(url: str) -> List[str]:
    """
    url is a page of a manga on mangareader.net. Returns a list of links to the
    pages of the given manga chapter
    """
    html = BeautifulSoup(simple_get(url), 'html.parser')
    page_menu = html.find(id='pageMenu')
    page_links = []

    for i in range(len(page_menu.contents)):
        if page_menu.contents[i] != '\n':
            page_links.append('http://www.mangareader.net' + page_menu.contents[i].attrs['value'])

    return page_links


def save_chapter(manga_name: str, chapter: int) -> None:
    """
    Downloads and saves appropriate chapter in pdf form in correct location
    """
    m_name_url = manga_name_to_url(manga_name)
    first_page_url = f'http://www.mangareader.net/{m_name_url}/{chapter}'

    if validity_checker(first_page_url, manga_name, chapter) is False:
        return None

    page_links = get_page_links(first_page_url)

    # saves all pages in chapter
    page = 1
    for link in page_links:
        save_page(link, f'{manga_name} ch{chapter}-{page}', manga_name)
        page += 1

    # creates chapter
    create_pdf(manga_name, chapter)

    print(f'Ch{chapter} of {manga_name} has been saved!')


def save_chapters(manga_name: str, start: int, end: int) -> None:
    """
    Downloads multiple chapters. Start and end are inclusive
    """
    for chapter in range(start, end + 1):
        save_chapter(manga_name, chapter)

    print(f'Chapters {start}-{end} of {manga_name} have been downloaded!')


def validity_checker(url: str, manga_name: str, chapter: int) -> bool:
    """
    Checks if given mangareader.net url is a valid chapter/manga

    >>> validity_checker('http://www.mangareader.net/one-piece/500', 'One Piece', 500)
    True

    >>> validity_checker('http://www.mangareader.net/one-piece/1000', 'One Piece', 1000)
    Sorry Chapter1000 of One Piece does not exist.
    False

    >>> validity_checker('http://www.mangareader.net/two-piece/20', 'Two Piece', 20)
    Sorry, Two Piece does not exist on mangareader.net
    False
    """
    # access manga page without chapter, if error is raised: manga doesn't exist
    chless_url = f'http://www.mangareader.net/{manga_name_to_url(manga_name)}'
    try:
        manga_check = BeautifulSoup(simple_get(chless_url), 'html.parser')
    except TypeError:
        print(f'Sorry, {manga_name} does not exist on mangareader.net')
        return False

    # start by accessing url as usual
    html = BeautifulSoup(simple_get(url), 'html.parser')

    # if no error raises but 'recom' id in imgholder: chapter doesn't exist
    imgholder = html.find(id='imgholder')
    if len(imgholder.find_all(id='recom')) > 0:
        print(f'Sorry Chapter{chapter} of {manga_name} does not exist.')
        return False

    # if you got all the way here both the manga and chapter are valid
    return True


if __name__ == '__main__':
    import doctest

    # doctest.testmod()

    # check if 'Downloads' exists in working directory. if not, create it
    if 'Downloads' not in os.listdir(os.getcwd()):
        os.mkdir(f'Downloads')
