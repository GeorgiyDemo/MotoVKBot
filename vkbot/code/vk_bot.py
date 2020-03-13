# https://oauth.vk.com/authorize?client_id=5155010&redirect_uri=https://oauth.vk.com/blank.html&display=page&scope=offline,groups&response_type=token&v=5.37
#TODO Удаление пользователя по команде СТОП

import pymongo
import vk_api
import yaml
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
import time
import requests
import multiprocessing as mp

class MongoUserClass:
    """Класс для работы с пользователями"""
    def __init__(self, connection):
        self.table = connection["users"]

    def search_user(self, user_id):
        if self.table.find_one({"user_id": user_id}) == None:
            return False
        return True

    def get_current_step(self, user_id):
        """Получение текущего шага пользователя"""
        r = self.table.find_one({"user_id": user_id},{"_id": 0,"current_step": 1})
        if r == None:
            return 0
        return r["current_step"]

    def new_data(self, user_id, first_name, second_name, current_step, moto_model="-", moto_type="-", money_count="-"):
        """Занесение начальных значений пользователя в БД"""
        self.table.insert_one({"user_id": user_id, "first_name": first_name, "second_name": second_name,
                              "current_step": current_step, "moto_model": moto_model, "moto_type": moto_type, "money_count": money_count})

    def update_data(self, user_id, *items):
        set_dict = {}
        for e in items: 
            set_dict.update(e)

        self.table.update_one({"user_id": user_id}, {"$set": set_dict})


class MongoMsgClass:
    """Класс для получения текста ответных сообщений в зависимости от шага"""
    def __init__(self, connection):
        self.connection = connection
        self.table = mongo["out_messages"]
    
    def get_message(self, step):
        result = self.table.find_one({"current_step": step}, {"message": 1, "_id": 0})
        return result["message"]

def get_settings():
    """Чтение настроек с yaml"""
    with open("./yaml/settings.yml", 'r') as stream:
        return yaml.safe_load(stream)


class WallMonitoringClass:
    def __init__(self, token, group):
        self.vk = vk_api.VkApi(token=token)
        self.group = group
        while True:
            self.monitoring()
            time.sleep(10)

    # Мониторим последние 3 записи т.к может быть такое, что проставили хештеги проще
    def monitoring(self):
        results = self.vk.method(
            "wall.get", {"owner_id": self.group, "count": 3})
        for result in results["items"]:
            # TODO получаем
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

        server_url = self.vk.method('photos.getMessagesUploadServer', {
                                    'peer_id': self.user_id})["upload_url"]
        photo_r = requests.post(
            server_url, files={'photo': open(self.path, 'rb')}).json()
        photo_final = self.vk.method("photos.saveMessagesPhoto", {
                                     "photo": photo_r["photo"], "server": photo_r["server"], "hash": photo_r["hash"]})[0]
        photo_str = "photo" + \
            str(photo_final["owner_id"]) + "_" + str(photo_final["id"])
        self.__photo_str = photo_str


