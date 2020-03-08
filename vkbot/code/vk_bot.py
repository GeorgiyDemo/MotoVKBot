#https://oauth.vk.com/authorize?client_id=5155010&redirect_uri=https://oauth.vk.com/blank.html&display=page&scope=offline,groups&response_type=token&v=5.37
#TODO Ботов сюда
#TODO БД СЮДА

import vk_api
import yaml
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
import time
import requests
import multiprocessing as mp

#TODO вынести потом в БД
message_dict = {
    1 : "\nМеня зовут Яшка. Я чат-бот, и у меня есть ключи от Мотосарая. здесь продаются з/ч для кастом байков.\n\nДавай познакомимся?\nОтвечая на мои вопросы, ты будешь получать разные бонусы.\n\nЧтобы получить чек-лист \"Трушного боббера\" нажми на кнопку.\nЧтобы ознакомиться с нашими товарами нажми на \"Магазин\".\n\n__________\nЕсли вдруг у тебя не появляются кнопки, сделай как показано на изображении.",
    2 : "В нашем магазине есть подборки по категориям товаров, в каждой из них ты найдешь что-то для своего проекта.\n\n",
}
def get_settings():
    """Чтение настроек с yaml"""
    with open("./yaml/settings.yml", 'r') as stream:
        return yaml.safe_load(stream)

class WallMonitoringClass:
    def __init__(self, token):
        
        self.vk = vk_api.VkApi(token=token)
        while True:
            self.monitoring()
            time.sleep(10)
    
    #Мониторим последние 3 записи т.к может быть такое, что проставили хештеги проще
    def monitoring(self):
        results = self.vk.method("wall.get", {"owner_id": -170171504, "count":3})
        for result in results["items"]:
            #TODO получаем
            print(result["text"])

class PhotoUploaderClass:
    """Класс для загрузки фото в VK"""
    def __init__(self, vk, user_id, path):
        self.vk = vk
        self.user_id = user_id
        self.path = path
        self.__photo_str = None
        self.photo_uploader()

    @property
    def photo_str(self):
        return self.__photo_str

    def photo_uploader(self):
        """Загрузка фото с локали в VK"""

        server_url = self.vk.method('photos.getMessagesUploadServer', {'peer_id': self.user_id})["upload_url"]
        photo_r = requests.post(server_url, files={'photo': open(self.path, 'rb')}).json()
        photo_final = self.vk.method("photos.saveMessagesPhoto",{"photo": photo_r["photo"], "server": photo_r["server"], "hash": photo_r["hash"]})[0]
        photo_str = "photo" + str(photo_final["owner_id"]) + "_" + str(photo_final["id"])
        self.__photo_str = photo_str
    

class MainClass:
    def __init__(self, token):

        # Авторизуемся как сообщество
        self.vk = vk_api.VkApi(token=token)
        self.processing()

    def processing(self):
        """Обработка входящих сообщений"""
        # Работа с сообщениями
        longpoll = VkLongPoll(self.vk)

        # Основной цикл
        for event in longpoll.listen():

            # Если пришло новое сообщение
            if event.type == VkEventType.MESSAGE_NEW:

                # Если оно имеет метку для бота
                if event.to_me:
                    
                    print(event.text)
                    # Шаг 1
                    if event.text == "Начать":
                        
                        #Кнопки для VK
                        keyboard = VkKeyboard(one_time=True)
                        keyboard.add_button('Чек-лист "Трушного боббера"', color=VkKeyboardColor.DEFAULT)
                        keyboard.add_button('Магазин', color=VkKeyboardColor.DEFAULT)
                        #Загружаем фото
                        photo_obj = PhotoUploaderClass(self.vk, event.user_id, "./img/buttons.jpg")
                        message_str = "Привет, "+self.get_username(event.user_id)+message_dict[1]
                        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), "keyboard": keyboard.get_keyboard(), 'message': message_str, 'attachment': photo_obj.photo_str})

                    #Шаг 2
                    elif event.text == 'Магазин':
                        message_str = ""
                        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})
                    
                    #Шаг 3
                    elif event.text == 'Чек-лист &quot;Трушного боббера&quot;':
                        message_str = "*БАТОН 2*"
                        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})

    def get_username(self, user_id):
        """Метод, возвращающий имя пользователя по id"""

        name = self.vk.method('users.get', {'user_id': user_id})[0]["first_name"]
        return name

if __name__ == "__main__":

    settings = get_settings()
    mp.Process(target=WallMonitoringClass,args=(settings["user_token"],)).start()
    MainClass(settings["group_token"])
