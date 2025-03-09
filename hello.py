from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import re

def extract_phones(prefix, numbers):
    if not numbers:
        return []
    return re.findall(rf'{prefix} (\d+)', numbers)


def filter_and_sort_phones(phone_list):
    valid_phones = [
        phone for phone in phone_list
        if re.match(r'^[3489]\d{9}$', phone)
    ]
    return sorted(valid_phones)

def listorg(inn):
    status = None
    url = f"https://www.list-org.com/search?val={inn}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        status = f"list-org.com - ошибка сайта {response.status_code}"
        print(f"list-org.com - ошибка сайта {response.status_code}")
        return None, ['1'], 'Название неизвестно', None, status


    soup = BeautifulSoup(response.text, "html.parser")
    org_list = soup.find("div", class_="org_list")

    if not org_list:
        status = 'По указанному ИНН ничего не найдено'
        print("list-org.com - по указанному ИНН ничего не найдено")
        return None, ['1'], 'Название неизвестно', None, status

    first_link = org_list.find("a", href=True)
    if not first_link:
        status = "list-org.com - не удалось извлечь ссылку"
        print("list-org.com - не удалось извлечь ссылку")
        return None, ['1'], 'Название неизвестно', None, status

    full_url = "https://www.list-org.com" + first_link["href"]

    response = requests.get(full_url, headers=headers)
    if response.status_code != 200:
        status = f"list-org.com - ошибка страницы организации {response.status_code}"
        print(f"list-org.com - ошибка страницы организации {response.status_code}")
        return full_url, ['1'], 'Название неизвестно', None, status

    soup = BeautifulSoup(response.text, "html.parser")
    phone_links = soup.find_all("a", class_="clipboards nwra", href=re.compile(r"^/phone/\d+-\d+$"))
    phones = [link["href"].split("/phone/")[1].replace("-", "") for link in phone_links]

    full_name = None
    name = soup.find('h1', class_='ms-2', text=lambda x: x and 'Организация' in x)
    if name:
        full_name = name.text.strip().replace('Организация ', '')

    ogrn = None
    ogrn_label = soup.find("span", title="Основной государственный регистрационный номер")
    if ogrn_label:
        ogrn_container = ogrn_label.find_parent("p")
        if ogrn_container:
            ogrn_value = ogrn_container.find("span", class_="clipboard")
            if ogrn_value:
                ogrn = ogrn_value.text.strip()

    return full_url, phones, full_name, ogrn, status


def checko(ogrn):
    url = f"https://checko.ru/company/{ogrn}/contacts"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"checko.ru - ошибка сайта {response.status_code}")

    soup = BeautifulSoup(response.text, "html.parser")

    phones = []
    for link in soup.find_all("a", href=True):
        if link["href"].startswith("tel:+7"):
            phones.append(link["href"].replace("tel:+7", "", 1))

    return phones, url


def saby(inn):
    url = f"https://saby.ru/profile/{inn}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"saby.ru - ошибка сайта {response.status_code}")
        return ['1'], url

    soup = BeautifulSoup(response.text, "html.parser")
    phone_divs = soup.find_all("div", class_="ws-ellipsis contractorCard-ContactItem__text")
    phones = []

    for div in phone_divs:
        if div.text.strip().startswith("+7"):
            phone_text = div.text.strip()
            cleaned_phone = re.sub(r"[^0-9]", "", phone_text)[1:]
            phones.append(cleaned_phone)
            return phones, url

    return ['1'], url


def zachestniybiznes(inn):
    search_url = f"https://zachestnyibiznes.ru/search?query={inn}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    response = requests.get(search_url, headers=headers)

    if response.status_code != 200:
        search_status = f"Ошибка {response.status_code}: не удалось получить данные с zachestnyibiznes.ru"
        print(f"Ошибка {response.status_code}: не удалось получить данные с zachestnyibiznes.ru")
        return None, ['1'], search_status, None

    soup = BeautifulSoup(response.text, "html.parser")
    company_block = soup.find("p", class_="no-indent m-b-5 f-s-16 c-black")

    full_url = ''
    if company_block:
        link_tag = company_block.find("a", class_="no-underline-full")
        if link_tag and "href" in link_tag.attrs:
            full_url = "https://zachestnyibiznes.ru" + link_tag["href"]
        else:
            search_status = 'Не удалось получить ссылку на zachestnyibiznes.ru'
            return None, ['1'], search_status, None

    response = requests.get(full_url, headers=headers)
    if response.status_code != 200:
        parse_status = f"Ошибка {response.status_code}: не удалось получить телефоны с zachestnyibiznes.ru"
        print(f"Ошибка {response.status_code}: не удалось получить данные с zachestnyibiznes.ru")
        return full_url, ['1'], None, parse_status

    soup = BeautifulSoup(response.text, "html.parser")

    phones = []
    for link in soup.find_all("a", href=True):
        if link["href"].startswith("tel:+7"):
            phones.append(link["href"].replace("tel:+7", "", 1))

    return full_url, phones, None, None


