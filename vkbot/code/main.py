# https://oauth.vk.com/authorize?client_id=5155010&redirect_uri=https://oauth.vk.com/blank.html&display=page&scope=offline,groups&response_type=token&v=5.37
#TODO Удаление пользователя по команде СТОП
#TODO Шаг 13+

import pymongo
import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
import time
import requests
import multiprocessing as mp
import util_module
from mongo_module import MongoUserClass, MongoMsgClass

class WallMonitoringClass:
    """Класс в отдельном процессе для мониторинга стены"""
    def __init__(self, user_token, club_token, group, connection):
        self.user_vk = vk_api.VkApi(token=user_token)
        self.club_vk = vk_api.VkApi(token=club_token)
        #Взаимодействие с БД пользователей
        myclient = pymongo.MongoClient(connection)
        self.mongo_user_obj = MongoUserClass(myclient['MotoVKBot'])
        self.group = group
        self.user_alerts_dict = {}
        while True:
            self.monitoring()
            self.user_alerting()
            time.sleep(60)

    # Мониторим последние 3 записи т.к может быть такое, что проставили хештеги проще
    def monitoring(self):
        #TODO слоаврь пользователей и новости
        user_alerts_dict = {}
        tags_list = self.mongo_user_obj.get_alltags()
        results = self.user_vk.method(
            "wall.get", {"owner_id": self.group, "count": 3})
        for result in results["items"]:
            for tag in tags_list:
                #Если есть тег и этой записи еще нет в БД
                if tag in util_module.wallpost_check(result["text"]) and not self.mongo_user_obj.get_walldata("wall{}_{}".format(self.group,result["id"])):
                    
                    user_lists = self.mongo_user_obj.get_usersbytags(tag)
                    wall_id = "wall{}_{}".format(self.group,result["id"])
                    user_alerts_dict[wall_id] = user_lists
                    #Выставляем данные в БД
                    self.mongo_user_obj.set_walldata(wall_id, tag)
        
        #Выставляем данные для user_alerting
        self.user_alerts_dict = user_alerts_dict

    def user_alerting(self):
        """Метод для оповещения пользователей"""
        d = self.user_alerts_dict
        if len(d) == 0:
            return
        for wall_id, users_list in d.items():
            for current_user in users_list:
                #Отправляем новость
                self.club_vk.method('messages.send', {'user_id': current_user, 'random_id': get_random_id(),'attachment': wall_id})
                #+1 пост для пользователя
                self.mongo_user_obj.inc_user_postssend(current_user)
                time.sleep(0.2)

