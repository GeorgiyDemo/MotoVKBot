# https://oauth.vk.com/authorize?client_id=5155010&redirect_uri=https://oauth.vk.com/blank.html&display=page&scope=offline,groups&response_type=token&v=5.37
#TODO Удаление пользователя по команде СТОП
#TODO Шаг 15+

import vk_api
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
import time
import requests
import multiprocessing as mp
import util_module
from mongo_module import MongoMainClass, MongoMsgClass, MongoTTLClass

class WallMonitoringClass:
    """Класс в отдельном процессе для мониторинга стены"""
    def __init__(self, user_token, club_token, group, connection_str):
        self.user_vk = vk_api.VkApi(token=user_token)
        self.club_vk = vk_api.VkApi(token=club_token)
        #Взаимодействие с БД пользователей
        self.mongo_obj = MongoMainClass(connection_str)
        self.group = group
        self.user_alerts_dict = {}
        while True:
            self.monitoring()
            self.user_alerting()
            time.sleep(60)

    # Мониторим последние 3 записи т.к может быть такое, что проставили хештеги проще
    def monitoring(self):
        #Словарь пользователей и новости
        user_alerts_dict = {}
        tags_list = self.mongo_obj.get_alltags()
        results = self.user_vk.method(
            "wall.get", {"owner_id": self.group, "count": 3})
        for result in results["items"]:
            for tag in tags_list:
                #Если есть тег и этой записи еще нет в БД
                if tag in util_module.wallpost_check(result["text"]) and not self.mongo_obj.get_walldata("wall{}_{}".format(self.group,result["id"])):
                    
                    user_lists = self.mongo_obj.get_usersbytags(tag)
                    wall_id = "wall{}_{}".format(self.group,result["id"])
                    user_alerts_dict[wall_id] = user_lists
                    #Выставляем данные в БД
                    self.mongo_obj.set_walldata(wall_id, tag)
        
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
                self.mongo_obj.inc_user_postssend(current_user)
                time.sleep(0.2)