class MainClass:
    def __init__(self, token, connection):
        
        #Коннект к БД
        self.connection = connection
        # Авторизуемся как сообщество
        self.vk = vk_api.VkApi(token=token)
        #Взаимодействие с БД пользователей
        self.mongo_user_obj = MongoUserClass(connection)
        #Взаимодействие с исходящими сообщеньками в БД
        self.mongo_msg_obj = MongoMsgClass(connection)

        #Сообщение и какой метод за него отвечает
        self.main_dict = {
            "Начать" : self.step_1,
            "Магазин" : self.step_2,
            "Чек-лист &quot;Трушного боббера&quot;" : self.step_3,
            "Кастом" : self.step_6,
            "Сток" : self.step_7,
            "0" : self.step_9,
            '0-5000' : self.step_9,
            '5001-15000' :  self.step_9,
            '15001+' :  self.step_9,
        }

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
                    
                    #Если текст есть в словаре self.main_dict, отвечающем за ассоциацию
                    if event.text in self.main_dict:
                        self.main_dict[event.text](event)
                    
                    #Если нет, то это может быть модель мото с шага 4
                    elif self.mongo_user_obj.get_current_step(event.user_id) == 4:
                        #Вызываем шаг 5
                        self.step_5(event)


                    else:
                        print("Неизвестная команда: '{}'".format(event.text))

    def step_1(self, event):
        """Обработка шага 1"""
        #Получаем имя пользователя
        first_name, second_name = self.get_username(event.user_id)
        if not self.mongo_user_obj.search_user(event.user_id):
            self.mongo_user_obj.new_data(event.user_id, first_name, second_name, 1)

        # Кнопки для VK
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Чек-лист "Трушного боббера"',color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Магазин', color=VkKeyboardColor.DEFAULT)
        
        # Загружаем фото
        photo_obj = PhotoUploaderClass(self.vk, event.user_id, "./img/buttons.jpg")
        message_str = "Привет, "+first_name+self.mongo_msg_obj.get_message(1)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), "keyboard": keyboard.get_keyboard(), 'message': message_str, 'attachment': photo_obj.photo_str})

    def step_2(self, event):
        """Обработка шага 2"""
        self.mongo_user_obj.update_data(event.user_id, {"current_step": 2})
        message_str = self.mongo_msg_obj.get_message(2)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})
        #Т.к. у нас безусловный переход от 2 к 4 шагу
        time.sleep(2)
        self.step_4(event)

    def step_3(self, event):
        """Обработка шага 3"""
        self.mongo_user_obj.update_data(event.user_id, {"current_step": 3})
        message_str = self.mongo_msg_obj.get_message(3)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})
        #Т.к. у нас безусловный переход от 2 к 4 шагу
        time.sleep(2)
        self.step_4(event)
    
    def step_4(self, event):
        """
        Обработка шага 4
        - Вызывается только от step_2/step_3
        """
        self.mongo_user_obj.update_data(event.user_id, {"current_step": 4})
        message_str = self.mongo_msg_obj.get_message(4)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})
    
    def step_5(self, event):
        """Вызывается после того, как пользователь введет какой-либо текст после шага 4"""
        #Занесение информации о модели
        moto_model = event.text
        self.mongo_user_obj.update_data(event.user_id, {"current_step": 5}, {"moto_model": moto_model})

        # Кнопки для VK
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Кастом',color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Сток', color=VkKeyboardColor.DEFAULT)

        message_str = self.mongo_msg_obj.get_message(5)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, "keyboard": keyboard.get_keyboard()})


    def step_6(self, event):
        """Обработка шага 6"""
        
        self.mongo_user_obj.update_data(event.user_id, {"moto_type": "кастом"},{"current_step":6})
        message_str = self.mongo_msg_obj.get_message(6)
        photo_obj = PhotoUploaderClass(self.vk, event.user_id, "./img/custom.jpg")
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, 'attachment': photo_obj.photo_str})
        time.sleep(2)
        self.step_8(event)
        

    def step_7(self, event):
        """Обработка шага 7"""

        self.mongo_user_obj.update_data(event.user_id, {"moto_type": "сток"},{"current_step":7})
        message_str = self.mongo_msg_obj.get_message(7)
        photo_obj = PhotoUploaderClass(self.vk, event.user_id, "./img/expendable.jpg")
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, 'attachment': photo_obj.photo_str}) #'attachment': "market-170171504_3154895"
        time.sleep(2)
        self.step_8(event)

        #market-170171504?section=album_4

    def step_8(self, event):
        """Обработка шага 8"""

        self.mongo_user_obj.update_data(event.user_id,{"current_step":8})

        # Кнопки для VK
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('0',color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('0-5000', color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('5001-15000', color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('15001+', color=VkKeyboardColor.DEFAULT)
        message_str = self.mongo_msg_obj.get_message(8)

        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, "keyboard": keyboard.get_keyboard()})
    
    def step_9(self, event):
        """Обработка шага 9"""
        
        #Занесение информация о цене:
        moto_price = event.text
        self.mongo_user_obj.update_data(event.user_id, {"current_step":9}, {"money_count" : moto_price})
        message_str = self.mongo_msg_obj.get_message(9)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})

    def get_username(self, user_id):
        """Метод, возвращающий имя пользователя по id"""

        name = self.vk.method('users.get', {'user_id': user_id})[0]
        return name["first_name"], name["last_name"]


if __name__ == "__main__":

    settings = get_settings()
    mp.Process(target=WallMonitoringClass, args=(settings["user_token"],settings["group_id"], )).start()
    myclient = pymongo.MongoClient(settings["mongodb_connection"])
    mongo = myclient['MotoVKBot']
    MainClass(settings["group_token"], mongo)
