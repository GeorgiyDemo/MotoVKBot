#TODO предложение о добавлении поста в предложку сообщества

import vk_api
import yaml
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id

import requests


message_dict = {
    1 : "\nМеня зовут Яшка. Я чат-бот, и у меня есть ключи от Мотосарая. здесь продаются з/ч для кастом байков.\n\nДавай познакомимся?\nОтвечая на мои вопросы, ты будешь получать разные бонусы.\n\nЧтобы получить чек-лист \"Трушного боббера\" нажми на кнопку.\nЧтобы ознакомиться с нашими товарами нажми на \"Магазин\".\n\n__________\nЕсли вдруг у тебя не появляются кнопки, сделай как показано на изображении."
}
def get_settings():
    """Чтение настроек с yaml"""
    with open("./yaml/settings.yml", 'r') as stream:
        return yaml.safe_load(stream)

def get_username(vk, user_id):
    """Метод, возвращающий имя пользователя по id"""

    name = vk.method('users.get', {'user_id': user_id})[0]["first_name"]
    return name

class MainClass():
    def __init__(self):

        self.settings = get_settings()
        # Авторизуемся как сообщество
        self.vk = vk_api.VkApi(token=self.settings["token"])

        self.processing()

    def get_url(self, message_id):
        """
        Метод для получения url изобржения из id сообщения
        """
        
        # Получаем сообщеньку по методу
        r = self.vk.method('messages.getById', {'message_ids': message_id, "group_id" : self.settings["group_id"]})["items"]
        
        # Находим все размеры фото
        all_sizes = r[0]["attachments"][0]["photo"]["sizes"]

        # В цикле по каждой ищем самое большое изображение
        height, width, index = 0, 0, 0
        for i in range(len(all_sizes)):
            if all_sizes[i]["width"] > width and all_sizes[i]["height"] > height:
                height = all_sizes[i]["height"]
                width = all_sizes[i]["width"]
                index = i

        # Обращаемся к полученному индексу
        url = all_sizes[index]["url"]

        # Берем последний элемент списка (т.к. он самый большой)
        return url

    def processing(self):
        """
        Метод обработки входящих сообщений
        """
        # Работа с сообщениями
        longpoll = VkLongPoll(self.vk)

        # Основной цикл
        for event in longpoll.listen():

            # Если пришло новое сообщение
            if event.type == VkEventType.MESSAGE_NEW:

                # Если оно имеет метку для бота
                if event.to_me:

                    # Шаг 1
                    if event.text == "Начать":
                        
                        message_str = "Привет, "+get_username(self.vk, event.user_id)+message_dict[1]
                        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str })

                    #Шаг 3
                    elif event.text == "Чек-лист \"Трушного боббера\"":
                        print(event)
                        message_str = "Привет, просто отправь мне любое фото 🧩"
                        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str })

if __name__ == "__main__":
    MainClass()