class UserAlertClass:
    """Класс для оповещения пользователей спустя N времени"""
    def __init__(self, token, connection_str):
        while True:
            #self.step6to11_checker()
            #self.step12to13_checker() # 2 дня
            #self.step15to16_checker() # 2 недели
            #self.step18to19plus()   # 1 неделя
            self.checker()
            time.sleep(60)
    
    """
    def step6to11_checker(self):
        for пользователи in все пользователи в БД
            if current_step == 6 and posts_send == 1:
                переход к 11
    """
    def step12to13_checker(self):
        if current_step == 12 and {users_ttl.transition} : "step12to13"} == None:

    def checker(self):
        print("UserAlertClass: [Я ВЫПОЛНЯЮСЬ]")

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
    def __init__(self, token, connection_str):
        
        #Соединение с БД
        myclient = pymongo.MongoClient(connection_str)
        connection = myclient['MotoVKBot']

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
            "Кастом" : self.step_7,
            "Сток" : self.step_6,
            "Дешево и сердито" : self.step_9,
            "Недорогой эксклюзив" : self.step_9,
            "Дорогой эксклюзив" : self.step_9,
            "Дорого-богато" : self.step_9,
            "Цена" : self.step_11,
            "Качество" : self.step_11,
            "Получить купон" : self.step_12,
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
                    
                    print("Сообщение: '{}' от https://vk.com/id{}".format(event.text, event.user_id))

    def step_1(self, event):
        """Обработка шага 1"""
        #Получаем имя пользователя
        first_name, second_name = self.get_username(event.user_id)
        if not self.mongo_user_obj.search_userdata(event.user_id):
            self.mongo_user_obj.new_userdata(event.user_id, first_name, second_name, 1)

        # Кнопки для VK
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Чек-лист "Трушного боббера"',color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Магазин', color=VkKeyboardColor.DEFAULT)
        
        # Загружаем фото
        photo_obj = PhotoUploaderClass(self.vk, event.user_id, "./img/buttons.jpg")
        message_str = self.mongo_msg_obj.get_message(1, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), "keyboard": keyboard.get_keyboard(), 'message': message_str, 'attachment': photo_obj.photo_str})

    def step_2(self, event):
        """Обработка шага 2"""
        self.mongo_user_obj.update_userdata(event.user_id, {"current_step": 2})
        message_str = self.mongo_msg_obj.get_message(2, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})
        #Т.к. у нас безусловный переход от 2 к 4 шагу
        time.sleep(2)
        self.step_4(event)

    def step_3(self, event):
        """Обработка шага 3"""
        self.mongo_user_obj.update_userdata(event.user_id, {"current_step": 3})
        message_str = self.mongo_msg_obj.get_message(3, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})
        #Т.к. у нас безусловный переход от 2 к 4 шагу
        time.sleep(2)
        self.step_4(event)
    
    def step_4(self, event):
        """
        Обработка шага 4
        - Вызывается только от step_2/step_3
        """
        self.mongo_user_obj.update_userdata(event.user_id, {"current_step": 4})
        message_str = self.mongo_msg_obj.get_message(4, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})
    
    def step_5(self, event):
        """Вызывается после того, как пользователь введет какой-либо текст после шага 4"""
        #Занесение информации о модели
        moto_model = event.text
        self.mongo_user_obj.update_userdata(event.user_id, {"current_step": 5}, {"moto_model": moto_model})
        # Кнопки для VK
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Кастом',color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Сток', color=VkKeyboardColor.DEFAULT)
        message_str = self.mongo_msg_obj.get_message(5, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, "keyboard": keyboard.get_keyboard()})

    def step_6(self, event):
        """Обработка шага 6"""
        
        self.mongo_user_obj.update_userdata(event.user_id, {"moto_type": "сток"},{"current_step":6})
        message_str = self.mongo_msg_obj.get_message(6, event.user_id)
        photo_obj = PhotoUploaderClass(self.vk, event.user_id, "./img/expendable.jpg")
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, 'attachment': photo_obj.photo_str})
        
    def step_7(self, event):
        """Обработка шага 7"""

        self.mongo_user_obj.update_userdata(event.user_id, {"moto_type": "кастом"},{"current_step":7})
        message_str = self.mongo_msg_obj.get_message(7, event.user_id)
        photo_obj = PhotoUploaderClass(self.vk, event.user_id, "./img/custom.jpg")
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, 'attachment': photo_obj.photo_str}) #'attachment': "market-170171504_3154895"
        time.sleep(2)
        self.step_8(event)

    def step_8(self, event):
        """Обработка шага 8"""

        self.mongo_user_obj.update_userdata(event.user_id, {"current_step": 8})
        # Кнопки для VK
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Дешево и сердито',color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Недорогой эксклюзив', color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Дорогой эксклюзив', color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Дорого-богато', color=VkKeyboardColor.DEFAULT)
        message_str = self.mongo_msg_obj.get_message(8, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, "keyboard": keyboard.get_keyboard()})

    def step_9(self, event):
        """Обработка шага 9"""
        #Занесение информации о типе платежеспособности пользователя
        price_type = event.text
        self.mongo_user_obj.update_userdata(event.user_id, {"current_step": 9}, {"price_type": price_type})
        # Кнопки для VK
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Цена',color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Качество', color=VkKeyboardColor.DEFAULT)

        message_str = self.mongo_msg_obj.get_message(9, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, "keyboard": keyboard.get_keyboard()})

    def step_11(self, event):
        """Обработка шага 11"""
        #Занесение информации о приоритетах пользователя
        priority_type = event.text
        self.mongo_user_obj.update_userdata(event.user_id, {"current_step": 11}, {"priority_type": priority_type})

        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Получить купон',color=VkKeyboardColor.DEFAULT)

        message_str = self.mongo_msg_obj.get_message(11, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, "keyboard": keyboard.get_keyboard()})

    def step_12(self, event):
        """Обработка шага 12"""
        self.mongo_user_obj.update_userdata(event.user_id, {"current_step": 12}, {"coupon_5": "seen"})
        message_str = self.mongo_msg_obj.get_message(12, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})

        #TODO Выставляем TTL для users_ttl.step12to13

    def get_username(self, user_id):
        """Метод, возвращающий имя пользователя по id"""

        name = self.vk.method('users.get', {'user_id': user_id})[0]
        return name["first_name"], name["last_name"]


if __name__ == "__main__":
    p_list = []
    settings = util_module.get_settings()
    p = mp.Process(target=WallMonitoringClass, args=(settings["user_token"],settings["group_token"], settings["group_id"], settings["mongodb_connection"], ))
    p.start()
    p_list.append(p)
    p = mp.Process(target=MainClass, args=(settings["group_token"],settings["mongodb_connection"], ))
    p.start()
    p_list.append(p)
    p = mp.Process(target=UserAlertClass, args=(settings["group_token"],settings["mongodb_connection"], ))
    p.start()
    p_list.append(p)
    
    #Ультракостыль, чтоб Docker в случае ошибки перезапускал скрипт
    stop_flag = True
    while stop_flag:
        for proc in p_list:
            if type(proc.exitcode) == int:
                print('MAIN остановил работу!')
                stop_flag = False
        time.sleep(0.1)
    
    for proc in p_list:
        proc.terminate()