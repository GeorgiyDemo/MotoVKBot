import json

import requests
from bs4 import BeautifulSoup


# Функция с основной логикой парсинга сайта
def site1():
    theatre_dict = {}
    response = requests.get("https://www.bolshoi.ru/timetable/").text
    content = BeautifulSoup(response, "lxml")

    # Секции с распределением по датам
    sections = content.find_all("div", class_="DATE timetable_content")
    for section in sections:

        # Работа с датой
        date = section.find("div", class_="timetable_content__date")
        date_first = date.find("b", class_="timetable_content__date_date").text
        date_second = date.find("i", class_="timetable_content__date_weekday").text
        date_string = date_first + ", " + date_second
        theatre_dict[date_string] = {}

        # Словарь для временного хранения данных
        locale_list = []

        # Находим все представления/выступления в секции (на текущую дату)
        theatres = section.find_all("tr", class_="past_q")
        for theatre in theatres:

            locale_dict = {"name": None, "description": None, "place&time": None}
            processing_flag = False
            # Название выступления
            theatre_name = theatre.find("a", class_="timetable_content__performance_title")
            if theatre_name != None:
                locale_dict["name"] = theatre_name.text
                processing_flag = True

            # Если есть название выступления, то продолжаем работу
            if processing_flag == True:
                # Описание выступления
                theatre_description = theatre.find("p", class_="timetable_content__performance_description")
                if theatre_description != None and theatre_description.text != "":
                    locale_dict["description"] = theatre_description.text

                # Место и время выступления
                theatre_place_time = theatre.find("td", class_="timetable_content__place")
                if theatre_place_time != None:
                    value = theatre_place_time.text.replace("\t", "")
                    value = value.replace("\n", " ")
                    locale_dict["place&time"] = value[1:]
                locale_list.append(locale_dict)

        theatre_dict[date_string] = {"names": locale_list}

    return theatre_dict


def filter_by_date(dct, date):
    formated_d = {}
    month_name2number = {
        "01": "января",
        "02": "февраля",
        "03": "марта",
        "04": "апреля",
        "05": "мая",
        "06": "июня",
        "07": "июля",
        "08": "августа",
        "09": "сентября",
        "10": "октября",
        "11": "ноября",
        "12": "декабря",
    }

    date_type = ""

    # Если дата в виде дня/месяца/года
    try:
        day, month, year = date.split("/")
        date_type = "day/month/year"

    # Если дата в виде месяца/года
    except ValueError:
        month, year = date.split("/")
        date_type = "month/year"

    # Слово для поиска месяца
    search_word = month_name2number[month]

    # Если дата в виде месяца/года
    if date_type == "month/year":
        for key in dct:
            if search_word in key:
                formated_d[key] = dct[key]

    # Если дата в виде дня/месяца/года
    elif date_type == "day/month/year":

        for key in dct:
            if search_word in key and day in key:
                formated_d[key] = dct[key]

    return json.dumps(formated_d, ensure_ascii=False)


# Функция, вызываемая из бота
def parser(date):
    # Получаем все данные
    all_d = site1()
    # Фильтруем на спектали по дате
    result = filter_by_date(all_d, date)
    # Фильтруем на данные согласно дате
    return result
