import json

import requests
from bs4 import BeautifulSoup


# Функция формирования url на основе даты
def date2url(date):
    month_dict = {
        "01": "1",
        "02": "2",
        "03": "3",
        "04": "4",
        "05": "5",
        "06": "6",
        "07": "7",
        "08": "8",
        "09": "9",
        "10": "10",
        "11": "11",
        "12": "12",
    }

    try:
        day, month, year = date.split("/")
    except ValueError:
        month, year = date.split("/")

    if month in month_dict:
        month = month_dict[month]

    url = "https://et-cetera.ru/poster/?month=" + month + "&year=" + year
    return url


# Функция с основной логикой парсинга сайта
def site2(url):
    response = requests.get(url).text
    content = BeautifulSoup(response, "lxml")

    # Баннеры в будние дни
    daily_list = []
    banners = content.find_all("td", class_="day withShow")
    for banner in banners:
        # Название выступления
        banner_titles = banner.find_all("div", class_="banner")
        theatre_list = all_banners(banner_titles)
        daily_list.extend(theatre_list)

    # Баннер сегодня
    today_list = []
    today_banners = content.find_all("td", class_="day today withShow")
    for banner in today_banners:
        # Название выступления
        banner_titles = banner.find_all("div", class_="banner")
        theatre_list = all_banners(banner_titles)
        today_list.extend(theatre_list)

    # Баннеры в выходные дни
    weekday_list = []
    weekday_banners = content.find_all("td", class_="day withShow weekday")
    for banner in weekday_banners:
        # Название выступления
        banner_titles = banner.find_all("div", class_="banner")
        theatre_list = all_banners(banner_titles)
        weekday_list.extend(theatre_list)

    # Соединяем все списки
    global_list = daily_list + today_list + weekday_list

    # Формируем список
    theatre_list = []
    for event in global_list:
        theatre_list.append({"name": event["name"], "date": event["date"]})

    theatre_list.sort(key=lambda y: (y["date"]))

    return theatre_list


# Функция парсинга всех спектаклей на текущий день
def all_banners(banner_titles):
    out_list = []
    for b_title in banner_titles:
        # Получение даты концерта
        check = b_title.find("p")
        concert_date = check.get("data-date")

        # Получение отформатированного (красивого) названия спектакля
        value = b_title.text.replace("\t", "")
        concert_name = value.replace("\n", " ")
        concert_name = concert_name[2:]
        formatted_name = concert_name[:len(concert_name) - 3]
        out_list.append({"name": formatted_name, "date": concert_date})

    return out_list


def filter_by_date(lst, date):
    try:
        day, month, year = date.split("/")
    except ValueError:
        return json.dumps(lst, ensure_ascii=False)

    new_lst = []
    for e in lst:
        if e["date"] == day + "." + month + "." + year:
            new_lst.append(e)

    return json.dumps(new_lst, ensure_ascii=False)


# Функция, вызываемая из бота
def parser(date):
    url = date2url(date)
    all_d = site2(url)
    result = filter_by_date(all_d, date)
    return result