application = Flask(__name__)

@application.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        inn_org = request.form.get('inn_org')
        print('ИНН: ', inn_org, flush=True)

        tsp = request.form.get('tsp')
        print('ТСП: ', tsp, flush=True)

        tb = request.form.get('tb')
        print('ТБ: ', tb, flush=True)

        tsp_and_tb_phones = []
        if tsp or tb:
            tsp_and_tb_phones = list(set(extract_phones("тсп", tsp)) | set(extract_phones("тб",tb)))
        print('Телефоны ТСП и ТБ: ',tsp_and_tb_phones)

        listorg_url, listorg_phones, org_name, org_ogrn, listorg_status = listorg(inn_org)
        listorg_phones = filter_and_sort_phones(listorg_phones)
        print('Название организации: ', org_name, flush=True)
        print('ОГРН: ', org_ogrn, flush=True)
        print('Ссылка на list-org: ', listorg_url, flush=True)
        print('Телефоны из list-org: ', listorg_phones, flush=True)

        checko_phones, checko_url = checko(org_ogrn)
        checko_phones = filter_and_sort_phones(checko_phones)
        print('Ссылка на checko: ', checko_url, flush=True)
        print('Телефоны из checko: ', checko_phones, flush=True)

        saby_phones, saby_url = saby(inn_org)
        saby_phones = filter_and_sort_phones(saby_phones)
        print('Ссылка на saby: ', saby_url, flush=True)
        print('Телефоны из saby: ', saby_phones, flush=True)

        zachestniybiznes_url, zachestniybiznes_phones, zachestniybiznes_url_status, zachestniybiznes_phones_status = zachestniybiznes(inn_org)
        zachestniybiznes_phones = filter_and_sort_phones(zachestniybiznes_phones)
        print('Ссылка на zachestniybiznes: ', zachestniybiznes_url, flush=True)
        print('Телефоны из zachestniybiznes: ', zachestniybiznes_phones, flush=True)
        print('Ошибки страницы поиска: ', zachestniybiznes_url_status, flush=True)
        print('Ошибки страницы организации: ', zachestniybiznes_phones_status, flush=True)

        all_phones = list(set(checko_phones) | set(listorg_phones) | set(saby_phones) | set(zachestniybiznes_phones))
        filtered_phones = ['1']
        sorted_phones = []

        if tsp_and_tb_phones:
            filtered_phones = [phone for phone in all_phones if phone not in tsp_and_tb_phones]
            print('Все телефоны без ТСП и ТБ: ', filtered_phones, flush=True)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return render_template("results.html", inn_org=inn_org, tsp_and_tb_phones=tsp_and_tb_phones, org_name=org_name,
                               org_ogrn=org_ogrn, listorg_url=listorg_url, listorg_phones=listorg_phones,
                               checko_url=checko_url, checko_phones=checko_phones, saby_url=saby_url,
                               saby_phones=saby_phones, all_phones=all_phones, filtered_phones=filtered_phones,
                               sorted_phones=sorted_phones, listorg_status=listorg_status, tsp=tsp, tb=tb,
                               zachestniybiznes_url=zachestniybiznes_url, zachestniybiznes_phones=zachestniybiznes_phones,
                               zachestniybiznes_url_status=zachestniybiznes_url_status,
                               zachestniybiznes_phones_status=zachestniybiznes_phones_status)


        return render_template('index.html', inn_org=inn_org, tsp_and_tb_phones=tsp_and_tb_phones, org_name=org_name,
                               org_ogrn=org_ogrn, listorg_url=listorg_url, listorg_phones=listorg_phones,
                               checko_url=checko_url, checko_phones=checko_phones, saby_url=saby_url,
                               saby_phones=saby_phones, all_phones=all_phones, filtered_phones=filtered_phones,
                               sorted_phones=sorted_phones, listorg_status=listorg_status, tsp=tsp, tb=tb,
                               zachestniybiznes_url=zachestniybiznes_url, zachestniybiznes_phones=zachestniybiznes_phones,
                               zachestniybiznes_url_status=zachestniybiznes_url_status,
                               zachestniybiznes_phones_status=zachestniybiznes_phones_status)

    return render_template('index.html')

if __name__ == '__main__':
    application.run(debug=True)