class UserAlertClass:
    """Класс для оповещения пользователей спустя N времени"""
    def __init__(self, token, connection_str):
        #Создаем табличку ttl и выставляем ttl для коллекции
        
        self.group_vk = vk_api.VkApi(token=token)
        
        #Соединение с БД
        self.mongo_ttl_obj = MongoTTLClass(connection_str)
        self.mongo_obj = MongoMainClass(connection_str)
        self.mongo_msg_obj = MongoMsgClass(connection_str)

        self.mongo_ttl_obj.create_ttl_table()

        while True:
            self.step6to11_checker() #как новость приедет
            self.step12to13_checker() # 2 дня
            self.step16to17_checker() # 2 недели
            self.step19to20plus()   # 1 неделя
            time.sleep(30)
    
    def step6to11_checker(self):
        all_list = self.mongo_obj.get_all_users()
        for user in all_list:
            if user["current_step"] == 6 and user["posts_send"] > 0:
                self.step11_alter(user["user_id"])

    def step12to13_checker(self):
        """Проверка на переход от шага 12 к 13"""
        all_list = self.mongo_obj.get_all_users()
        for user in all_list: 
            if user["current_step"] == 12 and self.mongo_ttl_obj.get_ttl_table(user["_id"]):
                #Отправляем сообщеньку и меняем шаг
                self.step13(user["user_id"])
    
    def step16to17_checker(self):
        """Проверка на переход от шага 16 к 17"""
        all_list = self.mongo_obj.get_all_users()
        for user in all_list: 
            if user["current_step"] == 16 and self.mongo_ttl_obj.get_ttl_table(user["_id"]):
                #Отправляем сообщеньку и меняем шаг
                self.step17(user["user_id"])
    
    def step19to20plus(self):
        """Проверка на переход от шага 19 к 20+ шагам"""
        
        wish_dict = {
            "Дать другие товары" : self.step_20,
            "Понизить цены" : self.step_21,
            "Повысить качество" : self.step_22,
        }

        all_list = self.mongo_obj.get_all_users()
        for user in all_list: 
            if user["current_step"] == 19 and self.mongo_ttl_obj.get_ttl_table(user["_id"]):
                user_wish = self.mongo_obj.get_wishbyuser(user["user_id"])
                if user_wish in wish_dict:
                    wish_dict[user_wish](user["user_id"])

    def step11_alter(self, user_id):
        """
        Альтернативная реализация шага 11
        Отличия:
        - Не выставляет priority_type от кастома
        - Обращение не через event
        """
        self.mongo_obj.update_userdata(user_id, {"current_step": 11})
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Получить купон',color=VkKeyboardColor.DEFAULT)
        message_str = self.mongo_msg_obj.get_message(11, user_id)
        self.group_vk.method('messages.send', {'user_id': user_id, 'random_id': get_random_id(), 'message': message_str, "keyboard": keyboard.get_keyboard()})

    def step13(self, user_id):
        """Обработка шага 13"""
        self.mongo_obj.update_userdata(user_id, {"current_step": 13})
        message_str = self.mongo_msg_obj.get_message(13, user_id)
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Да',color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Нет', color=VkKeyboardColor.DEFAULT)
        self.group_vk.method('messages.send', {'user_id': user_id, 'random_id': get_random_id(), 'message': message_str, "keyboard": keyboard.get_keyboard()})

    def step17(self, user_id):
        """Обработка шага 17"""
        self.mongo_obj.update_userdata(user_id, {"current_step": 17})
        message_str = self.mongo_msg_obj.get_message(17, user_id)
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Да',color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Нет', color=VkKeyboardColor.DEFAULT)
        self.group_vk.method('messages.send', {'user_id': user_id, 'random_id': get_random_id(), 'message': message_str, "keyboard": keyboard.get_keyboard()})

    def step_20(self, user_id):
        """Обработка шага 20"""
        self.mongo_obj.update_userdata(user_id, {"current_step": 20})
        message_str = self.mongo_msg_obj.get_message(20, user_id)
        self.group_vk.method('messages.send', {'user_id': user_id, 'random_id': get_random_id(), 'message': message_str})
    
    def step_21(self, user_id):
        """Обработка шага 21"""
        self.mongo_obj.update_userdata(user_id, {"current_step": 21})
        message_str = self.mongo_msg_obj.get_message(21, user_id)
        self.group_vk.method('messages.send', {'user_id': user_id, 'random_id': get_random_id(), 'message': message_str})

    def step_22(self, user_id):
        """Обработка шага 22"""
        self.mongo_obj.update_userdata(user_id, {"current_step": 22})
        message_str = self.mongo_msg_obj.get_message(22, user_id)
        self.group_vk.method('messages.send', {'user_id': user_id, 'random_id': get_random_id(), 'message': message_str})
        
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
        
        # Авторизуемся как сообщество
        self.vk = vk_api.VkApi(token=token)
        #Взаимодействие с БД пользователей
        self.mongo_obj = MongoMainClass(connection_str)
        #Взаимодействие с исходящими сообщеньками в БД
        self.mongo_msg_obj = MongoMsgClass(connection_str)
        #Выставление ожидания времени ttl в табличке
        self.mongo_ttl_obj = MongoTTLClass(connection_str)

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
            "Да" : self.step_14,
            "Дать другие товары" : self.step_19,
            "Понизить цены" : self.step_19,
            "Повысить качество" : self.step_19,
            "Мне это не интересно" : self.step_19,
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
                    elif self.mongo_obj.get_current_step(event.user_id) == 4: self.step_5(event)

                    #Если ответ "Нет", то это либо переход к 15, либо к 18
                    elif event.text == "Нет" and self.mongo_obj.get_current_step(event.user_id) == 13: self.step_15(event)
                    elif event.text == "Нет" and self.mongo_obj.get_current_step(event.user_id) == 17: self.step_18(event)

                    #Если ответ "Получить купон", то это либо переход к 12, либо к 16
                    elif event.text == "Получить купон" and self.mongo_obj.get_current_step(event.user_id) == 11: self.step_12(event)
                    elif event.text == "Получить купон" and self.mongo_obj.get_current_step(event.user_id) == 15: self.step_16(event)
                    
                    print("Сообщение: '{}' от https://vk.com/id{}".format(event.text, event.user_id))

    def step_1(self, event):
        """Обработка шага 1"""
        #Получаем имя пользователя
        first_name, second_name = self.get_username(event.user_id)
        if not self.mongo_obj.search_userdata(event.user_id):
            self.mongo_obj.new_userdata(event.user_id, first_name, second_name, 1)

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
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 2})
        message_str = self.mongo_msg_obj.get_message(2, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})
        #Т.к. у нас безусловный переход от 2 к 4 шагу
        time.sleep(2)
        self.step_4(event)

    def step_3(self, event):
        """Обработка шага 3"""
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 3})
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
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 4})
        message_str = self.mongo_msg_obj.get_message(4, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})
    
    def step_5(self, event):
        """Вызывается после того, как пользователь введет какой-либо текст после шага 4"""
        #Занесение информации о модели
        moto_model = event.text
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 5}, {"moto_model": moto_model})
        # Кнопки для VK
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Кастом',color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Сток', color=VkKeyboardColor.DEFAULT)
        message_str = self.mongo_msg_obj.get_message(5, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, "keyboard": keyboard.get_keyboard()})

    def step_6(self, event):
        """Обработка шага 6"""
        
        self.mongo_obj.update_userdata(event.user_id, {"moto_type": "сток"},{"current_step":6})
        message_str = self.mongo_msg_obj.get_message(6, event.user_id)
        photo_obj = PhotoUploaderClass(self.vk, event.user_id, "./img/expendable.jpg")
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, 'attachment': photo_obj.photo_str})
        
    def step_7(self, event):
        """Обработка шага 7"""

        self.mongo_obj.update_userdata(event.user_id, {"moto_type": "кастом"},{"current_step":7})
        message_str = self.mongo_msg_obj.get_message(7, event.user_id)
        photo_obj = PhotoUploaderClass(self.vk, event.user_id, "./img/custom.jpg")
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, 'attachment': photo_obj.photo_str}) #'attachment': "market-170171504_3154895"
        time.sleep(2)
        self.step_8(event)

    def step_8(self, event):
        """Обработка шага 8"""

        self.mongo_obj.update_userdata(event.user_id, {"current_step": 8})
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
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 9}, {"price_type": price_type})
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
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 11}, {"priority_type": priority_type})

        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Получить купон',color=VkKeyboardColor.DEFAULT)

        message_str = self.mongo_msg_obj.get_message(11, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, "keyboard": keyboard.get_keyboard()})

    def step_12(self, event):
        """Обработка шага 12"""
        message_str = self.mongo_msg_obj.get_message(12, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})
        
        #Выставляем TTL для step12to13
        self.mongo_ttl_obj.set_ttl_table("step12to13", event.user_id)
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 12}, {"coupon_5": "seen"})

    def step_14(self, event):
        """Обработка шага 14"""
        if self.mongo_obj.get_current_step(event.user_id) == 17:
            self.mongo_obj.update_userdata(event.user_id, {"current_step": 14}, {"coupon_10": "true"})
        else:
            self.mongo_obj.update_userdata(event.user_id, {"current_step": 14}, {"coupon_5": "true"})
        message_str = self.mongo_msg_obj.get_message(14, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})

    def step_15(self, event):
        """Обработка шага 15"""
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 15}, {"coupon_5": "false"})
        message_str = self.mongo_msg_obj.get_message(15, event.user_id)
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Получить купон',color=VkKeyboardColor.DEFAULT)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str,  "keyboard": keyboard.get_keyboard()})

    def step_16(self, event):
        """Обработка шага 16"""
        message_str = self.mongo_msg_obj.get_message(16, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})
        
        #Выставляем TTL для step16to17
        self.mongo_ttl_obj.set_ttl_table("step16to17", event.user_id)
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 16}, {"coupon_10": "seen"})

    def step_18(self, event):
        """Обработка шага 18"""
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 18}, {"coupon_10": "false"})
        message_str = self.mongo_msg_obj.get_message(18, event.user_id)
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Дать другие товары',color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Понизить цены', color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Повысить качество', color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Мне это не интересно', color=VkKeyboardColor.DEFAULT)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, "keyboard": keyboard.get_keyboard()})
    
    def step_19(self, event):
        wish = event.text
        message_str = self.mongo_msg_obj.get_message(19, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})
        
        #Выставляем TTL для step16to17
        self.mongo_ttl_obj.set_ttl_table("step19to20plus", event.user_id)
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 19}, {"wish": wish})

    def get_username(self, user_id):
        """Метод, возвращающий имя пользователя по id"""
        name = self.vk.method('users.get', {'user_id': user_id})[0]
        return name["first_name"], name["last_name"]


if __name__ == "__main__":
    p_list = []
    settings = util_module.get_settings()
    p = mp.Process(target=WallMonitoringClass, args=(settings["user_token"],settings["group_token"], settings["group_id"], settings["mongodb_connection"], ))
    p_list.append(p)
    p = mp.Process(target=MainClass, args=(settings["group_token"],settings["mongodb_connection"], ))
    p_list.append(p)
    p = mp.Process(target=UserAlertClass, args=(settings["group_token"],settings["mongodb_connection"], ))
    p_list.append(p)
    for p in p_list:
        p.start()
    
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