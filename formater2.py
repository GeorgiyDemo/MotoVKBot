import json


def format(json_data):
    out_list = []

    datetime_list = []
    input_list = json.loads(json_data)

    for element in input_list:
        datetime_list.append(element["date"])
    datetime_list = list(set(datetime_list))
    datetime_list.sort()
    for date in datetime_list:
        out_str = "📅 " + date
        for element in input_list:
            if element["date"] == date:
                out_str += "\n" + element["name"]
        out_list.append(out_str)

    if out_list == []:
        out_list.append("Спектакли за указанный промежуток времени не найдены!")

    return out_list
